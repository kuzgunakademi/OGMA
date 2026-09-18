"""model_capability.py — Model Capability Test + Profile (D4).

Model secildiginde 20 standart gorev testi calistirilir (gercek LLM cagrilari);
cevaplar anahtar-kelime/yapisal olarak skorlanir; olculmus Capability Profile
uretilir. Kafadan puan vermek yerine "bu model Ogma'nin gorevlerinde bu
performansi gosterdi" raporu uretilir.

5 kategori: Basic Analysis, Code Understanding, Architecture,
Impact Analysis, Refactoring — her kategori 4 test (toplam 20).
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from core.analysis_engine import AnalysisEngine


# ============================================================
# Test tanimlari: her test bir prompt + skorlama fonksiyonu icerir
# ============================================================

def _has_any(text: str, keywords: List[str]) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in keywords)


def _has_all(text: str, keywords: List[str]) -> bool:
    t = text.lower()
    return all(k.lower() in t for k in keywords)


def _nonempty_response(text: str) -> bool:
    return bool(text and len(text.strip()) > 20)


# --- KATEGORI 1: BASIC ANALYSIS (basit analiz, ozet, siniflandirma) ---

def _t01_score(resp: str, **kw) -> float:
    """T01: Kod amaci cikarma."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["fonksiyon", "function", "def", "class", "sınıf"]):
        score += 0.4
    if _has_any(resp, ["analiz", "analyze", "kod", "code", "yapar", "does"]):
        score += 0.3
    if len(resp) > 50:
        score += 0.3
    return min(score, 1.0)

def _t02_score(resp: str, **kw) -> float:
    """T02: Import iliskisi aciklama."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["import", "kütüphane", "library", "bağımlılı", "bağlı"]):
        score += 0.4
    if _has_any(resp, kw.get("imported_names", [])):
        score += 0.4
    if len(resp) > 40:
        score += 0.2
    return min(score, 1.0)

def _t03_score(resp: str, **kw) -> float:
    """T03: Basit siniflandirma (framework/kütüphane/araç)."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["framework", "kütüphane", "library", "araç", "tool", "standart"]):
        score += 0.5
    if _has_any(resp, kw.get("expected_categories", [])):
        score += 0.5
    return min(score, 1.0)

def _t04_score(resp: str, **kw) -> float:
    """T04: Ozet uretme (uzunluk + yapilirlik)."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if len(resp) > 80:
        score += 0.4
    if _has_any(resp, ["proje", "project", "sistem", "system", "program"]):
        score += 0.3
    if _has_any(resp, ["analiz", "yönet", "manage", "izle", "monitor", "oluştur"]):
        score += 0.3
    return min(score, 1.0)


# --- KATEGORI 2: CODE UNDERSTANDING (kod okuma, akıl yürütme) ---

def _t05_score(resp: str, **kw) -> float:
    """T05: Fonksiyon davranisi aciklama."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, kw.get("expected_concepts", [])):
        score += 0.5
    if _has_any(resp, ["döner", "return", "verir", "hesaplar", "çağır", "call"]):
        score += 0.3
    if len(resp) > 40:
        score += 0.2
    return min(score, 1.0)

def _t06_score(resp: str, **kw) -> float:
    """T06: Parametre/donuş tipi çıkarımı."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["parametre", "parameter", "argüman", "argument", "alır"]):
        score += 0.4
    if _has_any(resp, kw.get("expected_types", ["string", "int", "list", "dict", "sayı"])):
        score += 0.3
    if _has_any(resp, ["döner", "return", "sonuç"]):
        score += 0.3
    return min(score, 1.0)

def _t07_score(resp: str, **kw) -> float:
    """T07: Kod hatasi bulma (bilinen sintaks hatasi)."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["hata", "error", "sorun", "problem", "eksik", "missing"]):
        score += 0.5
    if _has_any(resp, kw.get("expected_bug_keywords", [])):
        score += 0.5
    return min(score, 1.0)

def _t08_score(resp: str, **kw) -> float:
    """T08: Kod farklari karsilastirma."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["fark", "diff", "değişiklik", "changed", "eklenen", "added"]):
        score += 0.5
    if len(resp) > 60:
        score += 0.5
    return min(score, 1.0)


# --- KATEGORI 3: ARCHITECTURE (mimari akil yurutme) ---

def _t09_score(resp: str, **kw) -> float:
    """T09: Mimari desen tanima."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["mimari", "architecture", "desen", "pattern", "katman", "layer"]):
        score += 0.5
    if _has_any(resp, ["separation", "ayrım", "modüler", "modular", "abstraction", "soyutlama"]):
        score += 0.5
    return min(score, 1.0)

def _t10_score(resp: str, **kw) -> float:
    """T10: Bagimlilik zinciri aciklama."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["bağımlı", "depend", "import", "kullanır", "uses"]):
        score += 0.5
    if _has_any(resp, kw.get("expected_deps", [])):
        score += 0.5
    return min(score, 1.0)

def _t11_score(resp: str, **kw) -> float:
    """T11: Coklu-dosya iliski akil yurutme."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, kw.get("expected_files", [])):
        score += 0.6
    if _has_any(resp, ["ilişki", "relation", "bağlantı", "connection", "çağır", "call"]):
        score += 0.4
    return min(score, 1.0)

def _t12_score(resp: str, **kw) -> float:
    """T12: Alt-sistem sinirlari belirleme."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["alt-sistem", "subsystem", "modül", "module", "katman", "layer"]):
        score += 0.5
    if _has_any(resp, kw.get("expected_subsystems", [])):
        score += 0.5
    return min(score, 1.0)


# --- KATEGORI 4: IMPACT ANALYSIS (etki analizi akil yurutme) ---

def _t13_score(resp: str, **kw) -> float:
    """T13: Degisiklik etkisini tahmin etme."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["etkiler", "affect", "etkilen", "impact", "risk", "bozul"]):
        score += 0.5
    if _has_any(resp, kw.get("expected_impact", [])):
        score += 0.5
    return min(score, 1.0)

def _t14_score(resp: str, **kw) -> float:
    """T14: Risk degerlendirme."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["risk", "yüksek", "high", "düşük", "low", "dikkat", "careful"]):
        score += 0.5
    if len(resp) > 60:
        score += 0.5
    return min(score, 1.0)

def _t15_score(resp: str, **kw) -> float:
    """T15: Test etkilenimi tahmin etme."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["test", "testler", "coverage", "kapsam"]):
        score += 0.5
    if _has_any(resp, ["etkilen", "affect", "bozul", "break", "çalışmaz"]):
        score += 0.5
    return min(score, 1.0)

def _t16_score(resp: str, **kw) -> float:
    """T16: Coklu-dosya degisiklik koordinasyonu."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["değiştir", "change", "güncelle", "update", "uyum"]):
        score += 0.4
    if _has_any(resp, kw.get("expected_files", [])):
        score += 0.6
    return min(score, 1.0)


# --- KATEGORI 5: REFACTORING (refactor planlama) ---

def _t17_score(resp: str, **kw) -> float:
    """T17: Refactoring onerisi uretme."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["böl", "split", "refactor", "yeniden", "ayır", "extract"]):
        score += 0.5
    if len(resp) > 80:
        score += 0.5
    return min(score, 1.0)

def _t18_score(resp: str, **kw) -> float:
    """T18: Kod iyileştirme onerisi."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["iyileştir", "improve", "optimize", "daha iyi", "better"]):
        score += 0.4
    if _has_any(resp, ["okunabilir", "readable", "temiz", "clean", "sade"]):
        score += 0.3
    if len(resp) > 60:
        score += 0.3
    return min(score, 1.0)

def _t19_score(resp: str, **kw) -> float:
    """T19: Yapisal öneri (yeni modül/dosya)."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["dosya", "file", "modül", "module", "oluştur", "create"]):
        score += 0.5
    if _has_any(resp, kw.get("expected_structure", [])):
        score += 0.5
    return min(score, 1.0)

def _t20_score(resp: str, **kw) -> float:
    """T20: Migrasyon plani (eski -> yeni yapi)."""
    if not _nonempty_response(resp):
        return 0.0
    score = 0.0
    if _has_any(resp, ["adım", "step", "plan", "aşama", "phase", "sıra"]):
        score += 0.4
    if _has_any(resp, ["migrasyon", "migration", "taşı", "move", "geçiş"]):
        score += 0.3
    if len(resp) > 80:
        score += 0.3
    return min(score, 1.0)


# ============================================================
# Test tanimlari listesi
# ============================================================

CAPABILITY_TESTS = [
    # (test_id, kategori, prompt_template, scorer, extra_kw)
    ("T01", "Basic Analysis",
     "Asagidaki Python kodunun ne yaptigini Turkce acikla:\n\n{code_snippet}",
     _t01_score, {}),
    ("T02", "Basic Analysis",
     "Asagidaki import satirlarini acikla. Bu moduller ne icin kullaniliyor?\n\n{imports_text}",
     _t02_score, {"imported_names": ["tkinter", "json", "os", "path", "requests"]}),
    ("T03", "Basic Analysis",
     "Asagidaki import'lari Framework/Kutuphane/Arac olarak kategorize et:\n\n{imports_text}",
     _t03_score, {"expected_categories": ["standart", "üçüncü", "yerel", "standard", "third", "local"]}),
    ("T04", "Basic Analysis",
     "Asagidaki proje istatistiklerine bakarak bu projenin ne oldugunu tek paragraf ozetle:\n\n{project_stats}",
     _t04_score, {}),

    ("T05", "Code Understanding",
     "Asagidaki fonksiyonun nasil calistigini adim adim acikla:\n\n{code_snippet}",
     _t05_score, {"expected_concepts": ["döngü", "loop", "koşul", "if", "return", "liste"]}),
    ("T06", "Code Understanding",
     "Asagidaki fonksiyonun parametrelerini ve donus degerini acikla:\n\n{code_snippet}",
     _t06_score, {}),
    ("T07", "Code Understanding",
     "Asagidaki kodda bir hata var. Bul ve acikla:\n\n{buggy_code}",
     _t07_score, {"expected_bug_keywords": ["tanımsız", "undefined", "name", "eksik", "missing", "değişken"]}),
    ("T08", "Code Understanding",
     "Asagidaki iki kod arasindaki farklari listele:\n\nESKI:\n{old_code}\n\nYENI:\n{new_code}",
     _t08_score, {}),

    ("T09", "Architecture",
     "Asagidaki kod yapisinda hangi mimari desen var? Acikla:\n\n{arch_snippet}",
     _t09_score, {}),
    ("T10", "Architecture",
     "Asagidaki dosyanin hangi modullere bagimli oldugunu ve neden oldugunu acikla:\n\n{deps_text}",
     _t10_score, {"expected_deps": ["config", "settings", "path", "json"]}),
    ("T11", "Architecture",
     "Asagidaki dosyalar arasindaki iliskiyi acikla:\n\nDosya A: {file_a_desc}\nDosya B: {file_b_desc}",
     _t11_score, {"expected_files": ["a", "b", "modul", "file"]}),
    ("T12", "Architecture",
     "Asagidaki klasor yapisinda hangi alt-sistemler var ve sinirlari nerede?\n\n{structure_text}",
     _t12_score, {"expected_subsystems": ["core", "gui", "config", "utils", "model"]}),

    ("T13", "Impact Analysis",
     "Asagidaki dosyada bir fonksiyonun imzasi degistirilirse hangi bolumler etkilenir?\n\nDosya: {file_desc}\nBagimlilar: {dependents_text}",
     _t13_score, {"expected_impact": ["etkilen", "affect", "bozul", "break", "hata"]}),
    ("T14", "Impact Analysis",
     "Asagidaki degisikligin risk seviyesini degerlendir (HIGH/MEDIUM/LOW) ve gerekcelendir:\n\n{impact_text}",
     _t14_score, {}),
    ("T15", "Impact Analysis",
     "Asagidaki modul degistirilirse hangi testler etkilenir? Eksik test kapsami var mi?\n\nModul: {module_desc}\nTestler: {tests_text}",
     _t15_score, {}),
    ("T16", "Impact Analysis",
     "Asagidaki dosyada yapilacak degisiklik icin hangi dosyalarin birlikte guncellenmesi gerekir?\n\nDosya: {file_desc}\nBagimlilar: {dependents_text}",
     _t16_score, {"expected_files": ["güncelle", "update", "değiştir", "change", "uyumla"]}),

    ("T17", "Refactoring",
     "Asagidaki dosya cok buyuk (1000+ satir). Nasil bolunmesi gerektigini oner:\n\n{large_file_desc}",
     _t17_score, {}),
    ("T18", "Refactoring",
     "Asagidaki kodu daha okunabilir hale getirmek icin 3 oner ver:\n\n{code_snippet}",
     _t18_score, {}),
    ("T19", "Refactoring",
     "Asagidaki fonksiyonlar ayni isi yapiyor. Hangi dosyada tutulmali, yeni bir modul olusturulmali? Oner:\n\n{twin_desc}",
     _t19_score, {"expected_structure": ["ortak", "common", "shared", "yeni", "new", "ayrı"]}),
    ("T20", "Refactoring",
     "Asagidaki eski yapiyi yeni yapiya gecirmek icin adim adim migrasyon plani yaz:\n\nESKI: {old_struct}\nYENI: {new_struct}",
     _t20_score, {}),
]

CATEGORIES = ["Basic Analysis", "Code Understanding", "Architecture",
              "Impact Analysis", "Refactoring"]

CATEGORY_LABELS = {
    "Basic Analysis": "Basit Analiz",
    "Code Understanding": "Kod Anlama",
    "Architecture": "Mimari",
    "Impact Analysis": "Etki Analizi",
    "Refactoring": "Refactoring",
}


# ============================================================
# Test orneleri (sabit — gercek kod parcalari)
# ============================================================

SAMPLE_CODE = """import os
import json
from pathlib import Path

def load_config(path):
    if not Path(path).exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

class ConfigManager:
    def __init__(self, path):
        self.path = path
        self.data = load_config(path)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        save_config(self.path, self.data)
"""

SAMPLE_IMPORTS = """import os
import json
import tkinter as tk
from pathlib import Path
from typing import Optional
import requests
from config.settings import config
from core.local_client import LocalModelManager
"""

SAMPLE_BUGGY = """def greet(name):
    return "Hello, " + nmae + "!"

def process(items):
    total = 0
    for item in items:
        total += itm
    return total
"""

SAMPLE_ARCH = """class ConfigManager:
    def __init__(self, path):
        self.data = load_config(path)
    def get(self, key): ...
    def set(self, key, value): ...

class ModelManager:
    def __init__(self, config):
        self.config = config
    def load_model(self): ...
    def unload_model(self): ...

class GUIApp:
    def __init__(self):
        self.config = ConfigManager("settings.json")
        self.model = ModelManager(self.config)
"""

SAMPLE_DEPENDENTS = """config/settings.py su dosyalar tarafindan import ediliyor:
- gui_main.py (config.get ile ayarlari okuyor)
- main.py (CLI konfigurasyonu)
- core/ignore_manager.py (ignore listesi)
- core/session_manager.py (oturum kayitlari)
- gui/gelistirici_araclar_gui.py (workspace yolu)
"""

SAMPLE_STRUCTURE = """proje/
  core/          -> is mantigi, model yonetimi, analiz motoru
  gui/           -> Tkinter arayuz bilesenleri
  config/        -> ayarlar ve konfigurasyon
  utils/         -> yardimci fonksiyonlar
  tests/         -> birim testleri
  models/        -> API model tanimlari
"""

# ============================================================
# Ana test kosucu
# ============================================================

def run_capability_test(llm_client, model_id: str,
                        progress_callback=None) -> Dict:
    """20 standart gorev testi calistirir, olculmus Capability Profile uretir.

    Donus: {"categories": {kategori: {"score": %, "tests": [...]}},
            "overall_score": %, "model": ..., "tarih": ...,
            "recommendations": [...], "class": Lite/Standard/Pro}
    """
    results: List[Dict] = []
    total = len(CAPABILITY_TESTS)

    for i, (tid, category, prompt_template, scorer, extra_kw) in enumerate(CAPABILITY_TESTS):
        if progress_callback:
            progress_callback(i, total, f"{tid}: {category} testi...")

        # prompt'u doldur
        prompt = prompt_template.format(
            code_snippet=SAMPLE_CODE[:1500],
            imports_text=SAMPLE_IMPORTS,
            project_stats="42 dosya, 7 klasor, 5600 satir; core(20), gui(2), config(2), utils(3)",
            buggy_code=SAMPLE_BUGGY,
            old_code="def save(path, data):\n    open(path, 'w').write(str(data))",
            new_code="def save(path, data):\n    Path(path).parent.mkdir(parents=True, exist_ok=True)\n    with open(path, 'w', encoding='utf-8') as f:\n        json.dump(data, f, indent=2)",
            arch_snippet=SAMPLE_ARCH,
            deps_text="config/settings.py -> core/local_client.py, gui_main.py",
            file_a_desc="config/settings.py: uygulama ayarlarini JSON olarak saklar",
            file_b_desc="core/local_client.py: GGUF model yukler ve chat_completion yapar",
            structure_text=SAMPLE_STRUCTURE,
            file_desc="config/settings.py: tum uygulama ayarlari burada",
            dependents_text=SAMPLE_DEPENDENTS,
            impact_text="config/settings.py degistirilirse 5 dosya etkilenir, 2 test kirilir",
            module_desc="core/analysis_engine.py: mimari analiz motoru",
            tests_text="tests/unit/test_scanner.py mevcut; test_analysis_engine.py yok",
            large_file_desc="gui_main.py: 3800+ satir, GUI + agent + analysis + tools hepsi tek dosyada",
            twin_desc="def process(data) hem mod_a.py hem mod_b.py'de ayni isi yapiyor",
            old_struct="tek dosya: gui_main.py (3800 satir, her sey icinde)",
            new_struct="core/ + gui/ + config/ + utils/ (domain bazli ayri dosyalar)",
            **extra_kw,
        )

        try:
            response = llm_client.chat_completion(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
        except Exception:
            response = None

        score = scorer(response or "", **extra_kw)
        results.append({
            "test_id": tid,
            "kategori": category,
            "score": round(score, 2),
            "response_len": len(response or ""),
        })

    # kategori bazinda toplama
    categories: Dict[str, dict] = {}
    for cat in CATEGORIES:
        cat_tests = [r for r in results if r["kategori"] == cat]
        avg = sum(r["score"] for r in cat_tests) / len(cat_tests) if cat_tests else 0
        categories[cat] = {
            "label": CATEGORY_LABELS.get(cat, cat),
            "score_pct": round(avg * 100, 1),
            "tests": cat_tests,
        }

    overall = round(sum(r["score"] for r in results) / len(results) * 100, 1) if results else 0

    # model sinifi (olculmus skora gore otomatik)
    if overall >= 80:
        model_class = "Pro"
    elif overall >= 60:
        model_class = "Standard"
    else:
        model_class = "Lite"

    # oneriler
    recommendations = []
    for cat in CATEGORIES:
        pct = categories[cat]["score_pct"]
        label = categories[cat]["label"]
        if pct >= 80:
            recommendations.append(f"✓ {label}: %{pct} — guvenilir, bu gorev icin kullanilabilir")
        elif pct >= 60:
            recommendations.append(f"⚠ {label}: %{pct} — sinirli; kritik islerde dogrulayin")
        else:
            recommendations.append(f"✗ {label}: %{pct} — zayif; bu gorev icin deterministik sonuclara guvenin")

    return {
        "model": model_id,
        "tarih": datetime.now().isoformat(timespec="seconds"),
        "categories": categories,
        "overall_score": overall,
        "model_class": model_class,
        "recommendations": recommendations,
        "results": results,
        "test_count": len(results),
    }


def format_profile(profile: Dict) -> str:
    """Capability Profile'i metin olarak formatla (GUI/MCP icin)."""
    lines = ["MODEL CAPABILITY PROFILE", "=" * 50, ""]
    lines.append(f"Model: {profile['model']}")
    lines.append(f"Tarih: {profile['tarih']}")
    lines.append(f"Model sinifi: {profile['model_class']} (olculmus skora gore)")
    lines.append(f"Genel skor: {profile['overall_score']}%")
    lines.append("")

    lines.append(f"{'Kategori':<25}{'Skor':>8}  Bar")
    lines.append("-" * 55)
    for cat in CATEGORIES:
        c = profile["categories"].get(cat, {"label": cat, "score_pct": 0})
        filled = int(c["score_pct"] / 20)
        bar = "█" * filled + "░" * (5 - filled)
        label = c.get("label", cat)
        lines.append(f"{label:<25}%{c['score_pct']:>5}  {bar}")
    lines.append("")

    lines.append("ONERILER:")
    for r in profile.get("recommendations", []):
        lines.append(f"  {r}")

    return "\n".join(lines)
