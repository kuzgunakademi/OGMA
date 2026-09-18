# OGM — MIMARI TASARIM HEDEFI VE AMAC OZETI
# ==========================================
# Tarih: 2025-09-14
# Bu dokuman programin NEDEN bu sekilde tasarlandigini, hangi ilkelerle
# ilerledigini ve nereye gittigini tek bakista anlatir.
# =================================================

## 1. TEK CUMLEYLE AMAC

Her Windows PC'de (zayif donanim dahil), kod tabanini gercek iliskilerle
haritalayan, bir degisikligin tum domino etkisini hesaplayan ve kullanicinin
guvenli degisiklik yapmasini saglayan YEREL mimari asistan.

## 2. ANA FIKIR — UNDERSTAND -> MAP -> CHANGE

UNDERSTAND  Kod tabaninin ne yaptigini cikar (proje amaci, altyapi, durum)
MAP         Dosya/sinif/fonksiyon/bagimliliklari GERCEK iliskilerle haritala
            (Knowledge Graph: FILE/CLASS/FUNCTION/METHOD dugumleri,
             CONTAINS/IMPORTS/CALLS/INHERITS kenarlari)
CHANGE      Bir seyi degistirdiginde neyin etkilenecegini seviye seviye hesapla
            (transitive etki + etkilenen testler + risk seviyesi)

Cogu analiz araci UNDERSTAND'da kalir. Ogma'nin farkli degeri MAP ve
CHANGE'dedir — siradan coding agent'lardan ayiran taraf budur.

## 3. EN ONDEGELEN TASARIM ILKESI

"4 GB model bile olsa, deterministik proje bilgisinin uzerine oturtarak
 mumkun olan en guvenilir mimari asistan uretmek.
 15 GB model ise ayni altyapinin daha derin reasoning katmanidir."

Pratikte bu su demek:

  AST -> Graph -> Evidence -> LLM

- Gerceklik LLM'e DEGIL, deterministik motora emanet edilir:
  import grafikleri, cagri grafikleri, dongu tespiti, kalite skorlari,
  guvenlik taramalari — hepsi AST tabanli, uydurmasiz, tekrarlanabilir.
- LLM sadece ANLAM tarafinda devreye girer:
  "Bu yapi ne anlama geliyor? Risk nedir? Ne yapilmali?"
- Donanim yetersizse (4 GB model) analiz yine GERCEK veriye dayalidir;
  LLM yuzeyligi mimarinin kendisiyle telafi edilir. Ornek:
  graf "17 caller / 6 modul / 3 kritik sistem" diyorsa, kucuk modelin
  "etki dusuk" cevabi ezilir ve "statik graf yuksek etki gosteriyor,
  daha guclu model onerilir" denir.

## 4. HANGI ILKELER BU YAPIYI SEKILLENDIRDI

### a) "Kucuk model = daha kotu Ogma olmamali"
Model sinifi (Lite/Standard/Pro) gorev kalitesini dusurmez; sadece
reasoning derinligini degistirir. Deterministik cekirdek ayni kalir.

### b) "Analiz sistemi modelden bagimsiz olmali"
Model degisse (GGUF/CPU/GPU/Ollama/API) veri kaynagi ve analiz boru hatti
AYNI kalir; sadece yorum katmani derinlesir.

### c) "Mimari degil envanter yeterli degil"
Sadece dosya sayisi + import listesi yetmez. Gercek deger su sorularda:
"Bu fonksiyon degisirse hangi moduller/fonksiyonlar/testler etkilenir?"
Bu soru ancak Knowledge Graph ile cevaplanir.

### d) "Her PC'de gercekten calisabilir olmali"
Offline-first: bulut bagimliligi yok, API key sart degil, goreli yollar,
surucu-harf bagimsiz .bat'lar, gomulu motorlar (CUDA/Vulkan), USB ile tasinir.
AMD PC'de CPU modu, NVIDIA'li PC'de GPU secenegi — donanim taramasi
kullanicidan bu karari alir.

### e) "Gizlilik pazarlik konusu degil"
Tum islem yerelde. Kod asla buluta gitmez (kullanici OLLAMA/DeepSeek API
secmedikce — o da kendi karari).

### f) "Uretim hazir demek her butonun calismasi demek"
Yara bandi, gecici cozum, iskelet kod yok. Her ozellik gercek testle
dogrulanir (18 pytest). "Eklendi" demeden once olculur.

### g) "Raporlamak cozum degil"
Analiz bulgularini raporlamak yetmez: ikiz fonksiyondan biri silinecek,
olu dosya temizlenecek — bunu kim yapacak? Cozum zincirinin son halkasi
(temizlik sihirbazi: dry-run + yedek + geri alma + 7 gun erteleme) planli.

## 5. MIMARI KATMANLAR

Katman 1 — TOPLAMA     AST parse (onbellekli) -> dugum/kenar cikarimi
Katman 2 — ILISKI      Knowledge Graph + import grafi + cagri grafi + matris
Katman 3 — ANALIZ      dongu tespiti, olu kod, kalite/guvenlik, API yuzeyi,
                       kullanım dogrulama, etki analizi (transitive + risk)
Katman 4 — RAPOR       coklu cikti (raporlar/veri/kb) + coklu format
Katman 5 — YORUM       LLM (anlam/risk/oneri — deterministik kanit uzerine)
Katman 6 — ARAYUZ      GUI (mimari odakli) + CLI (ayni cekirdek)

Katman 1-4 TAMAMEN deterministik — hicbir yapay zeka bunlari belirlemez.
Katman 5 opsiyonel ve guvenilirligi katman 3'ün kanitlarina bagli.

## 6. SUREKLILIK — MIMARI HAFIZA

Ogma "su an kod ne durumda" demekle yetinmez:
- Her tarama gecmise kaydedilir (fingerprint + diff + istatistik)
- Zaman cizelgesi projenin evrimini gosterir (v1 -> v2 -> v3)
- Bu gecmis LLM'e baglam olarak verilir: "proje nasil bu hale geldi?"
- Sonuc: her oturumda sifirdan anlama yok, birikimli bilgi var.

## 7. OLCEKLENEBILIRLIK HEDEFI

"Analiz dogru mu?" sorusu test edilebilir olmali:
- Mini benchmark (5-10 gercek proje + precision/recall) planli
- Hedef: "AI destekli analiz araci" demekten cikip olculebilir
  teknoloji haline gelmek (precision/recall/false-positive raporlu).

## 8. KISACA

Ogma = deterministik proje bilgisi (AST/Graph/Evidence)
     + yerel LLM yorumu (anlam/risk/oneri)
     + transitive etki analizi (degisiklik guvenligi)
     + mimari hafiza (surekliilik)
     + her PC'de calisir (portable/offline)
Hedef: kullanicinin KENDI makinesinde, KENDI kodunu guvenle
degistirebilmesi icin gerekli tum mimari bilgiyi tek yerde toplamak.
