"""bagimlilik_analizi.py - import grafi, ters bagimlilik, alt-sistem matrisi,
dongu tespiti (Tarjan SCC). Devkit engine/deps.py port (stdlib-only).
"""
import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ast_cache import get_content_and_tree


def _resolve_module_to_file(module: str, py_paths: set) -> Optional[str]:
    """Import stringini proje dosyasina coz (en uzun onek eslesmesi)."""
    parts = module.split(".")
    for i in range(len(parts), 0, -1):
        prefix = ".".join(parts[:i])
        candidate = prefix.replace(".", "/") + ".py"
        if candidate in py_paths:
            return candidate
        pkg_init = prefix.replace(".", "/") + "/__init__.py"
        if pkg_init in py_paths:
            return pkg_init
    return None


def _resolve_relative(rel_path: str, level: int, module: str, py_paths: set) -> Optional[str]:
    """`from .x import y` cozumlemesi (level > 0)."""
    parts = rel_path.replace("\\", "/").split("/")
    pkg_parts = parts[:-1]
    if pkg_parts and pkg_parts[-1] == "__init__":
        pkg_parts = pkg_parts[:-1]
    for _ in range(level - 1):
        if pkg_parts:
            pkg_parts.pop()
    base = ".".join(pkg_parts)
    full = (base + "." + module) if module else base
    if not full:
        return None
    return _resolve_module_to_file(full, py_paths)


def extract_module_imports(tree) -> Tuple[set, List[dict]]:
    """Modul-seviye importlari cikar (fonksiyon govdesi + TYPE_CHECKING atlanir;
    bunlar import-zamani donguleri icin gecerli olan importlardir).
    Parametre: parse edilmis AST tree (ast_cache'ten).
    Donus: (mutlak modul adlari, [{"level": int, "module": str}, ...])"""
    absolutes = set()
    relatives: List[dict] = []

    def _add(node):
        if isinstance(node, ast.Import):
            for a in node.names:
                absolutes.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    absolutes.add(node.module)
            else:
                relatives.append({"level": node.level, "module": node.module or ""})

    def _visit(stmts):
        for node in stmts:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                _add(node)
            elif isinstance(node, ast.If):
                if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                    continue
                _visit(node.body)
                _visit(node.orelse)
            elif isinstance(node, (ast.Try, ast.With)):
                _visit(node.body)
                for h in getattr(node, "handlers", []):
                    _visit(h.body)
                _visit(node.orelse)
                _visit(node.finalbody)
            elif isinstance(node, (ast.For, ast.While)):
                _visit(node.body)
                _visit(node.orelse)

    _visit(tree.body)
    return absolutes, relatives


def _strongly_connected_components(graph: dict) -> List[List[str]]:
    """Tarjan SCC — dongu (cikar) tespiti."""
    index = {}
    lowlink = {}
    stack = []
    on_stack = set()
    result: List[List[str]] = []
    counter = [0]

    def connect(v):
        index[v] = lowlink[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                connect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            result.append(comp)

    for v in graph:
        if v not in index:
            connect(v)
    return result


def run_dependency_analysis(root_path: str, py_rel_paths: List[str]) -> Dict:
    """Tum proje icin bagimlilik analizi.

    Donus: {"graph", "reverse", "matrix", "subsystems", "cycles",
            "stats", "errors"}
    """
    root = Path(root_path)
    py_paths = set(p.replace("\\", "/") for p in py_rel_paths)
    graph: Dict[str, List[str]] = {}
    errors: List[str] = []

    for rel in sorted(py_paths):
        graph[rel] = []
        content, tree = get_content_and_tree(root / rel)
        if content is None:
            errors.append(f"{rel}: okunamadi")
            continue
        if tree is None:
            errors.append(f"{rel}: SyntaxError (importlar taranamadi)")
            continue

        absolutes, relatives = extract_module_imports(tree)

        for mod in absolutes:
            target = _resolve_module_to_file(mod, py_paths)
            if target and target != rel:
                graph[rel].append(target)
        for rimp in relatives:
            target = _resolve_relative(rel, rimp["level"], rimp["module"], py_paths)
            if target and target != rel:
                graph[rel].append(target)

    # Ters bagimlilik: kim import ediyor
    reverse: Dict[str, List[str]] = {rel: [] for rel in py_paths}
    for rel, targets in graph.items():
        for t in targets:
            reverse.setdefault(t, []).append(rel)

    # Alt-sistem (ust klasor) matrisi
    subsystems = sorted({p.split("/")[0] for p in py_paths if "/" in p})
    matrix = {s: {t: 0 for t in subsystems} for s in subsystems}

    def sub_of(f):
        return f.split("/")[0] if "/" in f else None

    for rel, targets in graph.items():
        src = sub_of(rel)
        if not src or src not in matrix:
            continue
        for t in targets:
            dst = sub_of(t)
            if dst and dst in matrix and dst != src:
                matrix[src][dst] += 1

    # Dongu grafigi: __init__.py dosyalari kendi alt modullerini import
    # ettigi icin cikarilir (gercek modul<->modul dongulerine odak)
    cycle_graph = {}
    for rel, targets in graph.items():
        if rel.endswith("__init__.py"):
            continue
        cycle_graph[rel] = [t for t in targets if not t.endswith("__init__.py")]

    sccs = _strongly_connected_components(cycle_graph)
    cycles = sorted((sorted(c) for c in sccs if len(c) > 1))

    most_depended = sorted(reverse.items(), key=lambda kv: -len(kv[1]))[:5]
    stats = {
        "modul_sayisi": len(py_paths),
        "bagimlilik_kenari": sum(len(t) for t in graph.values()),
        "bagimsiz_modul": sum(1 for t in graph.values() if not t),
        "dongu_sayisi": len(cycles),
        "en_cok_bagimli_olunan": [
            {"dosya": k, "kim_import_ediyor": len(v)} for k, v in most_depended
            if v
        ],
    }

    return {
        "graph": {k: sorted(set(v)) for k, v in graph.items()},
        "reverse": {k: sorted(set(v)) for k, v in reverse.items()},
        "matrix": matrix,
        "subsystems": subsystems,
        "cycles": cycles,
        "stats": stats,
        "errors": errors,
    }
