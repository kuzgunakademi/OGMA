"""ast_cache.py - dosya icerik + AST parse onbellek (ayni surec icinde).

Tam tarama sirasinda ayni dosya bagimlilik/cagri/kalite/api analizleri
tarafindan 5+ kez okunup parse edilir; bu onbellek o tekrari bitirir.
Anahtar: (mutlak yol, mtime) — dosya degisirse onbellek gecersizlesir.
"""
import ast
import threading
from pathlib import Path
from typing import Optional, Tuple

_lock = threading.Lock()
_cache: dict = {}  # (abs_path, mtime_ns) -> (content, tree or None)
_hits = [0, 0]  # [hit, miss]


def get_content_and_tree(path) -> Tuple[Optional[str], Optional[ast.AST]]:
    """Dosya icerigini ve parse edilmis AST'sini dondur (onbellekli).

    Parse edilemeyen dosyalarda tree=None (sonuc onbelleklenir,
    tekrar denemez). Okunamayan dosyalarda (None, None).
    """
    p = Path(path)
    try:
        mtime = p.stat().st_mtime_ns
    except OSError:
        return None, None
    key = (str(p.resolve()), mtime)
    with _lock:
        if key in _cache:
            _hits[0] += 1
            return _cache[key]
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        with _lock:
            _cache[key] = (None, None)
        return None, None
    try:
        tree = ast.parse(content)
    except SyntaxError:
        tree = None
    with _lock:
        _cache[key] = (content, tree)
        _hits[1] += 1
    return content, tree


def stats() -> dict:
    with _lock:
        return {"hit": _hits[0], "miss": _hits[1], "entry": len(_cache)}


def clear():
    with _lock:
        _cache.clear()
        _hits[0] = 0
        _hits[1] = 0
