"""Donanim taramasi ve profil onerisi.

Program ilk acildiginda calisir: CPU / GPU / RAM bilgisini toplar,
modele uygun profili onerir (cpu-only, kismi GPU, tam GPU).
Hicbir agir bagimlilik gerektirmez (standart kutuphane + OS komutlari).
"""
import ctypes
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

# Windows IsProcessorFeaturePresent sabitleri (winnt.h)
_PF_AVX = 39
_PF_AVX2 = 40
_PF_AVX512F = 41

# NVIDIA compute capability -> mimari adi
SM_FAMILY = {
    "7.5": "Turing",
    "8.0": "Ampere",
    "8.6": "Ampere",
    "8.7": "Ampere",
    "8.9": "Ada Lovelace",
    "9.0": "Hopper",
    "10.0": "Blackwell",
    "10.1": "Blackwell",
    "12.0": "Blackwell",
}


def _cpu_feature(code: int) -> Optional[bool]:
    try:
        return bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(code))
    except Exception:
        return None


def detect_cpu() -> Dict:
    info: Dict = {"name": platform.processor() or "Bilinmiyor",
                  "cores_logical": os.cpu_count() or 4,
                  "cores_physical": os.cpu_count() or 4,
                  "avx": None, "avx2": None, "avx512": None}
    try:
        import subprocess as sp
        out = sp.run(["powershell", "-NoProfile", "-Command",
                      "(Get-CimInstance Win32_Processor | "
                      "Select-Object -First 1 Name,NumberOfCores,"
                      "NumberOfLogicalProcessors | Format-List | Out-String)"],
                     capture_output=True, text=True, timeout=25)
        data: Dict[str, str] = {}
        for line in (out.stdout or "").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
        if data.get("Name"):
            info["name"] = data["Name"]
        if data.get("NumberOfCores", "").isdigit():
            info["cores_physical"] = int(data["NumberOfCores"])
        if data.get("NumberOfLogicalProcessors", "").isdigit():
            info["cores_logical"] = int(data["NumberOfLogicalProcessors"])
    except Exception:
        pass
    if os.name == "nt":
        info["avx"] = _cpu_feature(_PF_AVX)
        info["avx2"] = _cpu_feature(_PF_AVX2)
        info["avx512"] = _cpu_feature(_PF_AVX512F)
    return info


def quick_gpu_vendor() -> str:
    """Hizli NVIDIA kontrolu (nvidia-smi). 'nvidia' veya '' dondurur."""
    try:
        out = subprocess.run(["nvidia-smi", "-L"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and "GPU" in (out.stdout or ""):
            return "nvidia"
    except Exception:
        pass
    return ""


def detect_nvidia_gpus() -> List[Dict]:
    gpus: List[Dict] = []
    if not shutil.which("nvidia-smi"):
        return gpus
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,driver_version,memory.total,compute_cap",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20)
        for line in (out.stdout or "").strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            name, driver, mem, sm = parts[0], parts[1], parts[2], parts[3]
            try:
                vram_mb = int(float(mem))
            except ValueError:
                vram_mb = 0
            gpus.append({
                "name": name,
                "driver": driver,
                "vram_mb": vram_mb,
                "compute_cap": sm,
                "family": SM_FAMILY.get(sm, "Bilinmiyor"),
                "vendor": "NVIDIA",
            })
    except Exception:
        pass
    return gpus


def detect_other_gpus(nvidia_names: List[str]) -> List[Dict]:
    """NVIDIA disi GPU'lar (AMD / Intel) - bilgi amacli."""
    others: List[Dict] = []
    if os.name != "nt":
        return others
    try:
        import subprocess as sp
        out = sp.run(["powershell", "-NoProfile", "-Command",
                      "(Get-CimInstance Win32_VideoController | "
                      "Select-Object Name | Format-List | Out-String)"],
                     capture_output=True, text=True, timeout=25)
        for line in (out.stdout or "").splitlines():
            if ":" not in line:
                continue
            key, name = line.split(":", 1)
            if key.strip().lower() != "name":
                continue
            name = name.strip()
            if not name or any(n.lower() in name.lower() for n in nvidia_names):
                continue
            vendor = "AMD" if ("amd" in name.lower()
                               or "radeon" in name.lower()) else (
                "Intel" if "intel" in name.lower() else "Diger")
            others.append({"name": name, "vendor": vendor})
    except Exception:
        pass
    return others


def detect_ram_mb() -> int:
    try:
        if os.name == "nt":
            class MemStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MemStatus()
            st.dwLength = ctypes.sizeof(MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return int(st.ullTotalPhys // (1024 * 1024))
    except Exception:
        pass
    return 0


def detect_hardware() -> Dict:
    cpu = detect_cpu()
    nvidia = detect_nvidia_gpus()
    others = detect_other_gpus([g["name"] for g in nvidia])
    return {"cpu": cpu, "nvidia_gpus": nvidia,
            "other_gpus": others, "ram_mb": detect_ram_mb(),
            "os": platform.system()}


def recommend_profile(hw: Dict, cuda_available: bool = False,
                      vulkan_available: bool = False) -> Dict:
    """Donanima gore profil oner. Asla hata vermez, her zaman CPU fallback dondurur.

    Motor yoksa GPU ayari ONERILMEZ (config yazmak tek basina GPU acmaz).
    GPU potansiyeli 'gpu_potential' alaninda ayrica raporlanir.
    """
    cpu = hw.get("cpu", {})
    ram_mb = hw.get("ram_mb", 0)
    gpus = hw.get("nvidia_gpus", []) or []
    cores = cpu.get("cores_physical") or 4
    threads = max(2, min(cores, 16))

    rec: Dict = {
        "mode": "cpu",
        "n_threads": threads,
        "n_ctx": 8192 if ram_mb >= 12000 else 4096,
        "n_gpu_layers": 0,
        "reasons": [],
        "warnings": [],
    }

    if cpu.get("avx2") is False:
        rec["warnings"].append(
            "CPU AVX2 desteklemiyor gorunuyor; modern llama.cpp derlemeleri "
            "calismayabilir. Cok eski islemcilerde uyumluluk sorunu olur.")

    if not gpus:
        rec["reasons"].append("NVIDIA GPU bulunamadi -> CPU-only onerilir.")
        others = hw.get("other_gpus", []) or []
        for o in others:
            if o.get("vendor") == "AMD":
                if vulkan_available:
                    rec["mode"] = "vulkan"
                    rec["n_gpu_layers"] = 35
                    rec["reasons"].append(
                        f"AMD GPU tespit edildi ({o.get('name')}): gomulu "
                        "Vulkan motoru ile GPU denenebilir (n_gpu_layers=35).")
                else:
                    rec["reasons"].append(
                        f"AMD GPU tespit edildi ({o.get('name')}): Vulkan motoru "
                        "yok, bu yuzden CPU-only onerilir.")
            elif o.get("vendor") == "Intel":
                if vulkan_available:
                    rec["mode"] = "vulkan"
                    rec["n_gpu_layers"] = 20
                    rec["reasons"].append(
                        f"Intel GPU tespit edildi ({o.get('name')}): gomulu "
                        "Vulkan motoru ile kismi GPU denenebilir.")
                else:
                    rec["reasons"].append(
                        f"Intel GPU tespit edildi ({o.get('name')}): hesaplama icin "
                        "CPU-only onerilir.")
    else:
        g = gpus[0]
        vram_gb = g["vram_mb"] / 1024
        rec["gpu_name"] = g["name"]
        rec["gpu_family"] = g.get("family", "")
        rec["gpu_sm"] = g.get("compute_cap", "")
        if vram_gb >= 10:
            rec["mode"] = "cuda_full"
            rec["n_gpu_layers"] = 35
            rec["reasons"].append(
                f"{g['name']} ({vram_gb:.0f} GB VRAM): tam GPU offload uygun "
                "(n_gpu_layers=35).")
        elif vram_gb >= 6:
            rec["mode"] = "cuda_full"
            rec["n_gpu_layers"] = 35
            rec["reasons"].append(
                f"{g['name']} ({vram_gb:.0f} GB VRAM): 7B Q4 model tam GPU'ya "
                "sigar.")
        elif vram_gb >= 4:
            rec["mode"] = "cuda_partial"
            rec["n_gpu_layers"] = 20
            rec["reasons"].append(
                f"{g['name']} ({vram_gb:.0f} GB VRAM): kismi GPU offload "
                "(n_gpu_layers=20, geri kalan CPU).")
        else:
            rec["reasons"].append(
                f"{g['name']} VRAM dusuk ({vram_gb:.1f} GB) -> CPU-only daha stabil.")

    if 0 < ram_mb < 8000:
        rec["warnings"].append(
            f"RAM dusuk ({ram_mb // 1024} GB): kucuk model onerilir "
            "(Qwen2.5-1.5B Q4 ~1 GB) ve n_ctx=4096.")
        rec["n_ctx"] = 4096

    # DURUSTLUK FILTRESI: motor yoksa GPU modu onerme.
    # n_gpu_layers yazmak tek basina GPU acmaz; altinda motor sart.
    gpu_ok = (rec["mode"].startswith("cuda") and cuda_available) or \
             (rec["mode"] == "vulkan" and vulkan_available)
    if rec["mode"] != "cpu" and not gpu_ok:
        rec["gpu_potential"] = {
            "mode": rec["mode"],
            "n_gpu_layers": rec["n_gpu_layers"],
        }
        rec["mode"] = "cpu"
        rec["n_gpu_layers"] = 0
        rec["reasons"].append(
            "GPU motoru bulunamadi -> simdilik CPU-only. "
            "Gomulu motor (libs/) mevcutsa GPU devreye girer.")

    return rec


def has_cuda_build() -> bool:
    """CUDA motoru mevcut mu (ggml-cuda.dll, gomulu server dahil)?"""
    return _has_dll(("ggml-cuda.dll", "libggml-cuda.so",
                     "libggml-cuda.dylib", "ggml_cuda.dll"))


def _has_dll(lib_names) -> bool:
    try:
        import llama_cpp  # noqa: F401  (sadece konum icin)
    except Exception:
        pass
    try:
        import llama_cpp
        libdir = Path(llama_cpp.__file__).resolve().parent / "lib"
        dirs = [libdir, Path(llama_cpp.__file__).resolve().parent]
    except Exception:
        dirs = []
    try:
        dirs.append(project_base_dir() / "libs" / "llama-server-cuda")
        dirs.append(project_base_dir() / "libs" / "llama-server-vulkan")
    except Exception:
        pass
    for d in dirs:
        try:
            for probe in lib_names:
                if (d / probe).exists():
                    return True
        except Exception:
            continue
    return False


def has_vulkan_build() -> bool:
    """Vulkan motoru mevcut mu (ggml-vulkan.dll)?"""
    return _has_dll(("ggml-vulkan.dll", "libggml-vulkan.so",
                     "libggml-vulkan.dylib"))


class _FileTime(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong)]


_cpu_last: Optional[tuple] = None


def _filetime_to_int(ft) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def get_cpu_percent() -> Optional[float]:
    """Sistem geneli CPU kullanimi (%). Ilk cagrida baz olusur, None doner."""
    global _cpu_last
    if os.name != "nt":
        return None
    try:
        idle = _FileTime()
        kernel = _FileTime()
        user = _FileTime()
        if not ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        i, k, u = (_filetime_to_int(idle), _filetime_to_int(kernel),
                   _filetime_to_int(user))
        prev = _cpu_last
        _cpu_last = (i, k, u)
        if not prev:
            return None
        idle_d = i - prev[0]
        total_d = (k - prev[1]) + (u - prev[2])
        if total_d <= 0:
            return 0.0
        return round(max(0.0, min(100.0, (1.0 - idle_d / total_d) * 100.0)), 1)
    except Exception:
        return None


def get_ram_percent() -> Optional[int]:
    """Fiziksel RAM kullanimi (%)."""
    try:
        if os.name == "nt":
            class MemStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = MemStatus()
            st.dwLength = ctypes.sizeof(MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return int(st.dwMemoryLoad)
    except Exception:
        pass
    return None


def get_gpu_stats() -> Optional[Dict]:
    """NVIDIA GPU kullanim + VRAM. Yoksa None (AMD/Intel henuz olculmuyor)."""
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return None
        line = (out.stdout or "").strip().splitlines()
        if not line:
            return None
        parts = [p.strip().replace("%", "") for p in line[0].split(",")]
        if len(parts) < 4:
            return None
        return {"name": parts[0], "util": float(parts[1]),
                "mem_used_mb": int(float(parts[2])),
                "mem_total_mb": int(float(parts[3]))}
    except Exception:
        return None


def project_base_dir() -> Path:
    """Proje kok dizini (bu dosyanin iki ustu: core/ -> proje)."""
    return Path(__file__).resolve().parent.parent


def find_bundled_base_model() -> str:
    """models/base altindaki ilk .gguf dosyasi (tasinabilir taban model)."""
    base_dir = project_base_dir() / "models" / "base"
    try:
        if base_dir.is_dir():
            files = sorted(base_dir.glob("*.gguf"),
                           key=lambda p: p.name.lower())
            if files:
                return str(files[0])
    except Exception:
        pass
    return ""
