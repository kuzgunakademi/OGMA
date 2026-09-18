#!/usr/bin/env python3
"""ogma_mcp.py — Ogma MCP Sunucusu (E1).

Ogma'nin deterministik analiz aracarini MCP (Model Context Protocol)
araclari olarak disariya acar: VSCode, Cline, OpenCode gibi editor
asistanlari bu araclari cagirip KANITLANMIS graf yanitlari alir.

Calistirma (stdio — editorler icin standart):
    python ogma_mcp.py

Editor konfigurasyon ornegi (Cline/VSCode mcp.json):
    "ogma": {
        "command": "H:\\Ogma\\Python_Ortami\\envs\\ds_agent\\python.exe",
        "args": ["H:\\Ogma\\ogma_mcp.py"]
    }

Tum araclari deterministiktir (AST/Graph/Evidence) — LLM uydurmasi yok.
root_path verilmezse config'teki workspace_path kullanilir.
"""
import contextlib
import io
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import config  # noqa: E402

mcp = MCPServer(
    "ogma",
    instructions=(
        "Ogma: yerel kod mimarisi analiz araci. Tum araclari deterministik "
        "(AST tabanli) — yukledigimiz bilgi uydurma degil, kanitlidir. "
        "root_path verilmezse aktif workspace kullanilir."
    ),
)


@contextlib.contextmanager
def _quiet_stdout():
    """Tool calistirma sirasinda print'leri stderr'a yonlendir
    (stdio MCP protokolu stdout'u kullanir — print protokolu bozar)."""
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old


def _root(root_path: str = "") -> str:
    rp = (root_path or "").strip()
    if rp and Path(rp).is_dir():
        return rp
    ws = config.get("workspace_path", "") or ""
    if ws and Path(ws).is_dir():
        return ws
    return str(Path(__file__).resolve().parent)


@mcp.tool()
def ogma_project_overview(root_path: str = "") -> str:
    """Proje genel resmi: dosya/klasor/satir sayisi, diller, alt-sistemler, giris noktalari."""
    with _quiet_stdout():
        from core.architecture_scanner import ArchitectureScanner
        from core.araclar import collect_py_files
        root = _root(root_path)
        scanner = ArchitectureScanner(root, ["Python_Ortami", "__pycache__",
                                             "models", "libs", "storage", ".ogma_cache"])
        m = scanner.scan()
        lines = [f"Proje: {m.root_name} ({m.root_path})",
                 f"Boyut: {m.total_files} dosya, {m.total_folders} klasor, {m.total_lines} satir",
                 "Diller: " + ", ".join(f"{k}({v})" for k, v in
                                        sorted(m.languages.items(), key=lambda x: -x[1])),
                 "Alt-sistemler: " + ", ".join(
                     f"{f.name}({f.child_count} dosya/{f.total_lines} satir)"
                     for f in sorted(m.development_folders, key=lambda x: -x.total_lines)),
                 "Kok dosyalar: " + ", ".join(sorted(f.name for f in m.root_files))]
        return "\n".join(lines)


@mcp.tool()
def ogma_find_symbol(symbol: str, root_path: str = "") -> str:
    """Sembol ara: sinif/fonksiyon/metod -> dosya:satir. Duplicate kontrolu icin once bunu kullan."""
    with _quiet_stdout():
        from core.araclar import collect_py_files, find_symbol, format_find
        root = _root(root_path)
        result = find_symbol(root, collect_py_files(root), symbol)
        return format_find(result)


@mcp.tool()
def ogma_file_outline(file_path: str, root_path: str = "") -> str:
    """Dosya anahati: sinif/fonksiyon/metod haritasi imzalarla + satir araliklari. Kodu okumadan once haritaya bak."""
    with _quiet_stdout():
        from core.araclar import file_outline, format_outline, collect_py_files
        root = _root(root_path)
        rel = file_path.replace("\\", "/").strip()
        if not (root / rel).exists():
            matches = [p for p in collect_py_files(root) if p.endswith("/" + rel)]
            if matches:
                rel = matches[0]
        return format_outline(file_outline(root, rel))


@mcp.tool()
def ogma_impact_analysis(file_path: str, root_path: str = "") -> str:
    """Cok seviyeli etki analizi: bu dosyayi degistirirsem kim etkilenir?
    Seviye 1 dogrudan, seviye 2+ dolayli, etkilenen testler, risk (HIGH/MEDIUM/LOW)."""
    with _quiet_stdout():
        from core.araclar import (collect_py_files, impact_analysis_v2,
                                  format_impact_v2)
        root = _root(root_path)
        result = impact_analysis_v2(root, collect_py_files(root), file_path)
        return format_impact_v2(result)


@mcp.tool()
def ogma_dead_code(root_path: str = "") -> str:
    """Olu kodlar: proje-geneli cagri grafiyle hicbir yerden cagrilmayan
    fonksiyonlar + kullanilmayan import'lar (dosya bazli)."""
    with _quiet_stdout():
        from core.araclar import collect_py_files
        from core.analysis_engine import AnalysisEngine
        from core.architecture_scanner import ArchitectureScanner
        root = _root(root_path)
        scanner = ArchitectureScanner(root, ["Python_Ortami", "__pycache__",
                                             "models", "libs", "storage", ".ogma_cache"])
        m = scanner.scan()
        engine = AnalysisEngine(None, "mcp")
        return engine._chunked_dead_code(m, scanner)


@mcp.tool()
def ogma_quality_summary(root_path: str = "") -> str:
    """Kalite + guvenlik ozeti: ortalama skor, kritik sorunlar, guvenlik riskleri,
    en dusuk skorlu dosyalar (refactoring adaylari)."""
    with _quiet_stdout():
        from core.araclar import collect_py_files
        from core.kalite_analizi import run_quality_analysis
        root = _root(root_path)
        data = run_quality_analysis(root, collect_py_files(root))
        s = data["summary"]
        lines = [f"Kalite ozeti: {s['dosya_sayisi']} dosya, "
                 f"ortalama {s['ortalama_skor']}/40, "
                 f"sorun {s['sorun_sayisi']} (kritik {s['kritik_sorun']})"]
        sec = [(rel, x) for rel, v in data["by_file"].items() for x in v["security"]]
        if sec:
            lines.append("GUVENLIK RISKLERI:")
            for rel, x in sec[:15]:
                lines.append(f"  [{x['seviye'].upper()}] {rel}:{x['satir']} — {x['aciklama']}")
        else:
            lines.append("Guvenlik riski: yok")
        if s.get("en_dusuk_skorlu"):
            lines.append("En dusuk skorlular:")
            for d in s["en_dusuk_skorlu"]:
                lines.append(f"  - {d['dosya']}: {d['skor']}/40")
        return "\n".join(lines)


@mcp.tool()
def ogma_dependencies(root_path: str = "") -> str:
    """Bagimlilik grafi ozeti: donguler (dairesel import — KRITIK), en cok
    bagimli olunan dosyalar (etki riski), alt-sistem matrisi."""
    with _quiet_stdout():
        from core.araclar import collect_py_files
        from core.bagimlilik_analizi import run_dependency_analysis
        root = _root(root_path)
        data = run_dependency_analysis(root, collect_py_files(root))
        st = data["stats"]
        lines = [f"Bagimliliklar: {st['modul_sayisi']} modul, "
                 f"{st['bagimlilik_kenari']} kenar, "
                 f"{st['dongu_sayisi']} DONGU (dairesel import)"]
        if data["cycles"]:
            lines.append("DONGULER (KRITIK):")
            for i, cyc in enumerate(data["cycles"], 1):
                lines.append(f"  {i}. {' <-> '.join(cyc)}")
        depended = st.get("en_cok_bagimli_olunan", [])
        if depended:
            lines.append("En cok bagimli olunan:")
            for d in depended:
                lines.append(f"  - {d['dosya']}: {d['kim_import_ediyor']} dosya")
        return "\n".join(lines)


@mcp.tool()
def ogma_hafiza_timeline(root_path: str = "") -> str:
    """Mimari hafiza: tarama gecmisi zaman cizelgesi — proje nasil gelisti
    (dosya/satir/dongu/kalite degisimi)."""
    with _quiet_stdout():
        from core.hafiza import load_history, generate_timeline
        root = _root(root_path)
        _data, text = generate_timeline(load_history(root))
        return text


@mcp.tool()
def ogma_usage_validation(root_path: str = "") -> str:
    """Kullanim dogrulama: requirements.txt/pyproject'ta beyan edilen paketler
    vs gercek importlar (kullanilmayan adaylar, beyan edilmemis importlar)."""
    with _quiet_stdout():
        from core.araclar import collect_py_files
        from core.kullanim_dogrulama import validate_usage
        import re as _re
        root = _root(root_path)
        imports = set()
        for rel in collect_py_files(root):
            try:
                src = (Path(root) / rel).read_text(encoding="utf-8", errors="ignore")
                imports |= set(_re.findall(
                    r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)",
                    src, _re.MULTILINE))
            except Exception:
                continue
        local = {p.split("/")[0] for p in collect_py_files(root) if "/" in p}
        u = validate_usage(root, imports, local)
        lines = [f"Beyan edilen paket: {len(u['beyan_edilen'])}"]
        if u["kullanilmayan_adaylar"]:
            lines.append("KULLANILMAYAN ADAYLAR: " + ", ".join(u["kullanilmayan_adaylar"]))
        if u["beyan_edilmeyen_importlar"]:
            lines.append("BEYAN EDILMEMIS IMPORTLAR: " + ", ".join(
                u["beyan_edilmeyen_importlar"]))
        if not u["kullanilmayan_adaylar"] and not u["beyan_edilmeyen_importlar"]:
            lines.append("Tutarli: kullanilmayan/beyan edilmemis yok")
        return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()  # stdio — Cline/VSCode/OpenCode standarti
