from pathlib import Path
from typing import List, Dict
from config.settings import config


class IgnoreManager:
    """Sistem klasörlerini algılar ve ignore listesini yönetir."""

    SYSTEM_FOLDER_PATTERNS = {
        ".git": "Versiyon kontrol sistemi",
        ".svn": "Versiyon kontrol sistemi",
        ".hg": "Versiyon kontrol sistemi",
        "__pycache__": "Python önbellek klasörü",
        ".pytest_cache": "Pytest önbellek",
        ".mypy_cache": "Mypy tip kontrol önbelleği",
        "node_modules": "Node.js bağımlılıkları",
        "bower_components": "Bower bağımlılıkları",
        ".venv": "Python sanal ortam",
        "venv": "Python sanal ortam",
        "env": "Python sanal ortam",
        ".env": "Ortam değişkenleri",
        "miniconda3": "Miniconda kurulum klasörü",
        "Miniconda3": "Miniconda kurulum klasörü",
        "Miniconda_Kurulum.exe": "Miniconda kurulum dosyası",
        "Python_Ortami": "Python ortamı klasörü",
        ".opencode": "OpenCode yapısı",
        ".cache": "Önbellek klasörü",
        "dist": "Dağıtım dosyaları",
        "build": "Derleme çıktıları",
        ".eggs": "Python egg dosyaları",
        ".idea": "JetBrains IDE yapısı",
        ".vscode": "VS Code yapısı",
        "site-packages": "Python paketleri",
        ".devkit": "Geliştirici araçları",
        ".eva_cache": "EVA önbelleği",
        "dll_backup": "DLL yedekleri",
        "java": "Java runtime",
    }

    SYSTEM_FILE_PATTERNS = {
        "*.pyc": "Python derlenmiş dosya",
        "*.pyo": "Python optimizasyon dosyası",
        "*.pyd": "Python DLL",
        "*.dll": "Windows kütüphanesi",
        "*.so": "Linux kütüphanesi",
        "*.exe": "Çalıştırılabilir dosya",
        "*.class": "Java derlenmiş dosya",
        "*.o": "C/C++ nesne dosyası",
        ".DS_Store": "macOS sistem dosyası",
        "Thumbs.db": "Windows küçük resim",
        "*.log": "Günlük dosyası",
        "*.tmp": "Geçici dosya",
    }

    def __init__(self):
        self.custom_ignore = config.get("architecture_ignore_folders", [])

    def get_system_folders(self, scan_root: Path) -> Dict[str, str]:
        """Tarama kökündeki sistem klasörlerini algıla.
        Returns: {klasör_adı: neden_string}
        """
        result = {}
        if not scan_root.exists():
            return result

        for item in scan_root.iterdir():
            if item.is_dir():
                name = item.name
                # Gizli klasörler
                if name.startswith("."):
                    result[name] = "Gizli klasör"
                    continue
                # Sistem klasörü kalıpları
                if name in self.SYSTEM_FOLDER_PATTERNS:
                    result[name] = self.SYSTEM_FOLDER_PATTERNS[name]
                    continue
                # Büyük klasör kontrolü (miniconda gibi)
                try:
                    file_count = sum(1 for _ in item.rglob("*") if _.is_file())
                    if file_count > 200:
                        result[name] = f"Sistem klasörü ({file_count}+ dosya)"
                except (PermissionError, OSError):
                    pass

        return result

    def get_ignore_list(self, scan_root: Path) -> tuple:
        """Taranacak ve atlanacak klasörlerin listesini döndür.
        Returns: (taranacak_klasörler, atlanacak_klasörler)
        """
        system_folders = self.get_system_folders(scan_root)
        all_folders = {}

        if not scan_root.exists():
            return [], []

        for item in scan_root.iterdir():
            if item.is_dir():
                name = item.name
                if name.startswith("."):
                    all_folders[name] = {"ignore": True, "reason": "Gizli klasör", "is_system": True}
                elif name in system_folders:
                    all_folders[name] = {"ignore": True, "reason": system_folders[name], "is_system": True}
                elif name in self.custom_ignore:
                    all_folders[name] = {"ignore": True, "reason": "Kullanıcı seçimi", "is_system": False}
                else:
                    all_folders[name] = {"ignore": False, "reason": "", "is_system": False}

        return all_folders

    def save_ignore_list(self, ignore_list: List[str]):
        """Kullanıcının seçtiği ignore listesini kaydet."""
        self.custom_ignore = ignore_list
        config.set("architecture_ignore_folders", ignore_list)

    def get_custom_ignore_list(self) -> List[str]:
        """Kayıtlı özel ignore listesini döndür."""
        return self.custom_ignore
