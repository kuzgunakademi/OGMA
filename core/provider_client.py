"""provider_client.py — OpenAI-uyumlu genel provider client (E2).

Herhangi bir OpenAI-uyumlu API'ye baglanir (DeepSeek, Z.ai GLM, OpenRouter,
yerel vLLM/LM Studio, vs.): base_url + model + api_key tamamen ayarlardan
gelir. Deterministik analiz lokalde kalir; reasoning bu dis modellere
yonlendirilebilir.
"""
import requests
from typing import List, Optional, Dict

from core.base_client import BaseLLMClient
from utils.helpers import Console


class OpenAIProviderClient(BaseLLMClient):
    """OpenAI-uyumlu genel provider — endpoint/model/key ayarlardan gelir."""

    def __init__(self, name: str, base_url: str, model: str, api_key: str = ""):
        self.provider_name = name or "provider"
        self.model_name = model or "default"
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def get_backend_name(self) -> str:
        return f"provider:{self.provider_name}"

    def is_available(self) -> bool:
        if not self.base_url:
            return False
        try:
            r = requests.get(f"{self.base_url}/models",
                             headers=self.headers, timeout=5)
            return r.status_code == 200
        except Exception:
            # /models olmayabilir; chat denemesi olmadan da kullanilabilir
            return bool(self.base_url)

    def get_available_models(self) -> List:
        try:
            r = requests.get(f"{self.base_url}/models",
                             headers=self.headers, timeout=10)
            if r.status_code == 200:
                return [m.get("id", "") for m in r.json().get("data", [])
                        if m.get("id")]
        except Exception:
            pass
        return [self.model_name]

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        repeat_penalty: float = 1.0,
    ) -> Optional[str]:
        if not self.base_url:
            Console.error("Provider base_url tanimli degil!")
            return None
        try:
            payload = {
                "model": model or self.model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            if repeat_penalty and repeat_penalty > 1.0:
                payload["frequency_penalty"] = min(2.0, (repeat_penalty - 1.0) * 2.0)

            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
                timeout=120,
            )
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            Console.error(f"Provider hatasi ({self.provider_name}): "
                          f"{response.status_code} — {response.text[:200]}")
            return None
        except requests.exceptions.Timeout:
            Console.error("Provider istegi zaman asimina ugradi!")
            return None
        except requests.exceptions.ConnectionError:
            Console.error(f"Provider'a baglanilamadi: {self.base_url}")
            return None
        except Exception as e:
            Console.error(f"Provider istegi hatasi: {e}")
            return None
