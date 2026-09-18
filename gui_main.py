#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import sys
import os
from pathlib import Path
import threading
import json
import time
from typing import Optional
import datetime

# Mevcut moduller
from core.deepseek_client import DeepSeekClient
from core.local_client import LocalModelManager
from core.file_manager import FileManager
from core.session_manager import SessionManager
from core.hardware import (detect_hardware, recommend_profile,
                             find_bundled_base_model, has_cuda_build,
                             has_vulkan_build, quick_gpu_vendor)
from config.settings import config
from utils.helpers import Console
from models.api_models import AvailableModels

class ModernSettingsWindow:
    """Modern Ayarlar Penceresi — DeepSeek, Ollama, llama.cpp destegi"""
    def __init__(self, parent, agent, on_save_callback=None):
        self.parent = parent
        self.agent = agent
        self.on_save_callback = on_save_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Ogma - Ayarlar")
        self.window.geometry("650x800")
        self.window.resizable(True, True)
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.window.grab_set()

        self.setup_ui()

    def setup_ui(self):
        main_container = tk.Frame(self.window, bg='#f5f5f5')
        main_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)

        header_frame = tk.Frame(main_container, bg='#f5f5f5')
        header_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(header_frame, text="AYARLAR",
                 font=('Arial', 16, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(anchor=tk.W)

        tk.Label(header_frame,
                 text="Ogma yapilandirmasini ozellestirin",
                 font=('Arial', 10),
                 bg='#f5f5f5', fg='#7f8c8d').pack(anchor=tk.W, pady=(2, 0))

        canvas = tk.Canvas(main_container, bg='#f5f5f5', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f5f5f5')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # ===== BACKEND SECIMI =====
        backend_frame = tk.LabelFrame(scrollable_frame, text="BACKEND SECIMI",
                                      bg='#ffffff', fg='#2c3e50', font=('Arial', 10, 'bold'),
                                      padx=20, pady=20)
        backend_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(backend_frame, text="Backend:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        self.backend_var = tk.StringVar(value=config.get("backend", "deepseek"))
        backends = [("deepseek", "DeepSeek API (bulut)"), ("ollama", "Ollama (yerel)"), ("llamacpp", "llama.cpp (GGUF dosyasi)")]
        for val, text in backends:
            tk.Radiobutton(backend_frame, text=text, variable=self.backend_var, value=val,
                           bg='#ffffff', fg='#000000', selectcolor='#3498db',
                           command=self._on_backend_change).pack(anchor=tk.W, pady=2)

        # ===== DEEPSEEK AYARLARI =====
        self.deepseek_frame = tk.LabelFrame(scrollable_frame, text="DeepSeek API Ayarlari",
                                            bg='#ffffff', fg='#2c3e50', font=('Arial', 10, 'bold'),
                                            padx=20, pady=20)

        tk.Label(self.deepseek_frame, text="API Key:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        self.api_key_var = tk.StringVar(value=config.get("api_key", ""))
        tk.Entry(self.deepseek_frame, textvariable=self.api_key_var,
                 show="*", width=50, bg='#ffffff', fg='#000000').pack(fill=tk.X, pady=(0, 10))

        tk.Label(self.deepseek_frame, text="Model:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        self.model_var = tk.StringVar()
        model_combo = ttk.Combobox(self.deepseek_frame, textvariable=self.model_var, state="readonly")
        model_combo['values'] = [m.name for m in AvailableModels.MODELS]
        model_combo.pack(fill=tk.X, pady=(0, 5))

        current_model = self.agent.current_model
        if current_model and hasattr(current_model, 'name'):
            self.model_var.set(current_model.name)
        else:
            self.model_var.set("DeepSeek Chat")

        self.deepseek_frame.pack(fill=tk.X, pady=(0, 15))

        # ===== OLLAMA AYARLARI =====
        self.ollama_frame = tk.LabelFrame(scrollable_frame, text="Ollama Ayarlari",
                                          bg='#ffffff', fg='#2c3e50', font=('Arial', 10, 'bold'),
                                          padx=20, pady=20)

        tk.Label(self.ollama_frame, text="Ollama URL:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        self.ollama_url_var = tk.StringVar(value=config.get("ollama_url", "http://localhost:11434"))
        tk.Entry(self.ollama_frame, textvariable=self.ollama_url_var,
                 width=50, bg='#ffffff', fg='#000000').pack(fill=tk.X, pady=(0, 10))

        tk.Label(self.ollama_frame, text="Model (ornek: deepseek-r1:8b):", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        self.ollama_model_var = tk.StringVar(value=config.get("ollama_model", "deepseek-r1:8b"))
        tk.Entry(self.ollama_frame, textvariable=self.ollama_model_var,
                 width=50, bg='#ffffff', fg='#000000').pack(fill=tk.X, pady=(0, 10))

        tk.Label(self.ollama_frame, text="Populer modeller: deepseek-r1:8b, qwen2.5-coder:7b, llama3.1:8b, codellama:13b",
                 bg='#ffffff', fg='#7f8c8d', font=('Arial', 8)).pack(anchor=tk.W)

        # ===== LLAMA.CPP AYARLARI =====
        self.llamacpp_frame = tk.LabelFrame(scrollable_frame, text="llama.cpp GGUF Ayarlari",
                                            bg='#ffffff', fg='#2c3e50', font=('Arial', 10, 'bold'),
                                            padx=20, pady=20)

        tk.Label(self.llamacpp_frame, text="GGUF Dosya Yolu:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        gguf_path_frame = tk.Frame(self.llamacpp_frame, bg='#ffffff')
        gguf_path_frame.pack(fill=tk.X, pady=(0, 10))

        self.llamacpp_path_var = tk.StringVar(value=config.get("llamacpp_model_path", ""))
        tk.Entry(gguf_path_frame, textvariable=self.llamacpp_path_var,
                 bg='#ffffff', fg='#000000').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(gguf_path_frame, text="Gozat", command=self._browse_gguf,
                  bg='#3498db', fg='white', relief="solid", bd=1).pack(side=tk.RIGHT)

        tk.Label(self.llamacpp_frame, text="Model Klasoru (cache):", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(5, 5))

        gguf_dir_frame = tk.Frame(self.llamacpp_frame, bg='#ffffff')
        gguf_dir_frame.pack(fill=tk.X, pady=(0, 10))

        self.llamacpp_dir_var = tk.StringVar(value=config.get("llamacpp_model_dir", ""))
        tk.Entry(gguf_dir_frame, textvariable=self.llamacpp_dir_var,
                 bg='#ffffff', fg='#000000').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(gguf_dir_frame, text="Gozat", command=self._browse_gguf_dir,
                  bg='#3498db', fg='white', relief="solid", bd=1).pack(side=tk.RIGHT)

        llamacpp_grid = tk.Frame(self.llamacpp_frame, bg='#ffffff')
        llamacpp_grid.pack(fill=tk.X)

        tk.Label(llamacpp_grid, text="n_ctx (context):", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.llamacpp_n_ctx_var = tk.StringVar(value=str(config.get("llamacpp_n_ctx", 8192)))
        tk.Entry(llamacpp_grid, textvariable=self.llamacpp_n_ctx_var, width=10,
                 bg='#ffffff', fg='#000000').grid(row=0, column=1, padx=(10, 0), pady=5)

        tk.Label(llamacpp_grid, text="GPU Layers:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.llamacpp_n_gpu_var = tk.StringVar(value=str(config.get("llamacpp_n_gpu_layers", 0)))
        tk.Entry(llamacpp_grid, textvariable=self.llamacpp_n_gpu_var, width=10,
                 bg='#ffffff', fg='#000000').grid(row=1, column=1, padx=(10, 0), pady=5)

        tk.Label(llamacpp_grid, text="Threads:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.llamacpp_n_threads_var = tk.StringVar(value=str(config.get("llamacpp_n_threads", 4)))
        tk.Entry(llamacpp_grid, textvariable=self.llamacpp_n_threads_var, width=10,
                 bg='#ffffff', fg='#000000').grid(row=2, column=1, padx=(10, 0), pady=5)

        # ===== CALISMA ALANI =====
        workspace_frame = tk.LabelFrame(scrollable_frame, text="Calisma Alani",
                                        bg='#ffffff', fg='#2c3e50', font=('Arial', 10, 'bold'),
                                        padx=20, pady=20)
        workspace_frame.pack(fill=tk.X, pady=(0, 15))

        self.workspace_var = tk.StringVar(value=config.get("workspace_path", ""))
        tk.Label(workspace_frame, text="Mevcut calisma alani:", bg='#ffffff',
                 fg='#2c3e50', font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(0, 5))

        path_frame = tk.Frame(workspace_frame, bg='#ffffff')
        path_frame.pack(fill=tk.X, pady=(5, 0))

        tk.Entry(path_frame, textvariable=self.workspace_var,
                 state="readonly", bg='#f8f9fa', fg='#000000').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        tk.Button(path_frame, text="Degistir", command=self.change_workspace,
                  bg='#3498db', fg='white', relief="solid", bd=1).pack(side=tk.RIGHT)

        # ===== GELISMIS AYARLAR =====
        advanced_frame = tk.LabelFrame(scrollable_frame, text="Gelismis Ayarlar",
                                       bg='#ffffff', fg='#2c3e50', font=('Arial', 10, 'bold'),
                                       padx=20, pady=20)
        advanced_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(advanced_frame, text="Max Tokens:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        self.max_tokens_var = tk.StringVar(value=str(config.get("max_tokens", 1500)))
        tk.Entry(advanced_frame, textvariable=self.max_tokens_var,
                 bg='#ffffff', fg='#000000').grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=(0, 10))

        tk.Label(advanced_frame, text="Temperature:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
        self.temperature_var = tk.StringVar(value=str(config.get("temperature", 0.7)))
        tk.Entry(advanced_frame, textvariable=self.temperature_var,
                 bg='#ffffff', fg='#000000').grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=(0, 10))

        advanced_frame.columnconfigure(1, weight=1)

        # ===== BUTONLAR =====
        button_frame = tk.Frame(scrollable_frame, bg='#f5f5f5')
        button_frame.pack(fill=tk.X, pady=(20, 0))

        tk.Button(button_frame, text="AYARLARI KAYDET",
                  command=self.save_settings,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  relief="solid", bd=1).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(button_frame, text="IPTAL",
                  command=self.window.destroy,
                  bg='#e74c3c', fg='white', relief="solid", bd=1).pack(side=tk.RIGHT)

        self._on_backend_change()

    def _on_backend_change(self):
        backend = self.backend_var.get()
        self.deepseek_frame.pack_forget()
        self.ollama_frame.pack_forget()
        self.llamacpp_frame.pack_forget()

        if backend == "deepseek":
            self.deepseek_frame.pack(fill=tk.X, pady=(0, 15), after=self.window.winfo_children()[0].winfo_children()[-1] if False else None)
        elif backend == "ollama":
            self.ollama_frame.pack(fill=tk.X, pady=(0, 15))
        elif backend == "llamacpp":
            self.llamacpp_frame.pack(fill=tk.X, pady=(0, 15))

    def _browse_gguf(self):
        file_path = filedialog.askopenfilename(
            title="GGUF Dosyasi Sec",
            filetypes=[("GGUF files", "*.gguf"), ("All files", "*.*")]
        )
        if file_path:
            self.llamacpp_path_var.set(file_path)

    def _browse_gguf_dir(self):
        folder = filedialog.askdirectory(title="Model Klasoru Sec")
        if folder:
            self.llamacpp_dir_var.set(folder)

    def change_workspace(self):
        folder = filedialog.askdirectory(title="Calisma Alani Sec")
        if folder:
            self.workspace_var.set(folder)

    def save_settings(self):
        try:
            backend = self.backend_var.get()

            workspace = self.workspace_var.get().strip()
            if not workspace:
                messagebox.showerror("Hata", "Lutfen calisma alani secin!")
                return
            if not Path(workspace).exists():
                messagebox.showerror("Hata", "Secilen calisma alani mevcut degil!")
                return

            if backend == "deepseek":
                api_key = self.api_key_var.get().strip()
                if not api_key:
                    messagebox.showerror("Hata", "Lutfen API Key girin!")
                    return
                config.set("api_key", api_key)

                model_name = self.model_var.get()
                model = next((m for m in AvailableModels.MODELS if m.name == model_name), None)
                if model:
                    config.set("selected_model", model.id)

            elif backend == "ollama":
                config.set("ollama_url", self.ollama_url_var.get().strip())
                config.set("ollama_model", self.ollama_model_var.get().strip())

            elif backend == "llamacpp":
                gguf_path = self.llamacpp_path_var.get().strip()
                if not gguf_path:
                    messagebox.showerror("Hata", "Lutfen GGUF dosya yolu secin!")
                    return
                if not Path(gguf_path).exists():
                    messagebox.showerror("Hata", "GGUF dosyasi bulunamadi!")
                    return
                config.set("llamacpp_model_path", gguf_path)
                model_dir = self.llamacpp_dir_var.get().strip() or str(Path(gguf_path).parent)
                if Path(model_dir).is_dir():
                    config.set("llamacpp_model_dir", model_dir)
                else:
                    config.set("llamacpp_model_dir", str(Path(gguf_path).parent))
                try:
                    config.set("llamacpp_n_ctx", int(self.llamacpp_n_ctx_var.get()))
                    config.set("llamacpp_n_gpu_layers", int(self.llamacpp_n_gpu_var.get()))
                    config.set("llamacpp_n_threads", int(self.llamacpp_n_threads_var.get()))
                except ValueError:
                    messagebox.showerror("Hata", "Sayisal degerler gecersiz!")
                    return

            try:
                config.set("max_tokens", int(self.max_tokens_var.get()))
                config.set("temperature", float(self.temperature_var.get()))
            except ValueError:
                messagebox.showerror("Hata", "Max Tokens ve Temperature sayi olmali!")
                return

            config.set("backend", backend)
            config.set("workspace_path", workspace)
            config.set("profile_name", self.profile_var.get() if hasattr(self, 'profile_var') else "Varsayilan")

            if self.on_save_callback:
                self.on_save_callback()

            messagebox.showinfo("Basarili", "Ayarlar basariyla kaydedildi!\nYeniden baslatiliyor...")
            self.window.destroy()

        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilemedi: {str(e)}")

class HardwareWindow:
    """Ilk acilista donanim taramasi + profil onerisi penceresi."""
    MODE_LABELS = {"cpu": "CPU-only (onerilen)",
                   "cuda_partial": "Kismi GPU (CUDA)",
                   "cuda_full": "Tam GPU (CUDA)",
                   "vulkan": "GPU (Vulkan)"}

    def __init__(self, parent, agent, on_applied=None):
        self.parent = parent
        self.agent = agent
        self.on_applied = on_applied
        self.hw = detect_hardware()
        self.rec = recommend_profile(self.hw, cuda_available=has_cuda_build(),
                                     vulkan_available=has_vulkan_build())
        self.window = tk.Toplevel(parent)
        self.window.title("Donanim Taramasi")
        self.window.geometry("560x620")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="DONANIM TARAMASI", font=('Arial', 14, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(pady=(0, 5))
        tk.Label(main, text="Sisteminize uygun model profili onerilir. Tek tikla uygulanir.",
                 bg='#f5f5f5', fg='#7f8c8d', font=('Arial', 9)).pack(pady=(0, 12))

        hw_box = tk.LabelFrame(main, text="Tespit Edilen Donanim", bg='#ffffff',
                               fg='#2c3e50', font=('Arial', 10, 'bold'), padx=12, pady=10)
        hw_box.pack(fill=tk.X, pady=(0, 10))
        cpu = self.hw.get("cpu", {})
        avx2 = cpu.get("avx2")
        avx_txt = "Var" if avx2 else ("Yok" if avx2 is False else "Bilinmiyor")
        lines = [f"CPU: {cpu.get('name', '-')}",
                 f"Cekirdek: {cpu.get('cores_physical', '-')} fiziksel / "
                 f"{cpu.get('cores_logical', '-')} mantiksal  |  AVX2: {avx_txt}",
                 f"RAM: {self.hw['ram_mb'] // 1024} GB" if self.hw.get("ram_mb") else "RAM: Bilinmiyor"]
        for g in self.hw.get("nvidia_gpus", []):
            lines.append(f"GPU: {g['name']} ({g['vram_mb'] // 1024} GB, {g.get('family', '')})")
        for o in self.hw.get("other_gpus", []):
            lines.append(f"GPU: {o.get('name')} ({o.get('vendor')})")
        if not self.hw.get("nvidia_gpus") and not self.hw.get("other_gpus"):
            lines.append("GPU: Bulunamadi")
        for ln in lines:
            tk.Label(hw_box, text=ln, bg='#ffffff', fg='#2c3e50',
                     font=('Arial', 9), anchor=tk.W, justify=tk.LEFT).pack(fill=tk.X)

        rec_box = tk.LabelFrame(main, text="Onerilen Profil", bg='#eaf7ee',
                                fg='#1e8449', font=('Arial', 10, 'bold'), padx=12, pady=10)
        rec_box.pack(fill=tk.X, pady=(0, 10))
        tk.Label(rec_box, text=self.MODE_LABELS.get(self.rec["mode"], self.rec["mode"]),
                 bg='#eaf7ee', fg='#1e8449', font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        tk.Label(rec_box,
                 text=f"Threads: {self.rec['n_threads']}  |  Context: {self.rec['n_ctx']}  |  "
                      f"GPU katmani: {self.rec['n_gpu_layers']}",
                 bg='#eaf7ee', fg='#2c3e50', font=('Arial', 9)).pack(anchor=tk.W, pady=(4, 0))
        for r in self.rec.get("reasons", []):
            tk.Label(rec_box, text=f"- {r}", bg='#eaf7ee', fg='#2c3e50',
                     font=('Arial', 8), wraplength=480, justify=tk.LEFT).pack(anchor=tk.W)
        for w in self.rec.get("warnings", []):
            tk.Label(rec_box, text=f"! {w}", bg='#eaf7ee', fg='#b7950b',
                     font=('Arial', 8, 'bold'), wraplength=480, justify=tk.LEFT).pack(anchor=tk.W)
        pot = self.rec.get("gpu_potential")
        if pot:
            tk.Label(rec_box,
                     text=f"GPU potansiyeli (su an kapali): {pot['mode']} / "
                          f"n_gpu_layers={pot['n_gpu_layers']} — CUDA derlemesi kurulunca acilir.",
                     bg='#eaf7ee', fg='#7d6608', font=('Arial', 8),
                     wraplength=480, justify=tk.LEFT).pack(anchor=tk.W)

        btn = tk.Frame(main, bg='#f5f5f5')
        btn.pack(fill=tk.X, pady=(5, 0))
        tk.Button(btn, text="ONERIYI UYGULA", command=self._apply,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  relief="flat", padx=15, pady=8).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(btn, text="Kapat", command=self._close,
                  bg='#95a5a6', fg='white', relief="flat",
                  padx=15, pady=8).pack(side=tk.RIGHT)

    def _apply(self):
        try:
            config.set("llamacpp_n_threads", int(self.rec["n_threads"]))
            config.set("llamacpp_n_ctx", int(self.rec["n_ctx"]))
            config.set("llamacpp_n_gpu_layers", int(self.rec.get("n_gpu_layers", 0)))
            config.set("hardware_checked", True)
        except Exception as e:
            messagebox.showerror("Hata", f"Ayar uygulanamadi: {e}")
            return
        self.window.destroy()
        try:
            if self.on_applied:
                self.on_applied()
        except Exception:
            pass

    def _close(self):
        try:
            config.set("hardware_checked", True)
        except Exception:
            pass
        self.window.destroy()


class ComputeChoiceWindow:
    """Acilista hesaplama modu secimi: CPU-only veya GPU (tespit edilen kart gosterilir)."""

    def __init__(self, parent, agent, gpu_name: str, on_done=None,
                 engine: str = "CUDA"):
        self.parent = parent
        self.agent = agent
        self.gpu_name = gpu_name
        self.engine = engine
        self.on_done = on_done
        self.window = tk.Toplevel(parent)
        self.window.title("Hesaplama Modu Sec")
        self.window.geometry("520x420")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=25, pady=25)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="HESAPLAMA MODU", font=('Arial', 14, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(pady=(0, 5))
        tk.Label(main, text=f"Tespit edilen kart: {self.gpu_name}",
                 bg='#f5f5f5', fg='#7f8c8d', font=('Arial', 10, 'bold'),
                 wraplength=460, justify=tk.CENTER).pack(pady=(0, 15))

        tk.Button(main, text=f"GPU ILE DEVAM ET ({self.engine})\n(~60 token/sn, model ~4 snde yuklenir)",
                  command=lambda: self._choose("gpu"),
                  bg='#27ae60', fg='white', font=('Arial', 11, 'bold'),
                  relief="flat", padx=10, pady=12).pack(fill=tk.X, pady=(0, 10))
        tk.Button(main, text="CPU-ONLY ILE DEVAM ET\n(~15 token/sn, her PC'de calisir)",
                  command=lambda: self._choose("cpu"),
                  bg='#2980b9', fg='white', font=('Arial', 11, 'bold'),
                  relief="flat", padx=10, pady=12).pack(fill=tk.X, pady=(0, 10))

        tk.Label(main, text="GPU modu derleme ve yonetici yetkisi gerektirmez; "
                            "hazir llama-server kullanilir. Secim hatirlanir, Araclardan degistirilebilir.",
                 bg='#f5f5f5', fg='#95a5a6', font=('Arial', 8),
                 wraplength=460, justify=tk.CENTER).pack()

    def _choose(self, mode: str):
        try:
            config.set("compute_mode", mode)
            if mode == "gpu" and not int(config.get("llamacpp_n_gpu_layers", 0)):
                config.set("llamacpp_n_gpu_layers", 35)
        except Exception:
            pass
        self.window.destroy()
        try:
            if self.on_done:
                self.on_done(mode)
        except Exception:
            pass


class ModelSelectionWindow:
    """Model secim penceresi — DeepSeek / Ollama listesi, llamacpp icin GGUF dosyalari."""
    def __init__(self, parent, agent, on_change=None, on_gguf_selected=None):
        self.on_change = on_change
        self.on_gguf_selected = on_gguf_selected
        self._gguf_mode = (config.get("backend", "deepseek") == "llamacpp")
        self.parent = parent
        self.agent = agent
        self.window = tk.Toplevel(parent)
        self.window.title("AI Modeli Sec")
        self.window.geometry("550x500")
        self.window.resizable(False, False)
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.window.grab_set()

        self.setup_ui()

    def setup_ui(self):
        main_frame = tk.Frame(self.window, bg='#f5f5f5', padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(main_frame, text="AI MODELI SECIN",
                 font=('Arial', 14, 'bold'), bg='#f5f5f5', fg='#2c3e50').pack(pady=(0, 20))

        backend = config.get("backend", "deepseek")

        if self._gguf_mode:
            self._setup_gguf_ui(main_frame)
            return

        model_frame = tk.LabelFrame(main_frame, text=f"Mevcut Modeller ({backend})",
                                    bg='#ffffff', fg='#2c3e50', font=('Arial', 10, 'bold'),
                                    padx=15, pady=15)
        model_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        self.model_var = tk.StringVar()

        canvas = tk.Canvas(model_frame, bg='#ffffff', highlightthickness=0)
        scrollbar = ttk.Scrollbar(model_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#ffffff')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        if backend == "deepseek":
            models = AvailableModels.MODELS
        else:
            models = AvailableModels.OLLAMA_MODELS

        for model in models:
            frame = tk.Frame(scrollable_frame, bg='#ffffff')
            frame.pack(fill=tk.X, pady=5)

            tk.Radiobutton(frame, text=model.name, value=model.name,
                           variable=self.model_var, bg='#ffffff', fg='#000000',
                           selectcolor='#3498db', font=('Arial', 9)).pack(side=tk.LEFT)

            tk.Label(frame, text=f" - {model.description}",
                     bg='#ffffff', fg='#7f8c8d', font=('Arial', 8)).pack(side=tk.LEFT)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        if self.agent.current_model and hasattr(self.agent.current_model, 'name'):
            self.model_var.set(self.agent.current_model.name)
        elif models:
            self.model_var.set(models[0].name)

        button_frame = tk.Frame(main_frame, bg='#f5f5f5')
        button_frame.pack(fill=tk.X)

        tk.Button(button_frame, text="MODELI DEGISTIR",
                  command=self.change_model,
                  bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
                  relief="solid", bd=1).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(button_frame, text="Iptal",
                  command=self.window.destroy,
                  bg='#95a5a6', fg='white', relief="solid", bd=1).pack(side=tk.RIGHT)

    def _find_gguf_files(self):
        """Cache'teki model klasoru + secili modelin klasoru + taban model."""
        found = []
        seen = set()
        candidates = [d for d in [config.get("llamacpp_model_dir", "")] if d]
        cur = config.get("llamacpp_model_path", "")
        if cur:
            try:
                candidates.append(str(Path(cur).parent))
            except Exception:
                pass
        base = config.get("llamacpp_base_model", "")
        if not (base and Path(base).exists()):
            try:
                base = find_bundled_base_model()
            except Exception:
                base = ""
        if base:
            try:
                candidates.append(str(Path(base).parent))
            except Exception:
                pass
        for d in candidates:
            try:
                p = Path(d)
                if not p.is_dir():
                    continue
                key = str(p.resolve()).lower()
                if key in seen:
                    continue
                seen.add(key)
                for f in sorted(p.glob("*.gguf"), key=lambda x: x.name.lower()):
                    try:
                        size = f.stat().st_size
                    except Exception:
                        size = 0
                    found.append((str(f), f.name, size))
            except Exception:
                continue
        return found

    def _setup_gguf_ui(self, main_frame):
        """llamacpp backend: cache'teki klasordeki GGUF dosyalari + oneriler."""
        model_frame = tk.LabelFrame(main_frame, text="GGUF Modelleri (llama.cpp)",
                                    bg='#ffffff', fg='#2c3e50', font=('Arial', 10, 'bold'),
                                    padx=15, pady=15)
        model_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        folder_row = tk.Frame(model_frame, bg='#ffffff')
        folder_row.pack(fill=tk.X, pady=(0, 8))
        self._gguf_folder_var = tk.StringVar(value=config.get("llamacpp_model_dir", ""))
        tk.Label(folder_row, text="Klasor:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 8, 'bold')).pack(side=tk.LEFT)
        tk.Label(folder_row, textvariable=self._gguf_folder_var, bg='#ffffff', fg='#7f8c8d',
                 font=('Arial', 8), wraplength=300, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        tk.Button(folder_row, text="Degistir", command=self._change_gguf_folder,
                  bg='#3498db', fg='white', relief="flat", font=('Arial', 8)).pack(side=tk.RIGHT)

        self.model_var = tk.StringVar()
        canvas = tk.Canvas(model_frame, bg='#ffffff', highlightthickness=0)
        scrollbar = ttk.Scrollbar(model_frame, orient="vertical", command=canvas.yview)
        self._gguf_list_frame = tk.Frame(canvas, bg='#ffffff')
        self._gguf_list_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._gguf_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._refresh_gguf_list()

        tip = ("ONERI - Hizli baslangic: gomulu taban model (trendyol-7b Q4) yeterlidir.\n"
               "Daha iyi sonuc icin: Qwen2.5-14B, Turkish-LLM-14B veya kod icin qwen2.5-coder-14b.\n"
               "Cok hafif alternatif: Qwen2.5-1.5B-Instruct Q4 (~1 GB, indirilip klasore eklenebilir).\n"
               "Ayri tavsiye: guclu kartlarda Ollama backend + qwen2.5-coder:7b / deepseek-r1:8b.")
        tk.Label(main_frame, text=tip, bg='#fef9e7', fg='#7d6608',
                 font=('Arial', 8), wraplength=500, justify=tk.LEFT,
                 padx=8, pady=6).pack(fill=tk.X, pady=(0, 10))

        tk.Button(main_frame, text="Farkli GGUF Dosyasi Sec...",
                  command=self._browse_gguf,
                  bg='#ecf0f1', fg='#2c3e50', relief="solid", bd=1).pack(fill=tk.X, pady=(0, 10))

        button_frame = tk.Frame(main_frame, bg='#f5f5f5')
        button_frame.pack(fill=tk.X)
        tk.Button(button_frame, text="SEC VE YUKLE",
                  command=self.change_model,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  relief="solid", bd=1).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(button_frame, text="Iptal",
                  command=self.window.destroy,
                  bg='#95a5a6', fg='white', relief="solid", bd=1).pack(side=tk.RIGHT)

    def _refresh_gguf_list(self):
        """Klasordeki GGUF listesini yeniden ciz (cache guncel)."""
        for w in self._gguf_list_frame.winfo_children():
            w.destroy()
        files = self._find_gguf_files()
        if not files:
            tk.Label(self._gguf_list_frame, text="Klasorde .gguf dosyasi bulunamadi.\n'Farkli Dosya' ile secin.",
                     bg='#ffffff', fg='#e74c3c', font=('Arial', 9)).pack(padx=10, pady=10)
        for full, name, size in files:
            mb = f"{size / (1024*1024):.0f} MB" if size else "?"
            row = tk.Frame(self._gguf_list_frame, bg='#ffffff')
            row.pack(fill=tk.X, pady=3)
            tk.Radiobutton(row, text=name, value=full, variable=self.model_var,
                           bg='#ffffff', fg='#000000', selectcolor='#3498db',
                           font=('Arial', 9)).pack(side=tk.LEFT)
            tk.Label(row, text=f" ({mb})", bg='#ffffff', fg='#7f8c8d',
                     font=('Arial', 8)).pack(side=tk.LEFT)
        cur = config.get("llamacpp_model_path", "")
        if cur and any(f[0].lower() == cur.lower() for f in files):
            self.model_var.set(cur)
        elif files:
            self.model_var.set(files[0][0])
        try:
            self._gguf_folder_var.set(config.get("llamacpp_model_dir", ""))
        except Exception:
            pass

    def _change_gguf_folder(self):
        """Model klasorunu degistir, cache'i guncelle, listeyi tazele."""
        folder = filedialog.askdirectory(title="Model Klasoru Sec")
        if folder:
            config.set("llamacpp_model_dir", folder)
            self._refresh_gguf_list()

    def _browse_gguf(self):
        path = filedialog.askopenfilename(title="GGUF Dosyasi Sec",
                                          filetypes=(("GGUF", "*.gguf"), ("All", "*.*")))
        if path:
            self.model_var.set(path)

    def change_model(self):
        if self._gguf_mode:
            path = self.model_var.get().strip()
            if not path or not Path(path).exists():
                messagebox.showerror("Hata", "Gecerli bir GGUF dosyasi secin!")
                return
            config.set("llamacpp_model_path", path)
            self.window.destroy()
            try:
                if self.on_gguf_selected:
                    self.on_gguf_selected(path)
                elif self.on_change:
                    self.on_change()
            except Exception:
                pass
            return

        model_name = self.model_var.get()
        all_models = AvailableModels.MODELS + AvailableModels.OLLAMA_MODELS
        model = next((m for m in all_models if m.name == model_name), None)

        if model:
            self.agent.current_model = model
            config.set("selected_model", model.id)
            self.window.destroy()
            try:
                if self.on_change:
                    self.on_change()
            except Exception:
                pass
            messagebox.showinfo("Basarili", f"Model degistirildi: {model.name}")
        else:
            messagebox.showerror("Hata", "Lutfen gecerli bir model secin!")

class LoadingDialog:
    """Iptal edilebilir loading penceresi"""
    def __init__(self, parent, title="Islem devam ediyor...", message="Lutfen bekleyin", on_cancel=None):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("380x180")
        self.top.resizable(False, False)
        self.top.configure(bg='#2c3e50')
        self.top.transient(parent)
        self.cancelled = False
        self.on_cancel = on_cancel

        self.top.protocol("WM_DELETE_WINDOW", self.cancel)

        tk.Label(self.top, text="⏳", font=('Arial', 24), bg='#2c3e50', fg='#f39c12').pack(pady=(10, 2))
        tk.Label(self.top, text=message, font=('Arial', 10), bg='#2c3e50', fg='white').pack()

        self.status_label = tk.Label(self.top, text="Baslatiliyor...", font=('Arial', 9), bg='#2c3e50', fg='#95a5a6')
        self.status_label.pack(pady=(2, 0))

        self.progress = ttk.Progressbar(self.top, mode='indeterminate', length=280)
        self.progress.pack(pady=(5, 5))
        self.progress.start(15)

        tk.Button(self.top, text="✖ Iptal Et", command=self.cancel,
                  bg='#e74c3c', fg='white', relief="flat", padx=15, pady=3).pack()

        self._center(parent)

    def _center(self, parent):
        self.top.update_idletasks()
        w = self.top.winfo_width()
        h = self.top.winfo_height()
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.top.geometry(f"+{x}+{y}")

    def update_status(self, text):
        if not self.cancelled:
            self.status_label.config(text=text)
            self.top.update_idletasks()

    def cancel(self):
        self.cancelled = True
        self.progress.stop()
        if self.on_cancel:
            self.on_cancel()
        try:
            self.top.grab_release()
        except:
            pass
        self.top.destroy()

    def close(self):
        self.progress.stop()
        try:
            self.top.grab_release()
        except:
            pass
        self.top.destroy()


class ModernAnalysisWindow:
    """Modern Analiz Sonuclari Penceresi — Diff destegi ile"""
    def __init__(self, parent, file_path, analysis, improved_code, apply_callback, original_code=None):
        self.parent = parent
        self.file_path = file_path
        self.analysis = analysis
        self.improved_code = improved_code
        self.apply_callback = apply_callback
        self.original_code = original_code
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"Kod Analizi - {file_path}")
        self.window.geometry("1000x750")
        self.window.resizable(True, True)
        self.window.configure(bg='#f5f5f5')
        
        self.setup_ui()
    
    def setup_ui(self):
        main_frame = tk.Frame(self.window, bg='#f5f5f5')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        header_frame = tk.Frame(main_frame, bg='#f5f5f5')
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(header_frame, text=f"Kod Analizi: {self.file_path}", 
                 font=('Arial', 14, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(anchor=tk.W)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        analysis_frame = tk.Frame(notebook, bg='#ffffff')
        notebook.add(analysis_frame, text="Analiz Sonuclari")
        
        analysis_text = scrolledtext.ScrolledText(analysis_frame, wrap=tk.WORD, 
                                                font=('Arial', 10), bg='#ffffff', fg='#000000')
        analysis_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        analysis_text.insert(tk.END, self.analysis)
        analysis_text.config(state=tk.DISABLED)
        
        improved_frame = tk.Frame(notebook, bg='#ffffff')
        notebook.add(improved_frame, text="Iyilestirilmis Kod")
        
        improved_text = scrolledtext.ScrolledText(improved_frame, wrap=tk.WORD, 
                                                font=('Consolas', 10), bg='#f8f9fa', fg='#000000')
        improved_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        improved_text.insert(tk.END, self.improved_code if self.improved_code else "Iyilestirilmis kod bulunamadi.")
        improved_text.config(state=tk.DISABLED)
        
        button_frame = tk.Frame(main_frame, bg='#f5f5f5')
        button_frame.pack(fill=tk.X, pady=(15, 0))
        
        if self.improved_code:
            tk.Button(button_frame, text="Kodu Uygula", 
                      command=self.apply_improvements,
                      bg='#3498db', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
            
            if self.original_code:
                tk.Button(button_frame, text="Farki Gor", 
                          command=self.show_diff,
                          bg='#e67e22', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(button_frame, text="Analizi Kopyala", 
                  command=self.copy_analysis,
                  bg='#95a5a6', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(button_frame, text="Kapat", 
                  command=self.window.destroy,
                  bg='#e74c3c', fg='white', relief="solid", bd=1).pack(side=tk.RIGHT)
    
    def show_diff(self):
        CodeDiffWindow(self.parent, self.original_code, self.improved_code, self.file_path)
    
    def apply_improvements(self):
        if messagebox.askyesno("Onay", "Iyilestirilmis kodu uygulamak istediginize emin misiniz?\nOrijinal dosya yedeklenecek."):
            self.apply_callback(self.improved_code)
            self.window.destroy()
    
    def copy_analysis(self):
        self.parent.clipboard_clear()
        self.parent.clipboard_append(self.analysis)
        messagebox.showinfo("Başarılı", "✅ Analiz panoya kopyalandı!")

class OgmaGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 Ogma — Proje Analiz Asistani")
        self.root.geometry("1400x900")
        self.root.configure(bg='#2c3e50')

        # Kapanis temizligi
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Mevcut agent altyapisi
        self.agent = OgmaAgent()
        self.current_file: Optional[str] = None
        self.improved_code: Optional[str] = None
        
        # Oturum yoneticisi
        self.session_manager = SessionManager()
        
        self.setup_gui()
        self.initialize_agent()

    def _on_closing(self):
        """Pencere kapatildiginda monitoru durdur, modeli her durumda bosalt."""
        self._monitor_active = False
        try:
            if getattr(self, "agent", None):
                try:
                    self.agent.unload_model()
                except Exception:
                    pass
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass

    def setup_gui(self):
        """Modern GUI bilesenlerini olustur (mimari odakli)."""
        # Ust bar: baslik + yuklu model + hizli erisim
        self.setup_topbar()

        # Ana paneller - Split view
        self.setup_main_panels()

        # Sol panel icerigi (Mimari, Dosya, Sohbet, Araclar)
        self.setup_sidebar()

        # Sag panel icerigi (Mimari Ana Ekran, Dosya Analizi, Sonuclar, Gecmis)
        self.setup_content_area()

        # Durum cubugu
        self.setup_status_bar()

        # Ilk acilis: once donanim penceresi; kapaninca (veya daha once
        # gosterilmisse) CPU/GPU secimi. Asla paralel popup yok.
        try:
            self.root.after(2500, self._maybe_hardware_check)
        except Exception:
            pass

        # Canli sistem monitoru (CPU/GPU/RAM) - arka plan dongusu
        self._monitor_active = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()
    
    def setup_topbar(self):
        """Ust bar: her zaman gorunur model + hizli erisim."""
        bar = tk.Frame(self.root, bg='#1a252f', height=58)
        bar.pack(side=tk.TOP, fill=tk.X)
        bar.pack_propagate(False)

        left = tk.Frame(bar, bg='#1a252f')
        left.pack(side=tk.LEFT, fill=tk.Y, padx=12, pady=6)
        tk.Label(left, text="PROJE ANALIZ ASISTANI",
                 font=('Arial', 12, 'bold'), bg='#1a252f', fg='white').pack(anchor=tk.W)
        tk.Label(left, text="Mimari odakli  |  Dosya analizi + AI sohbet",
                 font=('Arial', 8), bg='#1a252f', fg='#95a5a6').pack(anchor=tk.W)

        center = tk.Frame(bar, bg='#1a252f')
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=6)
        self.top_model_var = tk.StringVar(value="Yuklu model: -")
        self.top_model_label = tk.Label(center, textvariable=self.top_model_var,
                                        font=('Arial', 10, 'bold'), bg='#1a252f',
                                        fg='#2ecc71', anchor=tk.W, justify=tk.LEFT)
        self.top_model_label.pack(fill=tk.X)
        self.top_load_var = tk.StringVar(value="Backend: -  |  Yukleme suresi: -")
        tk.Label(center, textvariable=self.top_load_var,
                 font=('Arial', 8), bg='#1a252f', fg='#bdc3c7',
                 anchor=tk.W, justify=tk.LEFT).pack(fill=tk.X)

        right = tk.Frame(bar, bg='#1a252f')
        right.pack(side=tk.RIGHT, padx=10, pady=10)
        # Sekme gecis butonlari (islem butonu DEGIL - her islevin tek resmi
        # yeri ilgili sekmededir: Model Sec -> Araclar, Ayarlar -> Araclar)
        tk.Button(right, text="Mimari", command=self.goto_arch_home,
                  bg='#8e44ad', fg='white', font=('Arial', 9, 'bold'),
                  relief="flat", padx=14, pady=6).pack(side=tk.LEFT, padx=3)
        tk.Button(right, text="Dosyalar", command=self.goto_editor,
                  bg='#16a085', fg='white', font=('Arial', 9, 'bold'),
                  relief="flat", padx=14, pady=6).pack(side=tk.LEFT, padx=3)
        tk.Button(right, text="Sohbet", command=self.goto_chat,
                  bg='#2980b9', fg='white', font=('Arial', 9, 'bold'),
                  relief="flat", padx=14, pady=6).pack(side=tk.LEFT, padx=3)
        tk.Button(right, text="Araclar", command=self.goto_tools,
                  bg='#e67e22', fg='white', font=('Arial', 9, 'bold'),
                  relief="flat", padx=14, pady=6).pack(side=tk.LEFT, padx=3)

    def goto_tools(self):
        try:
            self.sidebar_notebook.select(self.settings_tab)
        except Exception:
            pass

    def goto_arch_home(self):
        try:
            self.notebook.select(self.arch_home_frame)
        except Exception:
            pass
        try:
            self.sidebar_notebook.select(self.arch_tab)
        except Exception:
            pass

    def goto_chat(self):
        try:
            self.sidebar_notebook.select(self.chat_tab)
        except Exception:
            pass
        try:
            self.notebook.select(self.arch_home_frame)
        except Exception:
            pass

    def goto_editor(self):
        try:
            self.notebook.select(self.editor_frame)
        except Exception:
            pass
        try:
            self.sidebar_notebook.select(self.file_tab)
        except Exception:
            pass

    def setup_main_panels(self):
        """Ana panel bölümleri"""
        # Ana container
        main_container = tk.Frame(self.root, bg='#34495e')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # PanedWindow ile bölünmüş görünüm
        self.paned_window = tk.PanedWindow(main_container, orient=tk.HORIZONTAL, bg='#34495e', sashrelief="raised", sashwidth=5)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # Sol panel (Sidebar) - %30
        self.sidebar = tk.Frame(self.paned_window, bg='#2c3e50', width=400)
        
        # Sağ panel (Content) - %70
        self.content = tk.Frame(self.paned_window, bg='#ecf0f1')
        
        self.paned_window.add(self.sidebar, stretch="never")
        self.paned_window.add(self.content, stretch="always")
    
    def setup_sidebar(self):
        """Sol sidebar - Sekmeli: Dosya Yönetimi, AI Sohbet, Ayarlar"""
        # Header
        header_frame = tk.Frame(self.sidebar, bg='#2c3e50')
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        title_label = tk.Label(header_frame, 
                              text="🚀 Ogma", 
                              font=('Arial', 18, 'bold'), 
                              bg='#2c3e50', fg='white')
        title_label.pack(anchor=tk.W)
        
        subtitle_label = tk.Label(header_frame, 
                                 text="AI Agent Master",
                                 font=('Arial', 11), 
                                 bg='#2c3e50', fg='#bdc3c7')
        subtitle_label.pack(anchor=tk.W)
        
        author_label = tk.Label(header_frame, 
                               text="by İlker Can Karagülle",
                               font=('Arial', 9), 
                               bg='#2c3e50', fg='#95a5a6')
        author_label.pack(anchor=tk.W, pady=(2, 0))
        
        # Agent durumu
        status_frame = tk.Frame(self.sidebar, bg='#2c3e50')
        status_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        self.agent_status = tk.Label(status_frame, text="Baslatiliyor...", 
                                    font=('Arial', 9, 'bold'), bg='#2c3e50', fg='#f39c12')
        self.agent_status.pack(side=tk.LEFT)
        
        self.model_label = tk.Label(status_frame, text="Model: -", 
                                  font=('Arial', 8), bg='#2c3e50', fg='#bdc3c7')
        self.model_label.pack(side=tk.RIGHT)
        
        # === MODEL DASHBOARD ===
        self.dashboard_frame = tk.Frame(self.sidebar, bg='#1a252f', highlightbackground='#34495e', highlightthickness=1)
        self.dashboard_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        dash_header = tk.Frame(self.dashboard_frame, bg='#1a252f')
        dash_header.pack(fill=tk.X, padx=8, pady=(6, 2))
        tk.Label(dash_header, text="MODEL DURUMU", font=('Arial', 8, 'bold'),
                 bg='#1a252f', fg='#3498db').pack(side=tk.LEFT)
        
        self.dash_backend = tk.Label(self.dashboard_frame, text="Backend: -", font=('Arial', 7),
                                     bg='#1a252f', fg='#bdc3c7')
        self.dash_backend.pack(anchor=tk.W, padx=8)
        
        self.dash_model = tk.Label(self.dashboard_frame, text="Model: -", font=('Arial', 7),
                                   bg='#1a252f', fg='#ecf0f1')
        self.dash_model.pack(anchor=tk.W, padx=8)
        
        self.dash_status = tk.Label(self.dashboard_frame, text="Durum: -", font=('Arial', 7),
                                    bg='#1a252f', fg='#f39c12')
        self.dash_status.pack(anchor=tk.W, padx=8)
        
        self.dash_memory = tk.Label(self.dashboard_frame, text="Bellek: -", font=('Arial', 7),
                                     bg='#1a252f', fg='#95a5a6')
        self.dash_memory.pack(anchor=tk.W, padx=8)

        # Canli sistem monitoru (2 sn'de bir guncellenir)
        self.dash_cpu = tk.Label(self.dashboard_frame, text="CPU: olculuyor...", font=('Arial', 7),
                                 bg='#1a252f', fg='#1abc9c')
        self.dash_cpu.pack(anchor=tk.W, padx=8)
        self.dash_gpu = tk.Label(self.dashboard_frame, text="GPU: olculuyor...", font=('Arial', 7),
                                 bg='#1a252f', fg='#1abc9c')
        self.dash_gpu.pack(anchor=tk.W, padx=8)
        self.dash_ram = tk.Label(self.dashboard_frame, text="RAM: olculuyor...", font=('Arial', 7),
                                 bg='#1a252f', fg='#1abc9c')
        self.dash_ram.pack(anchor=tk.W, padx=8, pady=(0, 6))
        
        # Model durumu guncelleme butonlari
        dash_buttons = tk.Frame(self.dashboard_frame, bg='#1a252f')
        dash_buttons.pack(fill=tk.X, padx=8, pady=(0, 6))
        
        tk.Button(dash_buttons, text="Yukle", command=self.load_model_action,
                  bg='#27ae60', fg='white', font=('Arial', 7, 'bold'), relief="flat", width=8).pack(side=tk.LEFT, padx=(0, 3))
        tk.Button(dash_buttons, text="Bosalt", command=self.unload_model_action,
                  bg='#e74c3c', fg='white', font=('Arial', 7), relief="flat", width=8).pack(side=tk.LEFT, padx=(0, 3))
        tk.Button(dash_buttons, text="Yenile", command=self.refresh_dashboard,
                  bg='#3498db', fg='white', font=('Arial', 7), relief="flat", width=8).pack(side=tk.LEFT)
        
        # Sidebar Notebook (Sekmeler) - mimari once
        self.sidebar_notebook = ttk.Notebook(self.sidebar)
        self.sidebar_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Mimari Sekmesi (birincil)
        self.arch_tab = tk.Frame(self.sidebar_notebook, bg='#34495e')
        self.sidebar_notebook.add(self.arch_tab, text="🏗 Mimari")
        self.setup_arch_tab()

        # Dosya Yönetimi Sekmesi (ikincil)
        self.file_tab = tk.Frame(self.sidebar_notebook, bg='#34495e')
        self.sidebar_notebook.add(self.file_tab, text="📁 Dosyalar")
        self.setup_file_tab()

        # Model Sohbet Sekmesi (model her zaman gorunur)
        self.chat_tab = tk.Frame(self.sidebar_notebook, bg='#34495e')
        self.sidebar_notebook.add(self.chat_tab, text="💬 Model Sohbet")
        self.setup_chat_tab()

        # Araclar Sekmesi (tum ozellikler toplu)
        self.settings_tab = tk.Frame(self.sidebar_notebook, bg='#34495e')
        self.sidebar_notebook.add(self.settings_tab, text="⚙️ Araçlar")
        self.setup_settings_tab()
    
    def setup_arch_tab(self):
        """Mimari Sekmesi - mimari islemlerin TEK resmi yeri.
        Tek klasor secimi + cikti klasoru + ignore + tek baslat butonu."""
        box = tk.Frame(self.arch_tab, bg='#34495e')
        box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(box, text="MIMARI ANALIZ", font=('Arial', 11, 'bold'),
                 bg='#34495e', fg='white').pack(anchor=tk.W, pady=(0, 2))
        tk.Label(box, text="Klasoru sec, cikti klasorunu belirle, tara.",
                 font=('Arial', 8), bg='#34495e', fg='#bdc3c7',
                 wraplength=300, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 8))

        # [1] Model durumu (salt gosterim; Model Sec'in resmi yeri Araclar > MODEL)
        self.arch_model_var = tk.StringVar(value="Model: -")
        tk.Label(box, textvariable=self.arch_model_var, font=('Arial', 8, 'bold'),
                 bg='#1a252f', fg='#2ecc71', wraplength=300, justify=tk.LEFT,
                 padx=8, pady=6).pack(fill=tk.X, pady=(0, 8))

        # [2] Klasor Sec (TEK buton; dosya agaci ayni klasoru kullanir)
        tk.Button(box, text="Proje Klasoru Sec",
                  command=self.select_workspace,
                  bg='#3498db', fg='white', relief="flat",
                  font=('Arial', 9, 'bold')).pack(fill=tk.X, pady=2)
        self.arch_workspace_var = tk.StringVar(value="Klasor: -")
        tk.Label(box, textvariable=self.arch_workspace_var, font=('Arial', 8),
                 bg='#34495e', fg='#bdc3c7', wraplength=300, justify=tk.LEFT).pack(
                     anchor=tk.W, pady=(2, 6))

        # [3] Cikti klasoru (raporlar buraya yazilir)
        tk.Button(box, text="Rapor Cikti Klasoru Sec",
                  command=self.select_output_folder,
                  bg='#16a085', fg='white', relief="flat",
                  font=('Arial', 9, 'bold')).pack(fill=tk.X, pady=2)
        self.arch_output_var = tk.StringVar(value="Cikti: -")
        tk.Label(box, textvariable=self.arch_output_var, font=('Arial', 8),
                 bg='#34495e', fg='#bdc3c7', wraplength=300, justify=tk.LEFT).pack(
                     anchor=tk.W, pady=(2, 6))

        # [4] Ignore listesi (tarama oncesi gormek/duzenlemek icin)
        tk.Button(box, text="Ignore Ayarlari (tarama oncesi)",
                  command=self.show_ignore_settings,
                  bg='#95a5a6', fg='white', relief="flat",
                  font=('Arial', 8)).pack(fill=tk.X, pady=2)

        # [5] Tek baslat butonu
        tk.Button(box, text="Mimari Analizi Baslat",
                  command=self.launch_architecture_analyzer,
                  bg='#8e44ad', fg='white', relief="flat",
                  font=('Arial', 11, 'bold'), pady=8).pack(fill=tk.X, pady=(8, 2))
        tk.Label(box, text="Tara -> analiz turunu sec -> rapor cikti klasorune yazilir.",
                 font=('Arial', 8), bg='#34495e', fg='#95a5a6',
                 wraplength=300, justify=tk.LEFT).pack(anchor=tk.W)

    def select_output_folder(self):
        """Rapor cikti klasorunu sec (tarama oncesi)."""
        try:
            folder = filedialog.askdirectory(title="Rapor Cikti Klasoru Sec")
            if folder:
                config.set("architecture_output_dir", folder)
                self._update_workspace_labels()
                self.status_var.set(f"Rapor klasoru: {folder}")
        except Exception as e:
            messagebox.showerror("Hata", f"Cikti klasoru secme hatasi: {e}")

    def show_ignore_settings(self):
        """Ignore listesini taramadan once gormek/duzenlemek icin."""
        try:
            ws = config.get("workspace_path", "")
            if not ws or not Path(ws).exists():
                messagebox.showinfo("Bilgi", "Once Proje Klasoru Secin!")
                return
            from gui.architecture_analyzer_gui import IgnoreListWindow
            IgnoreListWindow(self.root, ws, on_start=lambda ignore_list: None)
        except Exception as e:
            messagebox.showerror("Hata", f"Ignore ayarlari acilamadi: {e}")

    def setup_file_tab(self):
        """Dosya Yönetimi Sekmesi (ikincil: tek dosya analizi)"""
        # Araç çubuğu (Klasor Sec KALDIRILDI - Mimari sekmesindeki klasoru kullanir)
        file_tools = tk.Frame(self.file_tab, bg='#34495e')
        file_tools.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(file_tools, text="🔄 Yenile", 
                  command=self.refresh_file_tree, width=8,
                  bg='#3498db', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(file_tools, text="➕ Yeni", 
                  command=self.show_new_menu, width=8,
                  bg='#27ae60', fg='white', relief="solid", bd=1).pack(side=tk.LEFT)
        
        # Arama
        search_frame = tk.Frame(self.file_tab, bg='#34495e')
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Label(search_frame, text="🔍", bg='#34495e', fg='white').pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, width=20,
                               bg='#ffffff', fg='#000000')
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        search_entry.bind('<KeyRelease>', self.on_search)
        
        # Dosya ağacı
        tree_container = tk.Frame(self.file_tab, bg='#34495e')
        tree_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.tree = ttk.Treeview(tree_container, show='tree', selectmode='browse')
        
        # Scrollbar
        tree_scroll = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Sağ tık menüsü
        self.setup_context_menu()
        
        # Event'ler
        self.tree.bind('<Double-1>', self.on_file_select)
        self.tree.bind('<Button-3>', self.show_context_menu)
        self.tree.bind('<<TreeviewOpen>>', self.on_treeview_open)
    
    def setup_chat_tab(self):
        """Model Sohbet Sekmesi - hangi modelle konusuldugu hep gorunur."""
        chat_container = tk.Frame(self.chat_tab, bg='#34495e')
        chat_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.chat_model_var = tk.StringVar(value="Sohbet modeli: -")
        tk.Label(chat_container, textvariable=self.chat_model_var,
                 font=('Arial', 8, 'bold'), bg='#1a252f', fg='#3498db',
                 wraplength=320, justify=tk.LEFT, padx=8, pady=6).pack(
                     fill=tk.X, pady=(0, 8))

        # Sohbet geçmişi
        self.chat_display = scrolledtext.ScrolledText(chat_container, wrap=tk.WORD, 
                                                     font=('Arial', 10), 
                                                     bg='#ffffff', fg='#000000',
                                                     state=tk.DISABLED)
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Başlangıç mesajı
        self.chat_display.config(state=tk.NORMAL)
        welcome_chat = """🤖 Ogma Asistan: Merhaba! Size nasıl yardımcı olabilirim?

Ben bir AI asistanıyım ve şu konularda yardımcı olabilirim:
• Kod açıklamaları ve optimizasyon önerileri
• Programlama sorunlarını çözme
• Dosya ve proje yönetimi tavsiyeleri
• Genel teknik sorular

───────────────────────────────────────────────────
💡 İpucu: 
• Enter: Mesaj gönder
• Shift + Enter: Yeni satır
• Sol panelden ayarları yapabilirsiniz

"""
        self.chat_display.insert(tk.END, welcome_chat)
        self.chat_display.config(state=tk.DISABLED)
        
        # Giriş alanı
        input_frame = tk.Frame(chat_container, bg='#34495e')
        input_frame.pack(fill=tk.X)
        
        self.chat_input = scrolledtext.ScrolledText(input_frame, height=4, wrap=tk.WORD,
                                                   font=('Arial', 10), 
                                                   bg='#ffffff', fg='#000000')
        self.chat_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        button_frame = tk.Frame(input_frame, bg='#34495e')
        button_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        tk.Button(button_frame, text="📤\nGönder", 
                  command=self.send_chat, width=8,
                  bg='#27ae60', fg='white', relief="solid", bd=1).pack(pady=(0, 5))
        tk.Button(button_frame, text="🗑️\nTemizle", 
                  command=self.clear_chat, width=8,
                  bg='#e74c3c', fg='white', relief="solid", bd=1).pack(pady=5)
        tk.Button(button_frame, text="💾\nKaydet", 
                  command=self.save_chat, width=8,
                  bg='#3498db', fg='white', relief="solid", bd=1).pack(pady=(5, 0))
        
        # Enter tuşu bağlama
        self.chat_input.bind('<Return>', self.on_chat_input_enter)
        self.chat_input.bind('<Shift-Return>', self.on_chat_input_shift_enter)
    
    def _tool_button(self, parent, text, command, bg):
        tk.Button(parent, text=text, command=command, bg=bg, fg='white',
                  relief="flat", font=('Arial', 9, 'bold')).pack(fill=tk.X, pady=2)

    def setup_settings_tab(self):
        """Araclar Sekmesi - tum ozellikler gruplu ve bulunabilir."""
        settings_container = tk.Frame(self.settings_tab, bg='#34495e')
        settings_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        model_box = tk.LabelFrame(settings_container, text="MODEL",
                                  bg='#2c3e50', fg='white', font=('Arial', 9, 'bold'))
        model_box.pack(fill=tk.X, pady=(0, 8))
        self._tool_button(model_box, "Model Sec / Degistir", self.show_model_selection, '#9b59b6')
        self._tool_button(model_box, "Modeli Bosalt", self.unload_model_action, '#e74c3c')
        self._tool_button(model_box, "Model Indir (Ollama)", self.show_download_window, '#27ae60')
        self._tool_button(model_box, "Model Capability Test (D4)", self.show_capability_test, '#8e44ad')

        analiz_box = tk.LabelFrame(settings_container, text="ANALIZ",
                                   bg='#2c3e50', fg='white', font=('Arial', 9, 'bold'))
        analiz_box.pack(fill=tk.X, pady=(0, 8))
        # Mimari analizin TEK resmi yeri Mimari sekmesi; buradan oraya goturur
        self._tool_button(analiz_box, "Mimari Analiz (Mimari sekmesine gider)", self.goto_arch_home, '#8e44ad')
        self._tool_button(analiz_box, "Gelistirici Araclari (sembol/outline/etki)", self.show_dev_tools, '#2980b9')
        self._tool_button(analiz_box, "Canli Izleyici (degisiklik + etki)", self.show_watcher, '#c0392b')
        self._tool_button(analiz_box, "Toplu Analiz", lambda: BatchAnalysisWindow(self.root, self.agent), '#e67e22')
        self._tool_button(analiz_box, "Model Karsilastir", lambda: ModelCompareWindow(self.root, self.agent), '#8e44ad')

        sistem_box = tk.LabelFrame(settings_container, text="SISTEM",
                                   bg='#2c3e50', fg='white', font=('Arial', 9, 'bold'))
        sistem_box.pack(fill=tk.X, pady=(0, 8))
        self._tool_button(sistem_box, "Donanim Taramasi", self.show_hardware_window, '#1abc9c')
        self._tool_button(sistem_box, "GPU / CPU Degistir", self.show_compute_choice, '#d35400')
        self._tool_button(sistem_box, "Ayarlar", self.show_settings, '#3498db')
        self._tool_button(sistem_box, "Oturum Yonetimi", lambda: SessionManagerWindow(self.root, self.agent), '#16a085')
        self._tool_button(sistem_box, "Profil Kaydet", self.save_profile, '#27ae60')
        self._tool_button(sistem_box, "Yardim", self.show_help, '#3498db')

        info_frame = tk.LabelFrame(settings_container, text="Mevcut Ayarlar",
                                  bg='#2c3e50', fg='white', font=('Arial', 9, 'bold'))
        info_frame.pack(fill=tk.X, pady=(7, 0))

        self.settings_info = tk.Text(info_frame, height=5, wrap=tk.WORD,
                                    bg='#34495e', fg='#bdc3c7', font=('Arial', 8),
                                    state=tk.DISABLED)
        self.settings_info.pack(fill=tk.X, padx=5, pady=5)
    
    def setup_content_area(self):
        """Sag panel - Mimari Ana Ekran once, sonra Dosya Analizi."""
        # Notebook for tabs
        self.notebook = ttk.Notebook(self.content)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Mimari Ana Ekran (birincil)
        self.arch_home_frame = tk.Frame(self.notebook, bg='#ecf0f1')
        self.notebook.add(self.arch_home_frame, text="🏗 Mimari Analiz")
        self.setup_arch_home()

        # Dosya Analizi sekmesi (ikincil)
        self.editor_frame = tk.Frame(self.notebook, bg='#ecf0f1')
        self.notebook.add(self.editor_frame, text="📝 Dosya Analizi")
        self.setup_editor()

        # Analiz Sonuçları sekmesi
        self.analysis_frame = tk.Frame(self.notebook, bg='#ecf0f1')
        self.notebook.add(self.analysis_frame, text="📊 Sonuçlar")
        self.setup_analysis_tab()

        # Oturum Geçmişi sekmesi
        self.history_frame = tk.Frame(self.notebook, bg='#ecf0f1')
        self.notebook.add(self.history_frame, text="📜 Geçmiş")
        self.setup_history_tab()

        try:
            self.notebook.select(self.arch_home_frame)
        except Exception:
            pass

    def setup_arch_home(self):
        """Mimari ana ekran: 3 adimli akis + tum ozelliklere kisayol."""
        wrap = tk.Frame(self.arch_home_frame, bg='#ecf0f1')
        wrap.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

        tk.Label(wrap, text="Mimari Sonuc / Durum", font=('Arial', 16, 'bold'),
                 bg='#ecf0f1', fg='#2c3e50').pack(anchor=tk.W)
        tk.Label(wrap, text="Islemler soldaki MIMARI sekmesinden yonetilir. Son tarama ozeti asagida.",
                 font=('Arial', 10), bg='#ecf0f1', fg='#7f8c8d').pack(anchor=tk.W, pady=(2, 12))

        self.home_model_var = tk.StringVar(value="Yuklu model: -")
        tk.Label(wrap, textvariable=self.home_model_var, font=('Arial', 10, 'bold'),
                 bg='#1a252f', fg='#2ecc71', anchor=tk.W, justify=tk.LEFT,
                 padx=10, pady=8).pack(fill=tk.X, pady=(0, 10))
        self.home_ws_var = tk.StringVar(value="Klasor: -")
        tk.Label(wrap, textvariable=self.home_ws_var, font=('Arial', 9),
                 bg='#ffffff', fg='#2c3e50', anchor=tk.W, justify=tk.LEFT,
                 padx=10, pady=8).pack(fill=tk.X, pady=(0, 6))
        self.home_out_var = tk.StringVar(value="Cikti: -")
        tk.Label(wrap, textvariable=self.home_out_var, font=('Arial', 9),
                 bg='#ffffff', fg='#2c3e50', anchor=tk.W, justify=tk.LEFT,
                 padx=10, pady=8).pack(fill=tk.X, pady=(0, 12))

        # Son tarama ozeti (launcher doldurur)
        tk.Label(wrap, text="SON TARAMA OZETI", font=('Arial', 10, 'bold'),
                 bg='#ecf0f1', fg='#2c3e50').pack(anchor=tk.W, pady=(0, 4))
        self.home_summary = scrolledtext.ScrolledText(wrap, height=14, wrap=tk.WORD,
                                                      font=('Consolas', 9),
                                                      bg='#ffffff', fg='#2c3e50',
                                                      state=tk.DISABLED)
        self.home_summary.pack(fill=tk.BOTH, expand=True)

        tip = ("ONERI: Ilk acilista gomulu taban model (trendyol-7b Q4, Turkce, hafif) otomatik gelir.\n"
               "Daha iyi sonuc icin: Qwen2.5-14B / Turkish-LLM-14B, kod icin qwen2.5-coder-14b. "
               "Ayri tavsiye: Ollama backend + qwen2.5-coder:7b.")
        tk.Label(wrap, text=tip, bg='#fef9e7', fg='#7d6608', font=('Arial', 8),
                 wraplength=900, justify=tk.LEFT, padx=10, pady=8).pack(fill=tk.X, pady=(10, 0))

    def update_home_summary(self, text: str):
        """Son tarama ozetini sag paneldeki alana yaz."""
        try:
            self.home_summary.config(state=tk.NORMAL)
            self.home_summary.delete(1.0, tk.END)
            self.home_summary.insert(1.0, text)
            self.home_summary.config(state=tk.DISABLED)
        except Exception:
            pass
    
    def setup_editor(self):
        """Kod Editörü"""
        # Araç çubuğu
        editor_tools = tk.Frame(self.editor_frame, bg='#ecf0f1')
        editor_tools.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(editor_tools, text="💾 Kaydet", 
                  command=self.save_file,
                  bg='#27ae60', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(editor_tools, text="📄 Yeni", 
                  command=self.new_file,
                  bg='#3498db', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(editor_tools, text="📂 Aç", 
                  command=self.open_file,
                  bg='#3498db', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        self.analyze_btn = tk.Button(editor_tools, text="🔍 Analiz", 
                  command=self.analyze_current,
                  bg='#3498db', fg='white', relief="solid", bd=1)
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.quick_analyze_btn = tk.Button(editor_tools, text="⚡ Hızlı", 
                  command=self.quick_analyze,
                  bg='#3498db', fg='white', relief="solid", bd=1)
        self.quick_analyze_btn.pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(editor_tools, text="🗑️ Sil", 
                  command=self.delete_file,
                  bg='#e74c3c', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(editor_tools, text="🏗 Mimari", 
                  command=self.launch_architecture_analyzer,
                  bg='#8e44ad', fg='white', relief="solid", bd=1).pack(side=tk.LEFT)
        
        # Kod editörü container
        editor_container = tk.Frame(self.editor_frame, bg='#ecf0f1')
        editor_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Line numbers and editor
        editor_wrapper = tk.Frame(editor_container, bg='#ecf0f1')
        editor_wrapper.pack(fill=tk.BOTH, expand=True)
        
        # Line numbers
        self.line_numbers = tk.Text(editor_wrapper, width=4, padx=4, takefocus=0, 
                                   border=0, background='#f8f9fa', foreground='#6c757d',
                                   state='disabled', font=('Consolas', 10))
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        
        # Main editor
        self.code_editor = scrolledtext.ScrolledText(editor_wrapper, wrap=tk.WORD, 
                                                    font=('Consolas', 11), 
                                                    bg='#ffffff', fg='#000000',
                                                    undo=True)
        self.code_editor.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Line number sync
        self.code_editor.bind('<KeyRelease>', self.update_line_numbers)
        self.code_editor.bind('<MouseWheel>', self.update_line_numbers)
        self.code_editor.bind('<Button-1>', self.update_line_numbers)
        
        # Başlangıç mesajı
        welcome_msg = """# 🚀 Ogma Kod Editörüne Hoş Geldiniz!

## 📖 Nasıl Başlayacaksınız?
1. Sol taraftan bir dosya seçin veya yeni dosya oluşturun
2. Kodunuzu yazın veya düzenleyin  
3. "Analiz Et" butonu ile AI destekli kod analizi yapın
4. "Kaydet" butonu ile değişiklikleri kaydedin

## ✨ Özellikler:
• Tam dosya yönetimi
• AI destekli kod analizi
• Gerçek zamanlı düzenleme
• Otomatik yedekleme
• Modern kullanıcı arayüzü

───────────────────────────────────────────────────
Created by İlker Can Karagülle | Ogma 2024
"""
        self.code_editor.insert(tk.END, welcome_msg)
    
    def setup_analysis_tab(self):
        """Analiz Sonuçları Sekmesi"""
        analysis_container = tk.Frame(self.analysis_frame, bg='#ecf0f1')
        analysis_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(analysis_container, text="Kod analiz sonuçları burada görüntülenecek",
                bg='#ecf0f1', fg='#7f8c8d', font=('Arial', 12)).pack(expand=True)
    
    def setup_history_tab(self):
        """Geçmiş Sekmesi"""
        history_container = tk.Frame(self.history_frame, bg='#ecf0f1')
        history_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Araç çubuğu
        history_tools = tk.Frame(history_container, bg='#ecf0f1')
        history_tools.pack(fill=tk.X, pady=(0, 10))
        
        tk.Button(history_tools, text="🔄 Yenile", 
                  command=self.refresh_history,
                  bg='#3498db', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(history_tools, text="🗑️ Temizle", 
                  command=self.clear_history,
                  bg='#e74c3c', fg='white', relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(history_tools, text="💾 Dışa Aktar", 
                  command=self.export_history,
                  bg='#27ae60', fg='white', relief="solid", bd=1).pack(side=tk.LEFT)
        
        # Geçmiş listesi
        list_frame = tk.Frame(history_container, bg='#ecf0f1')
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.history_tree = ttk.Treeview(list_frame, columns=('Tarih', 'Dosya', 'İşlem'), show='headings')
        self.history_tree.heading('Tarih', text='Tarih')
        self.history_tree.heading('Dosya', text='Dosya')
        self.history_tree.heading('İşlem', text='İşlem')
        
        self.history_tree.column('Tarih', width=150)
        self.history_tree.column('Dosya', width=200)
        self.history_tree.column('İşlem', width=300)
        
        history_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.history_tree.yview)
        history_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.configure(yscrollcommand=history_scroll.set)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Detay paneli
        detail_frame = tk.LabelFrame(history_container, text="Detay", bg='#ecf0f1', fg='#2c3e50')
        detail_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.history_detail = scrolledtext.ScrolledText(detail_frame, height=6, wrap=tk.WORD,
                                                       font=('Arial', 9), 
                                                       bg='#ffffff', fg='#000000')
        self.history_detail.pack(fill=tk.X, padx=5, pady=5)
        
        self.history_tree.bind('<<TreeviewSelect>>', self.on_history_select)
    
    def setup_status_bar(self):
        """Durum Çubuğu"""
        status_frame = tk.Frame(self.root, bg='#34495e')
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ogma Agent Master başlatılıyor...")
        
        # Model bilgisi
        self.model_var = tk.StringVar()
        self.model_var.set("Model: Yükleniyor...")
        
        status_bar = tk.Label(status_frame, textvariable=self.status_var, 
                             relief=tk.FLAT, anchor=tk.W, 
                             bg='#34495e', fg='#ecf0f1', font=('Arial', 9))
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        model_label = tk.Label(status_frame, textvariable=self.model_var,
                               relief=tk.FLAT, anchor=tk.E,
                               bg='#34495e', fg='#bdc3c7', font=('Arial', 9))
        model_label.pack(side=tk.RIGHT)

        self.monitor_var = tk.StringVar(value="CPU: - | GPU: - | RAM: -")
        monitor_label = tk.Label(status_frame, textvariable=self.monitor_var,
                                 relief=tk.FLAT, anchor=tk.E,
                                 bg='#34495e', fg='#1abc9c', font=('Arial', 8, 'bold'))
        monitor_label.pack(side=tk.RIGHT, padx=(0, 12))

        # Loreweld imzasi
        footer_frame = tk.Frame(self.root, bg='#2c3e50')
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(footer_frame, text="© 2026 İlker Can Karagülle · Loreweld AI (loreweld.ai)",
                 bg='#2c3e50', fg='#7f8c8d', font=('Arial', 7, 'bold')).pack(side=tk.LEFT, padx=10)

    def _monitor_loop(self):
        """2 sn'de bir CPU/GPU/RAM olc, arayuzu guncelle."""
        import time as _t
        from core.hardware import get_cpu_percent, get_ram_percent, get_gpu_stats
        get_cpu_percent()  # baz olustur
        while getattr(self, "_monitor_active", False):
            try:
                cpu = get_cpu_percent()
                ram = get_ram_percent()
                gpu = get_gpu_stats()
                self.root.after(0, lambda c=cpu, r=ram, g=gpu: self._update_monitor(c, r, g))
            except Exception:
                pass
            _t.sleep(2)

    def _update_monitor(self, cpu, ram, gpu):
        """Monitor satirlarini guncelle (ana thread)."""
        try:
            cpu_txt = f"{cpu:.0f}%" if cpu is not None else "-"
            ram_txt = f"{ram}%" if ram is not None else "-"
            if gpu:
                gpu_txt = (f"%{gpu['util']:.0f} "
                           f"({gpu['mem_used_mb'] // 1024}/{gpu['mem_total_mb'] // 1024} GB)")
            else:
                gpu_txt = "-"
            self.dash_cpu.config(text=f"CPU: {cpu_txt}")
            self.dash_gpu.config(text=f"GPU: {gpu_txt}")
            self.dash_ram.config(text=f"RAM: {ram_txt}")
            self.monitor_var.set(f"CPU: {cpu_txt} | GPU: {gpu_txt} | RAM: {ram_txt}")
        except Exception:
            pass
    
    def setup_context_menu(self):
        """Sağ Tık Menüsü"""
        self.context_menu = tk.Menu(self.root, tearoff=0, bg='#ffffff', fg='#000000')
        
        self.context_menu.add_command(label="📄 Yeni Dosya", command=self.new_file)
        self.context_menu.add_command(label="📁 Yeni Klasör", command=self.new_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔍 Analiz Et", command=self.analyze_selected)
        self.context_menu.add_command(label="⚡ Hızlı Analiz", command=self.quick_analyze_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="✏️ Yeniden Adlandır", command=self.rename_selected)
        self.context_menu.add_command(label="🗑️ Sil", command=self.delete_selected)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🔄 Yenile", command=self.refresh_file_tree)

    # Diğer metodlar aynı kalacak, sadece threading hataları düzeltilecek
    # Kalan metodlar önceki versiyonla aynı, threading hataları düzeltilmiş şekilde

    def on_chat_input_enter(self, event):
        """Enter tuşu - mesaj gönder"""
        self.send_chat()
        return "break"
    
    def on_chat_input_shift_enter(self, event):
        """Shift+Enter - yeni satır"""
        return
    
    def clear_chat(self):
        """Sohbeti temizle"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.insert(tk.END, "💬 Sohbet temizlendi. Nasıl yardımcı olabilirim?\n")
        self.chat_display.insert(tk.END, "───────────────────────────────────────────────────\n")
        self.chat_display.config(state=tk.DISABLED)
    
    def save_chat(self):
        """Sohbeti kaydet"""
        try:
            content = self.chat_display.get(1.0, tk.END)
            if not content.strip():
                messagebox.showwarning("Uyarı", "Kaydedilecek sohbet içeriği yok!")
                return
            
            filename = f"sohbet_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            file_path = filedialog.asksaveasfilename(
                initialfile=filename,
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Başarılı", f"✅ Sohbet kaydedildi: {file_path}")
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Sohbet kaydedilemedi: {e}")
    
    def show_settings(self):
        """Ayarlar penceresini göster"""
        ModernSettingsWindow(self.root, self.agent, on_save_callback=self.on_settings_saved)
    
    def show_model_selection(self):
        if config.get("backend", "deepseek") == "llamacpp":
            ModelSelectionWindow(self.root, self.agent,
                                 on_change=self._on_model_changed,
                                 on_gguf_selected=self._on_gguf_chosen)
            return
        if not self.agent.llm_client:
            messagebox.showerror("Hata", "Once backend ayarlarini yapilandirin!")
            self.show_settings()
            return
        ModelSelectionWindow(self.root, self.agent, on_change=self._on_model_changed)

    def _on_gguf_chosen(self, path: str):
        """GGUF secildi: eski modeli bosalt, yeniyi yukle."""
        try:
            if self.agent.model_loaded:
                self.agent.unload_model()
        except Exception:
            pass
        try:
            self.refresh_dashboard()
        except Exception:
            pass
        self.status_var.set(f"Secildi: {Path(path).name} - yukleniyor...")
        self._reload_model()

    def _on_model_changed(self):
        try:
            self.update_model_display()
        except Exception:
            pass
        try:
            self.refresh_dashboard()
        except Exception:
            pass
        try:
            self.status_var.set("Model degistirildi.")
        except Exception:
            pass
    
    def save_profile(self):
        """Profili kaydet"""
        try:
            profile_name = config.get("profile_name", "Varsayılan")
            profiles = config.get("profiles", {})
            
            profiles[profile_name] = {
                "workspace_path": config.get("workspace_path"),
                "api_key": config.get("api_key"),
                "selected_model": config.get("selected_model"),
                "profile_description": config.get("profile_description", ""),
                "saved_at": datetime.datetime.now().isoformat()
            }
            
            config.set("profiles", profiles)
            messagebox.showinfo("Başarılı", f"✅ '{profile_name}' profili kaydedildi!")
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Profil kaydedilemedi: {e}")
    
    def on_settings_saved(self):
        """Ayarlar kaydedildiğinde"""
        self.refresh_file_tree()
        self.update_model_display()
        self.status_var.set("✅ Ayarlar güncellendi! Sistem hazır.")
        self.agent_status.config(text="● Çalışıyor", fg='#27ae60')
    
    def _apply_model_info_to_ui(self, info: dict):
        """Yuklu model + backend + yukleme suresini tum panellere yaz."""
        name = info.get('model_name', '-') if info.get('loaded') else "-"
        load_time = info.get('load_time', '-')
        loaded_at = info.get('loaded_at', '-')
        backend_label = info.get('backend_label', info.get('backend', '-'))

        top_text = f"Yuklu model: {name}" if info.get('loaded') else "Yuklu model: -"
        server_bit = f"  |  Server: {info['server_url']}" if info.get('server_url') else ""
        sub_text = (f"Backend: {backend_label}  |  Yukleme suresi: {load_time}  |  Yuklenme: {loaded_at}{server_bit}"
                    if info.get('loaded') else f"Backend: {backend_label}  |  Yukleme suresi: -")
        try:
            self.top_model_var.set(top_text)
        except Exception:
            pass
        try:
            self.top_load_var.set(sub_text)
        except Exception:
            pass
        try:
            self.model_var.set(top_text)
        except Exception:
            pass
        try:
            self.model_label.config(text=top_text)
        except Exception:
            pass
        try:
            self.chat_model_var.set(f"Sohbet modeli: {name} ({backend_label})")
        except Exception:
            pass
        try:
            if info.get('loaded'):
                self.arch_model_var.set(f"Model: {name} | Sure: {load_time}")
            else:
                self.arch_model_var.set("Model: yuklu degil -> Araclar > MODEL'den secin")
        except Exception:
            pass
        try:
            self.home_model_var.set(f"{top_text}  |  {sub_text}")
        except Exception:
            pass

    def update_model_display(self):
        """Model bilgisini güncelle"""
        try:
            info = self.agent.get_model_info()
        except Exception:
            return
        self._apply_model_info_to_ui(info)
    
    def show_help(self):
        """Yardım penceresini göster"""
        help_text = """🚀 Ogma KULLANIM KILAVUZU

1. BAŞLANGIÇ
• Ayarlar butonundan API Key ve çalışma dizini ayarlayın
• DeepSeek API Key: https://platform.deepseek.com/

2. DOSYA YÖNETİMİ
• Sol panelden dosyalarınıza erişin
• Sağ tık menüsü ile hızlı işlemler yapın

3. KOD ANALİZİ
• Dosya seçin ve "Analiz Et" butonuna tıklayın
• AI kodunuzu 5 başlıkta analiz eder

4. AI ASİSTAN
• Sohbet panelinden AI ile konuşun
• Kod soruları, problem çözme, açıklama isteme

5. ÖZELLİKLER
• Modern arayüz
• Responsive tasarım
• Gerçek zamanlı düzenleme
• Otomatik yedekleme

───────────────────────────────────────────────────
Created by İlker Can Karagülle | Ogma 2024
"""
        messagebox.showinfo("Yardım", help_text)
    
    def show_new_menu(self):
        """Yeni dosya/klasör menüsü"""
        menu = tk.Menu(self.root, tearoff=0, bg='#ffffff', fg='#000000')
        
        menu.add_command(label="📄 Yeni Dosya", command=self.new_file)
        menu.add_command(label="📁 Yeni Klasör", command=self.new_folder)
        menu.add_separator()
        menu.add_command(label="🐍 Python Dosyası", command=lambda: self.new_file_with_extension(".py"))
        menu.add_command(label="📝 Text Dosyası", command=lambda: self.new_file_with_extension(".txt"))
        menu.add_command(label="📊 JSON Dosyası", command=lambda: self.new_file_with_extension(".json"))
        menu.add_command(label="📋 Markdown Dosyası", command=lambda: self.new_file_with_extension(".md"))
        
        # Menüyü butonun altında göster
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()
    
    def new_file_with_extension(self, extension):
        """Belirli uzantıda yeni dosya oluştur"""
        try:
            file_name = simpledialog.askstring("Yeni Dosya", f"Dosya adı ({extension}):")
            if file_name:
                if not file_name.endswith(extension):
                    file_name += extension
                    
                if self.agent.file_manager.write_file(file_name, f"# {file_name}\n\n"):
                    self.refresh_file_tree()
                    self.current_file = file_name
                    self.code_editor.delete(1.0, tk.END)
                    self.code_editor.insert(1.0, f"# {file_name}\n\n")
                    self.update_line_numbers()
                    self.status_var.set(f"📄 Oluşturuldu: {file_name}")
                    self.session_manager.add_file_operation("create", file_name, True)
                else:
                    messagebox.showerror("Hata", "❌ Dosya oluşturulamadı!")
                    self.session_manager.add_file_operation("create", file_name, False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Yeni dosya oluşturma hatası: {e}")
    
    def on_search(self, event):
        """Dosya arama"""
        search_term = self.search_var.get().lower()
        if not search_term:
            self.refresh_file_tree()
            return
        
        # Basit arama implementasyonu
        for item in self.tree.get_children():
            item_text = self.tree.item(item, 'text').lower()
            if search_term in item_text:
                self.tree.selection_set(item)
                self.tree.focus(item)
                break
    
    def initialize_agent(self):
        def init_thread():
            try:
                self.root.after(0, lambda: self.status_var.set("Ogma baslatiliyor..."))
                self.root.after(0, lambda: self.agent_status.config(text="Baslatiliyor", fg='#f39c12'))
                
                success = self.agent.initialize()
                
                if success:
                    self.root.after(0, self.on_agent_ready)
                else:
                    self.root.after(0, lambda: self.status_var.set("Backend ayarlari gerekli - ust bardan Ayarlar'i acin"))
                    self.root.after(0, lambda: self.agent_status.config(text="Ayarlar Gerekli", fg='#e74c3c'))
                    self.root.after(0, self.refresh_dashboard)
                    
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Hata", f"❌ Başlatma hatası: {e}"))
                self.root.after(0, lambda: self.agent_status.config(text="● Hata", fg='#e74c3c'))
        
        threading.Thread(target=init_thread, daemon=True).start()
    
    def _update_workspace_labels(self):
        try:
            ws = config.get("workspace_path", "") or "-"
        except Exception:
            ws = "-"
        for attr in ("arch_workspace_var", "home_ws_var"):
            try:
                getattr(self, attr).set(f"Klasor: {ws}")
            except Exception:
                pass
        # Cikti klasoru: secilmemisse proje icindeki varsayilan
        try:
            out = config.get("architecture_output_dir", "")
            if not out:
                base = config.get("workspace_path", "") or str(
                    Path(__file__).resolve().parent)
                out = str(Path(base) / "storage" / "reports")
        except Exception:
            out = "-"
        for attr in ("arch_output_var", "home_out_var"):
            try:
                getattr(self, attr).set(f"Cikti: {out}")
            except Exception:
                pass

    def on_agent_ready(self):
        self.status_var.set("Ogma hazir! Once model, sonra mimari analiz.")
        self.agent_status.config(text="Calisiyor", fg='#27ae60')
        self.update_model_display()
        self.refresh_dashboard()
        self.refresh_file_tree()
        self.refresh_history()
        self._update_workspace_labels()

    def refresh_dashboard(self):
        """Sadece gostergeyi tazele. Asla otomatik model yuklemez."""
        info = self.agent.get_model_info()
        self.dash_backend.config(text=f"Backend: {info['backend_label']}")
        self.dash_model.config(text=f"Model: {info['model_name']}")

        if info['loaded']:
            self.dash_status.config(text=f"Durum: Aktif ({info.get('load_time', '-')})", fg='#27ae60')
            self.dash_memory.config(text=f"Bellek: {info['memory']}")
        else:
            self.dash_status.config(text="Durum: Yuklu degil", fg='#95a5a6')
            self.dash_memory.config(text="Bellek: -")
        self._apply_model_info_to_ui(info)

    def load_model_action(self):
        """Yukle butonu: secili modeli acikca yukle. Otomatik yukleme yapilmaz."""
        if self.agent.model_loaded:
            messagebox.showinfo("Bilgi", "Model zaten yuklu.")
            return
        if self.agent.backend == "llamacpp":
            if not config.get("llamacpp_model_path"):
                messagebox.showerror("Hata", "Once bir GGUF model dosyasi secin (Model Sec)!")
                self.show_model_selection()
                return
            self._reload_model()
        else:
            def init_thread():
                try:
                    self.root.after(0, lambda: self.status_var.set("Baglaniyor..."))
                    ok = self.agent.initialize()
                    if ok:
                        self.root.after(0, self.on_agent_ready)
                    else:
                        self.root.after(0, lambda: self.status_var.set("Baglanti kurulamadi, ayari kontrol edin."))
                        self.root.after(0, self.refresh_dashboard)
                except Exception as e:
                    self.root.after(0, lambda e=e: self.status_var.set(f"Baglanti hatasi: {e}"))
            threading.Thread(target=init_thread, daemon=True).start()

    def _reload_model(self):
        """Secili GGUF modeli yukle. Zaten yukluyse tekrar yuklemez."""
        if self.agent.model_loaded:
            self.status_var.set("Model zaten yuklu.")
            return

        def reload_thread():
            try:
                self.root.after(0, lambda: self.status_var.set("Model yukleniyor..."))
                success = self.agent.load_gguf_model(
                    callback=lambda msg, pct: self.root.after(0, lambda m=msg: self.status_var.set(f"Model: {m}"))
                )
                if success:
                    self.root.after(0, lambda: self.dash_status.config(text="Durum: Aktif", fg='#27ae60'))
                    self.root.after(0, lambda: self.refresh_dashboard())
                    self.root.after(0, lambda: self.status_var.set("Model yuklendi!"))
                else:
                    self.root.after(0, lambda: self.dash_status.config(text="Durum: Yuklenemedi", fg='#e74c3c'))
                    self.root.after(0, lambda: self.status_var.set("Model yuklenemedi!"))
            except Exception as e:
                self.root.after(0, lambda: self.dash_status.config(text=f"Durum: Hata - {e}", fg='#e74c3c'))
                self.root.after(0, lambda: self.status_var.set(f"Model yukleme hatasi: {e}"))

        threading.Thread(target=reload_thread, daemon=True).start()

    def unload_model_action(self):
        if messagebox.askyesno("Onay", "Modeli bosaltmak istediginize emin misiniz?"):
            self.agent.unload_model()
            self.refresh_dashboard()
            self.status_var.set("Model bosaltildi")

    def show_hardware_window(self):
        """Donanim taramasi penceresini ac."""
        HardwareWindow(self.root, self.agent, on_applied=self._on_hardware_applied)

    def show_dev_tools(self):
        """Gelistirici araclari penceresini ac (sembol/outline/etki)."""
        try:
            from gui.gelistirici_araclar_gui import GelistiriciAraclariWindow
            GelistiriciAraclariWindow(self.root)
        except Exception as e:
            messagebox.showerror("Hata", f"Araclar acilamadi: {e}")

    def show_watcher(self):
        """Canli izleyici penceresini ac (E3)."""
        try:
            from gui.watcher_gui import WatcherWindow
            WatcherWindow(self.root)
        except Exception as e:
            messagebox.showerror("Hata", f"Izleyici acilamadi: {e}")

    def show_capability_test(self):
        """Model capability test penceresini ac (D4)."""
        try:
            from gui.model_capability_gui import ModelCapabilityWindow
            ModelCapabilityWindow(self.root, self.agent)
        except Exception as e:
            messagebox.showerror("Hata", f"Capability test acilamadi: {e}")

    def _on_hardware_applied(self):
        # Ayarlar RAM'deki modele islemez: yuklu model varsa bosalt + yeni
        # ayarlarla GERCEKTEN yeniden yukle. Yoksa sadece gostergeyi tazele.
        was_loaded = bool(self.agent.model_loaded)
        if was_loaded:
            try:
                self.agent.unload_model()
            except Exception:
                pass
            try:
                self.refresh_dashboard()
            except Exception:
                pass
            try:
                self.status_var.set("Donanim profili uygulandi, model yeni ayarlarla yukleniyor...")
            except Exception:
                pass
            self.load_model_action()
        else:
            try:
                self.refresh_dashboard()
            except Exception:
                pass
            try:
                self.status_var.set("Donanim profili uygulandi. 'Yukle' ile modeli baslat.")
            except Exception:
                pass

    def _maybe_hardware_check(self):
        """Ilk acilista bir kez donanim onerisi goster."""
        try:
            if config.get("hardware_checked", False):
                return
        except Exception:
            return
        try:
            HardwareWindow(self.root, self.agent,
                           on_applied=self._on_hardware_applied)
        except Exception:
            pass

    @staticmethod
    def _gpu_offer(hw: dict):
        """Varsa (gpu adi, motor) dondur: NVIDIA->CUDA, AMD/Intel->Vulkan."""
        try:
            from core.local_client import LlamaServerClient
        except Exception:
            return None
        nvidia = hw.get("nvidia_gpus", []) or []
        if nvidia and LlamaServerClient.find_server_exe("cuda"):
            g = nvidia[0]
            return (f"{g['name']} ({g['vram_mb'] // 1024} GB VRAM)", "CUDA")
        others = hw.get("other_gpus", []) or []
        if others and LlamaServerClient.find_server_exe("vulkan"):
            return (f"{others[0].get('name')} ({others[0].get('vendor')})", "Vulkan")
        return None

    def show_compute_choice(self):
        """Araclar butonu: GPU/CPU secimini her zaman sor."""
        try:
            hw = detect_hardware()
            offer = self._gpu_offer(hw)
            if not offer:
                messagebox.showinfo("Bilgi", "Uygun GPU motoru bulunamadi, CPU-only ile devam ediliyor.")
                return
            name, engine = offer
        except Exception as e:
            messagebox.showerror("Hata", f"Donanim okunamadi: {e}")
            return
        if getattr(self, "_compute_window_open", False):
            return
        self._compute_window_open = True
        ComputeChoiceWindow(self.root, self.agent, name,
                            on_done=self._on_compute_chosen, engine=engine)

    def _on_compute_chosen(self, mode: str):
        self._compute_window_open = False
        if self.agent.model_loaded:
            try:
                self.agent.unload_model()
            except Exception:
                pass
        try:
            self.refresh_dashboard()
        except Exception:
            pass
        if self.agent.backend == "llamacpp":
            try:
                self.status_var.set("GPU modu aciliyor..." if mode == "gpu" else "CPU modu aciliyor...")
            except Exception:
                pass
            self._reload_model()
        else:
            try:
                self.status_var.set(f"Secim kaydedildi: {mode}")
            except Exception:
                pass

    def show_download_window(self):
        DownloadModelWindow(self.root, self.agent, on_complete=self.refresh_dashboard)

    def launch_architecture_analyzer(self):
        """Mimari analizciyi başlat"""
        from gui.architecture_analyzer_gui import ArchitectureAnalyzerLauncher
        ArchitectureAnalyzerLauncher(self.root, self.agent)

    def _tree_excluded_names(self) -> set:
        """Agacta gizlenecek klasor adlari (config + varsayilan sistem)."""
        try:
            custom = config.get("excluded_folders", []) or []
        except Exception:
            custom = []
        return set(custom) | {"__pycache__", "Python_Ortami", ".git", ".venv", "node_modules"}

    def _tree_item_visible(self, item: Path) -> bool:
        if item.name.startswith('.'):
            return False
        try:
            if item.name in self._tree_excluded_names():
                return False
        except Exception:
            pass
        return True

    def _tree_can_expand(self, item: Path) -> bool:
        """Derinlik tavanina ulasilmamissa genisletmeye izin ver."""
        try:
            max_depth = int(config.get("max_file_tree_depth", 3) or 3)
        except Exception:
            max_depth = 3
        try:
            ws = self.agent.file_manager.workspace_path
            depth = len(Path(item).resolve().relative_to(ws.resolve()).parts)
        except Exception:
            return True
        return depth < max_depth
    
    def refresh_file_tree(self):
        """Dosya ağacını yenile"""
        if not self.agent.file_manager:
            return
            
        try:
            self.tree.delete(*self.tree.get_children())
            
            if not hasattr(self.agent, 'file_manager') or not self.agent.file_manager:
                self.tree.insert('', 'end', text="⚠️ Çalışma dizini seçilmemiş", values=[""])
                return
                
            workspace_path = self.agent.file_manager.workspace_path

            def add_tree_items(parent, path):
                try:
                    items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                    for item in items:
                        if not self._tree_item_visible(item):
                            continue

                        item_id = self.tree.insert(parent, 'end', text=item.name,
                                                 values=[str(item)],
                                                 tags=('dir' if item.is_dir() else 'file',))
                        if item.is_dir() and self._tree_can_expand(item):
                            self.tree.insert(item_id, 'end', text="...")
                except (PermissionError, OSError):
                    self.tree.insert(parent, 'end', text="[Erişim Engellendi]")
            
            root_id = self.tree.insert('', 'end', text=workspace_path.name, 
                                     values=[str(workspace_path)], tags=('root',))
            add_tree_items(root_id, workspace_path)
            
        except Exception as e:
            self.tree.insert('', 'end', text=f"⚠️ Hata: {str(e)}", values=[""])
    
    def on_treeview_open(self, event):
        """Klasör genişletildiğinde içeriği yükle"""
        item = self.tree.focus()
        if not item:
            return
            
        item_path = Path(self.tree.item(item, 'values')[0])
        
        # Eğer zaten yüklenmişse tekrar yükleme
        if self.tree.get_children(item) and self.tree.item(self.tree.get_children(item)[0], 'text') != "...":
            return
            
        # Eski placeholder'ı temizle
        for child in self.tree.get_children(item):
            self.tree.delete(child)
        
        # Yeni içeriği yükle
        def load_children():
            try:
                items = sorted(item_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for child_item in items:
                    if not self._tree_item_visible(child_item):
                        continue

                    child_id = self.tree.insert(item, 'end', text=child_item.name,
                                              values=[str(child_item)],
                                              tags=('dir' if child_item.is_dir() else 'file',))
                    if child_item.is_dir() and self._tree_can_expand(child_item):
                        self.tree.insert(child_id, 'end', text="...")
            except (PermissionError, OSError):
                self.tree.insert(item, 'end', text="[Erişim Engellendi]")
        
        load_children()
    
    def on_file_select(self, event):
        """Dosya seçildiğinde"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = self.tree.item(selection[0])
        file_path = Path(item['values'][0])
        
        if file_path.is_file():
            try:
                relative_path = file_path.relative_to(self.agent.file_manager.workspace_path)
                self.load_file(str(relative_path))
            except ValueError:
                # Dosya workspace dışındaysa
                messagebox.showwarning("Uyarı", "Dosya workspace dışında!")
    
    def load_file(self, file_path: str):
        """Dosyayı yükle"""
        try:
            content = self.agent.file_manager.read_file(file_path)
            if content is not None:
                self.code_editor.delete(1.0, tk.END)
                self.code_editor.insert(1.0, content)
                self.current_file = file_path
                self.update_line_numbers()
                self.status_var.set(f"📂 Yüklendi: {file_path}")
                self.notebook.select(0)  # Editör sekmesine geç
                
                # Oturum geçmişine ekle
                self.session_manager.add_file_operation("read", file_path, True)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Dosya yüklenemedi: {e}")
            self.session_manager.add_file_operation("read", file_path, False)
    
    def update_line_numbers(self, event=None):
        """Line number'ları güncelle"""
        try:
            # Mevcut line number'ları temizle
            self.line_numbers.config(state=tk.NORMAL)
            self.line_numbers.delete(1.0, tk.END)
            
            # Satır sayısını al
            lines = self.code_editor.get(1.0, tk.END).count('\n')
            if lines > 0:
                line_numbers_text = '\n'.join(str(i) for i in range(1, lines + 1))
                self.line_numbers.insert(1.0, line_numbers_text)
            
            self.line_numbers.config(state=tk.DISABLED)
        except Exception:
            pass
    
    def refresh_history(self):
        """Geçmişi yenile"""
        try:
            self.history_tree.delete(*self.history_tree.get_children())
            
            # Dosya operasyonları
            file_ops = self.session_manager.current_session.get("file_operations", [])
            for op in file_ops[-50:]:  # Son 50 işlem
                self.history_tree.insert('', 'end', values=(
                    op.get('timestamp', '')[:19],
                    op.get('file_path', ''),
                    f"{op.get('operation', '')} - {'✅' if op.get('success') else '❌'}"
                ))
            
            # Konuşma geçmişi
            conversations = self.session_manager.current_session.get("conversation_history", [])
            for conv in conversations[-20:]:  # Son 20 konuşma
                if conv.get('role') == 'user':
                    self.history_tree.insert('', 'end', values=(
                        conv.get('timestamp', '')[:19],
                        '💬 Sohbet',
                        f"Kullanıcı: {conv.get('content', '')[:50]}..."
                    ))
        except Exception as e:
            try:
                self.status_var.set(f"Geçmiş yenilenemedi: {e}")
            except Exception:
                pass

    def clear_history(self):
        """Geçmişi temizle"""
        if messagebox.askyesno("Onay", "Tüm oturum geçmişini temizlemek istiyor musunuz?"):
            self.session_manager.clear_conversation_history()
            self.refresh_history()
            messagebox.showinfo("Başarılı", "✅ Geçmiş temizlendi!")
    
    def export_history(self):
        """Geçmişi dışa aktar"""
        try:
            filename = f"ravenart_history_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file_path = filedialog.asksaveasfilename(
                initialfile=filename,
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.session_manager.current_session, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Başarılı", f"✅ Geçmiş dışa aktarıldı: {file_path}")
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Geçmiş dışa aktarılamadı: {e}")
    
    def on_history_select(self, event):
        """Geçmiş öğesi seçildiğinde"""
        selection = self.history_tree.selection()
        if not selection:
            return
        
        item = self.history_tree.item(selection[0])
        values = item['values']
        
        detail = f"📅 Tarih: {values[0]}\n"
        detail += f"📁 Dosya: {values[1]}\n"
        detail += f"⚡ İşlem: {values[2]}\n\n"
        
        # Detaylı bilgiyi bul ve göster
        self.history_detail.delete(1.0, tk.END)
        self.history_detail.insert(tk.END, detail)
    
    def open_file(self):
        """Dosya aç"""
        try:
            file_path = filedialog.askopenfilename(
                initialdir=self.agent.file_manager.workspace_path if self.agent.file_manager else ".",
                title="Dosya Aç",
                filetypes=(("Python files", "*.py"), ("Text files", "*.txt"), ("All files", "*.*"))
            )
            
            if file_path:
                full_path = Path(file_path)
                relative_path = full_path.relative_to(self.agent.file_manager.workspace_path)
                self.load_file(str(relative_path))
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Dosya açma hatası: {e}")
    
    def save_file(self):
        """Dosyayı kaydet"""
        if not self.current_file:
            self.save_file_as()
            return
            
        try:
            content = self.code_editor.get(1.0, tk.END)
            if self.agent.file_manager.write_file(self.current_file, content.rstrip()):
                self.status_var.set(f"💾 Kaydedildi: {self.current_file}")
                self.session_manager.add_file_operation("save", self.current_file, True)
            else:
                messagebox.showerror("Hata", "❌ Dosya kaydedilemedi!")
                self.session_manager.add_file_operation("save", self.current_file, False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Kaydetme hatası: {e}")
            self.session_manager.add_file_operation("save", self.current_file, False)
    
    def save_file_as(self):
        """Farklı kaydet"""
        try:
            content = self.code_editor.get(1.0, tk.END)
            file_path = filedialog.asksaveasfilename(
                initialdir=self.agent.file_manager.workspace_path if self.agent.file_manager else ".",
                title="Dosyayı Kaydet",
                filetypes=(("Python files", "*.py"), ("Text files", "*.txt"), ("All files", "*.*"))
            )
            
            if file_path:
                full_path = Path(file_path)
                relative_path = full_path.relative_to(self.agent.file_manager.workspace_path)
                if self.agent.file_manager.write_file(str(relative_path), content.rstrip()):
                    self.current_file = str(relative_path)
                    self.refresh_file_tree()
                    self.status_var.set(f"💾 Kaydedildi: {self.current_file}")
                    self.session_manager.add_file_operation("save_as", self.current_file, True)
                else:
                    self.session_manager.add_file_operation("save_as", str(relative_path), False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Farklı kaydetme hatası: {e}")
    
    def new_file(self):
        """Yeni dosya oluştur"""
        try:
            file_name = simpledialog.askstring("Yeni Dosya", "Dosya adı:")
            if file_name:
                if not any(file_name.endswith(ext) for ext in ['.py', '.txt', '.json', '.md']):
                    file_name += '.py'
                    
                # Boş içerikle dosya oluştur
                if self.agent.file_manager.write_file(file_name, f"# {file_name}\n\n"):
                    self.refresh_file_tree()
                    self.current_file = file_name
                    self.code_editor.delete(1.0, tk.END)
                    self.code_editor.insert(1.0, f"# {file_name}\n\n")
                    self.update_line_numbers()
                    self.status_var.set(f"📄 Oluşturuldu: {file_name}")
                    self.session_manager.add_file_operation("create", file_name, True)
                else:
                    messagebox.showerror("Hata", "❌ Dosya oluşturulamadı!")
                    self.session_manager.add_file_operation("create", file_name, False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Yeni dosya oluşturma hatası: {e}")
    
    def new_folder(self):
        """Yeni klasör oluştur"""
        try:
            folder_name = simpledialog.askstring("Yeni Klasör", "Klasör adı:")
            if folder_name:
                if self.agent.file_manager.create_directory(folder_name):
                    self.refresh_file_tree()
                    self.status_var.set(f"📁 Klasör oluşturuldu: {folder_name}")
                    self.session_manager.add_file_operation("create_dir", folder_name, True)
                else:
                    messagebox.showerror("Hata", "❌ Klasör oluşturulamadı!")
                    self.session_manager.add_file_operation("create_dir", folder_name, False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Yeni klasör oluşturma hatası: {e}")
    
    def delete_file(self):
        """Mevcut dosyayı sil"""
        if not self.current_file:
            messagebox.showwarning("Uyarı", "Lütfen önce bir dosya seçin!")
            return
            
        try:
            if messagebox.askyesno("Sil", f"{self.current_file} dosyası silinsin mi?"):
                if self.agent.file_manager.delete_file(self.current_file):
                    self.refresh_file_tree()
                    self.current_file = None
                    self.code_editor.delete(1.0, tk.END)
                    self.status_var.set("🗑️ Dosya silindi.")
                    self.session_manager.add_file_operation("delete", self.current_file, True)
                else:
                    messagebox.showerror("Hata", "❌ Dosya silinemedi!")
                    self.session_manager.add_file_operation("delete", self.current_file, False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Silme hatası: {e}")
            self.session_manager.add_file_operation("delete", self.current_file, False)
    
    def delete_selected(self):
        """Seçili öğeyi sil"""
        selection = self.tree.selection()
        if not selection:
            return
            
        try:
            item = self.tree.item(selection[0])
            item_path = Path(item['values'][0])
            
            if messagebox.askyesno("Sil", f"{item_path.name} silinsin mi?"):
                relative_path = item_path.relative_to(self.agent.file_manager.workspace_path)
                if self.agent.file_manager.delete_file(str(relative_path)):
                    self.refresh_file_tree()
                    # Eğer silinen dosya mevcut dosyaysa, editörü temizle
                    if self.current_file == str(relative_path):
                        self.current_file = None
                        self.code_editor.delete(1.0, tk.END)
                    self.status_var.set(f"🗑️ Silindi: {item_path.name}")
                    self.session_manager.add_file_operation("delete", str(relative_path), True)
                else:
                    messagebox.showerror("Hata", "❌ Silme işlemi başarısız!")
                    self.session_manager.add_file_operation("delete", str(relative_path), False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Silme hatası: {e}")
    
    def rename_selected(self):
        """Seçili öğeyi yeniden adlandır"""
        selection = self.tree.selection()
        if not selection:
            return
            
        try:
            item = self.tree.item(selection[0])
            old_path = Path(item['values'][0])
            relative_old_path = old_path.relative_to(self.agent.file_manager.workspace_path)
            
            new_name = simpledialog.askstring("Yeniden Adlandır", "Yeni ad:", initialvalue=old_path.name)
            if new_name and new_name != old_path.name:
                # Yeni yol oluştur
                new_relative_path = str(relative_old_path.parent / new_name)
                if self.agent.file_manager.rename_file(str(relative_old_path), new_relative_path):
                    self.refresh_file_tree()
                    # Eğer yeniden adlandırılan dosya mevcut dosyaysa, güncelle
                    if self.current_file == str(relative_old_path):
                        self.current_file = new_relative_path
                    self.status_var.set(f"✏️ Yeniden adlandırıldı: {new_name}")
                    self.session_manager.add_file_operation("rename", f"{relative_old_path} -> {new_relative_path}", True)
                else:
                    messagebox.showerror("Hata", "❌ Yeniden adlandırılamadı!")
                    self.session_manager.add_file_operation("rename", f"{relative_old_path} -> {new_relative_path}", False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Yeniden adlandırma hatası: {e}")
    
    def analyze_selected(self):
        """Seçili dosyayı analiz et"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = self.tree.item(selection[0])
        file_path = Path(item['values'][0])
        
        if file_path.is_file():
            try:
                relative_path = file_path.relative_to(self.agent.file_manager.workspace_path)
                self.load_file(str(relative_path))
                self.analyze_current()
            except ValueError:
                messagebox.showwarning("Uyarı", "Dosya workspace dışında!")
    
    def quick_analyze_selected(self):
        """Seçili dosyayı hızlı analiz et"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = self.tree.item(selection[0])
        file_path = Path(item['values'][0])
        
        if file_path.is_file():
            try:
                relative_path = file_path.relative_to(self.agent.file_manager.workspace_path)
                self.quick_analyze_file(str(relative_path))
            except ValueError:
                messagebox.showwarning("Uyarı", "Dosya workspace dışında!")
    
    def analyze_current(self):
        """Mevcut dosyayı analiz et"""
        if not self.current_file:
            messagebox.showwarning("Uyarı", "Lütfen önce bir dosya seçin!")
            return
            
        if not self.agent.llm_client:
            messagebox.showerror("Hata", "LLM client baslatilmamis!")
            return

        self.analyze_btn.config(state=tk.DISABLED, bg='#7f8c8d')
        self.quick_analyze_btn.config(state=tk.DISABLED, bg='#7f8c8d')
        self.status_var.set("🔍 Kod analiz ediliyor...")

        cancelled = [False]

        def on_cancel():
            cancelled[0] = True
            self.analyze_btn.config(state=tk.NORMAL, bg='#3498db')
            self.quick_analyze_btn.config(state=tk.NORMAL, bg='#3498db')
            self.status_var.set("❌ Analiz iptal edildi!")

        loading = LoadingDialog(self.root, "Analiz Ediliyor", f"{self.current_file} analiz ediliyor...", on_cancel=on_cancel)
        loading.update_status("Dosya okunuyor...")

        def analyze_thread():
            try:
                loading.update_status("AI modeli calisiyor, lutfen bekleyin...")
                analysis, improved_code = self.agent.analyze_script_gui(self.current_file)
                self.improved_code = improved_code

                if cancelled[0]:
                    return

                loading.update_status("Sonuclar hazirlaniyor...")
                self.root.after(0, lambda: self.show_analysis_results(analysis, improved_code))
                self.root.after(0, lambda: self.status_var.set("✅ Analiz tamamlandı!"))
                self.root.after(100, loading.close)
                self.root.after(200, lambda: self.analyze_btn.config(state=tk.NORMAL, bg='#3498db'))
                self.root.after(200, lambda: self.quick_analyze_btn.config(state=tk.NORMAL, bg='#3498db'))

            except Exception as e:
                if not cancelled[0]:
                    self.root.after(0, loading.close)
                    self.root.after(0, lambda: messagebox.showerror("Hata", f"❌ Analiz başarısız: {e}"))
                    self.root.after(0, lambda: self.status_var.set("❌ Analiz başarısız!"))
                self.root.after(200, lambda: self.analyze_btn.config(state=tk.NORMAL, bg='#3498db'))
                self.root.after(200, lambda: self.quick_analyze_btn.config(state=tk.NORMAL, bg='#3498db'))
        
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def quick_analyze(self):
        """Hızlı analiz"""
        if not self.current_file:
            messagebox.showwarning("Uyarı", "Lütfen önce bir dosya seçin!")
            return
        
        self.quick_analyze_file(self.current_file)
    
    def quick_analyze_file(self, file_path: str):
        if not self.agent.llm_client:
            messagebox.showerror("Hata", "LLM client baslatilmamis!")
            return

        self.analyze_btn.config(state=tk.DISABLED, bg='#7f8c8d')
        self.quick_analyze_btn.config(state=tk.DISABLED, bg='#7f8c8d')
        self.status_var.set("⚡ Hızlı analiz yapılıyor...")

        cancelled = [False]

        def on_cancel():
            cancelled[0] = True
            self.analyze_btn.config(state=tk.NORMAL, bg='#3498db')
            self.quick_analyze_btn.config(state=tk.NORMAL, bg='#3498db')
            self.status_var.set("❌ Analiz iptal edildi!")

        loading = LoadingDialog(self.root, "Hızlı Analiz", f"{file_path} analiz ediliyor...", on_cancel=on_cancel)
        loading.update_status("Kod okunuyor...")

        def quick_analyze_thread():
            try:
                content = self.agent.file_manager.read_file(file_path)
                if not content:
                    if not cancelled[0]:
                        self.root.after(0, loading.close)
                        self.root.after(0, lambda: messagebox.showerror("Hata", "❌ Dosya okunamadı!"))
                    self.root.after(200, lambda: self.analyze_btn.config(state=tk.NORMAL, bg='#3498db'))
                    self.root.after(200, lambda: self.quick_analyze_btn.config(state=tk.NORMAL, bg='#3498db'))
                    return
                
                loading.update_status("AI modeli calisiyor...")
                prompt = f"Kodu analiz et. 3 sorun ve 3 iyilestirme onerisi ver:\n\n{content[:2000]}"
                
                response = self.agent.llm_client.chat_completion(
                    model=self.agent.current_model.id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=800
                )
                
                if cancelled[0]:
                    return

                if response:
                    def show_response():
                        self.add_chat_message("⚡ Hızlı Analiz", 
                            f"{file_path} için hızlı analiz:\n\n{response}")
                        self.status_var.set("✅ Hızlı analiz tamamlandı!")
                    self.root.after(0, show_response)
                else:
                    def show_failed():
                        self.add_chat_message("Sistem", "❌ Hızlı analiz başarısız!")
                        self.status_var.set("❌ Hızlı analiz başarısız!")
                    self.root.after(0, show_failed)
                
                self.root.after(100, loading.close)
                self.root.after(200, lambda: self.analyze_btn.config(state=tk.NORMAL, bg='#3498db'))
                self.root.after(200, lambda: self.quick_analyze_btn.config(state=tk.NORMAL, bg='#3498db'))

            except Exception as e:
                if not cancelled[0]:
                    self.root.after(0, loading.close)
                    self.root.after(0, lambda: self.add_chat_message("Sistem", f"❌ Hızlı analiz hatası: {e}"))
                    self.root.after(0, lambda: self.status_var.set("❌ Hızlı analiz hatası!"))
                self.root.after(200, lambda: self.analyze_btn.config(state=tk.NORMAL, bg='#3498db'))
                self.root.after(200, lambda: self.quick_analyze_btn.config(state=tk.NORMAL, bg='#3498db'))
        
        threading.Thread(target=quick_analyze_thread, daemon=True).start()
    
    def show_analysis_results(self, analysis, improved_code):
        original_code = self.agent.file_manager.read_file(self.current_file) if self.current_file else None
        win1 = ModernAnalysisWindow(self.root, self.current_file, analysis, improved_code, self.apply_improvements, original_code=original_code)
        win2 = AnalysisFollowUpWindow(self.root, self.agent, analysis, self.current_file)
        self.root.after(100, lambda: self._bring_windows_front(win1, win2))

    def _bring_windows_front(self, win1, win2):
        try:
            if win1 and win1.window:
                win1.window.lift()
                win1.window.focus_force()
        except Exception:
            pass
        try:
            if win2 and win2.window:
                win2.window.lift()
                win2.window.focus_force()
        except Exception:
            pass
    
    def apply_improvements(self, improved_code):
        """İyileştirilmiş kodu uygula"""
        try:
            # Orijinal dosyayı yedekle
            backup_path = f"{self.current_file}.backup"
            current_content = self.agent.file_manager.read_file(self.current_file)
            self.agent.file_manager.write_file(backup_path, current_content)
            
            # İyileştirilmiş kodu uygula
            if self.agent.file_manager.write_file(self.current_file, improved_code):
                self.load_file(self.current_file)  # Editörü yeniden yükle
                messagebox.showinfo("Başarılı", f"✅ Kod uygulandı! Orijinal dosya {backup_path} olarak yedeklendi.")
                self.session_manager.add_file_operation("apply_improvements", self.current_file, True)
            else:
                messagebox.showerror("Hata", "❌ Kod uygulanamadı!")
                self.session_manager.add_file_operation("apply_improvements", self.current_file, False)
        except Exception as e:
            messagebox.showerror("Hata", f"❌ Kod uygulama hatası: {e}")
            self.session_manager.add_file_operation("apply_improvements", self.current_file, False)
    
    def select_workspace(self):
        """Çalışma klasörü seç"""
        try:
            folder = filedialog.askdirectory(title="Çalışma Dizini Seç")
            if folder:
                config.set("workspace_path", folder)
                self.agent.file_manager = FileManager(Path(folder))
                self.refresh_file_tree()
                self._update_workspace_labels()
                self.status_var.set(f"Klasor secildi: {folder}")
        except Exception as e:
            messagebox.showerror("Hata", f"Klasor secme hatasi: {e}")
    
    def send_chat(self):
        """AI sohbete mesaj gönder"""
        message = self.chat_input.get(1.0, tk.END).strip()
        if not message:
            return
            
        self.chat_input.delete(1.0, tk.END)
        self.add_chat_message("👤 Kullanıcı", message)
        
        def chat_thread():
            try:
                response = self.agent.chat_with_ai(message)
                
                def update_ui():
                    self.add_chat_message("🤖 AI Asistan", response)
                    self.status_var.set("💬 Yanıt alındı")
                    
                    # Oturum geçmişine ekle
                    self.session_manager.add_conversation("user", message)
                    self.session_manager.add_conversation("assistant", response)
                    self.refresh_history()
                
                self.root.after(0, update_ui)
                
            except Exception as e:
                def show_error():
                    self.add_chat_message("❌ Sistem", f"Hata: {e}")
                
                self.root.after(0, show_error)
        
        self.status_var.set("🤖 AI yanıt hazırlıyor...")
        threading.Thread(target=chat_thread, daemon=True).start()
    
    def add_chat_message(self, sender: str, message: str):
        """Sohbete mesaj ekle"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"[{sender}]: {message}\n")
        self.chat_display.insert(tk.END, "─" * 60 + "\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
    
    def show_context_menu(self, event):
        """Sağ tık menüsünü göster"""
        try:
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
                self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

class OgmaAgent:
    """GUI icin uyarlanmis Agent sinifi — DeepSeek, Ollama ve llama.cpp destegi"""
    def __init__(self):
        self.config = config
        self.llm_client = None
        self.file_manager = None
        self.current_model = None
        self.backend = self.config.get("backend", "deepseek")
        self.model_loaded = False
        self.model_status = "Yukleniyor..."
        self.memory_usage = None
        self.model_load_seconds: Optional[float] = None
        self.model_loaded_at: Optional[str] = None
        self.chat_history = []
        self.last_analysis = None
        self.last_analysis_file = None

    def _mark_model_loaded(self, t0: float):
        """Basarili model yuklemede sure ve zaman damgasi isle."""
        try:
            self.model_load_seconds = round(time.time() - t0, 1)
        except Exception:
            self.model_load_seconds = None
        try:
            self.model_loaded_at = datetime.datetime.now().strftime("%H:%M:%S")
        except Exception:
            self.model_loaded_at = None

    def _mark_model_unloaded(self):
        self.model_load_seconds = None
        self.model_loaded_at = None

    def initialize(self) -> bool:
        self.backend = self.config.get("backend", "deepseek")
        if self.backend == "deepseek":
            return self._init_deepseek()
        elif self.backend == "ollama":
            return self._init_ollama()
        elif self.backend == "llamacpp":
            return self._init_llamacpp()
        elif self.backend == "provider":
            return self._init_provider()
        return False

    def _init_provider(self) -> bool:
        """OpenAI-uyumlu dis provider (E2): base_url/model/key ayarlardan gelir."""
        t0 = time.time()
        try:
            providers = self.config.get("providers", []) or []
            active = self.config.get("active_provider", "")
            p = next((x for x in providers if x.get("name") == active), None)
            if not p:
                self.model_status = "Aktif provider bulunamadi! Ayarlar'dan ekleyin."
                return False
            from core.provider_client import OpenAIProviderClient
            client = OpenAIProviderClient(
                name=p.get("name", "provider"),
                base_url=p.get("base_url", ""),
                model=p.get("model", ""),
                api_key=p.get("api_key", ""),
            )
            self.llm_client = client
            from types import SimpleNamespace
            self.current_model = SimpleNamespace(
                id=p.get("model", "default"),
                name=f"{p.get('name', 'provider')} ({p.get('model', '')})",
                description="OpenAI-uyumlu dis provider",
            )
            self.model_loaded = True
            self.model_status = f"Aktif: {self.current_model.name}"
            self._mark_model_loaded(t0)
            self._init_workspace()
            return True
        except Exception as e:
            self.model_status = f"Provider hatasi: {e}"
            self._mark_model_unloaded()
            return False

    def _init_deepseek(self) -> bool:
        t0 = time.time()
        try:
            api_key = self.config.get("api_key")
            if not api_key:
                self.model_status = "API Key gerekli!"
                return False
            self.llm_client = DeepSeekClient(api_key)
            available_models = self.llm_client.get_available_models()
            if available_models:
                selected_model_id = self.config.get("selected_model", "deepseek-chat")
                self.current_model = next(
                    (m for m in available_models if m.id == selected_model_id),
                    available_models[0],
                )
            else:
                self.current_model = AvailableModels.MODELS[0]
            self.model_loaded = True
            self.model_status = f"Aktif: {self.current_model.name}"
            self._mark_model_loaded(t0)
            return self._init_workspace()
        except Exception as e:
            self.model_status = f"DeepSeek hatasi: {e}"
            self._mark_model_unloaded()
            return False

    def _init_ollama(self) -> bool:
        t0 = time.time()
        try:
            ollama_url = self.config.get("ollama_url", "http://localhost:11434")
            manager = LocalModelManager(backend="ollama", ollama_url=ollama_url)
            if not manager.is_available():
                self.model_status = "Ollama calismiyor! 'ollama serve' gerekli"
                return False
            self.llm_client = manager
            installed = manager.get_available_models()
            ollama_model = self.config.get("ollama_model", "deepseek-r1:8b")
            if ollama_model in installed:
                model_id = ollama_model
            elif installed:
                model_id = installed[0]
            else:
                self.model_status = "Ollama'da yuklu model yok!"
                return False
            self.current_model = type(
                "LocalModel", (),
                {"id": model_id, "name": f"{model_id} (Ollama)", "description": "Yerel Ollama modeli"}
            )()
            self.model_loaded = True
            self.model_status = f"Aktif: {model_id}"
            self._mark_model_loaded(t0)
            return self._init_workspace()
        except Exception as e:
            self.model_status = f"Ollama hatasi: {e}"
            self._mark_model_unloaded()
            return False

    def _bundled_base_model(self) -> str:
        """Oncelik: config'deki taban yol, sonra proje/models/base altindaki ilk .gguf."""
        base = self.config.get("llamacpp_base_model", "")
        if base and Path(base).exists():
            return base
        try:
            found = find_bundled_base_model()
        except Exception:
            found = ""
        return found

    def _resolve_gguf_path(self) -> str:
        """Cache'teki model yolu gecerliyse onu, yoksa gomulu taban modeli dondur."""
        model_path = self.config.get("llamacpp_model_path", "")
        if model_path and Path(model_path).exists():
            return model_path
        base = self._bundled_base_model()
        if base:
            if not model_path:
                try:
                    self.config.set("llamacpp_model_path", base)
                except Exception:
                    pass
            return base
        return model_path

    def _use_gpu_server(self) -> bool:
        """GPU modu isteniyor VE uygun server binary mevcut mu?"""
        if self.config.get("compute_mode", "cpu") != "gpu":
            return False
        try:
            from core.local_client import LlamaServerClient
            return bool(LlamaServerClient.find_server_exe(self._server_flavor()))
        except Exception:
            return False

    def _server_flavor(self) -> str:
        """Donanima gore motor: NVIDIA -> cuda, digerleri -> vulkan."""
        try:
            if quick_gpu_vendor() == "nvidia":
                return "cuda"
        except Exception:
            pass
        return "vulkan"

    def _init_llamacpp(self) -> bool:
        t0 = time.time()
        try:
            model_path = self._resolve_gguf_path()
            if not model_path or not Path(model_path).exists():
                self.model_status = "GGUF model yolu belirtilmemis!"
                return False
            n_ctx = self.config.get("llamacpp_n_ctx", 8192)
            n_threads = self.config.get("llamacpp_n_threads", 4)
            if self._use_gpu_server():
                manager = LocalModelManager(backend="llamaserver",
                                            server_flavor=self._server_flavor())
                try:
                    manager.llamaserver.port = int(self.config.get("server_port", 8080))
                except Exception:
                    pass
                n_gpu = self.config.get("llamacpp_n_gpu_layers", 0) or 35
                self.model_status = "GPU server baslatiliyor..."
                if not manager.load_server_model(model_path, n_ctx, n_gpu):
                    self.model_status = "GPU server baslatilamadi!"
                    return False
                self.llm_client = manager
                self.current_model = type(
                    "LocalModel", (),
                    {"id": "llamaserver", "name": f"{Path(model_path).stem} (GPU)", "description": "llama-server GPU"}
                )()
            else:
                manager = LocalModelManager(backend="llamacpp")
                # CPU-only derlemede GPU katmani sifirlanir (config'de eski
                # deger kalmissa bile): CPU wheel n_gpu_layers>0 kaldiramaz.
                n_gpu = 0
                self.model_status = "Model yukleniyor..."
                if not manager.load_llamacpp_model(model_path, n_ctx, n_gpu, n_threads):
                    self.model_status = "GGUF modeli yuklenemedi!"
                    return False
                self.llm_client = manager
                self.current_model = type(
                    "LocalModel", (),
                    {"id": "llamacpp", "name": Path(model_path).stem, "description": "Yerel GGUF modeli"}
                )()
            self.model_loaded = True
            self.model_status = f"Aktif: {Path(model_path).name}"
            self._mark_model_loaded(t0)
            try:
                import os
                self.memory_usage = f"{os.path.getsize(model_path) / (1024*1024):.0f} MB"
            except:
                pass
            return self._init_workspace()
        except Exception as e:
            self.model_status = f"llama.cpp hatasi: {e}"
            self._mark_model_unloaded()
            return False

    def _init_workspace(self) -> bool:
        # Workspace opsiyoneldir: secilmemisse model yine de yuklenir,
        # kullanici klasoru sonra secer. Basarisiz init'e yol acmaz.
        workspace_path = self.config.get("workspace_path")
        if workspace_path and Path(workspace_path).exists():
            self.file_manager = FileManager(Path(workspace_path))
        else:
            self.file_manager = None
        return True

    def get_server_url(self) -> str:
        """Calisan GPU server adresi (yoksa bos string)."""
        try:
            client = getattr(self.llm_client, "llamaserver", None)
            if getattr(self.llm_client, "backend", "") == "llamaserver" and client:
                if getattr(client, "proc", None) and client.proc.poll() is None:
                    return client.base_url
        except Exception:
            pass
        return ""

    def get_model_info(self) -> dict:
        if self.model_load_seconds is None:
            load_time = "-"
        elif self.model_load_seconds < 60:
            load_time = f"{self.model_load_seconds:.1f} sn"
        else:
            load_time = f"{self.model_load_seconds / 60:.1f} dk"
        return {
            "backend": self.backend,
            "model_name": self.current_model.name if self.current_model else "-",
            "model_id": self.current_model.id if self.current_model else "-",
            "status": self.model_status,
            "loaded": self.model_loaded,
            "memory": self.memory_usage or "-",
            "load_seconds": self.model_load_seconds,
            "load_time": load_time,
            "loaded_at": self.model_loaded_at or "-",
            "backend_label": self._backend_label(),
            "compute": self._compute_label(),
            "server_url": self.get_server_url(),
        }

    def _backend_label(self) -> str:
        try:
            if getattr(self.llm_client, "backend", "") == "llamaserver":
                eng = getattr(getattr(self.llm_client, "llamaserver", None),
                              "engine", "") or ""
                return f"llama.cpp (GPU/{eng.upper()})" if eng else "llama.cpp (GPU)"
        except Exception:
            pass
        return {"deepseek": "DeepSeek API", "ollama": "Ollama",
                "llamacpp": "llama.cpp"}.get(self.backend, self.backend)

    def _compute_label(self) -> str:
        try:
            if getattr(self.llm_client, "backend", "") == "llamaserver":
                return "GPU"
        except Exception:
            pass
        if self.backend == "llamacpp":
            return "CPU"
        return "-"

    def load_gguf_model(self, callback=None) -> bool:
        t0 = time.time()
        model_path = self._resolve_gguf_path()
        if not model_path or not Path(model_path).exists():
            self.model_status = "GGUF model yolu belirtilmemis!"
            return False
        n_ctx = self.config.get("llamacpp_n_ctx", 4096)
        n_threads = self.config.get("llamacpp_n_threads", 4)
        if self._use_gpu_server():
            manager = LocalModelManager(backend="llamaserver",
                                        server_flavor=self._server_flavor())
            try:
                manager.llamaserver.port = int(self.config.get("server_port", 8080))
            except Exception:
                pass
            n_gpu = self.config.get("llamacpp_n_gpu_layers", 0) or 35
            self.model_status = "GPU server baslatiliyor..."
            if callback:
                callback("GPU server baslatiliyor...", 10)
            if not manager.load_server_model(model_path, n_ctx, n_gpu):
                self.model_status = "GPU server baslatilamadi!"
                self._mark_model_unloaded()
                return False
            self.llm_client = manager
            self.current_model = type(
                "LocalModel", (),
                {"id": "llamaserver", "name": f"{Path(model_path).stem} (GPU)", "description": "llama-server CUDA"}
            )()
        else:
            manager = LocalModelManager(backend="llamacpp")
            # CPU-only derlemede GPU katmani sifirlanir (config'de eski
            # deger kalmissa bile): CPU wheel n_gpu_layers>0 kaldiramaz.
            n_gpu = 0
            self.model_status = "Model yukleniyor..."
            if callback:
                callback("Yukleniyor...", 0)
            if not manager.load_llamacpp_model(model_path, n_ctx, n_gpu, n_threads):
                self.model_status = "GGUF modeli yuklenemedi!"
                self._mark_model_unloaded()
                return False
            self.llm_client = manager
            self.current_model = type(
                "LocalModel", (),
                {"id": "llamacpp", "name": Path(model_path).stem, "description": "Yerel GGUF modeli"}
            )()
        self.model_loaded = True
        self.model_status = f"Aktif: {Path(model_path).name}"
        self._mark_model_loaded(t0)
        try:
            import os
            self.memory_usage = f"{os.path.getsize(model_path) / (1024*1024):.0f} MB"
        except:
            pass
        if callback:
            callback("Tamamlandi!", 100)
        return True

    def unload_model(self):
        try:
            if self.llm_client:
                try:
                    client_backend = getattr(self.llm_client, "backend", "")
                    if client_backend == "llamaserver":
                        self.llm_client.unload_server_model()
                    elif self.backend == "llamacpp":
                        self.llm_client.unload_llamacpp_model()
                except Exception:
                    pass
        finally:
            self.llm_client = None
            self.current_model = None
            self.model_loaded = False
            self.model_status = "Model bosaltildi"
            self.memory_usage = None
            self._mark_model_unloaded()

    def analyze_script_gui(self, file_path: str):
        if not self.llm_client or not self.current_model:
            return "LLM client baslatilmamis!", None
        if not self.file_manager:
            return "Once proje klasoru secin!", None
        content = self.file_manager.read_file(file_path)
        if not content:
            return "Dosya okunamadi!", None

        self.last_analysis_file = file_path

        n_ctx = self.config.get("llamacpp_n_ctx", 8192) if hasattr(self, 'config') else 8192
        max_chars = (n_ctx - 1500) * 3
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n# ... [DOSYA KISITLANDI] ..."

        prompt = f"""Kodu analiz et. Kisa ve oz:
1. Ne yapiyor?
2. Sorunlar
3. Iyilestirmeler

Kod:
```python
{content}
```

Ozet cevap ver, 500 kelamSiniri aşma."""

        response = self.llm_client.chat_completion(
            model=self.current_model.id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )

        improved_code = None
        if response:
            self.last_analysis = response
            improved_code = self.generate_improved_code(content, response)

        return response if response else "Analiz yapilamadi!", improved_code

    def generate_improved_code(self, current_content: str, analysis: str):
        n_ctx = self.config.get("llamacpp_n_ctx", 8192) if hasattr(self, 'config') else 8192
        max_chars = (n_ctx - 1500) * 3
        if len(current_content) > max_chars:
            current_content = current_content[:max_chars] + "\n\n# ... [KISITLANDI] ..."
        if len(analysis) > max_chars:
            analysis = analysis[:max_chars]

        prompt = f"Kodu iyilestir. Sadece gerekli yerleri degistir:\n\n{current_content}\n\nAnaliz: {analysis}\n\nIyilestirilmis kodu ver:"

        improved_code = self.llm_client.chat_completion(
            model=self.current_model.id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )

        return improved_code

    SYSTEM_IDENTITY = (
        "Sen 'Ogma' adli masaustu programin icinde calisan AI asistansin. Ogma, proje klasorlerini "
        "tarayip mimari analiz raporu cikaran yerel bir yapay zeka aracidir. "
        "PROGRAMIN GERCEK OZELLIKLERI (bunlar vardir, 'yoktur' deme): "
        "1) Mimari Analiz: ana ekrandaki 'Mimari Analizi Baslat' ile proje klasoru secilir, yoksayilacak "
        "klasorler isaretlenir, analiz turu secilir (teknik altyapi, gelisim durumu, hata/eksik, olu kod), "
        "sonuc EKRANDA gosterilir ve dosyaya kaydedilebilir. "
        "2) Dosya Analizi: 'Dosya Analizi' sekmesinde tek dosya secilip analiz edilir, iyilestirilmis kod "
        "ve fark gorunumu sunulur. "
        "3) Model Degistirme VARDIR: ust bardaki 'Model Sec' butonu GGUF listesini acar; Ayrica Araclar "
        "menusunde 'GPU / CPU Degistir' butonu vardir. Secim sonrasi model otomatik yeniden yuklenir. "
        "4) Toplu Analiz, Model Karsilastirma, Oturum Yonetimi ve Donanim Taramasi Araclar menusundedir. "
        "5) Backendler: yerel GGUF (CPU veya GPU: NVIDIA'da CUDA, AMD/Intel'de Vulkan), Ollama, DeepSeek API. "
        "KURALLAR: Program hakkinda sorularda yukaridaki listeye sadik kal, ozellik uydurma, var olani "
        "inkar etme ('yoktur', 'bilgi veremem' deme). Emin olmadigin program detayinda kisa ve durust ol. "
        "Program disi genel sorulari kisa ve yardimsever yanitla. Turkce cevap ver."
    )

    def chat_with_ai(self, message: str, context: str = None) -> str:
        if not self.llm_client or not self.current_model:
            return "Agent baslatilmamis!"

        messages = [{"role": "system", "content": self.SYSTEM_IDENTITY}]
        if context:
            messages.append({"role": "system", "content": f"Analiz baglami: {context}"})

        for msg in self.chat_history[-10:]:
            messages.append(msg)

        messages.append({"role": "user", "content": message})

        response = self.llm_client.chat_completion(
            model=self.current_model.id,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )

        if response:
            self.chat_history.append({"role": "user", "content": message})
            self.chat_history.append({"role": "assistant", "content": response})

        return response if response else "Yanit alinamadi!"

    def ask_about_analysis(self, question: str) -> str:
        if not self.last_analysis:
            return "Once bir analiz yapmalisiniz!"
        context = f"Son analiz sonucu:\n{self.last_analysis[:2000]}"
        return self.chat_with_ai(question, context=context)

    def batch_analyze(self, folder_path: str = None) -> list:
        if not self.file_manager:
            return []
        if not folder_path:
            folder_path = self.file_manager.workspace_path
        results = []
        py_files = list(Path(folder_path).rglob("*.py"))
        for py_file in py_files:
            try:
                rel_path = str(py_file.relative_to(self.file_manager.workspace_path))
                content = self.file_manager.read_file(rel_path)
                if content:
                    results.append({"file": rel_path, "status": "ok", "lines": len(content.splitlines())})
            except:
                results.append({"file": str(py_file), "status": "error"})
        return results

    def get_session_summary(self) -> dict:
        return {
            "backend": self.backend,
            "model": self.current_model.name if self.current_model else "-",
            "total_chats": len(self.chat_history) // 2,
            "last_analysis_file": self.last_analysis_file or "-",
            "model_loaded": self.model_loaded,
        }


class DownloadModelWindow:
    """Ollama model indirme penceresi"""
    def __init__(self, parent, agent, on_complete=None):
        self.parent = parent
        self.agent = agent
        self.on_complete = on_complete
        self.window = tk.Toplevel(parent)
        self.window.title("Model Indir - Ollama")
        self.window.geometry("500x450")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.window.grab_set()
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="MODEL INDIR", font=('Arial', 14, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(pady=(0, 15))

        tk.Label(main, text="Ollama URL:", bg='#f5f5f5', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        self.url_var = tk.StringVar(value=config.get("ollama_url", "http://localhost:11434"))
        tk.Entry(main, textvariable=self.url_var, width=50).pack(fill=tk.X, pady=(0, 10))

        tk.Label(main, text="Model adi (ornek: deepseek-r1:8b):", bg='#f5f5f5', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        self.model_var = tk.StringVar(value=config.get("ollama_model", "deepseek-r1:8b"))
        tk.Entry(main, textvariable=self.model_var, width=50).pack(fill=tk.X, pady=(0, 10))

        tk.Label(main, text="Populer Modeller:", bg='#f5f5f5', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W, pady=(10, 5))

        popular = ["deepseek-r1:8b", "deepseek-r1:14b", "qwen2.5-coder:7b",
                   "qwen2.5:7b", "llama3.1:8b", "codellama:13b", "mistral:7b"]
        for m in popular:
            btn = tk.Button(main, text=m, command=lambda v=m: self.model_var.set(v),
                           bg='#ecf0f1', fg='#2c3e50', font=('Arial', 8), relief="flat",
                           anchor=tk.W, padx=5)
            btn.pack(fill=tk.X, pady=1)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(main, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(15, 5))

        self.status_label = tk.Label(main, text="Hazir", bg='#f5f5f5', fg='#7f8c8d',
                                     font=('Arial', 8))
        self.status_label.pack(anchor=tk.W)

        btn_frame = tk.Frame(main, bg='#f5f5f5')
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        tk.Button(btn_frame, text="INDIR", command=self.start_download,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(btn_frame, text="Iptal", command=self.window.destroy,
                  bg='#95a5a6', fg='white').pack(side=tk.RIGHT)

    def start_download(self):
        model = self.model_var.get().strip()
        url = self.url_var.get().strip()
        if not model:
            messagebox.showerror("Hata", "Model adi girin!")
            return
        self.status_label.config(text=f"{model} indiriliyor...", fg='#f39c12')
        self.progress_var.set(10)
        config.set("ollama_url", url)
        config.set("ollama_model", model)

        def download_thread():
            try:
                import requests, json
                r = requests.post(f"{url}/api/pull", json={"name": model}, stream=True, timeout=600)
                for line in r.iter_lines():
                    if line:
                        data = json.loads(line)
                        if "error" in data:
                            self.window.after(0, lambda: self.status_label.config(text=f"Hata: {data['error']}", fg='#e74c3c'))
                            return
                        if "completed" in data and "total" in data:
                            pct = (data["completed"] / data["total"]) * 100
                            self.window.after(0, lambda p=pct: self.progress_var.set(p))
                self.window.after(0, lambda: self.progress_var.set(100))
                self.window.after(0, lambda: self.status_label.config(text="Tamamlandi!", fg='#27ae60'))
                if self.on_complete:
                    self.window.after(200, self.on_complete)
            except Exception as e:
                self.window.after(0, lambda: self.status_label.config(text=f"Hata: {e}", fg='#e74c3c'))

        threading.Thread(target=download_thread, daemon=True).start()


class AnalysisFollowUpWindow:
    """Analiz sonrasi takip sorusu penceresi"""
    def __init__(self, parent, agent, analysis_text, file_path):
        self.parent = parent
        self.agent = agent
        self.analysis_text = analysis_text
        self.file_path = file_path
        self.window = tk.Toplevel(parent)
        self.window.title(f"Analiz Sohbeti - {file_path}")
        self.window.geometry("700x500")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5')
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tk.Label(main, text=f"Analiz: {self.file_path}", font=('Arial', 12, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(anchor=tk.W, pady=(0, 10))

        tk.Label(main, text="AI ile analiz hakkinda konusun, soru sorun:",
                 bg='#f5f5f5', fg='#7f8c8d', font=('Arial', 9)).pack(anchor=tk.W, pady=(0, 5))

        self.chat_display = scrolledtext.ScrolledText(main, wrap=tk.WORD, font=('Arial', 10),
                                                      bg='#ffffff', fg='#000000', state=tk.DISABLED, height=18)
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"[Analiz Sonucu]: {self.analysis_text[:500]}...\n")
        self.chat_display.insert(tk.END, "---\nSorunuzu yazin:\n")
        self.chat_display.config(state=tk.DISABLED)

        input_frame = tk.Frame(main, bg='#f5f5f5')
        input_frame.pack(fill=tk.X)

        self.question_input = tk.Entry(input_frame, font=('Arial', 10), bg='#ffffff')
        self.question_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.question_input.bind('<Return>', lambda e: self.ask_question())

        tk.Button(input_frame, text="Sor", command=self.ask_question,
                  bg='#3498db', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.RIGHT)

    def ask_question(self):
        q = self.question_input.get().strip()
        if not q:
            return
        self.question_input.delete(0, tk.END)
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"\n[Siz]: {q}\n")
        self.chat_display.config(state=tk.DISABLED)

        def ask_thread():
            response = self.agent.ask_about_analysis(q)
            def update():
                self.chat_display.config(state=tk.NORMAL)
                self.chat_display.insert(tk.END, f"[AI]: {response}\n---\n")
                self.chat_display.config(state=tk.DISABLED)
                self.chat_display.see(tk.END)
            self.window.after(0, update)

        threading.Thread(target=ask_thread, daemon=True).start()


class BatchAnalysisWindow:
    """Toplu analiz penceresi"""
    def __init__(self, parent, agent):
        self.parent = parent
        self.agent = agent
        self.window = tk.Toplevel(parent)
        self.window.title("Toplu Analiz")
        self.window.geometry("600x400")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="TOPLU PROJE ANALIZI", font=('Arial', 14, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(pady=(0, 15))

        tk.Label(main, text="Calisma alani: " + (self.agent.file_manager.workspace_path if self.agent.file_manager else "-"),
                 bg='#f5f5f5', fg='#7f8c8d', font=('Arial', 9)).pack(anchor=tk.W, pady=(0, 10))

        self.result_text = scrolledtext.ScrolledText(main, wrap=tk.WORD, font=('Consolas', 9),
                                                     bg='#ffffff', fg='#000000', state=tk.DISABLED)
        self.result_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        btn_frame = tk.Frame(main, bg='#f5f5f5')
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="Analiz Et", command=self.run_analysis,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(btn_frame, text="Kapat", command=self.window.destroy,
                  bg='#95a5a6', fg='white').pack(side=tk.RIGHT)

    def run_analysis(self):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "Taranan dosyalar:\n")
        results = self.agent.batch_analyze()
        for r in results:
            icon = "OK" if r["status"] == "ok" else "ERR"
            self.result_text.insert(tk.END, f"  [{icon}] {r['file']}")
            if r["status"] == "ok":
                self.result_text.insert(tk.END, f" ({r['lines']} satir)")
            self.result_text.insert(tk.END, "\n")
        self.result_text.insert(tk.END, f"\nToplam: {len(results)} dosya taranildi.\n")
        self.result_text.config(state=tk.DISABLED)


class CodeDiffWindow:
    """Kod farki goruntuleme penceresi — yan yana karsilastirma"""
    def __init__(self, parent, original_code, improved_code, file_path=""):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title(f"Kod Farki - {file_path}")
        self.window.geometry("1200x700")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.original_code = original_code
        self.improved_code = improved_code
        self.file_path = file_path
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5')
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        header = tk.Frame(main, bg='#f5f5f5')
        header.pack(fill=tk.X, pady=(0, 10))
        tk.Label(header, text=f"KOD FARKI: {self.file_path}",
                 font=('Arial', 12, 'bold'), bg='#f5f5f5', fg='#2c3e50').pack(side=tk.LEFT)

        stats = self._calc_stats()
        tk.Label(header, text=stats, font=('Arial', 9), bg='#f5f5f5', fg='#7f8c8d').pack(side=tk.RIGHT)

        paned = tk.PanedWindow(main, orient=tk.HORIZONTAL, sashrelief="raised", sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.LabelFrame(paned, text="ORIJINAL", bg='#ffffff', fg='#e74c3c',
                                   font=('Arial', 9, 'bold'))
        self.original_text = scrolledtext.ScrolledText(left_frame, wrap=tk.NONE, font=('Consolas', 10),
                                                       bg='#fff5f5', fg='#000000')
        self.original_text.pack(fill=tk.BOTH, expand=True)
        self.original_text.insert(tk.END, self.original_code)
        self.original_text.config(state=tk.DISABLED)

        right_frame = tk.LabelFrame(paned, text="IYILESTIRILMIS", bg='#ffffff', fg='#27ae60',
                                    font=('Arial', 9, 'bold'))
        self.improved_text = scrolledtext.ScrolledText(right_frame, wrap=tk.NONE, font=('Consolas', 10),
                                                       bg='#f5fff5', fg='#000000')
        self.improved_text.pack(fill=tk.BOTH, expand=True)
        self.improved_text.insert(tk.END, self.improved_code)
        self.improved_text.config(state=tk.DISABLED)

        paned.add(left_frame, stretch="always")
        paned.add(right_frame, stretch="always")

        self._highlight_diffs()

        btn_frame = tk.Frame(main, bg='#f5f5f5')
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        tk.Button(btn_frame, text="Orijinali Kopyala", command=lambda: self._copy(self.original_code),
                  bg='#e74c3c', fg='white', relief="flat").pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="Iyilestirilmis Kopyala", command=lambda: self._copy(self.improved_code),
                  bg='#27ae60', fg='white', relief="flat").pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="Kapat", command=self.window.destroy,
                  bg='#95a5a6', fg='white', relief="flat").pack(side=tk.RIGHT)

    def _calc_stats(self):
        orig_lines = set(self.original_code.splitlines())
        impr_lines = set(self.improved_code.splitlines())
        added = len(impr_lines - orig_lines)
        removed = len(orig_lines - impr_lines)
        return f"+{added} eklenen  -{removed} kaldirilan"

    def _highlight_diffs(self):
        orig_lines = self.original_code.splitlines()
        impr_lines = self.improved_code.splitlines()
        max_lines = max(len(orig_lines), len(impr_lines))
        for i in range(max_lines):
            orig_line = orig_lines[i] if i < len(orig_lines) else ""
            impr_line = impr_lines[i] if i < len(impr_lines) else ""
            if orig_line != impr_line:
                if i < len(orig_lines):
                    self.original_text.tag_add(f"diff_{i}", f"{i+1}.0", f"{i+1}.end")
                    self.original_text.tag_config(f"diff_{i}", background='#ffcccc')
                if i < len(impr_lines):
                    self.improved_text.tag_add(f"diff_{i}", f"{i+1}.0", f"{i+1}.end")
                    self.improved_text.tag_config(f"diff_{i}", background='#ccffcc')

    def _copy(self, text):
        self.parent.clipboard_clear()
        self.parent.clipboard_append(text)


class ModelCompareWindow:
    """Ayni dosyayi 2 farkli model ile karsilastir"""
    def __init__(self, parent, agent):
        self.parent = parent
        self.agent = agent
        self.window = tk.Toplevel(parent)
        self.window.title("Model Karsilastirma")
        self.window.geometry("900x600")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="MODEL KARSILASTIRMASI", font=('Arial', 14, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(pady=(0, 15))

        tk.Label(main, text="Dosya:", bg='#f5f5f5', fg='#2c3e50',
                 font=('Arial', 9, 'bold')).pack(anchor=tk.W)
        self.file_var = tk.StringVar()
        file_frame = tk.Frame(main, bg='#f5f5f5')
        file_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Entry(file_frame, textvariable=self.file_var, bg='#ffffff').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        tk.Button(file_frame, text="Sec", command=self._select_file, bg='#3498db', fg='white').pack(side=tk.RIGHT)

        info_label = tk.Label(main, text="Mevcut model ile analiz yapilir, sonra farkli bir model ile karsilastirilir.",
                              bg='#f5f5f5', fg='#7f8c8d', font=('Arial', 8))
        info_label.pack(anchor=tk.W, pady=(0, 10))

        paned = tk.PanedWindow(main, orient=tk.HORIZONTAL, sashrelief="raised", sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.LabelFrame(paned, text="Model 1 (Mevcut)", bg='#ffffff', fg='#3498db',
                                   font=('Arial', 9, 'bold'))
        self.result1_text = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, font=('Consolas', 9),
                                                      bg='#f0f8ff', fg='#000000')
        self.result1_text.pack(fill=tk.BOTH, expand=True)

        right_frame = tk.LabelFrame(paned, text="Model 2 (Belirtilecek)", bg='#ffffff', fg='#9b59b6',
                                    font=('Arial', 9, 'bold'))
        self.result2_text = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=('Consolas', 9),
                                                      bg='#f5f0ff', fg='#000000')
        self.result2_text.pack(fill=tk.BOTH, expand=True)

        paned.add(left_frame, stretch="always")
        paned.add(right_frame, stretch="always")

        btn_frame = tk.Frame(main, bg='#f5f5f5')
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        tk.Button(btn_frame, text="Karsilastir", command=self._compare,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(btn_frame, text="Kapat", command=self.window.destroy,
                  bg='#95a5a6', fg='white').pack(side=tk.RIGHT)

    def _select_file(self):
        path = filedialog.askopenfilename(title="Dosya Sec",
                                          filetypes=(("Python", "*.py"), ("Text", "*.txt"), ("All", "*.*")))
        if path:
            self.file_var.set(path)

    def _compare(self):
        file_path = self.file_var.get()
        if not file_path or not Path(file_path).exists():
            messagebox.showerror("Hata", "Gecerli bir dosya secin!")
            return

        self.result1_text.delete(1.0, tk.END)
        self.result2_text.delete(1.0, tk.END)
        self.result1_text.insert(tk.END, "Analiz yapiliyor...\n")
        self.result2_text.insert(tk.END, "Analiz yapiliyor...\n")

        def compare_thread():
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                model1 = self.agent.current_model
                prompt = f"Kodu analiz et ve kisa ozet ver:\n\n{content[:3000]}"

                result1 = self.agent.llm_client.chat_completion(
                    model=model1.id, messages=[{"role": "user", "content": prompt}],
                    temperature=0.3, max_tokens=2000)

                def update1():
                    self.result1_text.delete(1.0, tk.END)
                    self.result1_text.insert(tk.END, f"Model: {model1.name}\n\n{result1 or 'Hata'}")
                self.window.after(0, update1)

            except Exception as e:
                def err1():
                    self.result1_text.delete(1.0, tk.END)
                    self.result1_text.insert(tk.END, f"Hata: {e}")
                self.window.after(0, err1)

        threading.Thread(target=compare_thread, daemon=True).start()


class SessionManagerWindow:
    """Gelismis session/yonetim penceresi"""
    def __init__(self, parent, agent):
        self.parent = parent
        self.agent = agent
        self.window = tk.Toplevel(parent)
        self.window.title("Oturum Yonetimi")
        self.window.geometry("600x450")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.setup_ui()

    def setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=20, pady=20)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="OTURUM YONETIMI", font=('Arial', 14, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(pady=(0, 15))

        summary = self.agent.get_session_summary()
        info_frame = tk.LabelFrame(main, text="Ozet Bilgiler", bg='#ffffff', fg='#2c3e50',
                                   font=('Arial', 10, 'bold'))
        info_frame.pack(fill=tk.X, pady=(0, 10))

        for key, val in summary.items():
            row = tk.Frame(info_frame, bg='#ffffff')
            row.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(row, text=f"{key}:", bg='#ffffff', fg='#7f8c8d',
                     font=('Arial', 9, 'bold'), width=20, anchor=tk.W).pack(side=tk.LEFT)
            tk.Label(row, text=str(val), bg='#ffffff', fg='#2c3e50',
                     font=('Arial', 9)).pack(side=tk.LEFT)

        chat_frame = tk.LabelFrame(main, text="Sohbet Gecmisi", bg='#ffffff', fg='#2c3e50',
                                   font=('Arial', 10, 'bold'))
        chat_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.chat_list = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, font=('Consolas', 9),
                                                   bg='#f8f9fa', fg='#000000', state=tk.DISABLED)
        self.chat_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        if self.agent.chat_history:
            self.chat_list.config(state=tk.NORMAL)
            for msg in self.agent.chat_history:
                role = "Siz" if msg["role"] == "user" else "AI"
                self.chat_list.insert(tk.END, f"[{role}]: {msg['content'][:200]}\n---\n")
            self.chat_list.config(state=tk.DISABLED)

        btn_frame = tk.Frame(main, bg='#f5f5f5')
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        tk.Button(btn_frame, text="Sohbeti Disa Aktar", command=self._export_chat,
                  bg='#3498db', fg='white').pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="Sohbeti Temizle", command=self._clear_chat,
                  bg='#e74c3c', fg='white').pack(side=tk.LEFT)
        tk.Button(btn_frame, text="Kapat", command=self.window.destroy,
                  bg='#95a5a6', fg='white').pack(side=tk.RIGHT)

    def _export_chat(self):
        if not self.agent.chat_history:
            messagebox.showwarning("Uyari", "Disa aktarilacak sohbet yok!")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text", "*.txt")],
                                            initialfile="sohbet_gecmisi.txt")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                for msg in self.agent.chat_history:
                    role = "SIZ" if msg["role"] == "user" else "AI"
                    f.write(f"[{role}]: {msg['content']}\n\n")
            messagebox.showinfo("Basarili", f"Sohbet disa aktarildi: {path}")

    def _clear_chat(self):
        if messagebox.askyesno("Onay", "Tum sohbet gecmisini temizlemek istediginize emin misiniz?"):
            self.agent.chat_history = []
            self.chat_list.config(state=tk.NORMAL)
            self.chat_list.delete(1.0, tk.END)
            self.chat_list.config(state=tk.DISABLED)
            messagebox.showinfo("Basarili", "Sohbet temizlendi!")

def pre_startup_compute_choice(root) -> None:
    """GUI'den once her acilista CPU/GPU sor (NVIDIA + motor varsa).

    Secim ekrani ANA pencerenin ta kendisidir (gizli root + Toplevel yok):
    boylece pencere gorunmeme/odaklanma sorunu olmaz. X ile kapatilirsa
    program temizce cikar. Hizli yol (nvidia-smi, <1 sn);
    AMD/Vulkan secimi Araclar menusundedir.
    """
    import os as _os
    if _os.environ.get("OGMA_SKIP_PRECHOICE"):
        return
    try:
        if config.get("backend", "deepseek") != "llamacpp":
            return
    except Exception:
        return
    try:
        import subprocess as _sp
        out = _sp.run(["nvidia-smi", "--query-gpu=name,memory.total",
                       "--format=csv,noheader,nounits"],
                      capture_output=True, text=True, timeout=15)
        lines = (out.stdout or "").strip().splitlines()
        if out.returncode != 0 or not lines:
            return
        parts = [p.strip() for p in lines[0].split(",")]
        from core.local_client import LlamaServerClient
        if not LlamaServerClient.find_server_exe("cuda"):
            return
        try:
            gb = int(float(parts[1])) // 1024
        except Exception:
            gb = 0
        name = f"{parts[0]} ({gb} GB VRAM)" if gb else parts[0]
    except Exception:
        return

    root.title("Ogma - Hesaplama Modu Sec")
    root.geometry("520x440")
    root.configure(bg='#f5f5f5')
    choice = tk.StringVar(value="")

    def _pick(mode: str):
        try:
            config.set("compute_mode", mode)
            if mode == "gpu" and not int(config.get("llamacpp_n_gpu_layers", 0)):
                config.set("llamacpp_n_gpu_layers", 35)
        except Exception:
            pass
        choice.set(mode)

    def _on_x():
        choice.set("__exit__")

    frame = tk.Frame(root, bg='#f5f5f5', padx=25, pady=25)
    frame.pack(fill=tk.BOTH, expand=True)
    tk.Label(frame, text="HESAPLAMA MODU", font=('Arial', 14, 'bold'),
             bg='#f5f5f5', fg='#2c3e50').pack(pady=(0, 5))
    tk.Label(frame, text=f"Tespit edilen kart: {name}",
             bg='#f5f5f5', fg='#7f8c8d', font=('Arial', 10, 'bold'),
             wraplength=460, justify=tk.CENTER).pack(pady=(0, 15))
    tk.Button(frame, text="GPU ILE DEVAM ET (CUDA)\n(~60 token/sn, model ~4 snde yuklenir)",
              command=lambda: _pick("gpu"),
              bg='#27ae60', fg='white', font=('Arial', 11, 'bold'),
              relief="flat", padx=10, pady=12).pack(fill=tk.X, pady=(0, 10))
    tk.Button(frame, text="CPU-ONLY ILE DEVAM ET\n(~15 token/sn, her PC'de calisir)",
              command=lambda: _pick("cpu"),
              bg='#2980b9', fg='white', font=('Arial', 11, 'bold'),
              relief="flat", padx=10, pady=12).pack(fill=tk.X, pady=(0, 10))
    tk.Label(frame, text="Secim hatirlanir, Araclar menusunden degistirilebilir.",
             bg='#f5f5f5', fg='#95a5a6', font=('Arial', 8),
             wraplength=460, justify=tk.CENTER).pack()

    root.protocol("WM_DELETE_WINDOW", _on_x)
    root.wait_variable(choice)
    for w in root.winfo_children():
        try:
            w.destroy()
        except Exception:
            pass
    if choice.get() == "__exit__" or not choice.get():
        try:
            root.destroy()
        except Exception:
            pass
        raise SystemExit(0)

def main():
    from core.logger import install_crash_handler, log_exception
    install_crash_handler("gui")
    try:
        root = tk.Tk()
        pre_startup_compute_choice(root)
        app = OgmaGUI(root)
        root.mainloop()
    except SystemExit:
        raise
    except Exception as e:
        try:
            log_exception(type(e), e, e.__traceback__, "gui:main")
        except Exception:
            pass
        Console.error(f"Ogma baslatma hatasi: {e} (detay: storage/logs/errors.log)")

if __name__ == "__main__":
    main()