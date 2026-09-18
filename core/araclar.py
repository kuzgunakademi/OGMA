"""araclar.py - gelistirici araclari (tek tek calistirilabilir, taramadan bagimsiz).

- find_symbol:   sembol ara (sinif/fonksiyon/metod -> dosya:satir)
- file_outline:  dosya anahati (siniflar/fonksiyonlar satir araliklariyla)
- impact_analysis: degisiklik etki analizi (bu dosyayi kim import ediyor)

Hepsi stdlib-only; hedef klasor verilir, mimari tarama gerektirmez.
"""
import ast
import os
from pathlib import Path
from typing import Dict, List, Optional

from core.ast_cache import get_content_and_tree
from core.api_yuzeyi import _signature

DEFAULT_IGNORE = {".git", "__pycache__", ".venv", "venv", "env", "envs",
                  "node_modules", "Python_Ortami", "libs", "models",
                  ".ogma_cache", ".idea", ".vscode", "dist", "build",
                  "site-packages", "miniconda", "java"}


def collect_py_files(root_path: str, ignore: Optional[List[str]] = None) -> List[str]:
    """os.walk ile ignore dizinlere girmeden .py dosyalarini bul (goreceli yol)."""
    excluded = set(DEFAULT_IGNORE)
    excluded.update(ignore or [])
    root = Path(root_path)
    result: List[str] = []
    for kok, dirs, files in os.walk(str(root)):
        dirs[:] = [d for d in dirs if d not in excluded and not d.startswith(".")]
        for f in files:
            if f.endswith(".py"):
                try:
                    result.append(str(Path(kok, f).relative_to(root)).replace("\\", "/"))
                except ValueError:
                    continue
    return sorted(result)


def find_symbol(root_path: str, py_rel_paths: List[str], symbol: str) -> Dict:
    """Sembol ara: once tam eslesme, yoksa kismi (buyuk/kucuk harf duyarsiz)."""
    root = Path(root_path)
    exact, partial = [], []

    for rel in py_rel_paths:
        _content, tree = get_content_and_tree(root / rel)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if node.name == symbol:
                    exact.append({"file": rel, "line": node.lineno,
                                  "kind": "class", "symbol": node.name})
                elif symbol.lower() in node.name.lower():
                    partial.append({"file": rel, "line": node.lineno,
                                    "kind": "class", "symbol": node.name})
                for m in node.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        full = f"{node.name}.{m.name}"
                        if m.name == symbol:
                            exact.append({"file": rel, "line": m.lineno,
                                          "kind": "method", "symbol": full})
                        elif symbol.lower() in m.name.lower():
                            partial.append({"file": rel, "line": m.lineno,
                                            "kind": "method", "symbol": full})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == symbol:
                    exact.append({"file": rel, "line": node.lineno,
                                  "kind": "function", "symbol": node.name})
                elif symbol.lower() in node.name.lower():
                    partial.append({"file": rel, "line": node.lineno,
                                    "kind": "function", "symbol": node.name})

    rows = exact if exact else partial
    rows.sort(key=lambda x: (x["file"], x["line"]))
    return {"symbol": symbol, "count": len(rows), "results": rows,
            "exact_match": bool(exact)}


def format_find(result: Dict) -> str:
    lines = [f"Sembol: {result['symbol']}  ({result['count']} eslesme)"
             + ("" if result.get("exact_match") else "  [kismi eslesme]")]
    if not result["results"]:
        lines.append("  Bulunamadi.")
    for r in result["results"]:
        lines.append(f"  {r['kind']:<9}{r['symbol']:<40}{r['file']}:{r['line']}")
    return "\n".join(lines)


def file_outline(root_path: str, rel_path: str) -> Dict:
    """Dosya anahati: siniflar/fonksiyonlar/metodlar satir araliklariyla."""
    root = Path(root_path)
    _content, tree = get_content_and_tree(root / rel_path)
    if tree is None:
        return {"file": rel_path, "error": "Dosya parse edilemedi (bulunamadi/sintaks hatasi)"}

    functions = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({"name": n.name, "sig": _signature(n),
                              "line": n.lineno, "end": n.end_lineno})
    classes = []
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            methods = []
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append({"name": m.name, "sig": _signature(m),
                                    "line": m.lineno, "end": m.end_lineno})
            classes.append({"name": n.name, "line": n.lineno, "end": n.end_lineno,
                            "methods": methods})

    total_lines = (tree.body[-1].end_lineno if tree.body else 0)
    return {"file": rel_path, "lines": total_lines,
            "doc": (ast.get_docstring(tree) or "")[:200],
            "functions": functions, "classes": classes}


def format_outline(result: Dict) -> str:
    if "error" in result:
        return f"Dosya: {result['file']}\n  [HATA] {result['error']}"
    lines = [f"Dosya: {result['file']} ({result['lines']} satir)"]
    if result.get("doc"):
        lines.append(f"  Ozet: {result['doc']}")
    for fn in result["functions"]:
        lines.append(f"  fn   {fn['name']}{fn['sig']}  {fn['line']}-{fn['end']}")
    for c in result["classes"]:
        lines.append(f"  cls  {c['name']}  {c['line']}-{c['end']}")
        for m in c["methods"]:
            lines.append(f"       def {m['name']}{m['sig']}  {m['line']}-{m['end']}")
    return "\n".join(lines)


def impact_analysis(root_path: str, py_rel_paths: List[str], file_arg: str) -> Dict:
    """Degisiklik etki analizi: bu dosyayi kim import ediyor / o kimi import ediyor.

    Not: import grafiği istek uzerine hesaplanir (buyuk projelerde birkac saniye).
    """
    from core.bagimlilik_analizi import run_dependency_analysis
    data = run_dependency_analysis(root_path, py_rel_paths)
    graph = data["graph"]
    reverse = data["reverse"]

    # kismi yol eslesmesi: "settings.py" -> "config/settings.py"
    rel = file_arg.replace("\\", "/").strip()
    if rel not in graph:
        matches = [k for k in graph if k == f"{rel}" or k.endswith("/" + rel)]
        if len(matches) == 1:
            rel = matches[0]
        elif len(matches) > 1:
            return {"file": file_arg, "found": False,
                    "ambiguous": matches,
                    "hint": "Birden fazla dosya eslesti, tam yol verin"}

    return {"file": rel, "found": rel in graph,
            "dependents": sorted(reverse.get(rel, [])),
            "dependencies": sorted(graph.get(rel, []))}


def impact_analysis_v2(root_path: str, py_rel_paths: List[str], file_arg: str) -> Dict:
    """Cok seviyeli etki analizi (Knowledge Graph uzerinden) — D2.

    - level_1: dogrudan bagimlilar
    - level_2+: dolayli bağımlılar (transitive zincir)
    - etkilenen testler
    - risk seviyesi (HIGH/MEDIUM/LOW)
    """
    from core.bilgi_grafigi import (build_knowledge_graph, transitive_dependents,
                                    related_files)
    from core.bagimlilik_analizi import run_dependency_analysis

    g = build_knowledge_graph(root_path, py_rel_paths)

    # kismi yol eslesmesi
    rel = file_arg.replace("\\", "/").strip()
    file_keys = {n["file"] for n in g["nodes"] if n["type"] == "FILE"}
    if rel not in file_keys:
        matches = [k for k in file_keys if k.endswith("/" + rel) or k == rel]
        if len(matches) == 1:
            rel = matches[0]
        elif len(matches) > 1:
            return {"file": file_arg, "found": False, "ambiguous": sorted(matches),
                    "hint": "Birden fazla dosya eslesti, tam yol verin"}
        else:
            return {"file": file_arg, "found": False}

    fid = f"file:{rel}"
    # dugum -> dosya haritasi
    node_file: Dict[str, str] = {n["id"]: n.get("file", "") for n in g["nodes"]}
    # dosyanin tum dugumleri (file + icerdigi sinif/fonksiyon/metod)
    own_nodes = [fid] + [n["id"] for n in g["nodes"] if n.get("file") == rel
                         and n["id"] != fid]

    # her dugumden transitive dependents; bir DOSYA sadece en yakin
    # seviyesinde gorunur (dugum bazli degil, dosya bazli tek-seviye atama)
    level_ids: Dict[str, Set[str]] = {}
    assigned_nodes: Set[str] = set(own_nodes)
    assigned_files: Set[str] = {rel}
    for nid in own_nodes:
        d = transitive_dependents(g, nid)
        for lvl, ids in d.items():
            fresh = set()
            for i in ids:
                if i in assigned_nodes:
                    continue
                f = node_file.get(i, "")
                if not f or f in assigned_files:
                    continue
                assigned_nodes.add(i)
                assigned_files.add(f)
                fresh.add(i)
            if fresh:
                level_ids.setdefault(lvl, set()).update(fresh)

    # seviyelerden etkilenen dosyalar
    level_files: Dict[str, List[str]] = {}
    for lvl, ids in sorted(level_ids.items()):
        files = sorted({node_file.get(i, "") for i in ids} - {rel} - {""})
        level_files[lvl] = files

    all_affected: Set[str] = set()
    for ids in level_ids.values():
        all_affected |= {node_file.get(i, "") for i in ids}
    affected_files = sorted(f for f in all_affected if f and f != rel)

    # etkilenen testler
    test_files = sorted(f for f in affected_files
                        if f.lower().startswith("test") or "/test" in f
                        or f.startswith("tests/"))

    # dongu uyeligi
    dep_data = run_dependency_analysis(root_path, py_rel_paths)
    in_cycle = any(rel in cyc for cyc in dep_data.get("cycles", []))

    # risk seviyesi
    direct = level_files.get("level_1", [])
    n_direct = len(direct)
    n_indirect = len(affected_files) - n_direct
    if in_cycle or n_direct > 5 or n_indirect > 10:
        risk = "HIGH"
    elif n_direct >= 2 or n_indirect >= 2:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "file": rel, "found": True,
        "direct_dependents": direct,
        "indirect_levels": {k: v for k, v in level_files.items() if k != "level_1"},
        "affected_tests": test_files,
        "total_affected_files": len(affected_files),
        "in_cycle": in_cycle,
        "risk": risk,
    }


def format_impact_v2(result: Dict) -> str:
    """Cok seviyeli etki sonucunu metin sekline cevir."""
    if result.get("ambiguous"):
        return (f"[BULANIK] Birden fazla dosya eslesti:\n  " +
                "\n  ".join(result["ambiguous"]))
    if not result.get("found"):
        return f"Dosya projede bulunamadi: {result['file']}"

    risk = result["risk"]
    risk_label = {"HIGH": "[RISK: HIGH - degisiklik dikkatli planlanmali]",
                  "MEDIUM": "[RISK: MEDIUM - etki zinciri var]",
                  "LOW": "[RISK: LOW - izole degisiklik]"}[risk]
    lines = [f"Dosya: {result['file']}", risk_label, ""]

    direct = result["direct_dependents"]
    lines.append(f"SEVIYE 1 (dogrudan bagimlilar): {len(direct)}")
    for d in direct:
        lines.append(f"    - {d}")
    lines.append("")

    for lvl, files in sorted(result.get("indirect_levels", {}).items()):
        n = int(lvl.split("_")[1])
        lines.append(f"SEVIYE {n} (dolayli - {n-1} adim uzaklikta): {len(files)}")
        for f in files[:12]:
            lines.append(f"    - {f}")
        if len(files) > 12:
            lines.append(f"    ... (+{len(files) - 12} daha)")
        lines.append("")

    tests = result.get("affected_tests", [])
    if tests:
        lines.append(f"ETKILENEBILECEK TESTLER: {len(tests)}")
        for t in tests:
            lines.append(f"    - {t}")
        lines.append("")
    else:
        lines.append("ETKILENEBILECEK TESTLER: Yok (test kapsami yok - dikkat!)")
        lines.append("")

    if result.get("in_cycle"):
        lines.append("! Bu dosya DAIRESEL IMPORT dongusunun uyesi - risk yuksek.")

    lines.append(f"Toplam etkilenen dosya: {result['total_affected_files']}")
    return "\n".join(lines)


def format_impact(result: Dict) -> str:
    if result.get("ambiguous"):
        return (f"[BULANIK] Birden fazla dosya eslesti:\n  " +
                "\n  ".join(result["ambiguous"]))
    if not result.get("found"):
        return f"Dosya projede bulunamadi: {result['file']}"
    lines = [f"Dosya: {result['file']}",
             f"  Bunu import edenler (degisiklikten etkilenecekler): "
             f"{len(result['dependents'])}"]
    for d in result["dependents"]:
        lines.append(f"    - {d}")
    lines.append(f"  Bu dosyanin bagimliliklari: {len(result['dependencies'])}")
    for d in result["dependencies"]:
        lines.append(f"    - {d}")
    return "\n".join(lines)
