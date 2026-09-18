"""kb_raporlari.py - KB tarzi .md raporlari (devkit reports/generate port).

Cikti: kb/ klasoru altina:
  QUICKREF.md      — 2 dakikalik genel resim
  PROJECT_MAP.md   — tam proje haritasi (klasor/dosya/satir)
  SYMBOL_INDEX.md  — sembol indeksi (sinif/fonksiyon -> dosya:satir)
  ARCHITECTURE.md  — bagimlilik matrisi + donguler + cagri grafi + kalite

Hepsi deterministik; veri yoksa ilgili bolum zarifce atlanir.
"""
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def _header(title: str, arch_map) -> List[str]:
    return [f"# {title}", "",
            f"**Proje:** {arch_map.root_name}",
            f"**Yol:** {arch_map.root_path}",
            f"**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ""]


def _gen_quickref(arch_map, data: dict) -> str:
    lines = _header("QUICKREF — Genel Resim", arch_map)
    lines.append("## Boyut")
    lines.append("")
    lines.append(f"- **{arch_map.total_files}** dosya, **{arch_map.total_folders}** klasor, "
                 f"**{arch_map.total_lines}** satir kod")
    lines.append("")

    lines.append("## Diller")
    lines.append("")
    for lang, count in sorted(arch_map.languages.items(), key=lambda x: -x[1]):
        lines.append(f"- {lang}: {count} dosya")
    lines.append("")

    lines.append("## Alt-Sistemler (gelistirme klasorleri)")
    lines.append("")
    lines.append("| Klasor | Dosya | Satir |")
    lines.append("|--------|-------|-------|")
    for folder in sorted(arch_map.development_folders, key=lambda x: -x.total_lines):
        lines.append(f"| {folder.name} | {folder.child_count} | {folder.total_lines} |")
    lines.append("")

    if arch_map.root_files:
        lines.append("## Giris Noktalari (kok dosyalar)")
        lines.append("")
        for f in sorted(arch_map.root_files, key=lambda x: x.name.lower()):
            lang = f" [{f.language}]" if f.language else ""
            lines.append(f"- `{f.name}`{lang}")
        lines.append("")

    # Kalite ozeti (varsa)
    quality = data.get("quality")
    if quality and quality.get("summary"):
        s = quality["summary"]
        lines.append("## Kalite Ozeti")
        lines.append("")
        lines.append(f"- Ortalama skor: **{s['ortalama_skor']}/40** | "
                     f"Sorun: {s['sorun_sayisi']} (kritik: {s['kritik_sorun']})")
        lines.append("")

    # Donguler (varsa)
    deps = data.get("deps")
    if deps and deps.get("cycles") is not None:
        n = len(deps["cycles"])
        lines.append("## Dairesel Import (Dongu)")
        lines.append("")
        if n:
            lines.append(f"**{n} dongu tespit edildi** — detay: ARCHITECTURE.md")
        else:
            lines.append("Yok")
        lines.append("")

    lines.append("---")
    lines.append("*Bu rapor Ogma tarafindan otomatik uretildi.*")
    return "\n".join(lines)


def _gen_project_map(arch_map, data: dict) -> str:
    lines = _header("PROJECT MAP — Tam Proje Haritasi", arch_map)
    lines.append("```")
    lines.append(f"{arch_map.root_name}/")

    def render(node_children, indent):
        out = []
        dirs = [c for c in node_children if c.node_type.value in ("dev_folder", "folder")]
        files = [c for c in node_children if c.node_type.value == "file"]
        for d in sorted(dirs, key=lambda x: x.name.lower()):
            out.append(f"{indent}|-- {d.name}/  ({d.child_count} dosya, {d.total_lines} satir)")
            out.extend(render(d.children, indent + "|   "))
        for f in sorted(files, key=lambda x: x.name.lower()):
            lang = f" [{f.language}]" if f.language else ""
            lines_info = f", {f.line_count} satir" if f.line_count else ""
            out.append(f"{indent}|-- {f.name}{lang}{lines_info}")
        return out

    lines.extend(render([f for f in arch_map.root_files], ""))
    for folder in sorted(arch_map.development_folders, key=lambda x: x.name.lower()):
        lines.append(f"|-- {folder.name}/  ({folder.child_count} dosya, {folder.total_lines} satir)")
        lines.extend(render(folder.children, "|   "))
    lines.append("```")
    lines.append("")

    if arch_map.system_folders:
        lines.append("## Atlanan Sistem Klasorleri")
        lines.append("")
        for f in arch_map.system_folders:
            lines.append(f"- {f.name} ({f.child_count} dosya)")
        lines.append("")

    lines.append("---")
    lines.append("*Bu rapor Ogma tarafindan otomatik uretildi.*")
    return "\n".join(lines)


def _gen_symbol_index(arch_map, data: dict) -> str:
    lines = _header("SYMBOL INDEX — Sembol Indeksi", arch_map)
    api = data.get("api")
    if not api or not api.get("subsystems"):
        lines.append("(API yuzeyi verisi yok — Mimari Harita analizini calistirin)")
        return "\n".join(lines)

    total = api.get("stats", {})
    lines.append(f"**{total.get('classes', 0)}** sinif, **{total.get('functions', 0)}** fonksiyon "
                 f"(**{total.get('files', 0)}** dosya)")
    lines.append("")

    for sub, entry in sorted(api["subsystems"].items()):
        s = entry.get("stats", {})
        lines.append(f"## {sub} ({s.get('files', 0)} dosya, "
                     f"{s.get('classes', 0)} sinif, {s.get('functions', 0)} fonksiyon)")
        lines.append("")
        for rel, fdata in sorted(entry["files"].items()):
            classes = fdata.get("classes", [])
            funcs = fdata.get("functions", [])
            if not classes and not funcs:
                continue
            doc = fdata.get("doc", "")
            if doc:
                lines.append(f"### `{rel}`")
                lines.append(f"> {doc.splitlines()[0][:120]}")
            else:
                lines.append(f"### `{rel}`")
            lines.append("")
            for c in classes:
                lines.append(f"- **class {c['name']}** (satir {c['line']})")
                for m in c.get("methods", [])[:10]:
                    lines.append(f"  - `{m['name']}{m['sig']}` (satir {m['line']})")
            for f in funcs:
                lines.append(f"- `def {f['name']}{f['sig']}` (satir {f['line']})")
            lines.append("")

    lines.append("---")
    lines.append("*Bu rapor Ogma tarafindan otomatik uretildi.*")
    return "\n".join(lines)


def _gen_architecture(arch_map, data: dict) -> str:
    lines = _header("ARCHITECTURE — Bagimlilik, Cagri Grafi, Kalite", arch_map)

    deps = data.get("deps")
    if deps:
        stats = deps.get("stats", {})
        lines.append("## Bagimliliklar")
        lines.append("")
        lines.append(f"- Modul: {stats.get('modul_sayisi', 0)} | "
                     f"Kenar: {stats.get('bagimlilik_kenari', 0)} | "
                     f"Bagimsiz: {stats.get('bagimsiz_modul', 0)}")
        lines.append("")
        cycles = deps.get("cycles", [])
        lines.append("### Dairesel Import (Dongu)")
        lines.append("")
        if cycles:
            lines.append(f"**{len(cycles)} dongu tespit edildi:**")
            lines.append("")
            for i, cyc in enumerate(cycles, 1):
                lines.append(f"{i}. {' <-> '.join(f'`{c}`' for c in cyc)}")
        else:
            lines.append("Yok")
        lines.append("")
        depended = stats.get("en_cok_bagimli_olunan", [])
        if depended:
            lines.append("### En Cok Bagimli Olunan (etki riski)")
            lines.append("")
            for d in depended:
                lines.append(f"- `{d['dosya']}` — {d['kim_import_ediyor']} dosya import ediyor")
            lines.append("")

    cg = data.get("callgraph")
    if cg:
        cstats = cg.get("stats", {})
        lines.append("## Cagri Grafi / Olu Kod")
        lines.append("")
        lines.append(f"- Fonksiyon: {cstats.get('fonksiyon_sayisi', 0)} | "
                     f"Olu: {cstats.get('olu_fonksiyon', 0)}")
        dead = cg.get("project_dead", [])
        if dead:
            lines.append("")
            lines.append("**Olu fonksiyonlar (hicbir yerden cagrilmiyor):**")
            lines.append("")
            for d in dead[:20]:
                lines.append(f"- `{d['func']}` — {d['file']}:{d['line']}")
        lines.append("")

    quality = data.get("quality")
    if quality and quality.get("summary"):
        s = quality["summary"]
        lines.append("## Kalite")
        lines.append("")
        lines.append(f"- Ortalama skor: **{s['ortalama_skor']}/40** | "
                     f"Sorun: {s['sorun_sayisi']} (kritik: {s['kritik_sorun']})")
        worst = s.get("en_dusuk_skorlu", [])
        if worst:
            lines.append("")
            lines.append("**En dusuk skorlular (refactoring adaylari):**")
            lines.append("")
            for d in worst:
                lines.append(f"- `{d['dosya']}` — {d['skor']}/40")
        lines.append("")

    lines.append("---")
    lines.append("*Bu rapor Ogma tarafindan otomatik uretildi.*")
    return "\n".join(lines)


def generate_kb_reports(arch_map, data: Dict, out_dir: Path) -> List[str]:
    """kb/ klasorune .md raporlari yazar; yazilan dosya yollarini dondurur."""
    kb = Path(out_dir) / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    saved = []
    reports = [
        ("QUICKREF.md", _gen_quickref(arch_map, data)),
        ("PROJECT_MAP.md", _gen_project_map(arch_map, data)),
        ("SYMBOL_INDEX.md", _gen_symbol_index(arch_map, data)),
        ("ARCHITECTURE.md", _gen_architecture(arch_map, data)),
    ]
    for name, content in reports:
        p = kb / name
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        saved.append(str(p))
    return saved
