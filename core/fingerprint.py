"""fingerprint.py - dosya parmak izi + taramalar arasi degisiklik takibi.

Her full taramada dosya sha256'lari <scan_root>/.ogma_cache/fingerprint.json'a
yazilir; onceki taramayla karsilastirilarak eklenen/silinen/degisen dosyalar
raporlanir. Gizli klasor (.ogma_cache) tarayici tarafindan otomatik atlanir.
"""
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional


def cache_dir_for(scan_root: str) -> Path:
    return Path(scan_root) / ".ogma_cache"


def _fingerprint_path(scan_root: str) -> Path:
    return cache_dir_for(scan_root) / "fingerprint.json"


def compute_fingerprints(root_path: str, rel_paths: List[str]) -> Dict[str, str]:
    """Dosya sha256 parmak izleri (rel -> sha256)."""
    root = Path(root_path)
    fp: Dict[str, str] = {}
    for rel in sorted(set(p.replace("\\", "/") for p in rel_paths)):
        try:
            raw = (root / rel).read_bytes()
            fp[rel] = hashlib.sha256(raw).hexdigest()
        except Exception:
            continue
    return fp


def load_fingerprint(scan_root: str) -> Optional[Dict[str, str]]:
    p = _fingerprint_path(scan_root)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_fingerprint(scan_root: str, fp: Dict[str, str]) -> None:
    try:
        d = cache_dir_for(scan_root)
        d.mkdir(parents=True, exist_ok=True)
        _fingerprint_path(scan_root).write_text(
            json.dumps(fp, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def compute_diff(old: Dict[str, str], new: Dict[str, str]) -> Dict[str, List[str]]:
    """Iki parmak izi arasindaki fark."""
    old_keys = set(old or {})
    new_keys = set(new or {})
    added = sorted(new_keys - old_keys)
    deleted = sorted(old_keys - new_keys)
    modified = sorted(k for k in (old_keys & new_keys)
                      if old.get(k) != new.get(k))
    return {"added": added, "deleted": deleted, "modified": modified}
