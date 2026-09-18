"""bilgi_grafigi.py - Proje Knowledge Graph (AST -> iliskisel graf).

Dugumler: FILE, CLASS, FUNCTION, METHOD
Kenarlar: CONTAINS, IMPORTS, CALLS, INHERITS

Devkit'in daginik analizlerini (bagimlilik/cagri/api) tek graf modelinde
birlestirir; transitive etki analizi (D2) bu grafin uzerine kurulur.
Deterministik — LLM yok, stdlib-only.
"""
import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.ast_cache import get_content_and_tree
from core.bagimlilik_analizi import extract_module_imports, _resolve_module_to_file


# ============================================================
# Graf yapisi
# ============================================================

def _file_id(rel: str) -> str:
    return f"file:{rel}"


def _class_id(rel: str, name: str) -> str:
    return f"class:{rel}:{name}"


def _func_id(rel: str, name: str) -> str:
    return f"func:{rel}:{name}"


def _method_id(rel: str, cls: str, name: str) -> str:
    return f"method:{rel}:{cls}.{name}"


def build_knowledge_graph(root_path: str, py_rel_paths: List[str]) -> Dict:
    """Tum proje icin bilgi grafi uret.

    Donus: {"nodes": [...], "edges": [...], "index": {...}, "stats": {...},
            "errors": [...]}
    """
    root = Path(root_path)
    nodes: Dict[str, dict] = {}
    edges: List[dict] = []
    errors: List[str] = []

    file_ids: List[str] = []
    # rel -> {bare_name: [func_node_id, ...]} (modul-seviye fonksiyonlar)
    funcs_by_name: Dict[str, List[str]] = {}
    # rel -> {ClassName: {"id":..., "bases": [str], "methods": {name: id}}}
    classes_by_rel: Dict[str, Dict[str, dict]] = {}
    # rel -> {"abs": set, "rel_imports": [{"level","module"}]}
    imports_by_rel: Dict[str, dict] = {}
    # cagri adlari: rel -> {func_id: Set[cagri_adi]}
    calls_by_func: Dict[str, Set[str]] = {}

    # ---------- Pass 1: tanimlar (FILE/CLASS/FUNCTION/METHOD) ----------
    for rel in sorted(set(p.replace("\\", "/") for p in py_rel_paths)):
        content, tree = get_content_and_tree(root / rel)
        if tree is None:
            errors.append(f"{rel}: parse edilemedi")
            continue

        fid = _file_id(rel)
        nodes[fid] = {"id": fid, "type": "FILE", "name": rel.rsplit("/", 1)[-1],
                      "file": rel, "line": 1}
        file_ids.append(fid)

        # ETKI icin TUM importlar (fonksiyon-ici/lazy importlar dahil):
        # degisiklik yapildiginda lazy import yapan dosya da kirilir.
        absolutes: Set[str] = set()
        relatives: List[dict] = []
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        absolutes.add(a.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0:
                        if node.module:
                            absolutes.add(node.module)
                    else:
                        relatives.append({"level": node.level,
                                          "module": node.module or ""})
            imports_by_rel[rel] = {"abs": absolutes, "rel_imports": relatives}
        except Exception:
            imports_by_rel[rel] = {"abs": set(), "rel_imports": []}

        cls_map: Dict[str, dict] = {}
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cid = _class_id(rel, node.name)
                nodes[cid] = {"id": cid, "type": "CLASS", "name": node.name,
                              "file": rel, "line": node.lineno}
                edges.append({"from": fid, "to": cid, "type": "CONTAINS"})
                methods: Dict[str, str] = {}
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        mid = _method_id(rel, node.name, m.name)
                        nodes[mid] = {"id": mid, "type": "METHOD", "name": m.name,
                                      "file": rel, "line": m.lineno}
                        edges.append({"from": cid, "to": mid, "type": "CONTAINS"})
                        methods[m.name] = mid
                        calls_by_func[mid] = _collect_calls(m)
                bases = [_base_name(b) for b in node.bases]
                cls_map[node.name] = {"id": cid, "bases": bases, "methods": methods}
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fnid = _func_id(rel, node.name)
                nodes[fnid] = {"id": fnid, "type": "FUNCTION", "name": node.name,
                               "file": rel, "line": node.lineno}
                edges.append({"from": fid, "to": fnid, "type": "CONTAINS"})
                funcs_by_name.setdefault(node.name, []).append(fnid)
                calls_by_func[fnid] = _collect_calls(node)
        classes_by_rel[rel] = cls_map

    # ---------- Pass 2: IMPORTS kenarlari ----------
    for rel, imp in imports_by_rel.items():
        fid = _file_id(rel)
        for mod in sorted(imp["abs"]):
            target = _resolve_module_to_file(mod, set(imports_by_rel.keys()))
            if target and target != rel:
                edges.append({"from": fid, "to": _file_id(target), "type": "IMPORTS"})
        for rimp in imp["rel_imports"]:
            from core.bagimlilik_analizi import _resolve_relative
            target = _resolve_relative(rel, rimp["level"], rimp["module"],
                                       set(imports_by_rel.keys()))
            if target and target != rel:
                edges.append({"from": fid, "to": _file_id(target), "type": "IMPORTS"})

    # ---------- Pass 3: CALLS kenarlari ----------
    # sinif kurucu cagrilari da takip edilir: LocalModelManager() -> class dugumu
    classes_by_name: Dict[str, List[str]] = {}
    for rel, cls_map in classes_by_rel.items():
        for cname, info in cls_map.items():
            classes_by_name.setdefault(cname, []).append(info["id"])
    for owner_id, names in calls_by_func.items():
        owner_file = owner_id.split(":", 1)[1].rsplit(":", 1)[0] \
            if owner_id.startswith(("func:", "method:")) else None
        owner_cls = None
        if owner_id.startswith("method:"):
            owner_cls = owner_id.split(":", 1)[1].split(".")[0]
        for name in sorted(names):
            targets: List[str] = []
            # self.m() -> ayni sinifin metodu
            if owner_cls and owner_file:
                m = classes_by_rel.get(owner_file, {}).get(owner_cls, {})
                if name in m.get("methods", {}):
                    targets.append(m["methods"][name])
            # ayni dosyadaki modul fonksiyonu
            if owner_file:
                fnid = _func_id(owner_file, name)
                if fnid in nodes and fnid != owner_id:
                    targets.append(fnid)
            # proje genelinde benzersiz fonksiyon
            if not targets and name in funcs_by_name:
                if len(funcs_by_name[name]) == 1:
                    targets.append(funcs_by_name[name][0])
                else:
                    # belirsiz: over-approximate (etki analizi icin guvenli)
                    targets.extend(funcs_by_name[name])
            # sinif kurucu cagrisi (new ClassName())
            if not targets and name in classes_by_name:
                if len(classes_by_name[name]) == 1:
                    targets.append(classes_by_name[name][0])
                else:
                    targets.extend(classes_by_name[name])
            for t in targets:
                if t != owner_id:
                    edges.append({"from": owner_id, "to": t, "type": "CALLS"})

    # ---------- Pass 4: INHERITS kenarlari ----------
    all_class_names: Dict[str, List[str]] = {}
    for rel, cls_map in classes_by_rel.items():
        for cname, info in cls_map.items():
            all_class_names.setdefault(cname, []).append(rel)
    for rel, cls_map in classes_by_rel.items():
        for cname, info in cls_map.items():
            for base in info["bases"]:
                if not base or base in ("object", "Exception", "BaseException"):
                    continue
                if base in classes_by_rel.get(rel, {}):
                    edges.append({"from": info["id"],
                                  "to": _class_id(rel, base), "type": "INHERITS"})
                elif base in all_class_names and len(all_class_names[base]) == 1:
                    edges.append({"from": info["id"],
                                  "to": _class_id(all_class_names[base][0], base),
                                  "type": "INHERITS"})

    # ---------- indeks + istatistik ----------
    type_counts: Dict[str, int] = {}
    for n in nodes.values():
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
    edge_counts: Dict[str, int] = {}
    for e in edges:
        edge_counts[e["type"]] = edge_counts.get(e["type"], 0) + 1

    # ters bagimlilik indeksi: dugum -> [gelen kenarlar]
    incoming: Dict[str, List[dict]] = {nid: [] for nid in nodes}
    for e in edges:
        if e["to"] in incoming:
            incoming[e["to"]].append(e)

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "index": {"incoming": {k: [dict(e) for e in v] for k, v in incoming.items()}},
        "stats": {"node_sayisi": len(nodes), "kenar_sayisi": len(edges),
                  "dugum_tipleri": type_counts, "kenar_tipleri": edge_counts},
        "errors": errors,
    }


def _collect_calls(func_node) -> Set[str]:
    """Fonksiyon govdesindeki cagri adlari (Name + Attribute)."""
    names = set()
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Name):
                names.add(f.id)
            elif isinstance(f, ast.Attribute):
                names.add(f.attr)
    return names


def _base_name(node) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


# ============================================================
# Sorgular (D2 transitive etki bunlari kullanir)
# ============================================================

def transitive_dependents(graph: Dict, node_id: str,
                          max_depth: int = 20) -> Dict[str, List[str]]:
    """node_id'ye giden zincirlerin uzerinde duran tum dugumler (BFS, ters yon).

    Donus: {"level_1": [id, ...], "level_2": [...], ...} — seviye 1 dogrudan
    bagimlilar, seviye 2 dolayli, ...
    """
    incoming = graph.get("index", {}).get("incoming", {})
    result: Dict[str, List[str]] = {}
    visited = {node_id}
    frontier = [node_id]
    depth = 0
    while frontier and depth < max_depth:
        nxt: List[str] = []
        for nid in frontier:
            for e in incoming.get(nid, []):
                if e["from"] not in visited:
                    visited.add(e["from"])
                    nxt.append(e["from"])
        if nxt:
            result[f"level_{depth + 1}"] = sorted(set(nxt))
        frontier = nxt
        depth += 1
    return result


def related_files(graph: Dict, node_ids: List[str]) -> Set[str]:
    """Dugum listesini etkilenen dosya kumesine cevir."""
    files = set()
    for nid in node_ids:
        n = next((n for n in graph["nodes"] if n["id"] == nid), None)
        if n and n.get("file"):
            files.add(n["file"])
        elif nid.startswith("file:"):
            files.add(nid.split(":", 1)[1])
    return files
