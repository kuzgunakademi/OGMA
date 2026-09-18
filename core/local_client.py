import os
import json
import requests
import socket
import subprocess
import time as _time
from pathlib import Path
from typing import List, Optional, Dict
from utils.helpers import Console


def _project_dir() -> Path:
    return Path(__file__).resolve().parent.parent


class OllamaClient:
    """Ollama uzerinden yerel model calistirir.
    Ollama OpenAI-uyumlu API sunar, dogrudan HTTP istekleri gondeririz."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def get_installed_models(self) -> List[str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code == 200:
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            Console.warning(f"Ollama model listesi alinamadi: {e}")
        return []

    def pull_model(self, model_name: str, callback=None) -> bool:
        """Ollama'ya model indirir (streaming)."""
        try:
            Console.info(f"Model indiriliyor: {model_name}...")
            r = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=600,
            )
            for line in r.iter_lines():
                if line:
                    progress = json.loads(line)
                    if callback:
                        callback(progress)
                    if "error" in progress:
                        Console.error(f"Indirme hatasi: {progress['error']}")
                        return False
            Console.success(f"Model indirildi: {model_name}")
            return True
        except Exception as e:
            Console.error(f"Model indirme hatasi: {e}")
            return False

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        repeat_penalty: float = 1.0,
    ) -> Optional[str]:
        try:
            options = {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
            if repeat_penalty and repeat_penalty > 1.0:
                options["repeat_penalty"] = repeat_penalty
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": options,
            }
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            if r.status_code == 200:
                return r.json().get("message", {}).get("content", "")
            else:
                Console.error(f"Ollama hatasi: {r.status_code} - {r.text[:200]}")
                return None
        except requests.exceptions.ConnectionError:
            Console.error("Ollama calismiyor! 'ollama serve' komutuyla baslatin.")
            return None
        except Exception as e:
            Console.error(f"Ollama isteigi hatasi: {e}")
            return None


class LlamaCppClient:
    """llama-cpp-python kutuphanesiyle GGUF dosyasini dogrudan yukler."""

    def __init__(self):
        self.model = None
        self.model_path = None

    def is_available(self) -> bool:
        try:
            import llama_cpp
            return True
        except ImportError:
            return False

    def load_model(
        self,
        gguf_path: str,
        n_ctx: int = 8192,
        n_gpu_layers: int = 0,
        n_threads: int = 8,
    ) -> bool:
        try:
            import llama_cpp

            if not os.path.exists(gguf_path):
                Console.error(f"GGUF dosyasi bulunamadi: {gguf_path}")
                return False

            if n_ctx > 8192:
                Console.warning(f"n_ctx ({n_ctx}) cok buyuk! 8192'ye dusuruldu.")
                n_ctx = 8192

            Console.info(f"Model yukleniyor: {gguf_path}")
            self.model = llama_cpp.Llama(
                model_path=gguf_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                n_threads=n_threads,
                verbose=False,
            )
            self.model_path = gguf_path
            self.n_ctx = n_ctx
            Console.success(f"Model yuklendi: {Path(gguf_path).name} (n_ctx={n_ctx})")
            return True
        except ImportError:
            Console.error("llama-cpp-python yuklu degil! pip install llama-cpp-python")
            return False
        except Exception as e:
            Console.error(f"Model yukleme hatasi: {e}")
            return False

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        repeat_penalty: float = 1.0,
    ) -> Optional[str]:
        if not self.model:
            Console.error("Model yuklenmedi! Once load_model() cagirin.")
            return None

        try:
            n_ctx = getattr(self, 'n_ctx', 8192)
            max_input_chars = (n_ctx - max_tokens) * 3

            truncated_messages = []
            for msg in messages:
                content = msg.get("content", "")
                if len(content) > max_input_chars:
                    content = content[:max_input_chars] + "\n\n... [ICERIK KISITLANDI] ..."
                    Console.warning(f"Girdi kisitlandi: {len(msg.get('content',''))} -> {max_input_chars} karakter")
                truncated_messages.append({"role": msg["role"], "content": content})

            result = self.model.create_chat_completion(
                messages=truncated_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                repeat_penalty=repeat_penalty,
            )
            return result["choices"][0]["message"]["content"]
        except AssertionError as e:
            Console.error(f"Context window asimi! n_ctx={n_ctx}, max_tokens={max_tokens}. Dosya cok buyuk olabilir.")
            return None
        except Exception as e:
            Console.error(f"llama-cpp hatasi: {e}")
            return None

    def unload_model(self):
        if self.model:
            del self.model
            self.model = None
            self.model_path = None
            Console.info("Model bellekten silindi.")


class LlamaServerClient:
    """Resmi llama.cpp server binary'sini (CUDA) alt surec olarak yonetir.

    Derleme gerektirmez, yonetici yetkisi gerektirmez: libs/ altindaki
    hazir binary calistirilir, OpenAI-uyumlu HTTP API ile konusulur.
    """

    SERVER_DIRS = {"cuda": ("llama-server-cuda",),
                   "vulkan": ("llama-server-vulkan",),
                   "auto": ("llama-server-cuda", "llama-server-vulkan",
                            "llama-server")}

    def __init__(self, port: int = 8080, host: str = "127.0.0.1",
                 flavor: str = "auto"):
        self.host = host
        self.port = port
        self.flavor = flavor  # "auto" | "cuda" | "vulkan"
        self.engine = ""  # calisan motor: "cuda" | "vulkan"
        self.proc = None
        self.model_path = None
        self.n_ctx = 8192
        self.log_path = ""

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @staticmethod
    def find_server_exe(flavor: str = "auto") -> str:
        libs = _project_dir() / "libs"
        for d in LlamaServerClient.SERVER_DIRS.get(
                flavor, LlamaServerClient.SERVER_DIRS["auto"]):
            exe = libs / d / "llama-server.exe"
            if exe.is_file():
                return str(exe)
        return ""

    def _resolve_exe(self) -> str:
        exe = self.find_server_exe(self.flavor)
        if exe:
            for flavor, dirs in self.SERVER_DIRS.items():
                if flavor == "auto":
                    continue
                if any(exe.replace("\\", "/").endswith(f"libs/{d}/llama-server.exe")
                       for d in dirs):
                    self.engine = flavor
                    break
        return exe

    def is_available(self) -> bool:
        return bool(self.find_server_exe())

    def is_running(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/health", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _free_port(start: int = 8080, tries: int = 12) -> int:
        for port in range(start, start + tries):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    continue  # dolu, sonrakini dene
            except OSError:
                return port
        return start

    def start(
        self,
        gguf_path: str,
        n_ctx: int = 8192,
        n_gpu_layers: int = 35,
        timeout: int = 180,
    ) -> bool:
        exe = self._resolve_exe()
        if not exe:
            Console.error("llama-server.exe bulunamadi (libs/ altinda olmali)!")
            return False
        if not os.path.exists(gguf_path):
            Console.error(f"GGUF dosyasi bulunamadi: {gguf_path}")
            return False

        # Ayni model zaten calisiyorsa yeniden baslatma
        if self.is_running() and self.model_path == gguf_path and self.proc:
            if self.proc.poll() is None:
                Console.info("GPU server zaten calisiyor, yeniden kullaniliyor.")
                return True
            self.stop()

        self.stop()
        self.port = self._free_port(self.port)

        creationflags = 0
        if os.name == "nt":
            try:
                creationflags = subprocess.CREATE_NO_WINDOW
            except Exception:
                creationflags = 0

        Console.info(f"GPU server baslatiliyor: {Path(gguf_path).name} "
                     f"(n_gpu_layers={n_gpu_layers})")
        try:
            log_dir = _project_dir() / "storage" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self.log_path = str(log_dir / "llama-server.log")
            log_file = open(self.log_path, "w", encoding="utf-8", errors="replace")
        except Exception:
            log_file = subprocess.DEVNULL
            self.log_path = ""
        try:
            self.proc = subprocess.Popen(
                [exe, "-m", gguf_path,
                 "--n-gpu-layers", str(n_gpu_layers),
                 "-c", str(min(n_ctx, 8192)),
                 "--port", str(self.port)],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
        except Exception as e:
            try:
                if log_file is not subprocess.DEVNULL:
                    log_file.close()
            except Exception:
                pass
            Console.error(f"GPU server baslatilamadi: {e}")
            self.proc = None
            return False
        finally:
            try:
                # Handle server'a devredildi; bizdeki kopya kapatilabilir.
                if log_file is not subprocess.DEVNULL:
                    log_file.close()
            except Exception:
                pass

        deadline = _time.time() + timeout
        while _time.time() < deadline:
            if self.proc.poll() is not None:
                hint = f" Detay: {self.log_path}" if self.log_path else ""
                Console.error(f"GPU server erken kapandi (exe/surucu hatasi olabilir).{hint}")
                self.proc = None
                return False
            if self.is_running():
                self.model_path = gguf_path
                self.n_ctx = min(n_ctx, 8192)
                Console.success(f"GPU server hazir: {self.base_url}")
                return True
            _time.sleep(1)

        Console.error("GPU server zaman asimina ugradi!")
        self.stop()
        return False

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        repeat_penalty: float = 1.0,
    ) -> Optional[str]:
        if not self.is_running():
            Console.error("GPU server calismiyor! Once start() cagirin.")
            return None
        try:
            max_input_chars = (self.n_ctx - max_tokens) * 3
            truncated = []
            for msg in messages:
                content = msg.get("content", "")
                if len(content) > max_input_chars:
                    content = content[:max_input_chars] + "\n\n... [ICERIK KISITLANDI] ..."
                    Console.warning("Girdi kisitlandi (GPU server).")
                truncated.append({"role": msg["role"], "content": content})

            r = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={"messages": truncated,
                      "temperature": temperature,
                      "max_tokens": max_tokens,
                      "repeat_penalty": repeat_penalty,
                      "stream": False},
                timeout=300,
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            Console.error(f"GPU server hatasi: {r.status_code} - {r.text[:200]}")
            return None
        except requests.exceptions.ConnectionError:
            Console.error("GPU server baglantisi koptu!")
            return None
        except Exception as e:
            Console.error(f"GPU server istegi hatasi: {e}")
            return None

    def stop(self):
        if self.proc:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=10)
                except Exception:
                    self.proc.kill()
            except Exception:
                pass
            finally:
                self.proc = None
        self.model_path = None
        self.engine = ""


class LocalModelManager:
    """Tek sinifla Ollama + llama-cpp-python + llama-server (GPU) yonetir."""

    def __init__(self, backend: str = "ollama", ollama_url: str = "http://localhost:11434",
                 server_flavor: str = "auto"):
        self.backend = backend
        self.ollama = OllamaClient(base_url=ollama_url)
        self.llamacpp = LlamaCppClient()
        self.llamaserver = LlamaServerClient(flavor=server_flavor)

    def is_available(self) -> bool:
        if self.backend == "ollama":
            return self.ollama.is_available()
        elif self.backend == "llamacpp":
            return self.llamacpp.is_available()
        elif self.backend == "llamaserver":
            return self.llamaserver.is_available()
        return False

    def get_available_models(self) -> List[str]:
        if self.backend == "ollama":
            return self.ollama.get_installed_models()
        elif self.backend == "llamacpp":
            if self.llamacpp.model_path:
                return [Path(self.llamacpp.model_path).name]
            return []
        elif self.backend == "llamaserver":
            if self.llamaserver.model_path:
                return [Path(self.llamaserver.model_path).name]
            return []
        return []

    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        repeat_penalty: float = 1.0,
    ) -> Optional[str]:
        if self.backend == "ollama":
            return self.ollama.chat_completion(model, messages, temperature,
                                               max_tokens, repeat_penalty)
        elif self.backend == "llamacpp":
            return self.llamacpp.chat_completion(model, messages, temperature,
                                                 max_tokens, repeat_penalty)
        elif self.backend == "llamaserver":
            return self.llamaserver.chat_completion(model, messages, temperature,
                                                    max_tokens, repeat_penalty)
        return None

    def load_llamacpp_model(
        self,
        gguf_path: str,
        n_ctx: int = 8192,
        n_gpu_layers: int = 0,
        n_threads: int = 8,
    ) -> bool:
        return self.llamacpp.load_model(gguf_path, n_ctx, n_gpu_layers, n_threads)

    def pull_ollama_model(self, model_name: str, callback=None) -> bool:
        return self.ollama.pull_model(model_name, callback)

    def unload_llamacpp_model(self):
        self.llamacpp.unload_model()

    def load_server_model(
        self,
        gguf_path: str,
        n_ctx: int = 8192,
        n_gpu_layers: int = 35,
    ) -> bool:
        return self.llamaserver.start(gguf_path, n_ctx, n_gpu_layers)

    def unload_server_model(self):
        self.llamaserver.stop()
