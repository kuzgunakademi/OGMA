from pathlib import Path 
from typing import Tuple 
 
class Validators: 
    @staticmethod 
    def validate_api_key(api_key: str) -> Tuple[bool, str]:
        if not api_key or len(api_key) < 10: 
            return False, "API key çok kısa" 
        return True, "Geçerli API key" 
 
    @staticmethod 
    def validate_workspace_path(path_str: str) -> Tuple[bool, str]:
        try: 
            path = Path(path_str) 
            if not path.exists(): 
                return False, "Dizin mevcut değil" 
            if not path.is_dir(): 
                return False, "Geçerli bir dizin değil" 
            return True, "Geçerli dizin"
        except Exception as e:
            return False, f"Dizin kontrolü sırasında hata: {e}"