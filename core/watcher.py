"""watcher.py — dosya izleyici (E3): degisiklikleri yakalar, sadece
degisen dosyalari yeniden analiz eder (canli etki).

Polling tabanli (stdlib-only): her N saniyede fingerprint diff; degisiklik
varsa callback cagrilir. Tree-sitter yok — dosya-granuler tarama (A.9
cache + A.10 fingerprint ayni faydanin %90'ini verir).
"""
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core.fingerprint import (compute_fingerprints, load_fingerprint,
                              save_fingerprint, compute_diff)


class FileWatcher:
    """Polling tabanli dosya izleyici — degisen dosyalari yakalar."""

    def __init__(self, root_path: str, interval: int = 10,
                 callback: Optional[Callable] = None,
                 ignore: Optional[List[str]] = None):
        self.root_path = root_path
        self.interval = max(3, interval)
        self.callback = callback
        self.ignore = set(ignore or [])
        self._active = False
        self._thread: Optional[threading.Thread] = None
        self.last_diff: Optional[Dict] = None

    def _collect_py(self) -> List[str]:
        """.py dosyalarini topla (ignore edilen dizinlere girmeden)."""
        excluded = self.ignore | {".git", "__pycache__", ".venv", "venv", "env",
                                  "envs", "node_modules", "Python_Ortami",
                                  "libs", "models", ".ogma_cache", ".idea",
                                  ".vscode", "dist", "build", "site-packages",
                                  "miniconda", "java"}
        root = Path(self.root_path)
        result = []
        for kok, dirs, files in __import__("os").walk(str(root)):
            dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
            for f in files:
                if f.endswith(".py"):
                    try:
                        result.append(str(Path(kok, f).relative_to(root)).replace("\\", "/"))
                    except ValueError:
                        continue
        return sorted(result)

    def start(self):
        self._active = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._active = False
        if self._thread:
            self._thread.join(timeout=self.interval + 5)
            self._thread = None

    @property
    def is_active(self) -> bool:
        return self._active

    def check_once(self) -> Optional[Dict]:
        """Tek seferlik kontrol — degisiklik varsa diff dondurur."""
        py_files = self._collect_py()
        new_fp = compute_fingerprints(self.root_path, py_files)
        old_fp = load_fingerprint(self.root_path)
        diff = compute_diff(old_fp or {}, new_fp)
        save_fingerprint(self.root_path, new_fp)
        if diff["added"] or diff["deleted"] or diff["modified"]:
            self.last_diff = diff
            return diff
        return None

    def _loop(self):
        while self._active:
            try:
                diff = self.check_once()
                if diff and self.callback:
                    self.callback(diff)
            except Exception:
                pass
            for _ in range(self.interval):
                if not self._active:
                    break
                time.sleep(1)
