"""kullanim_dogrulama.py - requirements.txt/pyproject vs gercek importlar.

Devkit usage.py port (simplified, stdlib-only).
- Beyan edilen ama hic import edilmeyen bağımlılık adayları
- Import edilen ama beyan edilmeyen dis paketler
NOT: paket-adi -> import-adi eslemesi sezgisel; sonuclar tavsiye niteliginde.
"""
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

try:
    STDLIB = set(sys.stdlib_module_names)
except AttributeError:
    STDLIB = {
        "os", "sys", "json", "re", "logging", "pathlib", "typing", "datetime",
        "hashlib", "functools", "itertools", "collections", "abc", "asyncio",
        "subprocess", "math", "time", "random", "string", "enum", "dataclasses",
        "contextlib", "copy", "warnings", "io", "tempfile", "shutil", "argparse",
        "struct", "socket", "threading", "queue", "inspect", "ast", "traceback",
        "unittest", "sqlite3", "base64", "csv", "glob", "gzip", "heapq", "pickle",
        "pprint", "secrets", "statistics", "textwrap", "uuid", "xml", "ctypes",
        "importlib", "platform", "tkinter", "types",
    }

# yaygin paket-adi -> import-adi farklari
IMPORT_ALIASES = {
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "docx": "python-docx",
    "bson": "pymongo",
    "pynvml": "nvidia-ml-py",
}
PACKAGE_ALIASES = {v: k for k, v in IMPORT_ALIASES.items()}


def _normalize(name: str) -> str:
    return name.lower().replace("-", "_").replace(".", "_")


def extract_requirements(root_path: str) -> List[str]:
    """requirements.txt (varsa) veya pyproject.toml'dan paket adlari."""
    root = Path(root_path)

    req = root / "requirements.txt"
    if req.exists():
        names = []
        try:
            for line in req.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "-", "--")):
                    continue
                m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
                if m:
                    names.append(m.group(1))
            return names
        except Exception:
            return []

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
            if m:
                return re.findall(r'"([^"]+)"', m.group(1))
        except Exception:
            pass
    return []


def validate_usage(root_path: str, imported_tops: Set[str],
                   local_tops: Set[str]) -> Dict:
    """Beyan edilen paketler vs gercek importlari karsilastir.

    imported_tops: projede import edilen ust-seviye modul adlari
    local_tops: yerel paket/klasor adlari (alt-sistemler)
    """
    declared = extract_requirements(root_path)
    declared_norm = {_normalize(d): d for d in declared}

    local_norm = {_normalize(l) for l in local_tops}
    import_norm = {_normalize(i): i for i in imported_tops
                   if i not in STDLIB and _normalize(i) not in local_norm}

    # beyan edilen ama hic import edilmeyen
    unused = []
    for dnorm, orig in sorted(declared_norm.items()):
        alias_import = PACKAGE_ALIASES.get(dnorm, "")
        matched = any(
            dnorm == inorm or dnorm in inorm or inorm in dnorm
            or (alias_import and _normalize(alias_import) == inorm)
            for inorm in import_norm)
        if not matched:
            unused.append(orig)

    # import edilen ama beyan edilmeyen
    undeclared = []
    for inorm, orig in sorted(import_norm.items()):
        if inorm in ("__future__",):
            continue
        alias_pkg = IMPORT_ALIASES.get(orig.lower(), "")
        matched = any(
            inorm == dnorm or inorm in dnorm or dnorm in inorm
            or (alias_pkg and _normalize(alias_pkg) == dnorm)
            for dnorm in declared_norm)
        if not matched:
            undeclared.append(orig)

    return {
        "beyan_edilen": sorted(declared),
        "kullanilmayan_adaylar": unused,
        "beyan_edilmeyen_importlar": undeclared,
    }
