"""Watcher GUI — canli dosya izleyici (E3): degisen dosyalari yakalar,
her degisen .py dosyasi icin statik hata + etki analizi raporlar.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from pathlib import Path
from datetime import datetime

from config.settings import config


class WatcherWindow:
    """Canli izleyici penceresi: degisiklik yakala + otomatik etki analizi."""

    def __init__(self, parent):
        self.parent = parent
        self.watcher = None
        self.window = tk.Toplevel(parent)
        self.window.title("Canli Izleyici (E3)")
        self.window.geometry("760x600")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_ui()

    def _setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="CANLI IZLEYICI", font=('Arial', 13, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(anchor=tk.W, pady=(0, 2))
        tk.Label(main, text="Dosya degisikliklerini izler; her degisen .py dosyasi icin "
                            "statik hata + etki analizi otomatik raporlanir.",
                 font=('Arial', 8), bg='#f5f5f5', fg='#7f8c8d',
                 wraplength=650, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 10))

        # Ayarlar
        cfg = tk.LabelFrame(main, text="AYARLAR", bg='#ffffff', fg='#2c3e50',
                            font=('Arial', 9, 'bold'), padx=10, pady=8)
        cfg.pack(fill=tk.X, pady=(0, 8))

        row1 = tk.Frame(cfg, bg='#ffffff')
        row1.pack(fill=tk.X)
        tk.Label(row1, text="Klasor:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 8, 'bold')).pack(side=tk.LEFT)
        self.folder_var = tk.StringVar(
            value=config.get("workspace_path", "") or "")
        tk.Entry(row1, textvariable=self.folder_var, bg='#ffffff').pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        tk.Button(row1, text="Gozat", command=self._browse,
                  bg='#3498db', fg='white', relief="flat",
                  font=('Arial', 8)).pack(side=tk.LEFT)

        row2 = tk.Frame(cfg, bg='#ffffff')
        row2.pack(fill=tk.X, pady=(6, 0))
        tk.Label(row2, text="Kontrol araligi (sn):", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 8, 'bold')).pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="10")
        tk.Entry(row2, textvariable=self.interval_var, width=5,
                 bg='#ffffff').pack(side=tk.LEFT, padx=(5, 0))

        # Butonlar
        btn_row = tk.Frame(main, bg='#f5f5f5')
        btn_row.pack(fill=tk.X, pady=(0, 8))
        self.start_btn = tk.Button(btn_row, text="IZLEMAYI BASLAT",
                                   command=self._start,
                                   bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                                   relief="flat", padx=20, pady=6)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.stop_btn = tk.Button(btn_row, text="DURDUR",
                                  command=self._stop,
                                  bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'),
                                  relief="flat", padx=20, pady=6,
                                  state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.status_label = tk.Label(btn_row, text="Durum: Durdu", bg='#f5f5f5',
                                     fg='#95a5a6', font=('Arial', 9, 'bold'))
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Sonuclar
        result_frame = tk.LabelFrame(main, text="DEGISIKLIK + ETKI RAPORU",
                                     bg='#ffffff', fg='#2c3e50',
                                     font=('Arial', 9, 'bold'), padx=5, pady=5)
        result_frame.pack(fill=tk.BOTH, expand=True)

        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD,
                                                     font=('Consolas', 9),
                                                     bg='#1e2127', fg='#d4d4d4',
                                                     state=tk.DISABLED)
        self.result_text.pack(fill=tk.BOTH, expand=True)

    def _browse(self):
        folder = filedialog.askdirectory(title="Izlenecek Klasor Sec")
        if folder:
            self.folder_var.set(folder)

    def _start(self):
        folder = self.folder_var.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("Hata", "Gecerli bir klasor secin!")
            return
        try:
            interval = max(3, int(self.interval_var.get()))
        except ValueError:
            interval = 10

        from core.watcher import FileWatcher
        self.watcher = FileWatcher(folder, interval=interval,
                                   callback=self._on_changes)
        self.watcher.start()

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text=f"Durum: Izleniyor (her {interval} sn)",
                                 fg='#27ae60')
        self._append(f"[{datetime.now().strftime('%H:%M:%S')}] Izleyici baslatildi: "
                     f"{folder} (her {interval} sn)")

    def _stop(self):
        if self.watcher:
            self.watcher.stop()
            self.watcher = None
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="Durum: Durdu", fg='#95a5a6')
        self._append(f"[{datetime.now().strftime('%H:%M:%S')}] Izleyici durduruldu.")

    def _on_close(self):
        self._stop()
        self.window.destroy()

    def _on_changes(self, diff: Dict):
        """Arka planda degisiklik algilandiginda cagrilir."""
        from core.araclar import impact_analysis_v2, format_impact_v2, collect_py_files
        from core.analysis_engine import AnalysisEngine

        folder = self.folder_var.get().strip()
        changed = diff["added"] + diff["modified"]
        deleted = diff["deleted"]

        lines = [f"\n{'='*60}",
                 f"[{datetime.now().strftime('%H:%M:%S')}] DEGISIKLIK ALGILANDI: "
                 f"+{len(diff['added'])} -{len(deleted)} ~{len(diff['modified'])}",
                 f"{'='*60}"]

        for f in diff["added"]:
            lines.append(f"  + EKLENDI: {f}")
        for f in deleted:
            lines.append(f"  - SILINDI: {f}")
        for f in diff["modified"]:
            lines.append(f"  ~ DEGISTI: {f}")
        lines.append("")

        # Degisen .py dosyalari icin statik hata + etki
        py_changed = [f for f in changed if f.endswith(".py")]
        py_files = collect_py_files(folder)

        for rel in py_changed[:5]:
            # statik hata
            try:
                from core.analysis_engine import AnalysisEngine
                bugs = AnalysisEngine._static_bugs(
                    (Path(folder) / rel).read_text(encoding="utf-8", errors="ignore"))
                if bugs:
                    lines.append(f"  HATA ({rel}):")
                    for b in bugs[:5]:
                        lines.append(f"    {b}")
                else:
                    lines.append(f"  HATA ({rel}): temiz")
            except Exception:
                pass

            # etki
            try:
                impact = impact_analysis_v2(folder, py_files, rel)
                if impact.get("found"):
                    risk = impact.get("risk", "LOW")
                    n = impact.get("total_affected_files", 0)
                    tests = impact.get("affected_tests", [])
                    lines.append(f"  ETKI ({rel}): RISK={risk}, "
                                 f"{n} dosya etkilenir, {len(tests)} test")
                    for d in impact.get("direct_dependents", [])[:5]:
                        lines.append(f"    <- {d}")
            except Exception:
                pass
            lines.append("")

        text = "\n".join(lines)
        self.window.after(0, lambda: self._append(text))

    def _append(self, text: str):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, text + "\n")
        self.result_text.see(tk.END)
        self.result_text.config(state=tk.DISABLED)
