"""Integration tests for the full analysis pipeline."""
import os
import pytest
import tempfile
import asyncio
from pathlib import Path

from core.hybrid_analyzer import HybridAnalysisEngine, AnalysisMode
from core.architecture_scanner import ArchitectureScanner


class TestHybridAnalyzer:
    """Integration tests for the hybrid analyzer."""

    @pytest.mark.asyncio
    async def test_hybrid_analyzer_modes(self):
        """Test hybrid analyzer initializes in each mode."""
        for mode in (AnalysisMode.HYBRID, AnalysisMode.AST_ONLY, AnalysisMode.LLM_ONLY):
            hybrid = HybridAnalysisEngine(None, mode)
            assert hybrid.mode is mode
            assert hybrid.cancelled is False

    @pytest.mark.asyncio
    async def test_full_analysis_pipeline(self):
        """Test the full analysis pipeline on a sample project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a sample project
            (Path(tmpdir) / "main.py").write_text("""
import os
import json

def process_data(data):
    return [x * 2 for x in data]

class DataProcessor:
    def __init__(self):
        self.data = []
    
    def process(self, items):
        return [self.process_item(item) for item in items]
    
    def process_item(self, item):
        return item * 2

def main():
    processor = DataProcessor()
    result = processor.process([1, 2, 3, 4, 5])
    print(result)

if __name__ == "__main__":
    main()
""")
            
            (Path(tmpdir) / "config.py").write_text("""
CONFIG = {
    'debug': True,
    'max_workers': 4,
}
""")

            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()
            
            assert arch_map.total_files >= 1
            assert arch_map.total_lines > 0
            
            # Test hybrid analyzer initialization
            hybrid = HybridAnalysisEngine(None, AnalysisMode.AST_ONLY)
            assert hybrid.mode is AnalysisMode.AST_ONLY

            # Note: Full LLM analysis requires a model running;
            # this test only verifies the pipeline initializes correctly


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_directory(self):
        """Test scanning an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()
            
            assert arch_map.total_files == 0
            assert arch_map.total_folders == 0

    def test_symlinks_handled(self):
        """Test that symlinks are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            # Create a symlink (might fail on Windows without admin)
            try:
                os.symlink("main.py", Path(tmpdir) / "link.py")
            except (OSError, NotImplementedError):
                pass  # Symlinks may not work on Windows

            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()
            assert arch_map.total_files >= 1

    def test_unicode_filenames(self):
        """Test handling of unicode filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "测试.py").write_text("# 测试", encoding="utf-8")
            (Path(tmpdir) / "файл.py").write_text("# тест", encoding="utf-8")
            
            scanner = ArchitectureScanner(tmpdir, [])
            arch_map = scanner.scan()
            
            assert arch_map.total_files >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])