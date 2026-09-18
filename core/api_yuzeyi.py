"""api_yuzeyi.py - alt-sistem bazli public API ozeti (sinif/fonksiyon + imzalar).

Devkit api_surface.py + scan.py signature port (stdlib-only).
Cikti: veri/api_yuzeyi.json — her alt-sistem (ust klasor) icin dosyalar,
siniflar (metodlar + imzalar), fonksiyonlar (imzalar) ve docstring ozetleri.
"""
import ast
from pathlib import Path
from typing import Dict, List, Optional

from core.ast_cache import get_content_and_tree


def _signature(node) -> str:
    """Fonksiyon imzasi: (args) -> return."""
    args = node.args
    parts = []
    pos = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(pos) - len(args.defaults)) + list(args.defaults)
    for a, d in zip(pos, defaults):
        s = a.arg
        if d is not None:
            try:
                s += "=" + ast.unparse(d)
            except Exception:
                s += "=..."
        parts.append(s)
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        s = a.arg
        if d is not None:
            try:
                s += "=" + ast.unparse(d)
            except Exception:
                s += "=..."
        parts.append(s)
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    ret = ""
    if node.returns is not None:
        try:
            ret = " -> " + ast.unparse(node.returns)
        except Exception:
            ret = ""
    return "(" + ", ".join(parts) + ")" + ret


def build_api_surface(root_path: str, py_rel_paths: List[str]) -> Dict:
    """Alt-sistem bazli API yuzeyi.

    Donus: {"subsystems": {sub: {"files": {...}, "stats": {...}}},
            "stats": {...}, "errors": [...]}
    """
    root = Path(root_path)
    subsystems: Dict[str, dict] = {}
    errors: List[str] = []

    for rel in sorted(set(p.replace("\\", "/") for p in py_rel_paths)):
        _content, tree = get_content_and_tree(root / rel)
        if tree is None:
            errors.append(f"{rel}: parse edilemedi")
            continue

        sub = rel.split("/")[0] if "/" in rel else "_kok"
        entry = subsystems.setdefault(
            sub, {"files": {}, "stats": {"files": 0, "classes": 0, "functions": 0}})

        doc = ast.get_docstring(tree) or ""
        classes = []
        functions = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = [{"name": m.name, "sig": _signature(m), "line": m.lineno}
                           for m in node.body if isinstance(m, ast.FunctionDef)]
                classes.append({"name": node.name, "line": node.lineno,
                                "methods": methods})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({"name": node.name, "sig": _signature(node),
                                  "line": node.lineno})

        entry["files"][rel] = {"classes": classes, "functions": functions,
                               "doc": doc[:200]}
        entry["stats"]["files"] += 1
        entry["stats"]["classes"] += len(classes)
        entry["stats"]["functions"] += len(functions)

    total = {
        "files": sum(s["stats"]["files"] for s in subsystems.values()),
        "classes": sum(s["stats"]["classes"] for s in subsystems.values()),
        "functions": sum(s["stats"]["functions"] for s in subsystems.values()),
    }
    return {"subsystems": subsystems, "stats": total, "errors": errors}


def format_api_surface(data: Dict, max_per_sub: int = 12) -> str:
    """API yuzeyini metin olarak formatla (Mimari Harita raporuna ek)."""
    lines = ["PUBLIC API YUZEYI (alt-sistem bazli):"]
    stats = data["stats"]
    lines.append(f"  Toplam: {stats['files']} dosya, {stats['classes']} sinif, "
                 f"{stats['functions']} fonksiyon")
    for sub, entry in sorted(data["subsystems"].items()):
        s = entry["stats"]
        lines.append(f"  {sub}: {s['files']} dosya, {s['classes']} sinif, "
                     f"{s['functions']} fonksiyon")
        shown = 0
        for rel, fdata in sorted(entry["files"].items()):
            if shown >= max_per_sub:
                lines.append(f"    ... (daha fazla)")
                break
            classes = fdata["classes"]
            funcs = fdata["functions"]
            if not classes and not funcs:
                continue
            shown += 1
            line = f"    {rel}"
            if classes:
                line += f" | siniflar: " + ", ".join(
                    c["name"] for c in classes[:5])
            if funcs:
                line += f" | fn: " + ", ".join(
                    f"{f['name']}{f['sig']}" for f in funcs[:4])
            lines.append(line)
    return "\n".join(lines)
