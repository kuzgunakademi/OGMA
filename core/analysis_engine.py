from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import re

from core.architecture_scanner import ArchitectureMap


class AnalysisType(Enum):
    ARCHITECTURE_MAP = "architecture_map"
    PROJECT_PURPOSE = "project_purpose"
    TECH_INFRASTRUCTURE = "tech_infrastructure"
    DEV_STATUS = "dev_status"
    ERRORS_MISSING = "errors_missing"
    DEAD_CODE = "dead_code"
    DEPENDENCIES = "dependencies"
    QUALITY = "quality"


ANALYSIS_LABELS = {
    AnalysisType.ARCHITECTURE_MAP: "Mimari Harita",
    AnalysisType.PROJECT_PURPOSE: "Proje Amaci",
    AnalysisType.TECH_INFRASTRUCTURE: "Teknik Altyapi",
    AnalysisType.DEV_STATUS: "Gelisim Durumu",
    AnalysisType.ERRORS_MISSING: "Hatalar & Eksikler",
    AnalysisType.DEAD_CODE: "olu Kodlar",
    AnalysisType.DEPENDENCIES: "Bagimliliklar & Donguler",
    AnalysisType.QUALITY: "Kalite & Guvenlik",
}


# Model uygunluk bilgisi
MODEL_INFO = {
    "trendyol": "Turkce egitilmis, orta boyut. Analiz icin uygun.",
    "qwen": "Kod analizinde guclu. Analiz icin uygun.",
    "deepseek": "Kod analizinde cok guclu. Analiz icin cok uygun.",
    "llama": "Genel amacli. Analiz icin orta uygunluk.",
    "codellama": "Kod analizine ozel. Analiz icin cok uygun.",
}


@dataclass
class AnalysisResult:
    analysis_type: AnalysisType
    content: str
    timestamp: str
    file_scoped: str = ""
    data: Optional[dict] = None  # ham JSON veri (multi-output icin)


class AnalysisEngine:
    """AI ile mimari analiz yapar - chunked yontem ile."""

    def __init__(self, llm_client, model_id: str, max_tokens: int = 800,
                 max_preview_chars: int = 3000, max_files_per_call: int = 4):
        self.llm_client = llm_client
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.max_preview_chars = max(200, max_preview_chars)
        self.max_files_per_call = max(1, max_files_per_call)
        self.cancelled = False
        self._model_suitability = self._check_model_suitability()

    def _preview(self, scanner, path: str, cap: int) -> str:
        """Onizleme boyutu config tavanini asamaz."""
        return scanner.get_file_content_preview(
            path, max_chars=min(cap, self.max_preview_chars))

    def cancel(self):
        self.cancelled = True

    def _check_model_suitability(self) -> str:
        """Modelin analiz icin uygunlugunu kontrol et."""
        model_lower = self.model_id.lower()
        for key, info in MODEL_INFO.items():
            if key in model_lower:
                return info
        return "Model bilinmiyor. Analiz icin deneyebilirsiniz."

    def get_model_suitability(self) -> str:
        """Model uygunluk bilgisini dondur."""
        return self._model_suitability

    def analyze(
        self,
        arch_map: ArchitectureMap,
        analysis_types: List[AnalysisType],
        scanner=None,
        progress_callback=None,
    ) -> Dict[AnalysisType, AnalysisResult]:
        """Secilen analiz turlerini calistir - chunked yontem ile."""
        self.cancelled = False
        results = {}
        total = len(analysis_types)

        for i, analysis_type in enumerate(analysis_types):
            if self.cancelled:
                break

            label = ANALYSIS_LABELS.get(analysis_type, str(analysis_type))
            if progress_callback:
                progress_callback(i, total, f"Analiz {i+1}/{total}: {label}")

            # Mimari harita AI gerektirmez (+ API yuzeyi + KG + fingerprint diff)
            if analysis_type == AnalysisType.ARCHITECTURE_MAP:
                content = self._build_architecture_map_text(arch_map, scanner)
                map_data: dict = {}
                try:
                    from core.api_yuzeyi import build_api_surface
                    api_data = build_api_surface(arch_map.root_path,
                                                 self._collect_py_paths(arch_map))
                    map_data["api_yuzeyi"] = api_data
                    content = content + "\n\n" + self._format_api_section(api_data)
                except Exception:
                    pass
                try:
                    from core.bilgi_grafigi import build_knowledge_graph
                    kg = build_knowledge_graph(arch_map.root_path,
                                               self._collect_py_paths(arch_map))
                    map_data["bilgi_grafigi"] = kg
                except Exception:
                    pass
                try:
                    diff = self._compute_scan_diff(arch_map)
                    if diff is not None:
                        map_data["degisiklikler"] = diff
                        diff_text = self._format_diff_section(diff)
                        if diff_text:
                            content = content + "\n\n" + diff_text
                except Exception:
                    pass
                results[analysis_type] = AnalysisResult(
                    analysis_type=analysis_type,
                    content=content,
                    timestamp=datetime.now().isoformat(),
                    data=map_data or None,
                )
                continue

            # Gelisim durumu dosya tabanli, AI gerektirmez
            if analysis_type == AnalysisType.DEV_STATUS:
                content = self._build_dev_status_text(arch_map)
                results[analysis_type] = AnalysisResult(
                    analysis_type=analysis_type,
                    content=content,
                    timestamp=datetime.now().isoformat(),
                )
                continue

            # Teknik altyapi - chunked (+ kullanım doğrulama)
            if analysis_type == AnalysisType.TECH_INFRASTRUCTURE:
                content = self._chunked_tech_infra(arch_map, scanner, progress_callback)
                usage_data = None
                try:
                    from core.kullanim_dogrulama import validate_usage
                    imported_tops = set(re.findall(
                        r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)",
                        "\n".join(self._read_source_full(arch_map, f.path)
                                  for f in self._source_pool(arch_map, -1, 100000)
                                  if f.name.endswith(".py")) + "\n",
                        re.MULTILINE))
                    local_tops = {f.path.split("/")[0].split("\\")[0]
                                  for f in self._source_pool(arch_map, -1, 100000)
                                  if "/" in f.path or "\\" in f.path}
                    usage_data = validate_usage(arch_map.root_path,
                                                imported_tops, local_tops)
                    usage_text = self._format_usage_section(usage_data)
                    if usage_text:
                        content = content + "\n\n" + usage_text
                except Exception:
                    usage_data = None
                if content:
                    results[analysis_type] = AnalysisResult(
                        analysis_type=analysis_type,
                        content=content,
                        timestamp=datetime.now().isoformat(),
                        data=usage_data,
                    )
                continue

            # Hatalar - chunked
            if analysis_type == AnalysisType.ERRORS_MISSING:
                content = self._chunked_errors(arch_map, scanner, progress_callback)
                if content:
                    results[analysis_type] = AnalysisResult(
                        analysis_type=analysis_type,
                        content=content,
                        timestamp=datetime.now().isoformat(),
                    )
                continue

            #olu kodlar - chunked (proje-geneli cagri grafi ile)
            if analysis_type == AnalysisType.DEAD_CODE:
                content = self._chunked_dead_code(arch_map, scanner, progress_callback)
                if content:
                    results[analysis_type] = AnalysisResult(
                        analysis_type=analysis_type,
                        content=content,
                        timestamp=datetime.now().isoformat(),
                        data=getattr(self, "_last_callgraph", None),
                    )
                continue

            # Proje amaci - tek AI cagrisi
            if analysis_type == AnalysisType.PROJECT_PURPOSE:
                prompt = self._build_project_purpose_prompt(arch_map, scanner)
                if prompt:
                    response = self._call_llm(prompt, repeat_penalty=1.15)
                    if response:
                        results[analysis_type] = AnalysisResult(
                            analysis_type=analysis_type,
                            content=response,
                            timestamp=datetime.now().isoformat(),
                        )
                continue

            # Bagimliliklar & donguler - deterministik (AI gerektirmez)
            if analysis_type == AnalysisType.DEPENDENCIES:
                dep_data, dep_content = self._build_dependencies_text(arch_map)
                results[analysis_type] = AnalysisResult(
                    analysis_type=analysis_type,
                    content=dep_content,
                    timestamp=datetime.now().isoformat(),
                    data=dep_data,
                )
                continue

            # Kalite & guvenlik - deterministik (AI gerektirmez)
            if analysis_type == AnalysisType.QUALITY:
                q_data, q_content = self._build_quality_text(arch_map)
                results[analysis_type] = AnalysisResult(
                    analysis_type=analysis_type,
                    content=q_content,
                    timestamp=datetime.now().isoformat(),
                    data=q_data,
                )
                continue

        if progress_callback:
            progress_callback(total, total, "Analiz tamamlandi!")

        return results

    def _source_pool(self, arch_map: ArchitectureMap,
                     min_lines: int = -1, max_lines: int = 10 ** 9):
        """Kaynak dosya havuzu: kok + klasorler, ozyinelemeli."""
        pool = []

        def visit_folder(node):
            for child in node.children:
                if child.category.value == "source" \
                        and min_lines < (child.line_count or 0) < max_lines:
                    pool.append(child)
                if child.node_type.value in ("dev_folder", "folder"):
                    visit_folder(child)

        for f in (arch_map.root_files or []):
            if f.category.value == "source" \
                    and min_lines < (f.line_count or 0) < max_lines:
                pool.append(f)
        for folder in arch_map.development_folders:
            visit_folder(folder)
        return pool

    @staticmethod
    def _ast_names(content: str):
        """AST ile (importlar, modul-seviye tanimlar, kullanilan adlar,
        attribute adlari) cikar."""
        import ast as _ast
        tree = _ast.parse(content)
        imported = {}
        top_level = []
        for node in tree.body:
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                top_level.append(("def", node.name, node.lineno))
            elif isinstance(node, _ast.ClassDef):
                top_level.append(("class", node.name, node.lineno))
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Import):
                for a in node.names:
                    imported[(a.asname or a.name).split(".")[0]] = node.lineno
            elif isinstance(node, _ast.ImportFrom):
                for a in node.names:
                    if a.name != "*":
                        imported[a.asname or a.name] = node.lineno
        used = set()
        attrs = set()
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Name):
                used.add(node.id)
            elif isinstance(node, _ast.Attribute):
                attrs.add(node.attr)
                v = node
                while isinstance(v, _ast.Attribute):
                    v = v.value
                if isinstance(v, _ast.Name):
                    used.add(v.id)
        return imported, top_level, used, attrs

    def find_unused_imports(self, scanner, file_nodes) -> Dict[str, List[str]]:
        """Deterministik olu import tespiti (AST, halusinasyonsuz)."""
        result = {}
        for node in file_nodes:
            # Onizleme kesmesi yanlis pozitif uretirir: tam oku (200K'ya kadar).
            try:
                content = scanner.get_file_content_preview(
                    node.path, max_chars=200_000)
            except Exception:
                content = ""
            if not content or content.startswith("["):
                continue
            try:
                imported, _, used, _ = self._ast_names(content)
            except Exception:
                continue
            dead = sorted(f"{name} (satir {ln})" for name, ln in imported.items()
                          if name not in used)
            if dead:
                result[node.name] = dead
        return result

    def _chunked_tech_infra(self, arch_map: ArchitectureMap, scanner=None, progress_callback=None) -> str:
        """Teknik altyapiyi chunked olarak analiz et - dosya dosya import topla."""
        if not scanner:
            return "Tarama yapilmadi."

        # 1. Adim: Import'lari topla (AI gerektirmez, sadece dosya okuma)
        imports_by_file = {}
        source_files = self._source_pool(arch_map, -1, 500)

        # Config tavani kadar dosya oku
        source_files = source_files[:self.max_files_per_call]

        for idx, file_node in enumerate(source_files):
            if self.cancelled:
                break
            if progress_callback:
                progress_callback(idx, len(source_files), f"Import okunuyor: {file_node.name}")

            content = self._preview(scanner, file_node.path, 2000)
            file_imports = []
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    file_imports.append(line.split("#")[0].strip())
            if file_imports:
                imports_by_file[file_node.name] = file_imports

        # 2. Adim: Import'lari listele (AI gerektirmez)
        all_imports = set()
        for imports in imports_by_file.values():
            all_imports.update(imports)

        import_text = "\n".join(sorted(all_imports)[:30]) if all_imports else "Import bulunamadi"

        # 3. Adim: Deterministik kategorize (stdlib / ucuncu parti / yerel).
        # Kucuk modeller import listesini bozabildigi icin AI kullanilmaz.
        import sys as _sys
        stdlib = set(getattr(_sys, "stdlib_module_names", ()))
        local_roots = {"core", "config", "gui", "models", "utils"}
        cats: Dict[str, list] = {"Standart kutuphane": [], "Ucuncu parti": [],
                                 "Yerel moduller": []}
        for imp in sorted(all_imports):
            top = imp.replace("import ", "").replace("from ", "").split()[0].split(".")[0]
            if top in stdlib:
                cats["Standart kutuphane"].append(imp)
            elif top in local_roots:
                cats["Yerel moduller"].append(imp)
            else:
                cats["Ucuncu parti"].append(imp)

        if progress_callback:
            progress_callback(len(source_files), len(source_files), "Kategorize edildi.")

        response = ""
        for cat, items in cats.items():
            if items:
                response += f"{cat} ({len(items)}):\n"
                for it in items[:15]:
                    response += f"  - {it}\n"

        if not response:
            response = "Import bulunamadi."

        # Dosya bazli ozet ekle
        file_summary = "\nDosya bazli import'lar:\n"
        for fname, imports in imports_by_file.items():
            file_summary += f"  {fname}: {', '.join(imports[:5])}\n"

        return response + file_summary

    @staticmethod
    def _read_source_full(arch_map: ArchitectureMap, rel_path: str,
                          limit: int = 200_000) -> str:
        """Analiz icin dosyanin tamami (kesilmemis AST icin)."""
        try:
            p = Path(arch_map.root_path) / rel_path
            if p.stat().st_size > limit:
                return ""
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    @staticmethod
    def _static_bugs(content: str, max_findings: int = 8):
        """Deterministik hata taramasi: sintaks + tanimsiz adlar."""
        import ast as _ast
        import builtins as _bi
        try:
            tree = _ast.parse(content)
        except SyntaxError as e:
            return [f"satir {e.lineno}: SyntaxError: {e.msg}"]
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ImportFrom):
                if any(a.name == "*" for a in node.names):
                    return []  # yildizli import: adlar bilinemez, sus
        bound = set(dir(_bi)) | {
            "__name__", "__file__", "__package__", "__doc__",
            "__loader__", "__spec__", "__annotations__",
            "__cached__", "__builtins__",
        }
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                 _ast.ClassDef)):
                bound.add(node.name)
                args = getattr(node, "args", None)
                if args is None:
                    continue
                params = list(args.args) + list(args.kwonlyargs)
                if args.vararg:
                    params.append(args.vararg)
                if args.kwarg:
                    params.append(args.kwarg)
                for a in params:
                    bound.add(a.arg)
            elif isinstance(node, _ast.Lambda):
                largs = node.args
                lparams = list(largs.args) + list(largs.kwonlyargs)
                if largs.vararg:
                    lparams.append(largs.vararg)
                if largs.kwarg:
                    lparams.append(largs.kwarg)
                for a in lparams:
                    bound.add(a.arg)
            elif isinstance(node, _ast.Import):
                for a in node.names:
                    bound.add((a.asname or a.name).split(".")[0])
            elif isinstance(node, _ast.ImportFrom):
                for a in node.names:
                    if a.name != "*":
                        bound.add(a.asname or a.name)
            elif isinstance(node, _ast.Name) and isinstance(
                    node.ctx, (_ast.Store,)):
                bound.add(node.id)
            elif isinstance(node, _ast.ExceptHandler) and node.name:
                bound.add(node.name)
        undef = {}
        for node in _ast.walk(tree):
            if isinstance(node, _ast.Name) and isinstance(node.ctx, _ast.Load):
                if node.id not in bound and not (
                        node.id.startswith("__") and node.id.endswith("__")):
                    undef.setdefault(node.id, node.lineno)
        return [f"satir {ln}: '{name}' tanimli degil (yazim hatasi olabilir)"
                for name, ln in sorted(undef.items(), key=lambda x: x[1])
                ][:max_findings]

    def _chunked_errors(self, arch_map: ArchitectureMap, scanner=None, progress_callback=None) -> str:
        """Hatalar: statik tarama (sintaks + tanimsiz ad). Deterministik."""
        source_files = [f for f in self._source_pool(arch_map, -1, 100000)
                        if f.name.lower().endswith(".py")]
        source_files = source_files[:self.max_files_per_call * 2]
        all_issues = []

        for idx, file_node in enumerate(source_files):
            if self.cancelled:
                break
            if progress_callback:
                progress_callback(idx, len(source_files),
                                  f"Denetleniyor: {file_node.name}")
            content = self._read_source_full(arch_map, file_node.path)
            if not content:
                continue
            bugs = self._static_bugs(content)
            if bugs:
                all_issues.append(f"--- {file_node.name} ---\n" +
                                  "\n".join(f"  {b}" for b in bugs))

        if not all_issues:
            return ("Belirgin hata bulunamadi "
                    "(sintaks + tanimsiz ad taramasi temiz).")
        return "\n\n".join(all_issues)

    def _chunked_dead_code(self, arch_map: ArchitectureMap, scanner=None, progress_callback=None) -> str:
        """Olu kodlar: PROJE-GENELI cagri grafi + AST (deterministik).

        - Olu fonksiyonlar: adi HICBIR dosyada cagilmayan/referans
          edilmeyen modul-seviye fonksiyonlar (cagri grafi ile).
        - Kullanilmayan import'lar: dosyada hic gecmeyen adlar (kesin).
        Donus: (ham_veri, metin_rapor) yerine metin; ham veri result.data'ya
        konur.
        """
        from core.cagri_grafigi import analyze_call_graph
        py_paths = self._collect_py_paths(arch_map)
        if not py_paths:
            return "Olu kod analizi: .py dosyasi bulunamadi."

        if progress_callback:
            progress_callback(0, 2, "Cagri grafi olusturuluyor (proje-geneli)...")

        cg = analyze_call_graph(arch_map.root_path, py_paths)
        self._last_callgraph = cg

        if progress_callback:
            progress_callback(1, 2, "Olu importlar taraniyor...")

        lines = []

        # 1) Olu fonksiyonlar (proje-geneli)
        dead_funcs = cg["project_dead"]
        if dead_funcs:
            lines.append("OLU FONKSIYONLAR (proje genelinde hicbir yerden "
                         "cagilmayan/referans edilmeyen):")
            by_file: Dict[str, List[dict]] = {}
            for d in dead_funcs:
                by_file.setdefault(d["file"], []).append(d)
            for rel, items in sorted(by_file.items()):
                lines.append(f"--- {rel} ---")
                for d in items:
                    lines.append(f"  olu fonksiyon: {d['func']} (satir {d['line']})")
            lines.append("")

        # 2) Kullanilmayan importlar (dosya bazli)
        dead_by_file = self.find_unused_imports(
            scanner, [f for f in self._source_pool(arch_map, -1, 100000)
                      if f.name.lower().endswith(".py")])
        for fname, items in sorted(dead_by_file.items()):
            lines.append(f"--- {fname} ---")
            for it in items:
                lines.append(f"  olu import: {it}")
            lines.append("")

        if not lines:
            return "Olu kod bulunamadi (cagri grafi + import taramasi temiz)."
        note = ("Not: dinamik cagilar (getattr, string tabanli dispatch) tespit "
                "edilemez; disa acik API ise silmeyin.")
        return "\n".join(lines) + "\n" + note

    def _build_architecture_map_text(self, arch_map: ArchitectureMap, scanner=None) -> str:
        """AI gerektirmeyen mimari harita metni."""
        lines = []
        lines.append(f"PROJE: {arch_map.root_name}")
        lines.append(f"YOL: {arch_map.root_path}")
        lines.append(f"TARIH: {arch_map.scan_timestamp}")
        lines.append("")
        lines.append(f"OZET: {arch_map.total_files} dosya, {arch_map.total_folders} klasor, {arch_map.total_lines} satir kod")
        lines.append("")

        if arch_map.file_categories:
            lines.append("DOSYA KATEGORILERI:")
            for cat, count in sorted(arch_map.file_categories.items(), key=lambda x: -x[1]):
                lines.append(f"  - {cat}: {count}")
            lines.append("")

        if arch_map.languages:
            lines.append("PROGRAMLAMA DILLERI:")
            for lang, count in sorted(arch_map.languages.items(), key=lambda x: -x[1]):
                lines.append(f"  - {lang}: {count} dosya")
            lines.append("")

        if arch_map.development_folders:
            lines.append("GELISTIRME KLASORLERI:")
            for folder in arch_map.development_folders:
                lines.append(f"  KLASOR: {folder.name}")
                lines.append(f"     Dosya: {folder.child_count}, Satir: {folder.total_lines}")
                for child in folder.children[:8]:
                    if child.node_type.value in ("dev_folder", "folder"):
                        lines.append(f"     |- {child.name} ({child.child_count} dosya)")
                    elif child.node_type.value == "file":
                        cat_icons = {
                            "source": " ", "config": " ", "docs": " ",
                            "build": " ", "asset": " ", "data": " ",
                        }
                        icon = cat_icons.get(child.category.value, " ")
                        lines.append(f"     |- {icon} {child.name}")
                if len(folder.children) > 8:
                    lines.append(f"     ... (+{len(folder.children) - 8} daha)")
            lines.append("")

        if arch_map.root_files:
            lines.append("KOK DOSYALAR (proje giris noktalari):")
            for f in sorted(arch_map.root_files, key=lambda x: x.name.lower()):
                extra = f" [{f.language}]" if f.language else ""
                lines.append(f"  - {f.name}{extra}")
            lines.append("")

        if arch_map.system_folders:
            lines.append("SYSTEM KLASORLERI (atlandi):")
            for folder in arch_map.system_folders:
                lines.append(f"  {folder.name} ({folder.child_count} dosya)")

        return "\n".join(lines)

    def _build_dev_status_text(self, arch_map: ArchitectureMap) -> str:
        """Gelisim durumunu dosya tabanli hesapla (AI gerektirmez)."""
        lines = []
        lines.append("GELISIM DURUMU ANALIZI")
        lines.append("=" * 40)
        lines.append("")

        # Temel bilgiler
        lines.append(f"Toplam dosya: {arch_map.total_files}")
        lines.append(f"Toplam satir kod: {arch_map.total_lines}")
        lines.append("")

        # Dosya varligi kontrolu: tespit edilen dillere gore ilgili dosyalar
        root = Path(arch_map.root_path)
        langs = {str(k).lower() for k in (arch_map.languages or {})}
        checks = [
            ("README.md", "Dokumantasyon", True),
            ("KURULUM.txt", "Kurulum notu", True),
            ("requirements.txt", "Python bagimliliklari",
             any("python" in lang for lang in langs)),
            ("pyproject.toml", "Python proje yapilandirmasi",
             any("python" in lang for lang in langs)),
            ("package.json", "Node.js konfigurasyonu",
             any(x in lang for lang in langs for x in ("javascript", "typescript"))),
            ("Cargo.toml", "Rust konfigurasyonu",
             any("rust" in lang for lang in langs)),
            ("go.mod", "Go modulleri",
             any(lang == "go" for lang in langs)),
            ("Makefile", "Build dosyasi", True),
            ("Dockerfile", "Container dosyasi", True),
            (".gitignore", "Git yonetimi", True),
            ("LICENSE", "Lisans", True),
        ]

        lines.append("DOSYA KONTROLU:")
        for fname, desc, relevant in checks:
            if not relevant:
                continue
            exists = (root / fname).exists()
            status = "VAR" if exists else "YOK"
            lines.append(f"  [{status}] {fname} - {desc}")

        lines.append("")

        # Test kontrolu (tum agac, ozyinelemeli)
        has_tests = False

        def _has_test(node):
            nonlocal has_tests
            for child in node.children:
                if "test" in child.name.lower():
                    has_tests = True
                    return
                if child.node_type.value in ("dev_folder", "folder") and not has_tests:
                    _has_test(child)

        for _f in (arch_map.root_files or []):
            if "test" in _f.name.lower():
                has_tests = True
        for _folder in arch_map.development_folders:
            if not has_tests:
                _has_test(_folder)

        lines.append(f"Test dosyalari: {'VAR' if has_tests else 'YOK'}")

        # Gelisim asamasi tahmini
        lines.append("")
        lines.append("TAHMINI GELISIM ASAMASI:")

        has_deps = any((root / f).exists() for f in
                       ("requirements.txt", "pyproject.toml", "package.json",
                        "Cargo.toml", "go.mod"))
        score = 0
        if (root / "README.md").exists() or (root / "KURULUM.txt").exists(): score += 1
        if has_deps: score += 1
        if (root / ".git").exists(): score += 1
        if has_tests: score += 1
        if arch_map.total_files > 10: score += 1
        if arch_map.total_lines > 500: score += 1

        if score >= 5:
            status = "OLGUN - Aktif gelistirme"
        elif score >= 3:
            status = "GELISTIRME ASAMASINDA - Devam ediyor"
        elif score >= 1:
            status = "ERKEN ASAMA - Baslangic"
        else:
            status = "BELIRSIZ - Yeterli bilgi yok"

        lines.append(f"  Skor: {score}/6")
        lines.append(f"  Durum: {status}")

        return "\n".join(lines)

    def _collect_purpose_docs(self, arch_map: ArchitectureMap, scanner=None) -> str:
        """Amac sinyali: dokuman + giris noktalari (en fazla ~1200 karakter)."""
        parts = []

        entries = [f.name for f in (arch_map.root_files or [])
                   if f.name.lower().endswith((".py", ".bat", ".exe", ".md", ".txt", ".html"))]
        if entries:
            parts.append("Giris dosyalari: " + ", ".join(sorted(entries)[:10]))

        doc_names = ["README.md", "KURULUM.txt", "promo.html",
                     "requirements.txt", "package.json", "pyproject.toml"]
        for name in doc_names:
            try:
                if not (Path(arch_map.root_path) / name).exists() or not scanner:
                    continue
                content = scanner.get_file_content_preview(name, max_chars=600)
                if not content or content.startswith("["):
                    continue
                if name.endswith(".html"):
                    import re as _re
                    content = _re.sub(r"<[^>]+>", " ", content)
                    content = _re.sub(r"\s+", " ", content).strip()[:600]
                parts.append(f"--- {name} ---\n{content}")
                if sum(len(p) for p in parts) > 1200:
                    break
            except Exception:
                continue
        return "\n\n".join(parts) if parts else "Dokuman bulunamadi."

    def _build_project_purpose_prompt(self, arch_map: ArchitectureMap, scanner=None) -> str:
        """Proje amacini analiz et promptu."""
        tree_summary = self._get_tree_summary(arch_map)
        signals = self._collect_purpose_docs(arch_map, scanner)

        return f"""Asagidaki proje taramasina bakarak BU PROGRAMIN NE ISE YARADIGINI acikla.

Yapi:
{tree_summary}

Sinyaller:
{signals}

3 maddede yaz: 1) Program ne yapar (tek cumle), 2) Ana ozellikler, 3) Nasil calisir.
Sadece verilen bilgiye dayan, uydurma. Turkce yaz. 150 kelime siniri."""

    def _collect_py_paths(self, arch_map: ArchitectureMap) -> List[str]:
        """Tum .py dosya yollari (kok + klasorler, ozyinelemeli)."""
        paths: List[str] = []

        def visit(node):
            for child in node.children:
                if child.node_type.value == "file" and child.name.endswith(".py"):
                    paths.append(child.path)
                elif child.node_type.value in ("dev_folder", "folder"):
                    visit(child)

        visit(arch_map.development_folders) if hasattr(
            arch_map.development_folders, "children") else None
        for folder in arch_map.development_folders:
            visit(folder)
        for f in (arch_map.root_files or []):
            if f.name.endswith(".py"):
                paths.append(f.path)
        return paths

    def _build_dependencies_text(self, arch_map: ArchitectureMap):
        """Bagimlilik + dongu raporu (deterministik, AI gerektirmez).
        Donus: (ham_veri, metin_rapor)."""
        from core.bagimlilik_analizi import run_dependency_analysis
        py_paths = self._collect_py_paths(arch_map)
        if not py_paths:
            return None, "Bagimlilik analizi: .py dosyasi bulunamadi."

        data = run_dependency_analysis(arch_map.root_path, py_paths)
        stats = data["stats"]

        lines = ["BAGIMLILIK ANALIZI", "=" * 40, ""]
        lines.append(
            f"Modul sayisi: {stats['modul_sayisi']} | "
            f"Bagimlilik kenari: {stats['bagimlilik_kenari']} | "
            f"Bagimsiz modul: {stats['bagimsiz_modul']}")
        lines.append("")

        cycles = data["cycles"]
        if cycles:
            lines.append(f"DONGULER (KRITIK - {len(cycles)} adet):")
            lines.append("Dairesel import'lar projeyi calistirmada kirabilir.")
            for i, cyc in enumerate(cycles, 1):
                lines.append(f"  Dongu {i}: {' <-> '.join(cyc)}")
            lines.append("")
        else:
            lines.append("DONGULER: Yok (dairesel import tespit edilmedi)")
            lines.append("")

        depended = stats.get("en_cok_bagimli_olunan", [])
        if depended:
            lines.append("EN COK BAGIMLI OLUNAN (degisiklik etki riski yuksek):")
            for d in depended:
                lines.append(f"  - {d['dosya']}: {d['kim_import_ediyor']} dosya import ediyor")
            lines.append("")

        if data["matrix"]:
            lines.append("ALT-SISTEM BAGIMLILIK MATRISI (kaynak -> hedef: adet):")
            for src, targets in sorted(data["matrix"].items()):
                nonzero = {t: c for t, c in targets.items() if c > 0}
                if nonzero:
                    lines.append(f"  {src} -> " + ", ".join(
                        f"{t}({c})" for t, c in sorted(nonzero.items())))
            lines.append("")

        graph = data["graph"]
        orphans = [k for k, v in graph.items() if not v]
        if orphans and len(orphans) <= 15:
            lines.append("BAGIMSIZ MODULLER (hicbir sey import etmiyor):")
            for o in orphans:
                lines.append(f"  - {o}")
            lines.append("")

        if data["errors"]:
            lines.append("SORUNLAR:")
            for err in data["errors"]:
                lines.append(f"  - {err}")

        return data, "\n".join(lines)

    def _build_quality_text(self, arch_map: ArchitectureMap):
        """Kalite + guvenlik raporu (deterministik, AI gerektirmez).
        Donus: (ham_veri, metin_rapor)."""
        from core.kalite_analizi import run_quality_analysis
        py_paths = self._collect_py_paths(arch_map)
        if not py_paths:
            return None, "Kalite analizi: .py dosyasi bulunamadi."

        data = run_quality_analysis(arch_map.root_path, py_paths)
        summary = data["summary"]

        lines = ["KALITE & GUVENLIK ANALIZI", "=" * 40, ""]
        lines.append(
            f"Dosya: {summary['dosya_sayisi']} | "
            f"Ortalama skor: {summary['ortalama_skor']}/40 | "
            f"Sorun: {summary['sorun_sayisi']} (kritik: {summary['kritik_sorun']})")
        lines.append("")

        # Guvenlik riskleri (en once)
        sec_lines = []
        for rel, v in sorted(data["by_file"].items()):
            for s in v["security"]:
                sec_lines.append(f"  [{s['seviye'].upper()}] {rel}:{s['satir']} — {s['aciklama']}")
        if sec_lines:
            lines.append("GUVENLIK RISKLERI:")
            lines.extend(sec_lines[:20])
            lines.append("")
        else:
            lines.append("GUVENLIK RISKLERI: Yok (eval/shell/pickle/gizli bilgi taramasi temiz)")
            lines.append("")

        # Kritik sorunlar
        kritik_lines = []
        for rel, v in sorted(data["by_file"].items()):
            for i in v["issues"]:
                if i.get("seviye") == "kritik":
                    kritik_lines.append(f"  {rel}:{i['satir']} — {i['aciklama']}")
        if kritik_lines:
            lines.append("KRITIK SORUNLAR:")
            lines.extend(kritik_lines[:15])
            lines.append("")

        # Orta/onemli sorunlar (dosya bazli, ilk 20)
        orta_lines = []
        for rel, v in sorted(data["by_file"].items()):
            for i in v["issues"]:
                if i.get("seviye") in ("orta", "yuksek"):
                    orta_lines.append(f"  [{i['seviye'].upper()}] {rel}:{i['satir']} — {i['aciklama']}")
        if orta_lines:
            lines.append("ORTA/YUKSEK SORUNLAR:")
            lines.extend(orta_lines[:20])
            lines.append("")

        # En dusuk skorlu dosyalar
        if summary["en_dusuk_skorlu"]:
            lines.append("EN DUSUK SKORLU DOSYALAR (refactoring adaylari):")
            for d in summary["en_dusuk_skorlu"]:
                lines.append(f"  - {d['dosya']}: {d['skor']}/40")
            lines.append("")

        # Tip ipucu kapsami (proje geneli)
        th_vals = [(rel, v["type_hint"]) for rel, v in data["by_file"].items()
                   if v.get("type_hint") is not None]
        if th_vals:
            avg_th = round(sum(v for _, v in th_vals) / len(th_vals), 1)
            lines.append(f"TIP IPUCU KAPSAMI (proje ortalamasi): %{avg_th}")

        return data, "\n".join(lines)

    def _format_usage_section(self, usage_data: dict) -> str:
        """Kullanim dogrulama sonucunu metin sekline cevir."""
        lines = ["KULLANIM DOGRULAMA (requirements.txt vs gercek importlar):"]
        declared = usage_data.get("beyan_edilen", [])
        lines.append(f"  Beyan edilen paket: {len(declared)}")
        unused = usage_data.get("kullanilmayan_adaylar", [])
        if unused:
            lines.append(f"  KULLANILMAYAN ADAYLAR (beyan edilmis, import edilmemis):")
            for u in unused:
                lines.append(f"    - {u}")
        else:
            lines.append("  Kullanilmayan aday: yok")
        undeclared = usage_data.get("beyan_edilmeyen_importlar", [])
        if undeclared:
            lines.append(f"  BEYAN EDILMEMIS IMPORTLAR (import edilmis, beyan edilmemis):")
            for u in undeclared:
                lines.append(f"    - {u}  (requirements.txt'ye eklenmeli)")
        else:
            lines.append("  Beyan edilmemis import: yok")
        return "\n".join(lines)

    def _compute_scan_diff(self, arch_map: ArchitectureMap):
        """Son taramadan beri degisiklikleri hesapla; parmak izlerini kaydet.
        Ilk taramada None doner (baz olusturulur)."""
        from core.fingerprint import (compute_fingerprints, load_fingerprint,
                                      save_fingerprint, compute_diff)
        all_paths = [f.path for f in (arch_map.root_files or [])]
        for folder in arch_map.development_folders:
            def visit(node):
                for c in node.children:
                    if c.node_type.value == "file":
                        all_paths.append(c.path)
                    elif c.node_type.value in ("dev_folder", "folder"):
                        visit(c)
            visit(folder)

        new_fp = compute_fingerprints(arch_map.root_path, all_paths)
        old_fp = load_fingerprint(arch_map.root_path)
        save_fingerprint(arch_map.root_path, new_fp)
        if not old_fp:
            return None  # ilk tarama: baz olusturuldu
        return compute_diff(old_fp, new_fp)

    def _format_diff_section(self, diff: dict) -> str:
        """Degisiklik bolumunu metin sekline cevir."""
        added = diff.get("added", [])
        deleted = diff.get("deleted", [])
        modified = diff.get("modified", [])
        if not added and not deleted and not modified:
            return "DEGISIKLIKLER (son taramadan beri): Yok"
        lines = ["DEGISIKLIKLER (son taramadan beri): "
                 f"+{len(added)} eklenen, -{len(deleted)} silinen, "
                 f"~{len(modified)} degisen"]
        for a in added[:15]:
            lines.append(f"  + {a}")
        for d in deleted[:15]:
            lines.append(f"  - {d}")
        for m in modified[:15]:
            lines.append(f"  ~ {m}")
        if len(added) + len(deleted) + len(modified) > 45:
            lines.append("  ... (tam liste: veri/degisiklikler JSON)")
        return "\n".join(lines)

    def _format_api_section(self, api_data: dict) -> str:
        """API yuzeyini metin sekline cevir (Mimari Harita raporuna ek)."""
        try:
            from core.api_yuzeyi import format_api_surface
            return format_api_surface(api_data)
        except Exception:
            return ""

    def _get_tree_summary(self, arch_map: ArchitectureMap) -> str:
        """Mimari haritanin kisa ozetini olustur."""
        lines = []
        lines.append(f"Proje: {arch_map.root_name}")
        lines.append(f"Dosya: {arch_map.total_files}, Klasor: {arch_map.total_folders}, Satir: {arch_map.total_lines}")

        if arch_map.development_folders:
            lines.append("Gelistirme klasorleri:")
            for folder in arch_map.development_folders[:5]:
                lines.append(f"  {folder.name} ({folder.child_count} dosya)")

        if arch_map.languages:
            lines.append("Diller: " + ", ".join(f"{k}({v})" for k, v in sorted(arch_map.languages.items(), key=lambda x: -x[1])[:5]))

        return "\n".join(lines)

    def _call_llm(self, prompt: str, repeat_penalty: float = 1.0) -> Optional[str]:
        """Tek bir LLM cagrisi yap."""
        if not self.llm_client:
            return None

        try:
            return self.llm_client.chat_completion(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=self.max_tokens,
                repeat_penalty=repeat_penalty,
            )
        except Exception as e:
            return f"AI hatasi: {e}"
