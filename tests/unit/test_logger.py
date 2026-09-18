"""Unit tests for core.logger (rotating logs + crash reporting)."""
import logging
import sys

from core.logger import get_logger, install_crash_handler, log_exception


class TestLogger:
    def test_get_logger_singleton(self):
        a = get_logger()
        b = get_logger()
        assert a is b
        assert isinstance(a, logging.Logger)

    def test_log_exception_writes_errors_log(self, tmp_path, monkeypatch):
        import logging as _logging
        import core.logger as logger_mod
        # Onceki testlerin handler'larini yalit (registry'de ayni logger nesnesi doner)
        reg = _logging.getLogger("ogma")
        old_handlers = reg.handlers[:]
        for h in old_handlers:
            reg.removeHandler(h)
        monkeypatch.setattr(logger_mod, "_log_dir", lambda: tmp_path)
        logger_mod._logger = None
        try:
            try:
                raise ValueError("test-hatasi-123")
            except ValueError:
                log_exception(*sys.exc_info(), context="test")
            content = (tmp_path / "ogma.log").read_text(encoding="utf-8")
            assert "test-hatasi-123" in content
            assert "ValueError" in content
        finally:
            for h in reg.handlers[:]:
                reg.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    pass
            for h in old_handlers:
                reg.addHandler(h)
            logger_mod._logger = None

    def test_install_crash_handler(self):
        old_hook = sys.excepthook
        install_crash_handler("test-ctx")
        assert sys.excepthook is not old_hook
        sys.excepthook = old_hook

    def test_log_rotation_config(self):
        from logging.handlers import RotatingFileHandler
        logger = get_logger()
        handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert handlers, "donen dosya handler yok"
        assert handlers[0].maxBytes == 1024 * 1024
        assert handlers[0].backupCount == 3
