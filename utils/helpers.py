import colorama

colorama.init(strip=False, convert=False)

class Console:
    @staticmethod
    def success(message: str) -> None:
        print(f"[OK] {message}")
    
    @staticmethod
    def error(message: str) -> None:
        print(f"[ERROR] {message}")
    
    @staticmethod
    def warning(message: str) -> None:
        print(f"[WARNING] {message}")
    
    @staticmethod
    def info(message: str) -> None:
        print(f"[INFO] {message}")
    
    @staticmethod
    def prompt(message: str) -> str:
        return input(f"[PROMPT] {message}")