# OGM — ARAYUZ YENIDEN DUZENLEME PLANI (UI_RESTRUCTURE)
# =====================================================
# Tarih: 2025-09-14
# Durum: ONAY BEKLIYOR
# On kosul: Tam denetim tamamlandi (asagida)
# =================================================

## 1. TAM DENETIM SONUCU

### Kritik buglar
1. [ONARILDI] architecture_analyzer_gui.py: AnalysisType/ANALYSIS_LABELS
   tanimsizdi -> analiz turu penceresi cokuyor, mimari akis kirikti.
   Import geri eklendi, dogrulandi.
2. [ACIK] Hibrit motor <-> GUI entegrasyonu yarim:
   - GUI hibrit motoru async cagiriyor; donen format yeni
     (architecture_map/ast_results/llm_results/combined) ama
     _show_results eski format (AnalysisResult dict) bekliyor ->
     GUI'den analiz calisirsa sonuc penceresi patlar.
   - hybrid_analyzer.icindeki backward-compat AnalysisEngine wrapper'i
     bozuk (scan_root="" geciriyor).

### UI tekrarlari (ayni is, ayri butonlar)
- Klasor sec (select_workspace): 4 yerden
  (Mimari sekmesi, Dosyalar sekmesi, Mimari ana ekran, Araclar)
- Model sec (show_model_selection): 4 yerden
- Mimari analizi baslat (launch_architecture_analyzer): 4 yerden
- GGUF gozat / model degistir: 2'ser yerden

### Akis hatalari (kullanicinin bildirdikleri + dogrulanan)
- CIFT klasor secimi: once workspace seciliyor, sonra mimari analiz
  yine askdirectory aciyor (baslangici home/son-tarama) -> ayni klasor
  2 kez seciliyor, karisik.
- CIKTI klasoru tarama oncesi secilemiyor; sadece analiz sonrasi
  "farkli kaydet" var. (kullanici talebi: tarama oncesi cikti klasoru)
- Ignore listesi: secilen klasorde sadece dosya varsa liste bos
  gorunuyor (mantik dogru ama bilgi mesaji yok).

### Motor yanlis-pozitifleri (Ogma kendi uzerinde test edildi)
- Statik analiz lambda parametrelerini "bound" saymiyor ->
  "satir 181: 'm' tanimli degil" gibi yanlis uyarilar.
- find_unused_imports onizleme kesmesi (12K karakter) ->
  uzun dosyalarda kullanilan importlar "olu" saniliyor.
- Bu ikisi Ogma'nin kendi raporlarinin guvenilirligini dusuruyor.

## 2. YENI ARAYUZ PLANI — "TEK RESMI YER" ILKESI

Kural: Her islevin TEK calisir butonu var. Diger yerler o islevi
GOSTERIR (durum) ama buton olmaz; gerekirse ilgili sekmeye goturen
tek link olur.

### A. UST BAR (kisayol degil, durum cubugu)
- Sol: logo + program adi
- Orta: yuklu model + backend + yukleme suresi + server adresi (SALT GOSTERIM)
- Sag: SEKME GECIS butonlari (Mimari | Dosyalar | Sohbet | Araclar)
  -> dugme degil, sekme secici (notebook.select)
- KALDIRILAN: Model Sec / Ayarlar / Mimari Analiz / Model Sohbet /
  Dosya Analizi butonlari (hepsi tekrardi; islevleri sekmelerde)

### B. SOL PANEL (islemler — ilgili panel grubu)
1. MIMARI sekmesi — mimari islemlerin TEK yeri:
   - [1] Model durumu (salt gosterim; yuklu degilse "Araclar > MODEL"
      uyarisi)
   - [2] Klasor Sec (TEK buton; secince dosya agaci da ayni klasoru
      kullanir — tek kaynak: config.workspace_path)
   - [3] CIKTI Klasoru Sec (YENI; varsayilan storage/reports/,
      secim config'e yazilir)
   - [4] Ignore listesi (mevcut pencere + "sadece dosya var" bilgi mesaji)
   - [5] Mimari Analizi Baslat (TEK buton)
2. DOSYALAR sekmesi — dosya agaci + editor islemleri
   (Klasor Sec butonu KALDIRILIR; Mimari sekmesindeki klasoru kullanir,
   yaninda sadece "Yenile" kalir)
3. SOHBET sekmesi (degisiklik yok)
4. ARACLAR sekmesi — tum islevlerin menusu (tek menu):
   - MODEL: Model Sec / Modeli Bosalt / Model Indir  (Model Sec'in TEK
     resmi yeri burasi)
   - ANALIZ: Mimari Analiz Baslat (Mimari sekmesine goturur, yeni
     dialog acmaz) / Toplu Analiz / Model Karsilastir
   - SISTEM: Ayarlar / Donanim Taramasi / GPU-CPU Degistir /
     Oturum Yonetimi / Yardim

### C. SAG PANEL (sonuclar)
1. MIMARI SONUC sekmesi: tarama ozeti + rapor gorunumu
   ("Proje Mimari Analizi" karsilama ekrani kaldirilir — islevi
   Mimari sekmesine tasindi)
2. DOSYA ANALIZI (editor) — degisiklik yok
3. SONUCLAR + GECMIS — degisiklik yok

### D. AKIS DUZELTMELERI
- CIFT SECIM BITTI: workspace tek kez secilir (Mimari sekmesinden);
  "Analizi Baslat" yeniden klasor sormaz, workspace'i kullanir.
  (Istenirse Mimari sekmesinde secili klasorun yanina "Degistir" kalir.)
- CIKTI KLASORU: tarama oncesi secilir; analiz bitince rapor otomatik
  o klasore yazilir + "ac" linki. Save-as dialog'u opsiyonel kalir.
- IGNORE: sadece dosya iceren klasorlerde "Bu klasorde alt klasor yok"
  bilgi satiri.

### E. MOTOR DUZELTMELERI (rapor guvenilirligi)
- Statik analize lambda parametreleri bound ekle (yanlis "tanimli degil")
- find_unused_imports: 200K alti dosyalarda tam okuma (onizleme kesmesi
  yanlis pozitifleri bitirir)
- Hibrit-GUI entegrasyonu: ya duzgun bagla ya da GUI akisini calisan
  AnalysisEngine'de tutup hibrit motoru FAZ1 araclarla beraber entegre et

## 3. UYGULAMA SIRASI (onay sonrasi)
1. Motor duzeltmeleri (E) — yanlis pozitifleri bitir (0.5 gun)
2. Hibrit-GUI entegrasyon tamiri (kritik bug #2) (0.5 gun)
3. Ust bar sadelestirme + sekmeye goturen gecisler (0.5 gun)
4. Mimari sekmesi yeniden tasarim: tek klasor secimi + cikti klasoru +
   ignore bilgi mesaji + tek baslat butonu (1 gun)
5. Araclar menusu temizligi (tekrar eden butonlar kaldirilir) (0.5 gun)
6. Dosyalar sekmesinden Klasor Sec kaldirimi + test + dogrulama (0.5 gun)
