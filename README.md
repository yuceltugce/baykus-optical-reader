# Baykuş Optik — TYT/AYT Optik Form Okuma

Testofis "OPTİK-129" cevap kağıdını (öğrencilerin telefonla çektiği fotoğraflardan)
otomatik okuyacak sistem.

## Faz 1 — Fotoğraftan kanonik forma ✅

Ham, herhangi bir açıdan/arka planda (masa, kanepe vb.) çekilmiş bir telefon
fotoğrafını alıp, sabit boyutlu (1700x2400), doğru yönde, perspektifi
düzeltilmiş bir "kanonik" form görüntüsüne çeviriyoruz. Bu, balon-okuma
aşamasının SABİT piksel koordinatları kullanabilmesi için şart.

Pipeline 3 adımdan oluşuyor ([src/baykus_optik/pipeline.py](src/baykus_optik/pipeline.py)):

1. **Kağıt/form tespiti** ([paper.py](src/baykus_optik/paper.py)) — iki yöntemi
   dener: (a) formun üzerine basılı kalın SİYAH çerçeve, (b) kağıt/arka plan
   parlaklık farkı. Bulunan dörtgenin en/boy oranı forma benziyor mu diye
   kontrol edilip (plausibility check) en iyisi seçiliyor.
2. **Perspektif düzeltme** (`warp_paper`) — bulunan dörtgen, KENDİ ölçülen
   en/boy oranına göre (esnetme olmadan) sabit bir tuvale warp ediliyor.
3. **Yön düzeltme** ([orientation.py](src/baykus_optik/orientation.py)) — kağıt
   fotoğrafta 0/90/180/270 derece döndürülmüş olabilir (telefon yatay tutulmuş
   olabilir). Sayfanın KENAR HARİTASI (Canny) referansla karşılaştırılarak
   doğru yön bulunuyor (balonların dolu/boş olması bu haritayı etkilemiyor,
   sadece sayfanın sabit yapısal çizgileri önemli).

**Test sonucu:** 4 farklı gerçek fotoğrafta (tahta masa, kanepe kumaşı arka
plan, farklı açılar, biri 90° döndürülmüş) hepsi doğru şekilde düzleştirildi
ve doğru yöne çevrildi → `outputs/final/`.

## Faz 2 — Ana cevap tablosunu okuma ✅ (kısmen — bkz. Bilinen Kısıtlar)

TÜRKÇE / SOSYAL BİLİMLER / TEMEL MATEMATİK / FEN BİLİMLERİ sütunlarındaki
40 (+ AYT'de 46'ya kadar) sorunun 5 balonunun (A-E) piksel koordinatları
kalibre edildi ve her balonun dolu/boş olduğuna karar veren bir okuyucu
yazıldı:

- **[template.py](src/baykus_optik/template.py)** — her balonun (ders, soru
  no, şık) piksel konumunu hesaplayan formül. Satır aralığı (dy), satır
  İÇİNDEKİ en koyu noktaya değil, satırlar ARASINDAKİ (öğrenci ne
  işaretlerse işaretlesin hep beyaz kalan) BOŞLUKLARA bakılarak kalibre
  edildi -- bkz. `scripts/calibrate_rows.py` ve dosyanın başındaki kalibrasyon
  hikayesi yorumu (3 farklı yöntem denendi, ilk ikisi yeterince hassas
  çıkmadı).
- **[reader.py](src/baykus_optik/reader.py)** — her balonun içindeki
  "mürekkep yüzdesini" (dairesel bölgedeki koyu piksel oranı) hesaplayıp,
  4 örnek fotoğraftaki ~3440 balonun histogramından kalibre edilmiş bir
  eşikle karşılaştırıyor. Şablon koordinatı ile gerçek balon merkezi
  arasındaki birkaç piksellik sapmaya dayanıklı olmak için, tek noktada
  örneklemek yerine tahmin edilen merkezin etrafında küçük bir alanı tarayıp
  en iyi eşleşmeyi buluyor.

## Bilinen Kısıtlar / Sırada Ne Var

**Balon okumanın doğruluğu, fotoğraftaki perspektif düzeltmenin hassasiyetine
bağlı.** `warp_paper` tek bir 4-köşe homografi kullanıyor; bu, kağıdın
KÖŞELERİNİ doğru hizalıyor ama kağıt fiziksel olarak tam düz değilse (hafif
kıvrık/dalgalı, ya da köşe tespiti birkaç piksel kaymışsa) sayfanın ORTASINDA
birkaç piksellik sapma kalabiliyor. Şablonun kalibre edildiği referans
fotoğrafta (`data/samples/IMG_6046.jpg`) sonuçlar çok iyi; daha "zorlu" açıdan
çekilmiş fotoğraflarda (ör. `IMG_6045.jpg`) doğruluk düşüyor.

**Faz 3 (yapılacak):** Bu kalan sapmayı düzeltmek için formun üzerindeki
küçük siyah kare referans noktalarını (bkz. [markers.py](src/baykus_optik/markers.py)
-- ilk denemede ham fotoğrafta aranıp arka plan yüzünden başarısız olmuştu,
ama artık TEMİZ/arka plansız kanonik görüntüde çok daha güvenilir çalışması
beklenir) her fotoğrafta yeniden bulup, o fotoğrafa özel küçük bir "ince
hizalama" düzeltmesi uygulamak gerekiyor.

**Ayrıca henüz yapılmadı:** öğrenci no, okul kodu, kitapçık türü (A/B), T.C.
kimlik no, ad-soyad harf ızgarası gibi diğer balon alanlarının okunması --
şu an sadece ana 4 dersin cevap tablosu okunuyor.

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Kullanım

```bash
python3 scripts/process_all_samples.py   # data/samples/*.jpg -> outputs/final/*.jpg (Faz 1)
python3 scripts/visualize_answers.py     # + cevapları okuyup görselleştirir (Faz 2)
```

Tek bir fotoğraf için:

```python
from baykus_optik.pipeline import process_photo_file
from baykus_optik.reader import read_all

oriented = process_photo_file("yol/foto.jpg")  # 1700x2400 BGR numpy array
results = read_all(oriented)  # her soru için QuestionResult listesi
for r in results:
    print(r.column_key, r.question_no, r.status, r.answer)
```

## Klasör yapısı

```
data/samples/          örnek telefon fotoğrafları (girdi)
outputs/                debug çıktıları + outputs/final/ (kanonik görüntüler) + outputs/answers/ (okunan cevaplar görselleştirilmiş)
src/baykus_optik/
  paper.py              kağıt/form tespiti + perspektif düzeltme
  orientation.py         0/90/180/270 yön düzeltme (kenar-haritası karşılaştırma)
  pipeline.py            paper+orientation'ı birleştiren process_photo()
  template.py            ana cevap tablosundaki her balonun piksel koordinatı
  reader.py              balon doluluk tespiti + soru bazlı karar mantığı
  markers.py              (henüz pipeline'da kullanılmıyor -- Faz 3 için, bkz. yukarıdaki not)
  orientation_reference_edges.png   yön tespiti için referans kenar haritası
scripts/
  setup_orientation_reference.py   referans kenar haritasını (yeniden) oluşturur
  calibrate_rows.py                 template.py'deki ROW1_Y/ROW_DY'yi nasıl bulduğumuz
  calibrate_fill_threshold.py       reader.py'deki FILL_THRESHOLD'u nasıl bulduğumuz
  process_all_samples.py            tüm örnekleri Faz 1 pipeline'ından geçirir
  visualize_answers.py              Faz 1 + Faz 2'yi çalıştırıp cevapları görselleştirir
  verify_template.py                template.py koordinatlarını görsel doğrulama
  detect_paper_debug.py             sadece Faz 1'i debug etmek için
  detect_markers_debug.py           eski/referans: ham fotoğrafta doğrudan marker tespiti denemesi
```
