# OGM - GELISTIRICI ARACLARI PLANI (arsivden port)
# =================================================
# Kaynak: H:\EVA ARŞİV\_EVA_OLD_DEVKIT_ARCHIVE\teknik_borc\araclar
# Durum: ONAY BEKLIYOR - uygulama su anki arayuz duzenlemesinden SONRA
# =================================================

## AMAÇ
Eski arşivdeki teknik borç araçlarını Ogma'ya "Geliştirici Araçları" olarak
eklemek. Her araç TEK TEK çalışır (mimari taramadan bağımsız), hedef klasör
kullanıcı tarafından seçilir. FAZ 1 araçları dosyalara DOKUNMAZ (salt analiz).

## FAZ 1 — Salt-okunur analiz araçları (core/tools/ paketi + GUI penceresi)
1. Buyuk Script Tarayici   — 300+/500+/1000+ satır dosyalar + bölme önerisi (kaynak: buyuk_script_analizoru.py)
2. FIX/TODO Etiket Tarayici — TODO/FIX/HACK/TEMP/BUG işaretleri file:satır (kaynak: fix_etiketi_tarayici.py)
3. İkiz Fonksiyon Bulucu   — AST normalize + MD5 ile çapraz dosya kopya tespiti (kaynak: fonksiyon_benzerlik_analizoru.py)
4. Çağrı Grafiği + Proje Geneli Ölü Kod — import zinciri + self.func() çağrıları → ölü kod taramasını proje çapına yükseltir (kaynak: cagri_grafigi_analizoru.py)
+ ortak.py → core/tools/common.py (walk_py_files + 8 kriterli gelişmişlik skoru)
+ GUI: "Geliştirici Araçları" penceresi (araç listesi + hedef klasör + çalıştır + sonuç + rapor kaydet)
+ Testler: her araç için unit test

## FAZ 2 — Temizlik Sihirbazı (DİKKAT: dosya taşır/siler)
- otomatik_karar_ver + otomatik_temizlik + temizlik_gecmisi port
- İnteraktif karar: arşivle / etiketle / birleştir / bırak
- DRY-RUN varsayılan; --apply ile yedek + geri alma; 7 gün ertelenmiş silme
- Kullanıcı onayı olmadan HİÇBİR dosya silinmez

## FAZ 3 — Opsiyonel
- "Hepsini Çalıştır" orkestratör butonu
- arsiv_ayraci (ARCHIVE işaretleri) — Ogma rapor formatında kullanılmıyor, muhtemelen gerek yok

## DIŞARIDA BIRAKILANLAR
- pc_temizleyici.py — kod analizi değil (PC temizleyici, admin)
- ana_teknik_borc_tarayici.py — GUI zaten orkestratör
- .devkit/yardimci_araclar — modern hali H:\devkit'te zaten var (deps/impact/api_surface)

## NOTLAR
- Tüm araçlar stdlib (ast, re, hashlib, difflib) — yeni bağımlılık yok
- walk_py_files Ogma ignore listesi ile (Python_Ortami, __pycache__, libs, models, .git...)
- Rapor çıktısı: storage/reports/ veya kullanıcı seçimi
- ÖN KOŞUL: Önce arayüz yeniden düzenleme (UI_RESTRUCTURE_PLAN) tamamlanmalı
