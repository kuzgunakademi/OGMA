"""kalite_analizi.py - dosya bazli kalite skoru, dongusel karmaşiklik,
guvenlik pattern taramasi (AST-tabanli, deterministik).

Devkit engine/quality.py (genisletilmis) port + AST-tabanli guvenlik.
stdlib-only.
"""
import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.ast_cache import get_content_and_tree


# ============================================================
# Skorlama (0-10 x 4 = 0-40)
# ============================================================

def score_file(fdata: dict) -> dict:
    """Dosya kalite skoru: Aktiflik/Gereklilik/Kod Kalitesi/Butunluk."""
    lines = fdata.get("lines", 0)
    classes = fdata.get("classes", [])
    functions = fdata.get("functions", [])
    imports = fdata.get("imports", [])

    import_score = min(len(imports) * 1.5, 5)
    class_score = min(len(classes) * 2, 5)
    aktiflik = min(import_score + class_score, 10)

    if lines > 500:
        gereklilik = 10
    elif lines > 200:
        gereklilik = 8
    elif lines > 50:
        gereklilik = 6
    elif lines > 10:
        gereklilik = 4
    else:
        gereklilik = 2

    kalite = 5
    for c in classes:
        if c.get("methods"):
            kalite += 1
        for m in c.get("methods", []):
            if m.get("decorators"):
                kalite += 0.5
    kalite = min(kalite, 10)

    butunluk = 0
    if classes:
        butunluk += 4
    if any(c.get("methods") for c in classes):
        butunluk += 3
    if functions:
        butunluk += 2
    if imports:
        butunluk += 1
    butunluk = min(butunluk, 10)

    return {
        "Aktiflik": round(aktiflik, 1),
        "Gereklilik": gereklilik,
        "Kod Kalitesi": round(kalite, 1),
        "Butunluk": butunluk,
        "Toplam": round(aktiflik + gereklilik + kalite + butunluk, 1),
    }


# ============================================================
# AST tabanli taramalar
# ============================================================

def cyclomatic_complexity(func_node) -> int:
    """McCabe karmaşıklığı: 1 + karar noktaları."""
    complexity = 1
    for sub in ast.walk(func_node):
        if isinstance(sub, (ast.If, ast.While, ast.For, ast.AsyncFor,
                            ast.ExceptHandler, ast.With, ast.AsyncWith,
                            ast.Assert, ast.IfExp, ast.comprehension)):
            complexity += 1
        elif isinstance(sub, ast.BoolOp):
            complexity += len(sub.values) - 1
        elif isinstance(sub, ast.match_case):
            complexity += 1
    return complexity


def detect_unreachable(func_node) -> List[int]:
    """return/raise sonrasi erisilemez satirlar (ayni govde blogu)."""
    dead_lines = []
    for node in ast.walk(func_node):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for i, stmt in enumerate(body):
            if not isinstance(stmt, (ast.Return, ast.Raise)):
                continue
            for after in body[i + 1:]:
                if isinstance(after, ast.Pass):
                    continue
                if isinstance(after, ast.Expr) and isinstance(
                        getattr(after, "value", None),
                        (ast.Constant, ast.JoinedStr)):
                    continue  # docstring
                dead_lines.append(getattr(after, "lineno", 0))
    return sorted(set(l for l in dead_lines if l))


def detect_unused_variables(func_node) -> List[Tuple[str, int]]:
    """Atanan ama hic okunmayan degiskenler (fonksiyon kapsami)."""
    assigned: Dict[str, int] = {}
    used = set()
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Name):
            if isinstance(sub.ctx, ast.Store):
                assigned.setdefault(sub.id, sub.lineno)
            elif isinstance(sub.ctx, ast.Load):
                used.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            pass
    for sub in ast.walk(func_node):
        if isinstance(sub, ast.Attribute):
            v = sub
            while isinstance(v, ast.Attribute):
                v = v.value
            if isinstance(v, ast.Name):
                used.add(v.id)
    return [(name, ln) for name, ln in sorted(assigned.items(), key=lambda x: x[1])
            if name not in used and not name.startswith("_")]


SECURITY_CHECKS = {
    "eval_kullanimi": ("kritik", "eval() kullanilmis — kod enjeksiyonu riski"),
    "exec_kullanimi": ("kritik", "exec() kullanilmis — kod enjeksiyonu riski"),
    "shell_true": ("kritik", "subprocess shell=True — komut enjeksiyonu riski"),
    "pickle_load": ("yuksek", "pickle yukleme — guvensiz deserialization riski"),
    "yaml_unsafe": ("yuksek", "yaml.load Loader'siz — guvensiz deserialization"),
    "gizli_bilgi": ("kritik", "sabitlenmis sifre/anahtar gorunumu"),
}


def detect_security(tree) -> List[dict]:
    """AST-tabanli guvenlik riskleri (regex degil, yanlis-pozitif dusuk)."""
    findings: List[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            fname = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else "")
            if fname == "eval":
                findings.append(("eval_kullanimi", getattr(node, "lineno", 0)))
            elif fname == "exec":
                findings.append(("exec_kullanimi", getattr(node, "lineno", 0)))
            elif fname in ("load", "loads") and isinstance(f, ast.Attribute):
                base = f.value
                base_name = base.id if isinstance(base, ast.Name) else ""
                if base_name == "pickle":
                    findings.append(("pickle_load", getattr(node, "lineno", 0)))
                elif base_name == "yaml" and fname == "load":
                    has_loader = any(
                        (kw.arg in ("Loader", "unsafe")) for kw in node.keywords)
                    if not has_loader:
                        findings.append(("yaml_unsafe", getattr(node, "lineno", 0)))
            # subprocess shell=True
            if isinstance(f, ast.Attribute) and f.attr in ("run", "Popen", "call"):
                base = f.value
                if isinstance(base, ast.Name) and base.id == "subprocess":
                    for kw in node.keywords:
                        if kw.arg == "shell":
                            val = kw.value
                            if isinstance(val, ast.Constant) and val.value is True:
                                findings.append(("shell_true",
                                                 getattr(node, "lineno", 0)))
        elif isinstance(node, ast.Assign):
            # sabitlenmis sifre/anahtar: NAME = "literal"
            target = node.targets[0] if node.targets else None
            if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str) and node.value.value:
                t = target.id.lower()
                if any(k in t for k in ("password", "passwd", "secret", "api_key",
                                        "apikey", "token")):
                    if node.value.value and len(node.value.value) >= 8 \
                            and not node.value.value.startswith(("os.", "env(")):
                        findings.append(("gizli_bilgi", getattr(node, "lineno", 0)))

    return [{"tip": tip, "satir": ln,
             "seviye": SECURITY_CHECKS[tip][0],
             "aciklama": SECURITY_CHECKS[tip][1]}
            for tip, ln in findings]


def type_hint_coverage(tree) -> Tuple[float, int]:
    """Fonksiyonlarin tip ipucu kapsami (%)."""
    total = 0
    hinted = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            total += 1
            has_return = node.returns is not None
            has_args = any(a.annotation for a in node.args.args
                           if a.arg not in ("self", "cls"))
            if has_return or has_args:
                hinted += 1
    return (round(hinted / total * 100, 1) if total else 100.0), total


# ============================================================
# Dosya analizi
# ============================================================

def analyze_file(rel: str, content: str, tree=None) -> Optional[dict]:
    """Tek dosya: skor + sorunlar + guvenlik + metrikler."""
    if tree is None:
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {"scores": None,
                    "issues": [{"tip": "parse_hatasi", "seviye": "kritik",
                                "satir": e.lineno or 0,
                                "aciklama": f"SyntaxError: {e.msg}"}],
                    "security": [], "complexity": {}, "type_hint": None,
                    "lines": len(content.splitlines())}

    lines = len(content.splitlines())
    classes = []
    functions = []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [{"name": m.name, "decorators": [d.id for d in m.decorator_list
                                                       if isinstance(d, ast.Name)]}
                       for m in node.body if isinstance(m, ast.FunctionDef)]
            classes.append({"name": node.name, "methods": methods})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(node)

    fdata = {"lines": lines, "classes": classes, "functions": functions,
             "imports": imports}
    scores = score_file(fdata)

    issues: List[dict] = []
    if lines > 1000:
        issues.append({"tip": "buyuk_dosya",
                       "seviye": "kritik" if lines > 1500 else "orta",
                       "satir": lines,
                       "aciklama": f"{lines} satir — birden fazla module bolunmeli (SRP)"})
    if len(imports) > 20:
        issues.append({"tip": "fazla_bagimlilik", "seviye": "dusuk",
                       "satir": 0,
                       "aciklama": f"{len(imports)} import — fazla dis bagimlilik"})
    if not classes and len(functions) > 15:
        issues.append({"tip": "sinif_eksik", "seviye": "dusuk",
                       "satir": 0,
                       "aciklama": f"{len(functions)} fonksiyon 0 sinif — OOP dusunulebilir"})

    # dongusel karmaşıklık
    complexity: Dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cc = cyclomatic_complexity(node)
            complexity[node.name] = cc
            if cc > 15:
                issues.append({"tip": "yuksek_karmasiklik",
                               "seviye": "yuksek" if cc > 25 else "orta",
                               "satir": node.lineno,
                               "aciklama": f"'{node.name}' CC={cc} — kucuk parcalara bolunmeli"})

    # ulaşılamaz kod
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for ln in detect_unreachable(node):
                issues.append({"tip": "ulasilamaz_kod", "seviye": "orta",
                               "satir": ln,
                               "aciklama": "return/raise sonrasi erisilemez kod"})

    # kullanılmayan değişken (fonksiyon kapsami, ilk 5)
    unused_vars: List[Tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            unused_vars.extend(detect_unused_variables(node))
    for name, ln in unused_vars[:5]:
        issues.append({"tip": "kullanilmayan_degisken", "seviye": "dusuk",
                       "satir": ln,
                       "aciklama": f"'{name}' atanmis ama hic okunmuyor"})

    # güvenlik
    security = detect_security(tree)
    for s in security:
        issues.append({"tip": f"guvenlik_{s['tip']}", "seviye": s["seviye"],
                       "satir": s["satir"], "aciklama": s["aciklama"]})

    th_pct, th_total = type_hint_coverage(tree)

    return {"scores": scores, "issues": issues, "security": security,
            "complexity": complexity, "type_hint": th_pct,
            "type_hint_total": th_total, "lines": lines}


def run_quality_analysis(root_path: str, py_rel_paths: List[str]) -> Dict:
    """Tum proje icin kalite analizi.

    Donus: {"by_file": {...}, "summary": {...}, "errors": [...]}
    """
    root = Path(root_path)
    by_file: Dict[str, dict] = {}
    errors: List[str] = []
    all_scores = []
    total_issues = 0
    kritik = 0

    for rel in sorted(set(p.replace("\\", "/") for p in py_rel_paths)):
        content, tree = get_content_and_tree(root / rel)
        if content is None:
            errors.append(f"{rel}: okunamadi")
            continue
        if tree is None:
            by_file[rel] = {
                "scores": None,
                "issues": [{"tip": "parse_hatasi", "seviye": "kritik",
                            "satir": 0, "aciklama": "SyntaxError"}],
                "security": [], "complexity": {}, "type_hint": None,
                "lines": 0,
            }
            continue
        result = analyze_file(rel, content, tree=tree)
        if result is None:
            continue
        by_file[rel] = result
        if result["scores"]:
            all_scores.append(result["scores"]["Toplam"])
        total_issues += len(result["issues"])
        kritik += sum(1 for i in result["issues"] if i.get("seviye") == "kritik")

    worst = sorted(
        ((rel, v["scores"]["Toplam"]) for rel, v in by_file.items()
         if v["scores"]),
        key=lambda x: x[1])[:5]

    summary = {
        "dosya_sayisi": len(by_file),
        "ortalama_skor": round(sum(all_scores) / len(all_scores), 1)
        if all_scores else 0,
        "sorun_sayisi": total_issues,
        "kritik_sorun": kritik,
        "en_dusuk_skorlu": [{"dosya": r, "skor": s} for r, s in worst],
    }

    return {"by_file": by_file, "summary": summary, "errors": errors}
