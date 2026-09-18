"""model_capability_gui.py — Model Capability Test penceresi (D4).

Model secildiginde 20 gorev testi calistirilir; olculmus Capability Profile
gosterilir. Skorlar kafadan degil, gercek LLM cagilarindan gelir.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import json
from pathlib import Path
from datetime import datetime

from config.settings import config

PROFILE_CACHE = "model_capability_profile.json"


class ModelCapabilityWindow:
    """Model Capability Test penceresi: 20 gorev testi + olculmus profil."""

    def __init__(self, parent, agent):
        self.parent = parent
        self.agent = agent
        self.window = tk.Toplevel(parent)
        self.window.title("Model Capability Test (D4)")
        self.window.geometry("700x650")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)

        self._setup_ui()
        self._load_cached_profile()

    def _setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="MODEL CAPABILITY TEST", font=('Arial', 13, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(anchor=tk.W, pady=(0, 2))
        tk.Label(main, text="20 standart gorev testi calistirilir; olculmus profil uretilir. "
                            "Kafadan puan verilmaz — gercek LLM cagilarindan gelir.",
                 font=('Arial', 8), bg='#f5f5f5', fg='#7f8c8d',
                 wraplength=600, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 10))

        # Model bilgisi
        info = tk.LabelFrame(main, text="MODEL", bg='#ffffff', fg='#2c3e50',
                             font=('Arial', 9, 'bold'), padx=10, pady=5)
        info.pack(fill=tk.X, pady=(0, 8))
        model_name = "-"
        if self.agent.current_model:
            model_name = self.agent.current_model.name
        elif self.agent.backend == "provider":
            model_name = config.get("active_provider", "") or "provider"
        tk.Label(info, text=f"Backend: {self.agent.backend}  |  Model: {model_name}",
                 bg='#ffffff', fg='#2c3e50', font=('Arial', 9)).pack(anchor=tk.W)

        # Buton
        btn_row = tk.Frame(main, bg='#f5f5f5')
        btn_row.pack(fill=tk.X, pady=(0, 8))
        self.test_btn = tk.Button(btn_row, text="CAPABILITY TEST BASLAT (20 test)",
                                  command=self._start_test,
                                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                                  relief="flat", padx=20, pady=6)
        self.test_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.save_btn = tk.Button(btn_row, text="Profili Kaydet",
                                  command=self._save_profile,
                                  bg='#16a085', fg='white', relief="flat",
                                  font=('Arial', 8), state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.status_label = tk.Label(btn_row, text="Durum: Hazir", bg='#f5f5f5',
                                     fg='#95a5a6', font=('Arial', 9, 'bold'))
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Progress
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(main, variable=self.progress_var,
                                            maximum=20)
        self.progress_bar.pack(fill=tk.X, pady=(0, 8))

        # Sonuclar
        result_frame = tk.LabelFrame(main, text="CAPABILITY PROFILE",
                                     bg='#ffffff', fg='#2c3e50',
                                     font=('Arial', 9, 'bold'), padx=5, pady=5)
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD,
                                                     font=('Consolas', 9),
                                                     bg='#1e2127', fg='#d4d4d4',
                                                     state=tk.DISABLED)
        self.result_text.pack(fill=tk.BOTH, expand=True)

    def _load_cached_profile(self):
        """Onceki profil varsa goster (tekrar test gerekmez)."""
        p = Path(__file__).resolve().parent.parent / "storage" / PROFILE_CACHE
        if p.exists():
            try:
                profile = json.loads(p.read_text(encoding="utf-8"))
                from core.model_capability import format_profile
                text = format_profile(profile)
                self._set_result(text + "\n\n(onceki test sonucu — yeniden test icin baslat)")
                self.save_btn.config(state=tk.NORMAL)
            except Exception:
                pass

    def _start_test(self):
        if not self.agent.llm_client:
            messagebox.showerror("Hata", "Once bir model yukleyin!")
            return

        self.test_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Durum: Test calisiyor...", fg='#f39c12')
        self.progress_var.set(0)
        self._set_result("Test basliyor...\n(20 test x ~10-30 sn = ~5-10 dk)")

        model_id = self.agent.current_model.id if self.agent.current_model else "local"

        def test_thread():
            try:
                from core.model_capability import run_capability_test, format_profile
                results = []

                def progress(cur, total, msg):
                    self.window.after(0, lambda: self.progress_var.set(cur + 1))
                    self.window.after(0, lambda: self.status_label.config(
                        text=f"Durum: {msg} ({cur+1}/{total})"))

                profile = run_capability_test(
                    self.agent.llm_client, model_id,
                    progress_callback=progress)

                text = format_profile(profile)
                self._profile = profile
                self.window.after(0, lambda: self._set_result(text))
                self.window.after(0, lambda: self.status_label.config(
                    text=f"Durum: Tamamlandi ({profile['overall_score']}%)",
                    fg='#27ae60'))
                self.window.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
            except Exception as e:
                self.window.after(0, lambda: self.status_label.config(
                    text=f"Hata: {e}", fg='#e74c3c'))
                self.window.after(0, lambda: messagebox.showerror("Hata", str(e)))

        threading.Thread(target=test_thread, daemon=True).start()

    def _save_profile(self):
        profile = getattr(self, "_profile", None)
        if not profile:
            return
        p = Path(__file__).resolve().parent.parent / "storage" / PROFILE_CACHE
        try:
            p.write_text(json.dumps(profile, indent=2, ensure_ascii=False),
                         encoding="utf-8")
            messagebox.showinfo("Kaydedildi", f"Profil kaydedildi:\n{p}")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")

    def _set_result(self, text: str):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(1.0, text)
        self.result_text.config(state=tk.DISABLED)
