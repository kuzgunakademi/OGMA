"""Unit tests for ArchitectureScanner."""
import pytest
import tempfile
import os
from pathlib import Path

from core.architecture_scanner import ArchitectureScanner, ArchitectureMap, FileNode, FileCategory, NodeType


class TestArchitectureScanner:
    """Test ArchitectureScanner functionality."""

    def test_scan_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()
            assert isinstance(arch_map, ArchitectureMap)
            assert arch_map.total_files == 0
            assert arch_map.total_folders == 0

    def test_scan_with_python_files(self):
        """Test scanning directory with Python files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            (Path(tmpdir) / "utils.py").write_text("def helper(): pass")
            os.makedirs(Path(tmpdir) / "subdir")
            (Path(tmpdir) / "subdir" / "module.py").write_text("class Foo: pass")

            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()

            assert arch_map.total_files >= 3
            assert any(f.name == "main.py" for f in arch_map.root_files)

    def test_ignore_directories(self):
        """Test that ignored directories are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            os.makedirs(Path(tmpdir) / "__pycache__")
            (Path(tmpdir) / "__pycache__" / "cache.pyc").write_text("")

            scanner = ArchitectureScanner(tmpdir, ["__pycache__"])
            arch_map = scanner.scan()

            # __pycache__ should be in system_folders or ignored
            assert not any(f.name == "__pycache__" for f in arch_map.development_folders)

    def test_file_categorization(self):
        """Test file categorization by extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            (Path(tmpdir) / "config.json").write_text("{}")
            (Path(tmpdir) / "README.md").write_text("# Readme")
            (Path(tmpdir) / "image.png").write_text("fake")

            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()

            categories = arch_map.file_categories
            assert "source" in categories
            assert "config" in categories
            assert "docs" in categories
            assert "asset" in categories or "unknown" in categories

    def test_root_files_collection(self):
        """Test that root files are collected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            (Path(tmpdir) / "config.json").write_text("{}")

            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()

            assert len(arch_map.root_files) >= 2
            names = {f.name for f in arch_map.root_files}
            assert "main.py" in names
            assert "config.json" in names


class TestFileNode:
    """Test FileNode dataclass."""

    def test_file_node_creation(self):
        """Test FileNode creation and attributes."""
        node = FileNode(
            name="test.py",
            path="test.py",
            absolute_path="/tmp/test.py",
            node_type=NodeType.FILE,
            category=FileCategory.SOURCE,
            language="Python",
            size_bytes=100,
            line_count=10,
        )

        assert node.name == "test.py"
        assert node.category == FileCategory.SOURCE
        assert node.language == "Python"
        assert node.line_count == 10
        assert node.size_bytes == 100


class TestArchitectureMap:
    """Test ArchitectureMap aggregation."""

    def test_aggregate_totals(self):
        """Test that totals are correctly aggregated."""
        # This would test the _aggregate_totals method
        pass


# ============================================================
# Integration Tests
# ============================================================

class TestFullAnalysisPipeline:
    """Integration tests for the full analysis pipeline."""

    def test_full_analysis_pipeline(self):
        """Test the full analysis pipeline on a sample project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sample project structure
            (Path(tmpdir) / "main.py").write_text("""
import os
import json

def main():
    print("Hello World")

if __name__ == "__main__":
    main()
""")
            (Path(tmpdir) / "config.py").write_text("CONFIG = {'debug': True}")

            from core.architecture_scanner import ArchitectureScanner
            from core.analysis_engine import AnalysisEngine
            from core.hybrid_analyzer import HybridAnalysisEngine, AnalysisMode

            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()

            assert arch_map.total_files >= 1
            assert arch_map.total_lines > 0

    def test_hybrid_analyzer_basic(self):
        """Test hybrid analyzer initialization."""
        from core.hybrid_analyzer import HybridAnalysisEngine, AnalysisMode

        hybrid = HybridAnalysisEngine(None, AnalysisMode.HYBRID)
        assert hybrid.mode is AnalysisMode.HYBRID
        assert hybrid.cancelled is False
        hybrid.cancel()
        assert hybrid.cancelled is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])