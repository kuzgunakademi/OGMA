import os
import shutil
from pathlib import Path
from typing import Optional
from utils.helpers import Console

class FileManager:
    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path).resolve()
        Console.info(f"Çalışma dizini: {self.workspace_path}")
    
    def read_file(self, file_path: str) -> Optional[str]:
        """Dosya oku"""
        try:
            full_path = self.workspace_path / file_path
            if not full_path.exists():
                Console.error(f"Dosya bulunamadı: {file_path}")
                return None
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            Console.error(f"Dosya okunamadı: {e}")
            return None
    
    def write_file(self, file_path: str, content: str) -> bool:
        """Dosyaya yaz"""
        try:
            full_path = self.workspace_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            Console.error(f"Dosya yazılamadı: {e}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """Dosya var mı kontrol et"""
        full_path = self.workspace_path / file_path
        return full_path.exists()
    
    def get_file_tree(self, max_depth: int = 3, excluded: tuple = ()) -> str:
        """Dosya ağacını oluştur (derinlik tavani + haric listesi uygulanir)."""
        try:
            tree = []
            excluded_set = set(excluded or [])

            def build_tree(directory: Path, prefix: str = "", depth: int = 0):
                if depth > max_depth:
                    return

                try:
                    entries = sorted(directory.iterdir())
                    for index, entry in enumerate(entries):
                        # Gizli ve haric tutulanlari atla
                        if entry.name.startswith('.') or entry.name in excluded_set:
                            continue

                        # ASCII baglaclar (Windows konsol kod sayfasiyla uyumlu)
                        connector = "`-- " if index == len(entries) - 1 else "|-- "

                        if entry.is_dir():
                            tree.append(f"{prefix}{connector}{entry.name}/")
                            extension = "    " if index == len(entries) - 1 else "|   "
                            build_tree(entry, prefix + extension, depth + 1)
                        else:
                            tree.append(f"{prefix}{connector}{entry.name}")
                except (PermissionError, OSError) as e:
                    tree.append(f"{prefix}└── [Erişim Engellendi: {e}]")
            
            tree.append(f"{self.workspace_path.name}/")
            build_tree(self.workspace_path)
            return "\n".join(tree)
        except Exception as e:
            return f"Dosya ağacı oluşturulamadı: {e}"
    
    def delete_file(self, file_path: str) -> bool:
        """Dosya sil"""
        try:
            full_path = self.workspace_path / file_path
            if full_path.exists():
                if full_path.is_file():
                    full_path.unlink()
                else:
                    shutil.rmtree(full_path)
                return True
            return False
        except Exception as e:
            Console.error(f"Dosya silinemedi: {e}")
            return False
    
    def create_directory(self, dir_path: str) -> bool:
        """Klasör oluştur"""
        try:
            full_path = self.workspace_path / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            Console.error(f"Klasör oluşturulamadı: {e}")
            return False
    
    def rename_file(self, old_path: str, new_path: str) -> bool:
        """Dosya/Klasör yeniden adlandır"""
        try:
            old_full = self.workspace_path / old_path
            new_full = self.workspace_path / new_path
            
            if old_full.exists():
                old_full.rename(new_full)
                return True
            return False
        except Exception as e:
            Console.error(f"Yeniden adlandırılamadı: {e}")
            return False