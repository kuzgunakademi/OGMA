from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any


class BaseLLMClient(ABC):
    """Tum LLM istemcileri icin soyut sinif.
    DeepSeek API, Ollama ve llama-cpp-python hepsi bu arayuzu uygular."""

    @abstractmethod
    def get_available_models(self) -> List[Any]:
        pass

    @abstractmethod
    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        repeat_penalty: float = 1.0,
    ) -> Optional[str]:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Backend'in calisabilir durumda olup olmadigini kontrol et."""
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """Backend adini dondur (ornek: 'deepseek', 'ollama', 'llamacpp')."""
        pass
