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

- Ders başına işaretli / zayıf / boş / çoklu / görünmeyen soru sayısı ve balonların basılı halkasına oturma yüzdesi.
- "Tekrar tarayın": bir bölgede (ders × 10 soru) balonların %12'si halkasından kaymışsa, sorular fotoğrafın
  dışında kalıyorsa, bir soruda 3+ şık işaretliyse. Uyarı: halkalar görülemiyorsa, yerel düzeltme kurulamadıysa,
  kalem çok açıksa ya da çok soru dolu/boş sınırındaysa.
- Cevap alanının resmi: yeşil ince halka = balonun olduğunu düşündüğümüz yer, kırmızı kalın halka = işaretli,
  turuncu kalın halka = zayıf işaret (çok açık, yarım, X). **Halkalar balonların üstüne oturmuyorsa hizalama
  hatalıdır.**
- Ders ders cevap listesi (sarı = birden fazla işaret, turuncu = zayıf işaret).
- Güvenilmeyen sonuçta üstte kırmızı "tekrar tarayın" bandı.

## Kayıt

Her gönderim `app/uploads/<zaman>/` altına kaydedilir (git'e girmez): gelen dosya, `working.jpg`
(2000 px'e ölçeklenmiş girdi), `overlay.jpg`, `result.json` (tüm skorlar, uyarılar, hizalama teşhisi).
Hata olursa `error.txt`.

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
