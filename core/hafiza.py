"""hafiza.py - mimari hafiza: tarama gecmisi + zaman cizelgesi (D3).

Her full tarama kaydi <scan_root>/.ogma_cache/history.json'a eklenir;
zaman cizelgesi raporu projenin nasil gelistigini gosterir (v1->v2->v3).
Ogma boylece "su an kod ne durumda" yaninda "bu proje nasil bu hale
geldi" bilgisine de sahip olur; LLM'e de bu gecmis verilebilir.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

HISTORY_FILE = "history.json"
MAX_RECORDS = 100


def _history_path(scan_root: str) -> Path:
    return Path(scan_root) / ".ogma_cache" / HISTORY_FILE


def record_scan(scan_root: str, record: Dict) -> None:
    """Tarama kaydini gecmise ekle (en fazla MAX_RECORDS tutulur)."""
    try:
        history = load_history(scan_root)
        history.append(record)
        history = history[-MAX_RECORDS:]
        p = _history_path(scan_root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(history, indent=2, ensure_ascii=False),
                     encoding="utf-8")
    except Exception:
        pass


def load_history(scan_root: str) -> List[Dict]:
    p = _history_path(scan_root)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def build_record(arch_map, results: Dict) -> Dict:
    """Mevcut taramadan gecmis kaydi olustur (sonuclar opsiyonel)."""
    from datetime import datetime
    record: Dict = {
        "tarih": datetime.now().isoformat(timespec="seconds"),
        "dosya": arch_map.total_files,
        "klasor": arch_map.total_folders,
        "satir": arch_map.total_lines,
        "diller": dict(arch_map.languages or {}),
    }
    from core.analysis_engine import AnalysisType

    deps = results.get(AnalysisType.DEPENDENCIES)
    if deps and getattr(deps, "data", None):
        record["dongu_sayisi"] = len(deps.data.get("cycles", []))

    dead = results.get(AnalysisType.DEAD_CODE)
    if dead and getattr(dead, "data", None):
        record["olu_fonksiyon"] = dead.data.get("stats", {}).get("olu_fonksiyon", 0)

    quality = results.get(AnalysisType.QUALITY)
    if quality and getattr(quality, "data", None):
        s = quality.data.get("summary", {})
        record["ortalama_skor"] = s.get("ortalama_skor", 0)
        record["kritik_sorun"] = s.get("kritik_sorun", 0)

    # degisiklik ozeti (A.10 diff'i ARCHITECTURE_MAP result.data'sinda)
    arch = results.get(AnalysisType.ARCHITECTURE_MAP)
    arch_data = getattr(arch, "data", None) or {}
    diff = arch_data.get("degisiklikler")
    if diff:
        record["degisiklik"] = {
            "eklenen": len(diff.get("added", [])),
            "silinen": len(diff.get("deleted", [])),
            "degisen": len(diff.get("modified", [])),
        }
    return record


def generate_timeline(history: List[Dict]) -> Tuple[Optional[dict], str]:
    """Zaman cizelgesi raporu: proje nasil gelisti.

    Donus: (ham_veri, metin_rapor). Tek kayit varsa baz kayit mesaji.
    """
    if not history:
        return None, "MIMARI HAFIZA: Gecmis kayit yok (ilk tarama sonrasi olusur)."

    data = {"kayit_sayisi": len(history), "kayitlar": history}
    lines = ["MIMARI HAFIZA — PROJE ZAMAN CIZELGESI", "=" * 50, ""]
    lines.append(f"Kayit sayisi: {len(history)}")
    lines.append("")

    header = (f"{'Tarih':<20}{'Dosya':>6}{'Satir':>7}{'Dongu':>7}"
              f"{'Olu':>5}{'Skor':>7}{'Degisim':>16}")
    lines.append(header)
    lines.append("-" * len(header))
    prev: Optional[Dict] = None
    for rec in history:
        dongu = str(rec.get("dongu_sayisi", "-"))
        olu = str(rec.get("olu_fonksiyon", "-"))
        skor = str(rec.get("ortalama_skor", "-"))
        ch = rec.get("degisiklik")
        if ch:
            ch_txt = (f"+{ch['eklenen']}/-{ch['silinen']}/~{ch['degisen']}")
        elif prev is None:
            ch_txt = "(baz)"
        else:
            ch_txt = "-"
        lines.append(f"{rec.get('tarih', '?'):<20}"
                     f"{rec.get('dosya', 0):>6}"
                     f"{rec.get('satir', 0):>7}"
                     f"{dongu:>7}{olu:>5}{skor:>7}{ch_txt:>16}")
        prev = rec
    lines.append("")

    # Gelisim ozeti (ilk vs son kayit)
    first, last = history[0], history[-1]
    if len(history) > 1:
        d_files = last.get("dosya", 0) - first.get("dosya", 0)
        d_lines = last.get("satir", 0) - first.get("satir", 0)
        lines.append("GELISIM OZETI (ilk kayittan bu yana):")
        lines.append(f"  Dosya: {first.get('dosya', 0)} -> {last.get('dosya', 0)} "
                     f"({d_files:+d})")
        lines.append(f"  Satir: {first.get('satir', 0)} -> {last.get('satir', 0)} "
                     f"({d_lines:+d})")
        if "ortalama_skor" in last and "ortalama_skor" in first:
            lines.append(f"  Kalite: {first['ortalama_skor']} -> "
                         f"{last['ortalama_skor']}")
        lines.append("")
        lines.append("Not: Bu gecmis LLM'e baglam olarak verilebilir; "
                     "model projeyi her seferinde sifirdan anlamak zorunda kalmaz.")

    return data, "\n".join(lines)
