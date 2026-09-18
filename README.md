# Ogma — Proje Analiz Asistanı

**Hybrid AST + LLM Kod Mimarisi Analiz Aracı** — Her Windows PC'de (zayıf donanım dahil), kod tabanını gerçek ilişkilerle haritalayan, bir değişikliğin tüm domino etkisini hesaplayan ve kullanıcının güvenli değişiklik yapmasını sağlayan **yerel mimari asistan**.

> Sürücü-harf bağımsız, offline-first çalışır; USB ile taşınabilir. Kod asla buluta gitmez.

## Ana Fikir: UNDERSTAND → MAP → CHANGE

- **UNDERSTAND** — Kod tabanının ne yaptığını çıkar (proje amacı, altyapı, durum)
- **MAP** — Dosya/sınıf/fonksiyon/bağımlılıkları GERÇEK ilişkilerle haritala (Knowledge Graph: `FILE/CLASS/FUNCTION/METHOD` düğümleri, `CONTAINS/IMPORTS/CALLS/INHERITS` kenarları)
- **CHANGE** — Bir şeyi değiştirdiğinde neyin etkileneceğini seviye seviye hesapla (transitive etki + etkilenen testler + risk seviyesi)

Çoğu analiz aracı UNDERSTAND'da kalır. Ogma'nın farklı değeri **MAP** ve **CHANGE**'dedir.

## Tasarım İlkesi: AST → Graph → Evidence → LLM

- Gerçeklik LLM'e değil, **deterministik motora** emanet edilir: import grafikleri, çağrı grafikleri, döngü tespiti, kalite skorları, güvenlik taramaları — hepsi AST tabanlı, uydurmasız, tekrarlanabilir.
- LLM sadece **anlam** tarafında devreye girer: "Bu yapı ne anlama geliyor? Risk nedir? Ne yapılmalı?"
- Zayıf donanımda (4 GB model) analiz yine gerçek veriye dayanır; LLM yüzeyselliği mimarinin kendisiyle telafi edilir.

## Mimari Katmanlar

| Katman | Görev |
|---|---|
| 1. Toplama | AST parse (önbellekli) → düğüm/kenar çıkarımı |
| 2. İlişki | Knowledge Graph + import grafi + çağrı grafi + matris |
| 3. Analiz | Döngü tespiti, ölü kod, kalite/güvenlik, API yüzeyi, kullanım doğrulama, etki analizi |
| 4. Rapor | Çoklu çıktı (rapor/veri/KB) + çoklu format |
| 5. Yorum | LLM (anlam/risk/öneri — deterministik kanıt üzerine) |
| 6. Arayüz | GUI (mimari odaklı) + CLI (aynı çekirdek) |

Katman 1–4 tamamen deterministiktir — hiçbir yapay zeka bunları belirlemez. Katman 5 opsiyoneldir ve güvenilirliği katman 3'ün kanıtlarına bağlıdır.

## Özellikler

- **Transitive etki analizi** — "Bu fonksiyon değişirse hangi modüller/fonksiyonlar/testler etkilenir?"
- **Mimari hafıza** — Her tarama geçmişe kaydedilir (fingerprint + diff + istatistik), zaman çizelgesi projenin evrimini gösterir.
- **Model bağımsızlığı** — GGUF / CPU / GPU / Ollama / API; veri kaynağı ve analiz boru hattı aynı kalır.
- **Donanım taraması** — AVX2 kontrolü, NVIDIA/CUDA veya AMD/Intel/Vulkan otomatik tespiti, thread/context önerisi.
- **Gizlilik** — Tüm işlem yerelde. API anahtarı `storage/config.json` içinde saklanmaz (boş gelir), kullanıcı kendi anahtarını girer.

## Kurulum ve Çalıştırma

**Gereksinimler (kullanıcının indirmesi gereken hiçbir şey yoktur):**
- Windows 10/11, 64-bit
- AVX2 destekli işlemci (2013 sonrası)
- ~11 GB boş alan
- NVIDIA GPU şart değildir; varsa otomatik bulunur (CUDA sürücü 550+)

**Çalıştırma:**
```
run_gui.bat        → GUI'yi başlatır (sürücü harfinden bağımsız)
```

**Yeni PC'de Python ortamı bozulursa:**
```
env_create.bat     → Miniconda + internet gerekir (bir kez)
```

## Depoda Neler YOK ve Bunları Nasıl Sağlarsın?

> Bu repo yalnızca **kaynak kodunu** içerir. Çalışma zamanına ait büyük ikili dosyalar ve yerel durum `gitignore` ile dışarıda tutulmuştur — repoyu klonlayan kişi aşağıdakileri **kendisi sağlamalıdır**.

| Öğe | Ne işe yarar | Nasıl elde edilir |
|---|---|---|
| `Python_Ortami/` | Taşınabilir conda ortamı (CPU modeli için `llama-cpp-python` dahil) | Depoda yoktur. `env_create.bat` ile yeniden oluşturulur (Miniconda + bir kez internet gerekir) |
| `Miniconda_Kurulum.exe` | Miniconda kurulum paketi (~92 MB) | Depoda yoktur. [conda.io resmi sitesinden](https://docs.conda.io/en/latest/miniconda.html) indirilir |
| `models/` → `base/` | Yerel GGUF model dosyaları (~4.1 GB, Türkçe 7B Q4 taban model) | Depoda yoktur. Kendi GGUF modelinizi `models/base/` altına koymalısınız |
| `libs/llama-server-cuda`, `libs/llama-server-vulkan`, `libs/*.zip` | GPU motorları (CUDA/Vulkan runtime ~646 MB) | Depoda yoktur. [llama.cpp sürümlerinden](https://github.com/ggml-org/llama.cpp/releases) `llama-server` CUDA/Vulkan paketleri indirilip `libs/` altına yerleştirilir |
| `storage/` | Çalışma zamanı durumu (`config.json`, session cache, loglar) | Depoda yoktur. İlk çalıştırmada otomatik oluşturulur. API anahtarları yalnızca burada, yerel olarak saklanır |

**Hatırlatma:** `models/api_models.py`, `models/__init__.py` bir Python paketi olduğundan depoda **vardır**; yalnızca alt klasörlerdeki (GGUF modelleri, motorlar) hariç tutulmuştur.

## Kullanım

**CLI:**
```
python main.py
```

**MCP sunucusu (IDE entegrasyonu — VSCode / Cline / OpenCode):**
```
"ogma": {
  "command": "<proje>\\Python_Ortami\\envs\\ds_agent\\python.exe",
  "args": ["<proje>\\ogma_mcp.py"]
}
```
9 araç: sembol ara, dosya anahattı, etki analizi, ölü kod, kalite, bağımlılık, hafıza, kullanım doğrulama, proje özeti. Tüm araçlar deterministiktir (kanıtlı grafik).

## Test

```
pytest
```

## Proje Yapısı

```
ogma/
├── core/          # Analiz motoru (AST, Knowledge Graph, etki/kalite/güvenlik analizi)
├── gui/           # Mimari odaklı GUI ekranları
├── models/        # API model tanımları (yerel GGUF modelleri depoda değildir)
├── utils/         # Yardımcılar ve doğrulayıcılar
├── config/        # Ayarlar
├── tests/         # Testler
├── main.py        # CLI giriş noktası
├── gui_main.py    # GUI giriş noktası
├── ogma_mcp.py    # MCP sunucusu
└── pyproject.toml
```

## Lisans

Bu proje özel/henüz lisanssızdır. Kullanım ve dağıtım koşulları için proje sahibiyle iletişime geçin.

---

© 2026 **İlker Can Karagülle** · [Loreweld AI](https://loreweld.ai) tarafından geliştirildi.