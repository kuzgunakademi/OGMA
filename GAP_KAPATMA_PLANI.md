# OGM — DEVKIT GAP KAPATMA PLANI + D FAZLARI (Knowledge Graph / Etki / Hafiza)
# ============================================================
# Tarih: 2025-09-14
# Durum: D1-D2 TAMAMLANDI, D3-D4-D5 BEKLIYOR (benchmark EN SON)
# Ilke: "4 GB model bile olsa deterministik proje bilgisinin uzerine
#        oturtarak en guvenilir asistan; 15 GB ayni altyapinin derin
#        reasoning katmani" — AST -> Graph -> Evidence -> LLM
# =================================================

## D1 [TAMAMLANDI 2025-09-14] KNOWLEDGE GRAPH CEKIRDEGI
- Dosya: core/bilgi_grafigi.py — tek graf modeli:
  Dugumler: FILE/CLASS/FUNCTION/METHOD (543 dugum Ogma'da)
  Kenarlar: CONTAINS/IMPORTS/CALLS/INHERITS (646 kenar)
- ETKI icin TUM importlar (fonksiyon-ici/lazy dahil), sinif kurucu
  cagrilari takip (LocalModelManager() -> class dugumu)
- Sorgular: transitive_dependents (BFS, seviyelendirilmis), related_files
- ARCHITECTURE_MAP result.data["bilgi_grafigi"] ile JSON cikti
- Dogrulama: sentetik projede kalitim/cagri/import zinciri + transitive
  helper->top->Child.run->main.py zinciri tam cikti

## D2 [TAMAMLANDI 2025-09-14] TRANSITIVE ETKI + RISK
- core/araclar.py: impact_analysis_v2 + format_impact_v2
- Cok seviyeli: level_1 dogrudan, level_2+ dolayli (dosya bazli
  tek-seviye atama — dosya en yakin seviyesinde bir kez)
- Etkilenen testler + dongu uyeligi + risk (HIGH/MEDIUM/LOW)
- GUI: Gelistirici Araclari > Etki Analizi artik v2
- Dogrulama: analysis_engine.py -> 6 dosya/2 test/MEDIUM; lazy import
  (hybrid_analyzer) ve kurucu cagrilari zincire girdi

## A FAZLARI [HEPSI TAMAMLANDI 2025-09-14]
A.1 Bagimlilik/Dongu, A.2 Cagri Grafi+Proje-Olu Kod, A.3 Kalite/Guvenlik,
A.6 API Yuzeyi, A.8 Kullanim Dogrulama, A.9 AST Cache, A.10 Fingerprint/Diff
FAZ B KB Raporlari (QUICKREF/PROJECT_MAP/SYMBOL_INDEX/ARCHITECTURE .md),
FAZ C Gelistirici Araclari (Sembol Ara/Dosya Anahati/Etki Analizi v2)

## D3-D4-D5 (BEKLIYOR)
- D3 [TAMAMLANDI 2025-09-14]: Mimari Hafiza — core/hafiza.py; her tarama
  kaydi .ogma_cache/history.json (max 100), zaman cizelgesi kb/HAFIZA.md
  (dosya/satir/dongu/olu/skor/degisim tablosu + gelisim ozeti), LLM'e
  baglam verilebilir. Coklu ciktiya eklendi (16 dosya).
- D4 [TAMAMLANDI 2025-09-14]: Model Capability Test + Profile
  — core/model_capability.py (20 standart gorev testi, 5 kategori;
  her test gercek LLM cagrisi + anahtar-kelime/yapisal skorlama)
  + gui/model_capability_gui.py (progress + bar grafik + JSON cache).
  Model sinifi olculmus skora gore otomatik. 18 pytest gecti.
- D5: Mini Benchmark (5-10 gercek proje + precision/recall) ~2-3 gun — EN SON
- Promo guncelleme (UNDERSTAND->MAP->CHANGE) — D2+D4 sonrasi

## FAZ E — IDE ENTEGRASYONU (MCP + Provider + Watcher)
- E1 [TAMAMLANDI 2025-09-14]: MCP Sunucu — ogma_mcp.py, 9 arac
  (project_overview, find_symbol, file_outline, impact_analysis v2,
  dead_code, quality_summary, dependencies, hafiza_timeline,
  usage_validation); stdio transport; mcp 2.x MCPServer API.
  E2E test: gercek MCP istemcisi stdio uzerinden baglandi, 9 arac
  listelendi, 4 sorgu gercek veriyle yanitlandi (overview/find/impact/
  HAFIZA). KURULUM.txt'ye VSCode/Cline konfigurasyon rehberi eklendi.
  mcp paketi requirements'a opsiyonel eklendi.
- E2 [TAMAMLANDI 2025-09-14]: OpenAI-uyumlu provider uc noktalari
  — core/provider_client.py (base_url/model/key ayarlardan, herhangi
  OpenAI-uyumlu API: DeepSeek/Z.ai GLM/OpenRouter/yerel vLLM/LM Studio)
  + OgmaAgent._init_provider backend + settings (providers list +
  active_provider). Dogrulama: provider init calisti (glm-5.3-flash
  profil), 18 pytest gecti. Not: provider yonetim UI (ekle/sil/sec)
  Ayarlar penceresine sonraki adimda eklenebilir.
- E3 [TAMAMLANDI 2025-09-14]: Watcher modu — core/watcher.py (polling
  FileWatcher: fingerprint diff + callback) + gui/watcher_gui.py (baslat/
  durdur/interval + canli rapor: degisen dosya listesi + statik hata +
  etki analizi RISK). GUI: Araclar > ANALIZ > "Canli Izleyici".
  Dogrulama: sentetik dosya ekleme yakalandi (added mod.py), 18 pytest.
  (Tree-sitter ertelendi: portable bozulur; dosya-granüler cache ayni
  faydanin %90'ini verir)
