import json
from pathlib import Path


class Config:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.storage_dir = self.base_dir / "storage"
        self.storage_dir.mkdir(exist_ok=True)

        self.config_file = self.storage_dir / "config.json"
        self.session_file = self.storage_dir / "session_cache.json"

        self.default_config = {
            # DeepSeek API ayarlari
            "api_key": "",
            "selected_model": "deepseek-chat",
            # Yerel model ayarlari
            "backend": "deepseek",  # "deepseek" | "ollama" | "llamacpp"
            "ollama_url": "http://localhost:11434",
            "ollama_model": "deepseek-r1:8b",
            "llamacpp_model_path": "",
            "llamacpp_model_dir": "",
            "llamacpp_base_model": "",
            "hardware_checked": False,
            "llamacpp_n_ctx": 8192,
            "llamacpp_n_gpu_layers": 0,
            "llamacpp_n_threads": 8,
            "compute_mode": "cpu",
            "server_port": 8080,
            "providers": [],
            "active_provider": "",
            # Genel ayarlar
            "workspace_path": "",
            "profile_name": "Varsayilan",
            "profile_description": "",
            "profiles": {},
            "excluded_folders": [],
            "max_tokens": 1500,
            "temperature": 0.7,
            "auto_save_session": True,
            "max_file_tree_depth": 3,
            # Mimari analizci ayarlari
            "architecture_ignore_folders": [],
            "architecture_last_scan_root": "",
            "architecture_output_dir": "",
            "architecture_max_preview_chars": 3000,
            "architecture_max_files_per_call": 4,
        }
        self.load_config()

    def load_config(self):
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                    self.default_config.update(loaded_config)
        except Exception as e:
            print(f"Config yuklenirken hata: {e}")

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.default_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Config kaydedilemedi: {e}")

    def get(self, key: str, default=None):
        return self.default_config.get(key, default)

    def set(self, key: str, value):
        self.default_config[key] = value
        self.save_config()


config = Config()
