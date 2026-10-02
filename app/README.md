# Uçtan uca deneme: iPhone → PC → cevaplar

Telefon aynı Wi-Fi'deki bilgisayara formu gönderir; bilgisayar E2 yöntemiyle hizalar
(global homography + ders başına balon konturu düzeltmesi, bkz. `experiments/edge_alignment_v2`),
balonların dolu/boş olduğunu okur ve sonucu telefona geri gösterir.

## Çalıştırma

Proje kökünden:

```sh
.venv/bin/python app/server.py
```

Ekranda `https://192.168.x.x:8000` gibi bir adres çıkar. iPhone'da (aynı Wi-Fi) Safari ile açın.
macOS "gelen bağlantılara izin ver" diye sorarsa izin verin. Durdurmak: Ctrl+C.

iPhone Safari düz `http://` adresini güvenli bağlantıya çevirmeye çalıştığı için sunucu `https` ile çalışır.
Sertifikayı sunucu ilk açılışta kendisi üretir (`app/certs/`, git'e girmez). Kendi ürettiğimiz sertifika olduğu
için Safari bir kez uyarır: **Ayrıntıları Göster → bu web sitesini ziyaret et → Web Sitesini Ziyaret Et**.
Masaüstü tarayıcıda uyarısız denemek için: `.venv/bin/python app/server.py --http`.
Ek kütüphane gerekmez (yalnız `.venv`'deki OpenCV, NumPy, SciPy, PyMuPDF).

## iPhone'dan gönderme

1. **Formu tara / dosya seç** → **Dosya Seç** → sağ üstte **•••** → **Belgeleri Tara** → tara → **Kaydet** → PDF'i seç.
2. Menü yoksa: Notlar'da tara → Paylaş → Dosyalar'a Kaydet → sonra **Dosya Seç**.
3. **Fotoğraf Çek** ham kamera fotoğrafı gönderir. Deneyler iPhone tarayıcı çıktısıyla yapıldı; ham fotoğrafta
   hizalama denenmedi.

PDF'in yalnızca ilk sayfası okunur. JPEG ve PNG de kabul edilir.

## Ekranda ne görülür

- Ders başına işaretli / boş / belirsiz soru sayısı ve otomatik doğrulanabilen balon yüzdesi.
- Uyarılar: bir derste balonların %80'inden azı doğrulanabildiyse veya yerel düzeltme kurulamadıysa.
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

- Doluluk kararı `app/reading.py`: kırmızı kanal, kağıda göre koyuluk, eşik her kağıdın kendi boş balonlarından.
  Ayrıntı ve doğrulama: `SAHA_DENEMELERI.md`. Testler: `.venv/bin/python -m unittest discover -s app/tests`.
  Cevap doğruluğu henüz bir cevap anahtarıyla ölçülmedi.
- Referans ve şablon: `dataset/flat_front/004.png` + `experiments/edge_alignment_v2/reference/template.json`.
  Form düz yönde (üstü yukarıda) taranmalı.
- Test: veri setinden bir PNG (`flat_front/001`), en kötü E0 görüntüsü (`flat_angled/006`, E0'da 5.8 px hata)
  ve orijinal iPhone PDF sayfaları aynı cevap sayılarını verdi. Gerçek bir iPhone'dan canlı gönderim henüz denenmedi.
