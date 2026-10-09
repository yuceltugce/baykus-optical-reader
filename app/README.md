# Uçtan uca deneme: iPhone → PC → cevaplar

Telefon aynı Wi-Fi'deki bilgisayara formu gönderir; bilgisayar E2 yöntemiyle hizalar
(global homography + ders başına balon konturu düzeltmesi, bkz. `experiments/edge_alignment_v2`),
balonların dolu/boş olduğunu okur ve sonucu telefona geri gösterir.

## Çalıştırma

Proje kökünden:

```sh
.venv/bin/python -B app/server.py
```

Ekranda `https://192.168.x.x:8000` gibi bir adres çıkar. iPhone'da (aynı Wi-Fi) Safari ile açın.
macOS "gelen bağlantılara izin ver" diye sorarsa izin verin. Durdurmak: Ctrl+C.

iPhone Safari düz `http://` adresini güvenli bağlantıya çevirmeye çalıştığı için sunucu `https` ile çalışır.
Sertifikayı sunucu ilk açılışta kendisi üretir (`app/certs/`, git'e girmez). Kendi ürettiğimiz sertifika olduğu
için Safari bir kez uyarır: **Ayrıntıları Göster → bu web sitesini ziyaret et → Web Sitesini Ziyaret Et**.
Masaüstü tarayıcıda uyarısız denemek için: `.venv/bin/python -B app/server.py --http`.
Ek kütüphane gerekmez (yalnız `.venv`'deki OpenCV, NumPy, SciPy, PyMuPDF).

## iPhone'dan gönderme

1. **Formu tara / dosya seç** → **Dosya Seç** → sağ üstte **•••** → **Belgeleri Tara** → tara → **Kaydet** → PDF'i seç.
2. Menü yoksa: Notlar'da tara → Paylaş → Dosyalar'a Kaydet → sonra **Dosya Seç**.
3. **Fotoğraf Çek** kullanmayın: ham kamera fotoğrafı kırpılmamış olduğu için hizalanamaz.

PDF'in yalnızca ilk sayfası okunur. JPEG ve PNG de kabul edilir.

## Ekranda ne görülür

- **Tekrar tara** (hiç sonuç gösterilmez) — yeni bir taramanın düzelteceği sorunlarda: köşe işaretleri bulunamadı
  (kesik ya da ters çekim), bir bölgede (ders × 10 soru) balonların %12'si halkasından kaymış, sorular fotoğrafın
  dışında, bir soruda 3+ şık işaretli ya da soruların %10'undan fazlası çoklu (gölge/parlama). Mesajlar
  `pipeline.RETAKE_TEXT`.
- **Form okundu** — ders başına cevaplı/boş sayısı ve yeni taramanın düzeltmeyeceği sorunlar ("Dikkat"): kalem
  çok açık, basılı halkalar soluk olduğu için yerleşim doğrulanamayan bölgeler.
- **Emin olamadığımız sorular** — zayıf (çok açık, yarım, silinmiş) ya da birden fazla işaretli her soru için
  fotoğraftan o sorunun satırı (üzerine çizim yapılmadan) ve A–E / Boş düğmeleri. Tahminimiz mavi çerçeveyle
  gösterilir ama seçilmez; hepsi seçilince **Cevapları kaydet** açılır → `app/uploads/<zaman>/confirmed.json`.
- **Cevapların** — ders sekmeleri, "1) A" listesi; onay bekleyenler sarı "?", öğrencinin seçtikleri yeşil.
- **İşaretli fotoğraf** — kırmızı = işaretli, turuncu = belirsiz, yeşil ince = boş. Dokununca büyür.
  **Halkalar balonların üstüne oturmuyorsa hizalama hatalıdır.**
- **Teknik ayrıntılar** (kapalı) — köşe işareti sayısı, eşik, ders başına sayılar, teknik uyarılar.

## Kayıt

Her gönderim `app/uploads/<zaman>/` altına kaydedilir (git'e girmez): gelen dosya, `working.jpg`
(2000 px'e ölçeklenmiş girdi), `overlay.jpg`, `result.json` (tüm skorlar, uyarılar, hizalama teşhisi),
öğrenci onayladıysa `confirmed.json` (seçimleri ve son cevaplar). Hata olursa `error.txt`.

Bilgisayardaki tarayıcıda denemek için: `.venv/bin/python -B app/server.py --http` → `http://127.0.0.1:8000`.

## Sınırlar

- Doluluk kararı `app/reading.py`: kırmızı kanal, kağıda göre koyuluk, her şık aynı sorunun diğer şıklarıyla
  karşılaştırılır. Ölçüm (4 kağıdın 159 fotoğrafı, çoğunluk cevabına göre): iPhone %0.25, Redmi 18 fotoğrafta 6
  yanlış soru. Ayrıntı: `SAHA_DENEMELERI.md`. Testler: `.venv/bin/python -B -m unittest discover -s app/tests`.
- Referans ve şablon: `dataset/flat_front/004.png` + `experiments/edge_alignment_v2/reference/template.json`.
  Form düz yönde (üstü yukarıda) taranmalı; ters çekim okunmaz.
- Telefon tarayıcısının kırpılmış çıktısı beklenir (iPhone "Belgeleri Tara", Redmi tarayıcı). Ham kamera
  fotoğrafında köşe işareti eşleştirmesi çalışmaz.

## Diğer araçlar

- `batch_process.py` — bir klasördeki bütün PDF/resimleri okur; `ozet.csv`, `cevaplar.csv`, `rapor.html` yazar.
- `model_dene.py`, `model_kirp.py`, `model_sayfa.py` — OpenRouter üzerinden görüntü modelleriyle (Gemini, GPT)
  karşılaştırma denemeleri. Anahtar yalnız `OPENROUTER_API_KEY` ortam değişkeninden okunur.
