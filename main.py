#!/usr/bin/env python3
"""Ogma CLI - terminal arayuzu.

Tum model/mimari mantigi gui_main.OgmaAgent'tadir; bu dosya sadece
komut dongusunden sorumludur (cift bakim yapilmaz).
"""
import sys
import os
from pathlib import Path
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

expected_python = str(Path(__file__).resolve().parent
                    / "Python_Ortami" / "envs" / "ds_agent" / "python.exe")
if sys.executable != expected_python and not os.path.exists(expected_python):
    print(f"Uyari: Beklenen Python ortami bulunamadi: {expected_python}")

from gui_main import OgmaAgent
from core.file_manager import FileManager
from config.settings import config
from utils.helpers import Console
from models.api_models import AvailableModels


class OgmaCLI:
    def __init__(self):
        self.agent = OgmaAgent()

    def _ensure_workspace(self) -> bool:
        if self.agent.file_manager:
            return True
        Console.warning("Workspace secilmemis.")
        while True:
            try:
                p = input("Proje klasoru yolu (bos = cikis): ").strip()
            except (EOFError, KeyboardInterrupt):
                return False
            if not p:
                return False
            if Path(p).exists():
                config.set("workspace_path", p)
                self.agent.file_manager = FileManager(Path(p))
                return True
            Console.error("Dizin bulunamadi!")

    def initialize(self) -> bool:
        Console.info("Ogma Baslatiliyor...")
        Console.info("© 2026 İlker Can Karagülle · Loreweld AI (loreweld.ai)")
        if not self.agent.initialize():
            Console.error("Baslatma basarisiz!")
            return False
        return self._ensure_workspace()

    def list_files(self) -> None:
        if not self.agent.file_manager:
            Console.error("Dosya yoneticisi baslatilmamis!")
            return
        try:
            tree = self.agent.file_manager.get_file_tree(
                max_depth=int(config.get("max_file_tree_depth", 3) or 3),
                excluded=tuple(config.get("excluded_folders", []) or []),
            )
            print(f"\n{Fore.BLUE}DOSYA AGACI:{Style.RESET_ALL}")
            print(tree)
        except Exception as e:
            Console.error(f"Dosya listesi alinamadi: {e}")

    def analyze_script(self, file_path: str) -> None:
        analysis, improved = self.agent.analyze_script_gui(file_path)
        if not analysis:
            Console.error("Analiz yapilamadi!")
            return
        print(f"\n{Fore.CYAN}{file_path} ANALIZ RAPORU:{Style.RESET_ALL}")
        print("=" * 60)
        print(analysis)
        print("=" * 60)
        if improved:
            print(f"\n{Fore.GREEN}IYILESTIRILMIS KOD:{Style.RESET_ALL}")
            print("=" * 50)
            print(improved)
            print("=" * 50)
            try:
                save = input(
                    f"{Fore.CYAN}? Iyilestirilmis kodu kaydetmek istiyor musunuz? (e/h): {Style.RESET_ALL}"
                ).lower()
            except (EOFError, KeyboardInterrupt):
                return
            if save in ["e", "evet", "y", "yes"]:
                content = self.agent.file_manager.read_file(file_path)
                backup_path = f"{file_path}.backup"
                self.agent.file_manager.write_file(backup_path, content or "")
                if self.agent.file_manager.write_file(file_path, improved):
                    Console.success(f"Kod kaydedildi! Orijinal {backup_path} olarak yedeklendi.")
                else:
                    Console.error("Kod kaydedilemedi!")

    def change_model(self) -> None:
        backend = self.agent.backend
        if backend == "deepseek":
            models = AvailableModels.MODELS
            print(f"\n{Fore.YELLOW}Mevcut Modeller:{Style.RESET_ALL}")
            for i, m in enumerate(models, 1):
                print(f"{i}. {m.name} ({m.id}) - {m.description}")
            try:
                choice = input(f"\n{Fore.CYAN}? Model numarasi: {Style.RESET_ALL}").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if choice.isdigit() and 1 <= int(choice) <= len(models):
                config.set("selected_model", models[int(choice) - 1].id)
                self.agent.initialize()
                Console.success(f"Model degistirildi: {models[int(choice) - 1].name}")
            else:
                Console.error("Gecersiz secim!")
        elif backend == "llamacpp":
            try:
                path = input(f"{Fore.CYAN}? GGUF dosya yolu: {Style.RESET_ALL}").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if path and Path(path).exists():
                config.set("llamacpp_model_path", path)
                config.set("llamacpp_model_dir", str(Path(path).parent))
                self.agent.unload_model()
                self.agent.initialize()
            else:
                Console.error("Dosya bulunamadi!")
        elif backend == "ollama":
            try:
                name = input(f"{Fore.CYAN}? Ollama model adi: {Style.RESET_ALL}").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if name:
                config.set("ollama_model", name)
                self.agent.initialize()
            else:
                Console.error("Gecersiz secim!")

    def change_backend(self) -> None:
        print(f"\n{Fore.YELLOW}Mevcut Backendler:{Style.RESET_ALL}")
        print("1. deepseek - DeepSeek API (internet gerekli)")
        print("2. ollama   - Ollama (yerel, ollama serve gerekli)")
        print("3. llamacpp - llama.cpp (yerel GGUF dosyasi)")
        try:
            choice = input(f"\n{Fore.CYAN}? Backend secin: {Style.RESET_ALL}").strip()
        except (EOFError, KeyboardInterrupt):
            return
        backends = {"1": "deepseek", "2": "ollama", "3": "llamacpp"}
        if choice in backends:
            config.set("backend", backends[choice])
            self.agent.unload_model()
            self.agent.initialize()
        else:
            Console.error("Gecersiz secim!")

    def run(self) -> None:
        if not self.initialize():
            Console.error("Baslatma basarisiz! Program sonlandiriliyor.")
            return

        info = self.agent.get_model_info()
        Console.info("\n" + "=" * 50)
        Console.info("OGMA - KOD ANALIZ ASISTANI (CLI)")
        Console.info(f"Backend: {info.get('backend_label', self.agent.backend)}")
        Console.info(f"Model: {info.get('model_name', '-')}")
        Console.info("=" * 50)

        self.list_files()

        while True:
            print(f"\n{Fore.YELLOW}Kullanilabilir Komutlar:{Style.RESET_ALL}")
            print("• [dosya_adi] - Script'i analiz et (orn: main.py)")
            print("• soru <mesaj> - AI ile sohbet et")
            print("• liste - Dosyalari listele")
            print("• model - Model degistir")
            print("• backend - Backend degistir")
            print("• cikis - Programdan cik")

            try:
                command = input(f"\n{Fore.CYAN}? Komutunuz: {Style.RESET_ALL}").strip()
            except KeyboardInterrupt:
                Console.info("\nProgram kullanici tarafindan sonlandirildi.")
                break
            except EOFError:
                break

            if not command:
                continue

            low = command.lower()
            if low in ["cikis", "exit", "quit", "q"]:
                Console.info("Program sonlandiriliyor...")
                break
            elif low in ["liste", "list", "ls"]:
                self.list_files()
            elif low in ["model", "mod"]:
                self.change_model()
            elif low in ["backend", "back", "b"]:
                self.change_backend()
            elif low.startswith("soru "):
                print(self.agent.chat_with_ai(command[5:].strip()))
            else:
                if self.agent.file_manager and self.agent.file_manager.file_exists(command):
                    self.analyze_script(command)
                else:
                    Console.error(f"Dosya bulunamadi: {command}")

        self.agent.unload_model()


def main():
    from core.logger import install_crash_handler, log_exception
    install_crash_handler("cli")
    try:
        app = OgmaCLI()
        app.run()
    except Exception as e:
        try:
            log_exception(type(e), e, e.__traceback__, "cli:main")
        except Exception:
            pass
        Console.error(f"Kritik hata: {e} (detay: storage/logs/errors.log)")
        sys.exit(1)


if __name__ == "__main__":
    main()
