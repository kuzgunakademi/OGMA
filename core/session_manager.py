import json
from typing import List, Dict, Any
from config.settings import config
from utils.helpers import Console

class SessionManager:
    def __init__(self):
        self.session_file = config.session_file
        self.current_session = self.load_session()
    
    def load_session(self) -> Dict[str, Any]:
        """Oturumu yükle"""
        try:
            if self.session_file.exists():
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            Console.error(f"Oturum yüklenirken hata: {e}")
        
        return {
            "conversation_history": [],
            "file_operations": [],
            "workspace_context": ""
        }
    
    def save_session(self) -> None:
        """Oturumu kaydet"""
        try:
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_session, f, indent=2, ensure_ascii=False)
        except Exception as e:
            Console.error(f"Oturum kaydedilirken hata: {e}")
    
    def add_conversation(self, role: str, content: str, context: Dict[str, Any] = None) -> None:
        """Konuşma geçmişine ekle"""
        conversation = {
            "role": role,
            "content": content,
            "timestamp": self._get_timestamp(),
            "context": context or {}
        }
        
        self.current_session["conversation_history"].append(conversation)
        
        # Geçmişi sınırla (son 50 mesaj)
        if len(self.current_session["conversation_history"]) > 50:
            self.current_session["conversation_history"] = self.current_session["conversation_history"][-50:]
        
        if config.get("auto_save_session", True):
            self.save_session()
    
    def add_file_operation(self, operation: str, file_path: str, success: bool) -> None:
        """Dosya operasyonu kaydet"""
        file_op = {
            "operation": operation,
            "file_path": file_path,
            "success": success,
            "timestamp": self._get_timestamp()
        }
        
        self.current_session["file_operations"].append(file_op)
        
        # Dosya operasyonlarını sınırla (son 100 işlem)
        if len(self.current_session["file_operations"]) > 100:
            self.current_session["file_operations"] = self.current_session["file_operations"][-100:]
        
        if config.get("auto_save_session", True):
            self.save_session()
    
    def get_conversation_context(self) -> List[Dict[str, str]]:
        """Konuşma bağlamını hazırla"""
        history = self.current_session["conversation_history"][-10:]  # Son 10 mesaj
        return [{"role": msg["role"], "content": msg["content"]} for msg in history]
    
    def get_file_context(self) -> str:
        """Dosya operasyonları bağlamını hazırla"""
        recent_ops = self.current_session["file_operations"][-5:]  # Son 5 operasyon
        if not recent_ops:
            return ""
        
        context = "Son dosya operasyonları:\n"
        for op in recent_ops:
            status = "✓" if op["success"] else "✗"
            context += f"{status} {op['operation']}: {op['file_path']}\n"
        
        return context
    
    def clear_conversation_history(self) -> None:
        """Konuşma geçmişini temizle"""
        self.current_session["conversation_history"] = []
        self.save_session()
    
    def _get_timestamp(self) -> str:
        from datetime import datetime
        return datetime.now().isoformat()