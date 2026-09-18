import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
from pathlib import Path
from datetime import datetime

from core.hybrid_analyzer import HybridAnalysisEngine, AnalysisMode
from core.analysis_engine import AnalysisType, ANALYSIS_LABELS
from core.architecture_scanner import ArchitectureScanner, ArchitectureMap
from core.ignore_manager import IgnoreManager


class IgnoreListWindow:
    """Ignore listesi seçim penceresi."""

    def __init__(self, parent, scan_root: str, on_start):
        self.parent = parent
        self.scan_root = Path(scan_root)
        self.on_start = on_start
        self.check_vars = {}

        self.window = tk.Toplevel(parent)
        self.window.title("Analiz Öncesi Ayarlar")
        self.window.geometry("500x550")
        self.window.configure(bg='#2c3e50')
        self.window.transient(parent)
        self.window.grab_set()

        self._center(parent)
        self._setup_ui()

    def _center(self, parent):
        self.window.update_idletasks()
        w, h = 500, 550
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.window.geometry(f"+{x}+{y}")

    def _setup_ui(self):
        # Başlık
        tk.Label(self.window, text="🔍 Tarama Ayarları", font=('Arial', 14, 'bold'),
                 bg='#2c3e50', fg='white').pack(pady=(10, 5))
        tk.Label(self.window, text=f"Klasör: {self.scan_root.name}", font=('Arial', 10),
                 bg='#2c3e50', fg='#ecf0f1').pack()

        # Sistem klasörleri (otomatik algılanan)
        tk.Label(self.window, text="⚠️ Atlaması gereken klasörler (kutucukları işaretleyin):",
                 font=('Arial', 9, 'bold'), bg='#2c3e50', fg='#f39c12').pack(anchor='w', padx=15, pady=(10, 3))

        ignore_mgr = IgnoreManager()
        system_folders = ignore_mgr.get_system_folders(self.scan_root)

        # Scrollable frame
        canvas = tk.Canvas(self.window, bg='#34495e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg='#34495e')

        self.scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(15, 0), pady=5)
        scrollbar.pack(side="right", fill="y", padx=(0, 15), pady=5)

        # Sistem klasörleri
        for name, reason in sorted(system_folders.items()):
            var = tk.BooleanVar(value=True)
            self.check_vars[name] = var
            frame = tk.Frame(self.scroll_frame, bg='#34495e')
            frame.pack(fill=tk.X, padx=5, pady=1)
            tk.Checkbutton(frame, text=f"⚠️ {name}", variable=var,
                          bg='#34495e', fg='#e74c3c', selectcolor='#2c3e50',
                          activebackground='#34495e', font=('Arial', 9)).pack(side=tk.LEFT)
            tk.Label(frame, text=f"({reason})", bg='#34495e', fg='#95a5a6',
                     font=('Arial', 8)).pack(side=tk.LEFT, padx=(5, 0))

        # Tüm klasörleri listele
        has_custom = False
        if self.scan_root.exists():
            for item in sorted(self.scan_root.iterdir()):
                if item.is_dir() and not item.name.startswith(".") and item.name not in system_folders:
                    has_custom = True
                    var = tk.BooleanVar(value=item.name in ignore_mgr.get_custom_ignore_list())
                    self.check_vars[item.name] = var
                    frame = tk.Frame(self.scroll_frame, bg='#34495e')
                    frame.pack(fill=tk.X, padx=5, pady=1)
                    tk.Checkbutton(frame, text=f"📁 {item.name}", variable=var,
                                  bg='#34495e', fg='#ecf0f1', selectcolor='#2c3e50',
                                  activebackground='#34495e', font=('Arial', 9)).pack(side=tk.LEFT)

        # Sadece dosya iceren klasorlerde bilgi mesaji (kullanicinin bildirdigi karisiklik)
        if not has_custom and not system_folders:
            tk.Label(self.scroll_frame,
                     text="Bu klasorde alt klasor yok (sadece dosyalar).\n"
                          "Direkt 'Taramaya Basla' ile devam edebilirsiniz.",
                     bg='#34495e', fg='#f39c12', font=('Arial', 9),
                     wraplength=400, justify=tk.LEFT).pack(anchor=tk.W, padx=5, pady=10)

        # Butonlar
        btn_frame = tk.Frame(self.window, bg='#2c3e50')
        btn_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Button(btn_frame, text="Hepsini Seç", command=self._select_all,
                  bg='#3498db', fg='white', relief="flat", padx=10).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="Hepsini Kaldır", command=self._deselect_all,
                  bg='#95a5a6', fg='white', relief="flat", padx=10).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="🚀 Taramaya Başla", command=self._start_scan,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  relief="flat", padx=20).pack(side=tk.RIGHT)

    def _select_all(self):
        for var in self.check_vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self.check_vars.values():
            var.set(False)

    def _start_scan(self):
        ignore_list = [name for name, var in self.check_vars.items() if var.get()]
        # Kaydet
        IgnoreManager().save_ignore_list(ignore_list)
        self.window.destroy()
        self.on_start(ignore_list)


class AnalysisTypeWindow:
    """Analiz türü seçim penceresi."""

    def __init__(self, parent, arch_map: ArchitectureMap, on_analyze):
        self.parent = parent
        self.arch_map = arch_map
        self.on_analyze = on_analyze
        self.check_vars = {}

        self.window = tk.Toplevel(parent)
        self.window.title("Analiz Türü Seçin")
        self.window.geometry("450x480")
        self.window.configure(bg='#2c3e50')
        self.window.transient(parent)
        self.window.grab_set()

        self._center(parent)
        self._setup_ui()

    def _center(self, parent):
        self.window.update_idletasks()
        w, h = 450, 480
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.window.geometry(f"+{x}+{y}")

    def _setup_ui(self):
        # Başlık
        tk.Label(self.window, text="📊 Analiz Türü Seçin", font=('Arial', 14, 'bold'),
                 bg='#2c3e50', fg='white').pack(pady=(10, 5))

        # Özet
        summary = f"{self.arch_map.total_files} dosya | {self.arch_map.total_folders} klasör | {self.arch_map.total_lines} satır"
        tk.Label(self.window, text=summary, font=('Arial', 10),
                 bg='#2c3e50', fg='#ecf0f1').pack()

        # Analiz türleri
        analysis_options = [
            (AnalysisType.ARCHITECTURE_MAP, "Mimari Harita", "AI gerektirmez - anlık", "#27ae60"),
            (AnalysisType.PROJECT_PURPOSE, "Proje Amacı", "Ne yaptığını açıkla", "#3498db"),
            (AnalysisType.TECH_INFRASTRUCTURE, "Teknik Altyapı", "Kütüphaneler, framework'ler", "#9b59b6"),
            (AnalysisType.DEV_STATUS, "Gelişim Durumu", "Aktif / Geliştirme / Terk", "#f39c12"),
            (AnalysisType.ERRORS_MISSING, "Hatalar & Eksikler", "Potansiyel sorunlar", "#e74c3c"),
            (AnalysisType.DEAD_CODE, "Ölü Kodlar", "Proje-geneli cagri grafi + import", "#e67e22"),
            (AnalysisType.DEPENDENCIES, "Bağımlılıklar & Döngüler", "Import grafi + dairesel import tespiti", "#1abc9c"),
            (AnalysisType.QUALITY, "Kalite & Güvenlik", "Skor + CC + eval/shell/secret taraması", "#d35400"),
        ]

        for analysis_type, label, desc, color in analysis_options:
            # VARSAYILAN: HEPSI secili (full analiz); kullanici istedigini kaldirir
            var = tk.BooleanVar(value=True)
            self.check_vars[analysis_type] = var

            frame = tk.Frame(self.window, bg='#34495e', relief="flat")
            frame.pack(fill=tk.X, padx=15, pady=3)

            cb = tk.Checkbutton(frame, text=f"  {label}", variable=var,
                               bg='#34495e', fg='white', selectcolor='#2c3e50',
                               activebackground='#34495e', font=('Arial', 10, 'bold'))
            cb.pack(side=tk.LEFT)

            tk.Label(frame, text=desc, bg='#34495e', fg='#95a5a6',
                     font=('Arial', 8)).pack(side=tk.RIGHT, padx=10)

        # Süre tahmini
        self.time_label = tk.Label(self.window, text="Tahmini süre: Anlık", font=('Arial', 9),
                                    bg='#2c3e50', fg='#f39c12')
        self.time_label.pack(pady=(10, 3))

        # Seçim değiştikçe süre güncelle
        for var in self.check_vars.values():
            var.trace_add('write', self._update_time)

        # Butonlar
        btn_frame = tk.Frame(self.window, bg='#2c3e50')
        btn_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Button(btn_frame, text="Hepsini Seç", command=self._select_all,
                  bg='#3498db', fg='white', relief="flat", padx=10).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="Hepsini Kaldır", command=self._deselect_all,
                  bg='#95a5a6', fg='white', relief="flat", padx=10).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="🔍 Analiz Et", command=self._start_analysis,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  relief="flat", padx=20).pack(side=tk.RIGHT)

    def _select_all(self):
        for var in self.check_vars.values():
            var.set(True)

    def _deselect_all(self):
        for var in self.check_vars.values():
            var.set(False)

    def _update_time(self, *args):
        selected = [k for k, v in self.check_vars.items() if v.get()]
        ai_calls = sum(1 for t in selected if t != AnalysisType.ARCHITECTURE_MAP)
        if ai_calls == 0:
            self.time_label.config(text="Tahmini süre: Anlık")
        elif ai_calls <= 2:
            self.time_label.config(text=f"Tahmini süre: ~{ai_calls * 30}-{ai_calls * 60} saniye")
        else:
            self.time_label.config(text=f"Tahmini süre: ~{ai_calls * 30}-{ai_calls * 60} saniye ({ai_calls} AI çağrısı)")

    def _start_analysis(self):
        selected = [k for k, v in self.check_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen en az bir analiz türü seçin!")
            return
        self.window.destroy()
        self.on_analyze(selected)


class ArchitectureResultsWindow:
    """Analiz sonuçları görüntüleme penceresi."""

    def __init__(self, parent, arch_map: ArchitectureMap, results: dict):
        self.parent = parent
        self.arch_map = arch_map
        self.results = results

        self.window = tk.Toplevel(parent)
        self.window.title(f"Mimari Analiz - {arch_map.root_name}")
        self.window.geometry("900x700")
        self.window.configure(bg='#ecf0f1')
        self.window.transient(parent)

        self._center(parent)
        self._setup_ui()

        # Pencereyi öne getir
        self.window.after(100, lambda: self.window.lift())
        self.window.after(200, lambda: self.window.focus_force())

    def _center(self, parent):
        self.window.update_idletasks()
        w, h = 900, 700
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.window.geometry(f"+{x}+{y}")

    def _setup_ui(self):
        # Başlık
        header = tk.Frame(self.window, bg='#2c3e50', height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text=f"📊 Mimari Analiz: {self.arch_map.root_name}",
                 font=('Arial', 13, 'bold'), bg='#2c3e50', fg='white').pack(side=tk.LEFT, padx=10, pady=10)
        tk.Label(header, text=f"Tarih: {self.arch_map.scan_timestamp[:10]}",
                 font=('Arial', 9), bg='#2c3e50', fg='#95a5a6').pack(side=tk.RIGHT, padx=10)

        # Notebook (sekmeler)
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        # Her analiz türü için sekme
        for analysis_type, result in self.results.items():
            label = ANALYSIS_LABELS.get(analysis_type, str(analysis_type))
            tab = tk.Frame(self.notebook, bg='#ecf0f1')
            self.notebook.add(tab, text=f" {label} ")

            text_widget = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=('Consolas', 10),
                                                     bg='white', fg='#2c3e50', relief="flat")
            text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            text_widget.insert(1.0, result.content)
            text_widget.config(state=tk.DISABLED)

        # Alt butonlar
        btn_frame = tk.Frame(self.window, bg='#ecf0f1')
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Button(btn_frame, text="📋 Panoya Kopyala", command=self._copy_all,
                  bg='#3498db', fg='white', relief="flat", padx=10).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="💾 Dosyaya Kaydet", command=self._save_to_file,
                  bg='#27ae60', fg='white', relief="flat", padx=10).pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="Kapat", command=self.window.destroy,
                  bg='#95a5a6', fg='white', relief="flat", padx=10).pack(side=tk.RIGHT)

    def _copy_all(self):
        """Tüm sonuçları panoya kopyala."""
        all_text = []
        for analysis_type, result in self.results.items():
            label = ANALYSIS_LABELS.get(analysis_type, str(analysis_type))
            all_text.append(f"=== {label} ===\n{result.content}\n")
        self.window.clipboard_clear()
        self.window.clipboard_append("\n".join(all_text))
        messagebox.showinfo("Kopyalandı", "Tüm sonuçlar panoya kopyalandı!")

    def _save_to_file(self):
        """Sonuçları dosyaya kaydet."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"mimari_analiz_{self.arch_map.root_name}_{datetime.now().strftime('%Y%m%d')}.txt"
        )
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"Mimari Analiz Raporu\n")
                f.write(f"Proje: {self.arch_map.root_name}\n")
                f.write(f"Tarih: {self.arch_map.scan_timestamp}\n")
                f.write(f"{'='*60}\n\n")
                for analysis_type, result in self.results.items():
                    label = ANALYSIS_LABELS.get(analysis_type, str(analysis_type))
                    f.write(f"=== {label} ===\n")
                    f.write(result.content)
                    f.write(f"\n\n{'='*60}\n\n")
            messagebox.showinfo("Kaydedildi", f"Rapor kaydedildi:\n{file_path}")


class ArchitectureAnalyzerLauncher:
    """Mimari analizcyi başlatan ana sınıf."""

    def __init__(self, parent, agent):
        self.parent = parent
        self.agent = agent
        self.arch_map = None
        self.scan_root = None

        # CIFT SECIM BITTI: workspace tek kaynaktan (Mimari sekmesinden)
        # alinir; yeniden klasor dialogu acilmaz.
        from config.settings import config as _cfg
        scan_root = _cfg.get("workspace_path", "")

        if not scan_root or not Path(scan_root).is_dir():
            messagebox.showinfo(
                "Bilgi",
                "Once Proje Klasoru Secin!\n\n"
                "Soldaki MIMARI sekmesinden 'Proje Klasoru Sec' ile klasor secin.")
            return

        self.scan_root = scan_root
        _cfg.set("architecture_last_scan_root", scan_root)

        # Ignore list penceresi
        IgnoreListWindow(parent, scan_root, self._on_ignore_list_ready)

    def _on_ignore_list_ready(self, ignore_list):
        """Ignore listesi hazır, taramayı başlat."""
        if not self.scan_root:
            messagebox.showerror("Hata", "Tarama klasörü bulunamadı!")
            return

        # Loading ile tarama başlat
        self._start_scanning(self.scan_root, ignore_list)

    def _start_scanning(self, scan_root, ignore_list):
        """Taramayı arka planda başlat (Faz 1/3)."""
        scanner = ArchitectureScanner(scan_root, ignore_list)

        # Loading penceresi
        self.loading = _SimpleLoading(self.parent, "Taranıyor... (Faz 1/3)")
        self.loading.update("Faz 1/3 - Klasör yapısı taranıyor...")

        cancelled = [False]

        def on_cancel():
            cancelled[0] = True
            scanner.cancel()

        self.loading.set_cancel_callback(on_cancel)

        def scan_thread():
            try:
                def progress(current, total, msg):
                    if not cancelled[0]:
                        self.root.after(0, lambda m=msg: self.loading.update(f"Faz 1/3 - {m}"))

                arch_map = scanner.scan(progress_callback=progress)

                if cancelled[0]:
                    return

                self.arch_map = arch_map
                self._update_home_summary(arch_map)
                self.root.after(100, lambda: self.loading.close())
                self.root.after(200, lambda: self._show_analysis_type_window(arch_map))

            except Exception as e:
                self.root.after(0, lambda: self.loading.close())
                self.root.after(0, lambda e=e: messagebox.showerror("Hata", f"Tarama hatasi: {e}"))

        self.root = self.parent
        threading.Thread(target=scan_thread, daemon=True).start()

    def _show_analysis_type_window(self, arch_map):
        """Analiz türü seçim penceresini göster (tik atma)."""
        AnalysisTypeWindow(self.parent, arch_map, self._on_analysis_selected)

    def _update_home_summary(self, arch_map):
        """Sag paneldeki son tarama ozetini guncelle."""
        try:
            if not hasattr(self.parent, "update_home_summary"):
                return
            lines = [
                f"Proje: {arch_map.root_name}",
                f"Ozet: {arch_map.total_files} dosya, {arch_map.total_folders} klasor, "
                f"{arch_map.total_lines} satir",
                "",
                "Kategoriler: " + ", ".join(
                    f"{k}({v})" for k, v in sorted(arch_map.file_categories.items(),
                                                   key=lambda x: -x[1])),
                "Diller: " + ", ".join(
                    f"{k}({v})" for k, v in sorted(arch_map.languages.items(),
                                                   key=lambda x: -x[1])),
                "",
                "Kok dosyalar: " + ", ".join(
                    sorted(f.name for f in arch_map.root_files)),
            ]
            self.parent.update_home_summary("\n".join(lines))
        except Exception:
            pass

    def _on_analysis_selected(self, selected_types):
        """Analiz türleri seçildi, analizi başlat (çalışan kanıtlı akış)."""
        if not self.arch_map:
            messagebox.showerror("Hata", "Mimari harita bulunamadı!")
            return

        # AI client kontrolü (sadece AI gerektiren türler için zorunlu)
        needs_llm = any(t != AnalysisType.ARCHITECTURE_MAP and t != AnalysisType.DEV_STATUS
                        for t in selected_types)
        if needs_llm and not self.agent.llm_client:
            messagebox.showerror("Hata",
                "LLM client başlatılmamış!\nAI gerektiren analizler icin önce bir model yükleyin.\n"
                "(Sadece 'Mimari Harita' ve 'Gelisim Durumu' AI'sız çalışır.)")
            return

        from core.analysis_engine import AnalysisEngine, AnalysisType as _AT
        from config.settings import config as _cfg2

        engine = AnalysisEngine(
            llm_client=self.agent.llm_client,
            model_id=self.agent.current_model.id if self.agent.current_model else "llamacpp",
            max_tokens=int(_cfg2.get("max_tokens", 1500) or 1500),
            max_preview_chars=int(_cfg2.get("architecture_max_preview_chars", 3000) or 3000),
            max_files_per_call=int(_cfg2.get("architecture_max_files_per_call", 4) or 4),
        )

        # Loading penceresi
        self.loading = _SimpleLoading(self.parent, "Analiz Ediliyor (Faz 2/3)")
        self.loading.update("Faz 2/3 - Analiz başlıyor...")

        cancelled = [False]

        def on_cancel():
            cancelled[0] = True
            engine.cancel()

        self.loading.set_cancel_callback(on_cancel)

        def analyze_thread():
            try:
                def progress(current, total, msg):
                    if not cancelled[0]:
                        self.root.after(0, lambda m=msg: self.loading.update(f"Faz 2/3 - {m}"))

                results = engine.analyze(
                    arch_map=self.arch_map,
                    analysis_types=selected_types,
                    scanner=ArchitectureScanner(self.arch_map.root_path, self.arch_map.ignored_folders),
                    progress_callback=progress,
                )

                if cancelled[0]:
                    return

                # Faz 3/3: raporlari thread'de yaz (arayuz kilitlenmez)
                self.root.after(0, lambda: self.loading.update(
                    "Faz 3/3 - Raporlar cikti klasorune yaziliyor..."))
                saved = self._write_multi_output(results)

                if cancelled[0]:
                    return

                self.root.after(0, lambda: self.loading.close())
                self.root.after(100, lambda: self._show_results(results, saved))

            except Exception as e:
                self.root.after(0, lambda: self.loading.close())
                self.root.after(0, lambda e=e: messagebox.showerror("Hata", f"Analiz hatasi: {e}"))

        self.root = self.parent
        threading.Thread(target=analyze_thread, daemon=True).start()

    def _show_results(self, results, saved=None):
        """Sonuçları göster + kaydedilen dosyaları bildir."""
        if not results:
            messagebox.showinfo("Bilgi", "Analiz sonucu bulunamadi!")
            return

        # Pencereyi göster
        ArchitectureResultsWindow(self.parent, self.arch_map, results)

        if saved:
            n_reports = sum(1 for s in saved if "\\raporlar\\" in s or "/raporlar/" in s)
            n_data = len(saved) - n_reports - 1
            messagebox.showinfo(
                "Raporlar Kaydedildi",
                f"Cikti klasorune yazildi:\n"
                f"  - {n_reports} rapor dosyasi (her analiz ayri)\n"
                f"  - {n_data} JSON veri dosyasi\n"
                f"  - 1 birlesik OZET\n\n"
                f"Klasor: {saved[0]}")
        else:
            messagebox.showwarning("Uyari", "Raporlar yazilamadi!")

    def _write_multi_output(self, results):
        """COKLU cikti uret:
        - raporlar/ : her analiz turu ayri .txt
        - veri/     : tarama verileri .json (ozet, klasorler, kategoriler, diller)
        - OZET.txt  : tum raporlar birlesik
        """
        from datetime import datetime
        from config.settings import config as _cfg
        from core.analysis_engine import ANALYSIS_LABELS
        saved = []
        try:
            out_dir = _cfg.get("architecture_output_dir", "")
            if not out_dir:
                base = _cfg.get("workspace_path", "") or str(Path(__file__).resolve().parent)
                out_dir = str(Path(base) / "storage" / "reports")
            out = Path(out_dir)
            raporlar = out / "raporlar"
            veri = out / "veri"
            raporlar.mkdir(parents=True, exist_ok=True)
            veri.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M')

            # 1) Her analiz turu AYRI dosya
            combined = ["Mimari Analiz Raporu", f"Proje: {self.arch_map.root_name}",
                        f"Yol: {self.arch_map.root_path}",
                        f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        "=" * 60, ""]
            slug_map = {
                AnalysisType.ARCHITECTURE_MAP: "mimari_harita",
                AnalysisType.PROJECT_PURPOSE: "proje_amaci",
                AnalysisType.TECH_INFRASTRUCTURE: "teknik_altyapi",
                AnalysisType.DEV_STATUS: "gelisim_durumu",
                AnalysisType.ERRORS_MISSING: "hatalar_eksikler",
                AnalysisType.DEAD_CODE: "olu_kodlar",
                AnalysisType.DEPENDENCIES: "bagimliliklar_donguler",
                AnalysisType.QUALITY: "kalite_guvenlik",
            }
            for analysis_type, result in results.items():
                slug = slug_map.get(analysis_type, str(analysis_type.value))
                label = ANALYSIS_LABELS.get(analysis_type, str(analysis_type))
                content = result.content if hasattr(result, "content") else str(result)
                p = raporlar / f"{slug}_{ts}.txt"
                with open(p, "w", encoding="utf-8") as f:
                    f.write(f"=== {label} ===\n")
                    f.write(content)
                saved.append(str(p))
                # Ham JSON veri varsa ayri yaz (bagimlilik grafi/matris/dongu)
                if getattr(result, "data", None):
                    try:
                        import json as _json
                        jp = veri / f"{slug}_{ts}.json"
                        with open(jp, "w", encoding="utf-8") as f:
                            _json.dump(result.data, f, indent=2, ensure_ascii=False)
                        saved.append(str(jp))
                    except Exception:
                        pass
                combined.append(f"=== {label} ===")
                combined.append(content)
                combined.append("")
                combined.append("=" * 60)
                combined.append("")

            # 2) JSON veri dosyalari (devkit tarzi yapisal veri)
            scan_data = {
                "proje": self.arch_map.root_name,
                "yol": self.arch_map.root_path,
                "tarih": datetime.now().isoformat(timespec="seconds"),
                "ozet": {
                    "dosya": self.arch_map.total_files,
                    "klasor": self.arch_map.total_folders,
                    "satir": self.arch_map.total_lines,
                },
                "kategoriler": self.arch_map.file_categories,
                "diller": self.arch_map.languages,
                "kok_dosyalar": [f.name for f in self.arch_map.root_files],
                "gelistirme_klasorleri": [
                    {"ad": f.name, "dosya": f.child_count, "satir": f.total_lines,
                     "icindekiler": [c.name for c in f.children[:20]]}
                    for f in self.arch_map.development_folders
                ],
                "atlanan_sistem_klasorleri": [
                    {"ad": f.name, "dosya": f.child_count}
                    for f in self.arch_map.system_folders
                ],
            }
            p = veri / f"tarama_ozeti_{ts}.json"
            import json as _json
            with open(p, "w", encoding="utf-8") as f:
                _json.dump(scan_data, f, indent=2, ensure_ascii=False)
            saved.append(str(p))

            # Klasor bazli detay JSON
            detay = {
                "klasorler": [
                    {"ad": f.name, "yol": f.path, "dosya_sayisi": f.child_count,
                     "satir": f.total_lines,
                     "dosyalar": [
                         {"ad": c.name, "tur": c.node_type.value,
                          "kategori": c.category.value, "dil": c.language,
                          "satir": c.line_count, "boyut_kb": round(c.size_bytes / 1024, 1)}
                         for c in f.children
                     ]}
                    for f in self.arch_map.development_folders
                ]
            }
            p = veri / f"klasor_detay_{ts}.json"
            with open(p, "w", encoding="utf-8") as f:
                _json.dump(detay, f, indent=2, ensure_ascii=False)
            saved.append(str(p))

            # 3) Birlesik OZET.txt
            p = out / f"OZET_{ts}.txt"
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(combined))
            saved.append(str(p))

            # 4) KB raporlari (kb/*.md — QUICKREF/PROJECT_MAP/SYMBOL_INDEX/ARCHITECTURE)
            try:
                from core.kb_raporlari import generate_kb_reports

                def _rdata(atype):
                    r = results.get(atype)
                    return getattr(r, "data", None) if r else None

                def _rdata_helper():
                    from core.hafiza import build_record
                    return build_record(self.arch_map, results)

                arch_result = results.get(AnalysisType.ARCHITECTURE_MAP)
                arch_data = getattr(arch_result, "data", None) or {}
                kb_data = {
                    "deps": _rdata(AnalysisType.DEPENDENCIES),
                    "api": arch_data.get("api_yuzeyi"),
                    "callgraph": _rdata(AnalysisType.DEAD_CODE),
                    "quality": _rdata(AnalysisType.QUALITY),
                }
                kb_saved = generate_kb_reports(self.arch_map, kb_data, out)
                saved.extend(kb_saved)
            except Exception:
                pass

            # 5) Mimari Hafiza (D3): taramayi gecmise kaydet + zaman cizelgesi
            try:
                from core.hafiza import record_scan, load_history, generate_timeline
                record_scan(self.scan_root or str(out), _rdata_helper())
                history = load_history(self.scan_root or str(out))
                h_data, h_text = generate_timeline(history)
                p = out / "kb" / "HAFIZA.md"
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    f.write(h_text)
                saved.append(str(p))
            except Exception:
                pass
            return saved
        except Exception as e:
            messagebox.showerror("Hata", f"Raporlar yazilamadi: {e}")
            return saved

    def _save_results(self, results):
        """Sonuçları dosyaya kaydet."""
        from datetime import datetime
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"mimari_analiz_{self.arch_map.root_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"Mimari Analiz Raporu\n")
                    f.write(f"Proje: {self.arch_map.root_name}\n")
                    f.write(f"Yol: {self.arch_map.root_path}\n")
                    f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                    f.write(f"{'='*60}\n\n")
                    for analysis_type, result in results.items():
                        from core.analysis_engine import ANALYSIS_LABELS
                        label = ANALYSIS_LABELS.get(analysis_type, str(analysis_type))
                        f.write(f"=== {label} ===\n")
                        f.write(result.content)
                        f.write(f"\n\n{'='*60}\n\n")
                messagebox.showinfo("Kaydedildi", f"Rapor kaydedildi:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Hata", f"Kaydetme hatasi: {e}")


class _SimpleLoading:
    """Basit loading penceresi."""

    def __init__(self, parent, title="İşlem devam ediyor..."):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("380x140")
        self.top.resizable(False, False)
        self.top.configure(bg='#2c3e50')
        self.top.transient(parent)
        self.cancel_callback = None

        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)

        tk.Label(self.top, text="⏳", font=('Arial', 22), bg='#2c3e50', fg='#f39c12').pack(pady=(8, 2))

        self.status_label = tk.Label(self.top, text="Başlatılıyor...", font=('Arial', 10),
                                      bg='#2c3e50', fg='white')
        self.status_label.pack(pady=(0, 5))

        self.progress = ttk.Progressbar(self.top, mode='indeterminate', length=280)
        self.progress.pack(pady=(0, 5))
        self.progress.start(15)

        self.cancel_btn = tk.Button(self.top, text="✖ İptal", command=self._on_cancel,
                                     bg='#e74c3c', fg='white', relief="flat", padx=10)
        self.cancel_btn.pack()

        self._center(parent)

    def _center(self, parent):
        self.top.update_idletasks()
        w, h = 380, 140
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.top.geometry(f"+{x}+{y}")

    def update(self, text):
        try:
            self.status_label.config(text=text)
        except:
            pass

    def set_cancel_callback(self, callback):
        self.cancel_callback = callback

    def _on_cancel(self):
        if self.cancel_callback:
            self.cancel_callback()
        self.close()

    def close(self):
        try:
            self.progress.stop()
            self.top.destroy()
        except:
            pass
