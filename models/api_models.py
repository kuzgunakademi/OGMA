from dataclasses import dataclass
from typing import List, Optional
from enum import Enum


class ModelType(Enum):
    CHAT = "chat"
    CODE = "code"
    MULTIMODAL = "multimodal"


class BackendType(Enum):
    DEEPSEEK = "deepseek"
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"


@dataclass
class DeepSeekModel:
    id: str
    name: str
    type: ModelType
    description: str
    max_tokens: int
    context_window: int
    backend: BackendType = BackendType.DEEPSEEK


class AvailableModels:
    MODELS = [
        DeepSeekModel(
            id="deepseek-chat",
            name="DeepSeek Chat",
            type=ModelType.CHAT,
            description="Ana sohbet modeli",
            max_tokens=4096,
            context_window=32768,
        ),
        DeepSeekModel(
            id="deepseek-coder",
            name="DeepSeek Coder",
            type=ModelType.CODE,
            description="Kodlama odakli model",
            max_tokens=4096,
            context_window=32768,
        ),
        DeepSeekModel(
            id="deepseek-v2",
            name="DeepSeek V2",
            type=ModelType.CHAT,
            description="Gelismis sohbet modeli",
            max_tokens=8192,
            context_window=65536,
        ),
        DeepSeekModel(
            id="deepseek-v2-lite",
            name="DeepSeek V2 Lite",
            type=ModelType.CHAT,
            description="Hafif sohbet modeli",
            max_tokens=4096,
            context_window=32768,
        ),
    ]

    # Populer Ollama modelleri (kullanici bunlari ollama pull ile indirebilir)
    OLLAMA_MODELS = [
        DeepSeekModel(
            id="deepseek-r1:8b",
            name="DeepSeek R1 8B (Ollama)",
            type=ModelType.CHAT,
            description="Yerel - DeepSeek R1 8B parametre",
            max_tokens=4096,
            context_window=32768,
            backend=BackendType.OLLAMA,
        ),
        DeepSeekModel(
            id="deepseek-r1:14b",
            name="DeepSeek R1 14B (Ollama)",
            type=ModelType.CHAT,
            description="Yerel - DeepSeek R1 14B parametre",
            max_tokens=4096,
            context_window=32768,
            backend=BackendType.OLLAMA,
        ),
        DeepSeekModel(
            id="deepseek-coder-v2:16b",
            name="DeepSeek Coder V2 16B (Ollama)",
            type=ModelType.CODE,
            description="Yerel - Kodlama odakli 16B",
            max_tokens=4096,
            context_window=32768,
            backend=BackendType.OLLAMA,
        ),
        DeepSeekModel(
            id="qwen2.5-coder:7b",
            name="Qwen 2.5 Coder 7B (Ollama)",
            type=ModelType.CODE,
            description="Yerel - Qwen kodlama modeli",
            max_tokens=4096,
            context_window=32768,
            backend=BackendType.OLLAMA,
        ),
        DeepSeekModel(
            id="qwen2.5:7b",
            name="Qwen 2.5 7B (Ollama)",
            type=ModelType.CHAT,
            description="Yerel - Qwen genel sohbet",
            max_tokens=4096,
            context_window=32768,
            backend=BackendType.OLLAMA,
        ),
        DeepSeekModel(
            id="llama3.1:8b",
            name="Llama 3.1 8B (Ollama)",
            type=ModelType.CHAT,
            description="Yerel - Meta Llama 3.1",
            max_tokens=4096,
            context_window=131072,
            backend=BackendType.OLLAMA,
        ),
        DeepSeekModel(
            id="codellama:13b",
            name="Code Llama 13B (Ollama)",
            type=ModelType.CODE,
            description="Yerel - Kodlama odakli Llama",
            max_tokens=4096,
            context_window=16384,
            backend=BackendType.OLLAMA,
        ),
        DeepSeekModel(
            id="mistral:7b",
            name="Mistral 7B (Ollama)",
            type=ModelType.CHAT,
            description="Yerel - Mistral genel model",
            max_tokens=4096,
            context_window=32768,
            backend=BackendType.OLLAMA,
        ),
    ]

    @classmethod
    def get_model_ids(cls) -> List[str]:
        return [model.id for model in cls.MODELS]

    @classmethod
    def get_model_by_id(cls, model_id: str) -> Optional[DeepSeekModel]:
        for model in cls.MODELS:
            if model.id == model_id:
                return model
        return None

    @classmethod
    def get_all_models(cls, include_ollama: bool = False) -> List[DeepSeekModel]:
        models = list(cls.MODELS)
        if include_ollama:
            models.extend(cls.OLLAMA_MODELS)
        return models

    @classmethod
    def get_models_by_backend(cls, backend: BackendType) -> List[DeepSeekModel]:
        return [m for m in cls.get_all_models(include_ollama=True) if m.backend == backend]
