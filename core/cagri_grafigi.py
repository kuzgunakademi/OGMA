"""cagri_grafigi.py - proje-geneli fonksiyon cagri grafi ve olu fonksiyon tespiti.

Devkit techdebt callgraph + arsiv cagri_grafigi_analizoru port (stdlib-only).
Olu fonksiyon tespiti ARTIK proje capinda: bir fonksiyonun adi hicbir
dosyada (cagri veya referans) gecmiyorsa "olu" sayilir.
"""
import ast
from pathlib import Path
from typing import Dict, List, Optional, Set

from core.ast_cache import get_content_and_tree


def _parse_tree(tree) -> Optional[dict]:
    """Tree'den modul fonksiyonlarini cikar; yoksa None."""
    if tree is None:
        return None
    return tree


def _module_functions(tree) -> List[dict]:
    """Modul-seviye fonksiyonlar (metodlar haric)."""
    return [{"name": n.name, "line": n.lineno}
            for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _collect_call_names(node) -> Set[str]:
    """Cagri adlari: f(...) ve obj.f(...)."""
    names = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Name):
                names.add(f.id)
            elif isinstance(f, ast.Attribute):
                names.add(f.attr)
    return names


def _collect_used_names(tree) -> Set[str]:
    """Tum kullanilan adlar (cagri + referans): Name(Load) + Attribute.
    Referanslar onemli: fonksiyon callback olarak geciriliyorsa cagri
    olmadan da 'kullanilmis' sayilmalidir."""
    names = set()
    for sub in ast.walk(tree):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            names.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            names.add(sub.attr)
    return names


def analyze_call_graph(root_path: str, py_rel_paths: List[str]) -> Dict:
    root = Path(root_path)
    defined: Dict[str, List[dict]] = {}
    call_files: Dict[str, Set[str]] = {}   # cagri adi -> hangi dosyalarda cagriliyor
    used_all: Set[str] = set()
    errors: List[str] = []

    for rel in sorted(set(p.replace("\\", "/") for p in py_rel_paths)):
        _content, tree = get_content_and_tree(root / rel)
        if tree is None:
            errors.append(f"{rel}: parse edilemedi")
            continue
        defined[rel] = _module_functions(tree)

        for sub in ast.walk(tree):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Name):
                    call_files.setdefault(f.id, set()).add(rel)
                elif isinstance(f, ast.Attribute):
                    call_files.setdefault(f.attr, set()).add(rel)

        used_all |= _collect_used_names(tree)

    # cagri grafi
    callgraph: Dict[str, Dict[str, dict]] = {}
    for rel, funcs in defined.items():
        callgraph[rel] = {}
        for f in funcs:
            callers = sorted(set(call_files.get(f["name"], set())) - {rel})
            callgraph[rel][f["name"]] = {
                "callers_files": callers,
                "self_recursive": rel in call_files.get(f["name"], set()),
            }

    # proje-geneli olu fonksiyonlar: adi HICBIR dosyada cagrilmayan/referans edilmeyen
    project_dead = []
    for rel, funcs in defined.items():
        for f in funcs:
            name = f["name"]
            if name.startswith("_") or name == "main":
                continue
            if name not in used_all:
                project_dead.append({"file": rel, "func": name, "line": f["line"]})
    project_dead.sort(key=lambda x: (x["file"], x["line"]))

    most_called = sorted(
        ((name, len(files)) for name, files in call_files.items()),
        key=lambda x: -x[1])[:5]

    stats = {
        "fonksiyon_sayisi": sum(len(v) for v in defined.values()),
        "cagrilan_ayri_ad": len(call_files),
        "olu_fonksiyon": len(project_dead),
        "en_cok_cagrilan": [{"ad": n, "dosya_sayisi": c} for n, c in most_called],
    }

    return {
        "callgraph": callgraph,
        "project_dead": project_dead,
        "stats": stats,
        "errors": errors,
    }
