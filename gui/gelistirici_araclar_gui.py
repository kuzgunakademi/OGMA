"""Gelistirici Araclari penceresi — tek tek calistirilabilir yardimci araclar.

Araclar mimari taramadan bagimsizdir: hedef klasor verilir, arac tek tek
calisir, sonuc metin penceresinde gosterilir ve dosyaya kaydedilebilir.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
from pathlib import Path

from config.settings import config

TOOLS = [
    ("Sembol Ara", "Sinif/fonksiyon/metod arar (dosya:satir). Once var mi bak, "
                   "duplicate yapma."),
    ("Dosya Anahati", "Dosyanin sinif/fonksiyon haritasi (satir araliklariyla) — "
                      "kodu okumadan once haritaya bak."),
    ("Etki Analizi", "Bu dosyayi kim import ediyor? Cok seviyeli etki zinciri "
                     "(dogrudan + dolayli) + etkilenen testler + risk seviyesi. "
                     "Degisikligin domino etkisini gosterir (birkac saniye)."),
]


class GelistiriciAraclariWindow:
    """Gelistirici araclari penceresi — 3 arac, tek tek calisir."""

    def __init__(self, parent):
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("Gelistirici Araclari")
        self.window.geometry("760x640")
        self.window.configure(bg='#f5f5f5')
        self.window.transient(parent)

        self._setup_ui()

    def _setup_ui(self):
        main = tk.Frame(self.window, bg='#f5f5f5', padx=15, pady=15)
        main.pack(fill=tk.BOTH, expand=True)

        tk.Label(main, text="GELISTIRICI ARACLARI", font=('Arial', 13, 'bold'),
                 bg='#f5f5f5', fg='#2c3e50').pack(anchor=tk.W, pady=(0, 2))
        tk.Label(main, text="Araclar mimari taramadan bagimsizdir; hedef klasor "
                            "Mimari sekmesinden gelir.", font=('Arial', 8),
                 bg='#f5f5f5', fg='#7f8c8d').pack(anchor=tk.W, pady=(0, 10))

        # Arac secimi
        tool_frame = tk.LabelFrame(main, text="ARAC SEC", bg='#ffffff', fg='#2c3e50',
                                   font=('Arial', 9, 'bold'), padx=10, pady=8)
        tool_frame.pack(fill=tk.X, pady=(0, 8))

        self.tool_var = tk.StringVar(value=TOOLS[0][0])
        self.tool_desc = tk.Label(tool_frame, text=TOOLS[0][1], font=('Arial', 8),
                                  bg='#ffffff', fg='#7f8c8d', wraplength=650,
                                  justify=tk.LEFT)
        self.tool_desc.pack(fill=tk.X, pady=(0, 6))
        for name, desc in TOOLS:
            tk.Radiobutton(tool_frame, text=name, variable=self.tool_var, value=name,
                           command=self._on_tool_change, bg='#ffffff', fg='#000000',
                           selectcolor='#3498db', font=('Arial', 9)).pack(side=tk.LEFT,
                                                                          padx=(0, 15))

        # Hedef girdisi
        target_frame = tk.LabelFrame(main, text="HEDEF", bg='#ffffff', fg='#2c3e50',
                                     font=('Arial', 9, 'bold'), padx=10, pady=8)
        target_frame.pack(fill=tk.X, pady=(0, 8))

        row = tk.Frame(target_frame, bg='#ffffff')
        row.pack(fill=tk.X)
        tk.Label(row, text="Klasor:", bg='#ffffff', fg='#2c3e50',
                 font=('Arial', 8, 'bold')).pack(side=tk.LEFT)
        self.folder_var = tk.StringVar(value=config.get("workspace_path", "") or "")
        tk.Entry(row, textvariable=self.folder_var, bg='#ffffff').pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        tk.Button(row, text="Gozat", command=self._browse_folder,
                  bg='#3498db', fg='white', relief="flat",
                  font=('Arial', 8)).pack(side=tk.LEFT)

        self.param_row = tk.Frame(target_frame, bg='#ffffff')
        self.param_row.pack(fill=tk.X, pady=(6, 0))
        self.param_label = tk.Label(self.param_row, text="Sembol:", bg='#ffffff',
                                    fg='#2c3e50', font=('Arial', 8, 'bold'))
        self.param_label.pack(side=tk.LEFT)
        self.param_var = tk.StringVar()
        self.param_entry = tk.Entry(self.param_row, textvariable=self.param_var,
                                    bg='#ffffff')
        self.param_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Calistir
        tk.Button(main, text="CALISTIR", command=self._run_tool,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  relief="flat", padx=20, pady=6).pack(fill=tk.X, pady=(0, 8))

        # Sonuclar
        result_frame = tk.LabelFrame(main, text="SONUC", bg='#ffffff', fg='#2c3e50',
                                     font=('Arial', 9, 'bold'), padx=5, pady=5)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.result_text = scrolledtext.ScrolledText(result_frame, wrap=tk.WORD,
                                                     font=('Consolas', 9),
                                                     bg='#1e2127', fg='#d4d4d4',
                                                     state=tk.DISABLED)
        self.result_text.pack(fill=tk.BOTH, expand=True)

        btn_row = tk.Frame(main, bg='#f5f5f5')
        btn_row.pack(fill=tk.X)
        tk.Button(btn_row, text="Sonucu Kaydet", command=self._save_result,
                  bg='#16a085', fg='white', relief="flat",
                  font=('Arial', 8)).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_row, text="Kapat", command=self.window.destroy,
                  bg='#95a5a6', fg='white', relief="flat",
                  font=('Arial', 8)).pack(side=tk.RIGHT)

    def _on_tool_change(self):
        name = self.tool_var.get()
        for t_name, t_desc in TOOLS:
            if t_name == name:
                self.tool_desc.config(text=t_desc)
                break
        if name == "Sembol Ara":
            self.param_label.config(text="Sembol:")
        else:
            self.param_label.config(text="Dosya yolu (klasore goreli):")

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Hedef Klasor Sec")
        if folder:
            self.folder_var.set(folder)

    def _resolve_target_file(self) -> str:
        """Parametre olarak verilen dosyayi klasore gore coz."""
        raw = self.param_var.get().strip().replace("\\", "/")
        if not raw:
            return ""
        p = Path(raw)
        if p.is_absolute() and p.exists():
            return str(p)
        folder = self.folder_var.get().strip()
        candidate = Path(folder) / raw
        if candidate.exists():
            return raw  # goreceli birak (araclar goreceli yolla calisir)
        return raw

    def _run_tool(self):
        folder = self.folder_var.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showerror("Hata", "Gecerli bir hedef klasor secin!")
            return
        name = self.tool_var.get()
        param = self.param_var.get().strip()

        if name == "Sembol Ara" and not param:
            messagebox.showerror("Hata", "Sembol adi girin!")
            return
        if name in ("Dosya Anahati", "Etki Analizi") and not param:
            messagebox.showerror("Hata", "Dosya yolu girin!")
            return

        self._set_result(f"Calisiyor: {name}...")
        threading.Thread(target=self._run_thread, args=(name, folder, param),
                         daemon=True).start()

    def _run_thread(self, name: str, folder: str, param: str):
        try:
            from core import araclar
            if name == "Sembol Ara":
                py_files = araclar.collect_py_files(folder)
                result = araclar.find_symbol(folder, py_files, param)
                text = araclar.format_find(result)
            elif name == "Dosya Anahati":
                target = self._resolve_target_file_thread(folder, param)
                result = araclar.file_outline(folder, target)
                text = araclar.format_outline(result)
            else:
                py_files = araclar.collect_py_files(folder)
                result = araclar.impact_analysis_v2(folder, py_files, param)
                text = araclar.format_impact_v2(result)
            self._last_text = text
            self.window.after(0, lambda: self._set_result(text))
        except Exception as e:
            err = f"Hata: {e}"
            self._last_text = err
            self.window.after(0, lambda: self._set_result(err))

    def _resolve_target_file_thread(self, folder: str, param: str) -> str:
        raw = param.replace("\\", "/").strip()
        if Path(raw).is_absolute() and Path(raw).exists():
            return str(Path(raw))
        candidate = Path(folder) / raw
        if candidate.exists():
            return raw
        # dosya adina gore ara
        from core.araclar import collect_py_files
        for rel in collect_py_files(folder):
            if rel.endswith("/" + raw) or rel == raw:
                return rel
        return raw

    def _set_result(self, text: str):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(1.0, text)
        self.result_text.config(state=tk.DISABLED)

    def _save_result(self):
        text = getattr(self, "_last_text", "")
        if not text:
            messagebox.showwarning("Uyari", "Kaydedilecek sonuc yok!")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="arac_sonucu.txt")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                messagebox.showinfo("Kaydedildi", f"Sonuc kaydedildi:\n{path}")
            except Exception as e:
                messagebox.showerror("Hata", f"Kaydedilemedi: {e}")
