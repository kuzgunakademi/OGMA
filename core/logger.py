"""Merkezi loglama + crash reporting (stdlib only).

- storage/logs/ogma.log: donen log (1 MB x 3 yedek)
- storage/logs/errors.log: yakalanmamis hatalar (traceback + zaman)
- install_crash_handler(): sys.excepthook + threading.excepthook kurar
"""
import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _log_dir() -> Path:
    d = Path(__file__).resolve().parent.parent / "storage" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


_logger = None


def get_logger(name: str = "ogma") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    _logger = logging.getLogger(name)
    _logger.setLevel(logging.INFO)
    if not _logger.handlers:
        fh = RotatingFileHandler(
            str(_log_dir() / "ogma.log"),
            maxBytes=1024 * 1024, backupCount=3, encoding="utf-8",
        )
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        _logger.addHandler(fh)
    return _logger


def log_exception(exc_type, exc_value, exc_tb, context: str = "") -> None:
    """Yakalanmamis hatayi errors.log'a yaz (donen dosya)."""
    try:
        logger = get_logger()
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        if context:
            msg = f"[{context}] {msg}"
        logger.error("YAKALANMAMIS HATA:\n%s", msg)
    except Exception:
        pass


def install_crash_handler(context: str = "gui") -> None:
    """Tum yakalanmamis hatalari logla (thread'ler dahil)."""
    def _hook(exc_type, exc_value, exc_tb):
        log_exception(exc_type, exc_value, exc_tb, context)

    def _thread_hook(args):
        log_exception(args.exc_type, args.exc_value, args.exc_traceback,
                      context + ":thread")

    sys.excepthook = _hook
    try:
        threading.excepthook = _thread_hook
    except Exception:
        pass
