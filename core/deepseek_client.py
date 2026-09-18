import requests
from typing import List, Optional, Dict
from core.base_client import BaseLLMClient
from models.api_models import AvailableModels
from utils.helpers import Console


class DeepSeekClient(BaseLLMClient):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def get_backend_name(self) -> str:
        return "deepseek"

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/models", headers=self.headers, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def get_available_models(self) -> List:
        try:
            try:
                response = requests.get(
                    f"{self.base_url}/models",
                    headers=self.headers,
                    timeout=10,
                )
                if response.status_code == 200:
                    models_data = response.json()
                    available_models = []
                    for model_data in models_data.get("data", []):
                        available_models.append(model_data["id"])
                    Console.info(f"API'den {len(available_models)} model alindi")

                    matched_models = []
                    for available_id in available_models:
                        for model in AvailableModels.MODELS:
                            if model.id == available_id:
                                matched_models.append(model)

                    return matched_models if matched_models else AvailableModels.MODELS
            except Exception as e:
                Console.warning(f"API'den model listesi alinamadi, yerel liste kullaniliyor: {e}")

            return AvailableModels.MODELS

        except Exception as e:
            Console.warning(f"Model listesi alinamadi: {e}")
            return AvailableModels.MODELS

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        repeat_penalty: float = 1.0,
    ) -> Optional[str]:
        try:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            # OpenAI uyumlu API repeat_penalty bilmez; esdegeri frequency_penalty.
            if repeat_penalty and repeat_penalty > 1.0:
                payload["frequency_penalty"] = min(2.0, (repeat_penalty - 1.0) * 2.0)

            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                Console.error(f"API Hatasi: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            Console.error("API istegi zaman asimina ugradi!")
            return None
        except requests.exceptions.ConnectionError:
            Console.error("API'ye baglanilamadi! Internet baglantinizi kontrol edin.")
            return None
        except Exception as e:
            Console.error(f"API istegi sirasinda hata: {e}")
            return None
