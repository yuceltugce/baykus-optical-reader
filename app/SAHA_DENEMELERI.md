# Telefon denemelerinde çıkan iki sorun

iPhone ile gönderilen yeni formlarda uygulama iki farklı şekilde hata yaptı. Kayıtlar: `app/uploads/`.

## 1. Bir soruda bütün şıklar işaretli okundu

**Örnek:** `20260928-165952-809327` — 84 soru "birden fazla şık işaretli" çıktı. Hizalama doğruydu, halkalar balonların üstündeydi.

**Neden:** Okuma kuralı sabit bir parlaklık eşiği kullanıyor: gri tonu 170'ten koyu piksel "kalem izi" sayılıyor. Bu
fotoğraf karanlık çekilmiş; kağıdın kendi parlaklığı 170 civarında (iyi taramalarda ~250). Balonların içindeki pembe
baskı da gri tona çevrilince koyu görünüyor. Sonuç: boş balonlar da %30–65 "dolu" ölçülüyor, %50'yi geçenler
işaretli sayılıyor.

**Uygulanan çözüm** (`app/reading.py`):
1. **Kırmızı kanal.** Optik formlar pembe basılır; kırmızı kanalda pembe baskı neredeyse beyazdır, kurşun kalem
   ise koyu kalır. Balonun içindeki harfler ve halka okumayı artık etkilemiyor.
2. **Kağıda göre koyuluk.** Büyük bir morfolojik kapama ile her noktadaki kağıt parlaklığı tahmin ediliyor
   (işaretler ve baskı silinir, kağıt ve gölge kalır). Her piksel "buradaki kağıttan ne kadar koyu" diye ölçülüyor.
   Gölge kağıdı ve kalemi aynı oranda kararttığı için oran değişmiyor.
3. **Eşik bu kağıdın boş balonlarından.** Her soruda en fazla bir şık işaretli, yani balonların en az %80'i boş.
   Bütün skorların ortancası "tipik boş balon"u verir; eşik bunun belirgin üstüdür (6 sağlam standart sapma, en az
   0.08).
4. **Zayıf işaret.** Eşiğin hemen üstündeki işaretler (çok açık kalem, yarım doldurma, X) ayrıca "zayıf" diye
   gösteriliyor; resimde turuncu.

**Yolda denenip bırakılanlar:**
- Kağıda göre koyuluk + sabit %60 eşik: karanlık fotoğrafı düzeltti ama açık kalemli formu bozdu (19 → 2 cevap).
- Eşik = boş ve dolu kümelerinin ortası (Otsu + isodata): aynı kağıtta hem koyu hem açık işaret olunca açık
  işaretleri kaçırdı (Fen 18/38'deki açık C'ler boş okundu). Eşiği boş balonlardan belirlemek bunu çözdü.
- Kağıt tahmininde büyük bulanıklaştırma (sigma 15): keskin kenarlı bir gölgede, kenara yakın boş balonları
  koyu gösterdi (sentetik testte yakalandı). Sigma 2'ye indirildi.

**Sonuç:**
| Fotoğraf | Eski okuma (tek / boş / çoklu) | Yeni okuma (tek / boş / çoklu) |
|---|---|---|
| Karanlık (`a60f`) | 68 / 14 / **84** | 70 / 94 / 2 |
| Gölgeli (`2d6e`) | 58 / 35 / **73** | 70 / 94 / 2 |
| Temiz (`6532`), muhtemelen aynı kağıt | 73 / 91 / 2 | 70 / 94 / 2 |
| Açık kalem ("Zor deneme") | **19** / 147 / 0 | 80 / 85 / 1 (9 zayıf) |

- Karanlık, gölgeli ve temiz çekim artık birebir aynı sonucu veriyor.
- Veri setinin 41 görüntüsünde 6806 sorunun 70'inde eski ve yeni okuma farklı. Büyütülüp tek tek bakıldı: hepsi
  eski yöntemin kaçırdığı açık tarama, yarım doldurma veya X işaretleri; biri iki yöntemin de "çoklu" dediği,
  taramadaki siyah kenar şeridinin üstüne düşen soru.
- 5 sentetik birim testi: karanlık fotoğrafta pembe baskı, keskin gölge, açık kalem, boş kağıt, çift işaret.
- Cevap anahtarı olmadığı için doğruluk yüzdesi ölçülmedi.

**Bilinen sınır:** "Zor deneme"de basılı halkalar çok soluk olduğu için hizalama kontrolü (kapsama %4–19) yine
"tekrar tarayın" diyor; okuma değil hizalama doğrulaması yetersiz. Resimde halkalar balonların üstünde duruyor.

## 2. Gölge düşen formda balonlar kaydı

**Örnek:** `20260928-170100-603280` — Matematik ve Fen'de halkalar balonlardan kaydı; Fen'de balonların
yalnızca %4'ü doğrulanabildi. Kağıt düzdü, üstüne bir cismin gölgesi düşmüştü.

**Neden:**
1. Markerlar doğru ölçüldü (yakın planda merkezler karelerin ortasında).
2. Ama fotoğraftaki sayfa milimetre altı ölçekte hafif çarpık. SIFT ile ~1000 noktada ölçüldü: sorunsuz fotoğrafta
   sayfa her yerde ~1 px kayıyor, bunda 3–6 px; en çok sağ üst ve sol alt köşede, en az cevap alanında. A4 kağıtta
   bu 1 mm'den az; gözle görülmez. Kaynağı (kağıdın hafif kalkması mı, iPhone tarayıcısı mı) pikselden ayırt
   edilemedi.
3. Markerlar köşelerde olduğu için birbirine uymadı (tek bir dönüşüme ~4 px; diğer 13 denemede ~1 px).
4. RANSAC "çoğu nokta tam doğru, birkaçı tamamen yanlış" durumu için tasarlandı. Burada ise bütün markerlar biraz
   hatalıydı. 3 px kuralı doğru markerları attı ve tesadüfen uyuşan, sayfanın tek bölgesinde duran 5 marker seçildi.
   Bu noktalardan kurulan dönüşüm kararsızdı (koşul sayısı 22.440; normalde 50–1.500): o 5 markera uydu, uzakta
   50–120 px hata yaptı. En uzak bölge Fen olduğu için en çok orada kaydı. Yerel düzeltme de kurtaramadı, çünkü
   balonları tahminin yalnızca 10 px çevresinde arıyor.

**Doğrulama:** Aynı resim 9 markerın hepsiyle hizalanınca doğrulanan balon oranı Fen'de %4'ten %95'e,
Matematik'te %38'den %100'e çıktı. Halkalar gölgenin altında bile balonların üstüne oturdu.

**Uygulanan çözüm: korumalı RANSAC** (`experiments/edge_alignment_v2/src/homography.py`). RANSAC'ın kurduğu dönüşüm
kararsızsa (koşul sayısı > 5000) ona güvenilmez, bütün markerlarla en küçük kareler dönüşümü kullanılır.

Denenen seçenekler:

| Seçenek | Sonuç |
|---|---|
| Sadece RANSAC eşiğini 8–12 px'e çıkarmak | Yetmedi; bir markerda 30 px hata kaldı |
| OpenCV `USAC_MAGSAC` | Gölgeli fotoğrafta daha kötü (Fen'de %0 balon bulundu) |
| RANSAC'ı tamamen bırakmak | Gölgeliyi düzeltir ama gerçekten yanlış bir marker gelirse korumasız kalınır |
| "RANSAC markerların dörtte birini attıysa güvenme" | **Zararlı:** kıvrık `curved_angled/008`'de RANSAC'ın iyi seçimini (6/10 marker, koşul 111) reddetti; Fen hatası 3.7 → 8.0 px oldu. Kaldırıldı. |
| **Sadece kararsızlığa bakmak (seçilen)** | Gölgelide devreye giriyor, başka hiçbir yerde girmiyor |

**Sonuç:**
- Gölgeli fotoğraf: Fen'de bulunan balon %4 → %95, Matematik %38 → %100. Halkalar gölgenin altında bile oturuyor.
- 40 görüntülük veri seti: koruma hiçbir görüntüde devreye girmedi; E0–E3'teki bütün sayılar görüntü görüntü
  önceki sonuçlarla birebir aynı.
- Diğer 13 telefon denemesi: sonuçlar birebir aynı.
- Testler: gerçek gölgeli fotoğrafın marker koordinatlarıyla, kıvrık kağıtta iyi RANSAC seçiminin korunmasıyla ve
  gerçekten yanlış bir markerın atılmasıyla ayrı birim testleri var.

Gölgeli fotoğrafın okuması da sorun 1'in çözümüyle düzeldi (73 → 2 çoklu soru).

## Ortak ders

İki durumda da uygulama yanlış sonucu ekranda gösterdi; karanlık formda hiç uyarı vermedi. Artık sonucun üstünde
kırmızı bir **"Bu sonuca güvenmeyin — formu tekrar tarayın"** bandı çıkıyor, eğer:
- bir derste balonların yarısından azı bulunabildiyse (hizalama güvenilmez), ya da
- soruların %10'undan fazlası "birden fazla şık işaretli" okunduysa (okuma eşiği bu fotoğrafa uymuyor).

14 denemede bu band tam olarak üç sorunlu formda çıkıyor: açık kalemli "Zor deneme", karanlık form ve gölgeli form.

## 3. Halkası bulunan balonlar eşleşmiyordu (Hungarian zincirleme kayması)

**Örnek:** `6532c35e…` — 830 balonun 15'i eşleşmedi; bunların 9'unda kendi halkası 0.5–2.4 px yakında bulunmuştu.

**Neden:** Tahmin edilen balon merkezleri ile bulunan halkalar Hungarian algoritmasıyla bire-bir eşleştiriliyor.
Algoritma her balona bir halka vermek ve toplam mesafeyi en küçük yapmak zorunda. Kalemle doldurulduğu için halkası
bulunamayan bir balon (ör. 260) komşusunun halkasını (27.7 px) alıyor, komşusu da bir sonrakinin halkasını alıyor;
zincir sütun boyunca ilerleyip uzaktaki boş bir aday halkada bitiyor. Toplam mesafe daha küçük çıktığı için algoritma
bunu seçiyor. Sonraki "en yakın halka mı?" kontrolü bu yanlış atamaları reddettiği için hiçbir balon yanlış halkayla
eşleşmiyordu, ama zincirdeki bütün balonlar doğru halkasını kaybediyordu.

**Çözüm** (`experiments/edge_alignment_v2/src/common.py`, `associate`): Hungarian'a vermeden önce 10 px'ten uzak bütün
mesafeler aynı sabit değere (11) indiriliyor. Kapı dışındaki her atama aynı maliyette olunca zincir hiçbir zaman
daha ucuz olamaz. Hatayı yeniden üreten bir birim testi var (düzeltmeden önce başarısız, sonra başarılı).

**Sonuç:**
- Telefon denemeleri: eşleşen balon toplamı 9015 → 9054; en büyük kazanç "Optikler" (+29) ve `6532` (+9).
  Hiçbir fotoğrafta tek bir eşleşme kaybedilmedi; okunan cevaplar değişmedi.
- Veri seti (40 tarama): yalnız `curved_angled/001` Fen'de 3 balon daha ölçülüyor. E0–E3 tablolarında tek değişen
  sayı H_TPS_inliers Fen 1.85 → 1.83; E2 sonuçları ve inceleme listesi aynı.

## 4. Açılı çekimde en üst soru sırası atlanıyordu (sabit arama alanı)

**Örnek:** `flat_angled/006` (telefondan gönderilen `006.png` ile aynı) — 1. soru sırasının 20 balonundan 4'ü eşleşiyordu.

**Neden:** Halka bulucu yalnız sayfanın sağ altına bakıyordu: genişliğin %48'inden sağı, yüksekliğin %29'undan aşağısı.
Bu sabit yüzdeler iPhone tarayıcısının kırpmasına bağlı. 62 görüntüde ölçüldü: tipik payı ~30 px, ama bu açılı
çekimde tarayıcı farklı kırptığı için en üst sıra çizginin 10 px üstüne taştı ve Sosyal/Matematik/Fen'in 1. sorusunun
halkaları atlandı. 1. soru yerel düzeltmenin kontrol noktası satırı olduğu için düzeltme o derslerin üst kenarında
kontrol noktası bulamıyordu.

**Çözüm** (`common.answer_region`): referanstaki balonların kapladığı dikdörtgen 30 px pay ile homography üzerinden
fotoğrafa taşınıyor; halkalar yalnız bu dörtgenin içinde aranıyor. Arama alanı artık her fotoğrafın kendi kırpma ve
açısını izliyor. İki birim testi eklendi.

**Sonuç:**
- `flat_angled/006`: 1. sırada eşleşen balon 4 → 15, toplam 785 → 796; E2 Matematik hatası 0.39 → 0.36 px.
  (E3'ün piecewise_H yönteminde Sosyal 0.52 → 0.44 iyileşti, Fen 0.73 → 0.76 biraz kötüleşti; bu yöntem
  uygulamada kullanılmıyor.)
- Diğer 39 tarama ve diğer telefon denemeleri birebir aynı; hiçbir yerde eşleşme kaybı yok, okunan cevaplar aynı.
- E0 ve E1 değişmedi: 1. sıra bir kontrol noktası satırı, ölçüm o satırlarda yapılmıyor.

**Hâlâ açık:** aynı görüntüde 1. sıranın kalan 5 balonundan biri kalemle doldurulmuş (Türkçe 1-A), dördü (Fen 1-A, C,
D, E) ise çok soluk basılmış boş halkalar. En açık eşik (205) bile bunları yakalayamıyor; bu bir halka tespit
hassasiyeti sorunu.

## Not: Python'un eski önbellek kopyası

Okuma ayarı (kağıt tahminindeki bulanıklaştırma, 2 px) test sırasında aynı saniye içinde 2 → 15 → 2 yapılıp geri
alındığında Python'un derlenmiş önbellek kopyası (`__pycache__`) güncellenmedi ve program bir süre 15 ile çalıştı.
Commit'teki kod doğruydu. Önbellek temizlenip 53 gerçek görüntüde (8798 soru) 2 ile 15 karşılaştırıldı: tek bir
sorunun okuması bile değişmiyor, yani raporlanan sonuçlar geçerli. Sunucu artık önbelleksiz (`python -B`) başlatılıyor.

## Ek düzeltme: yarım kalan yüklemeler

Bağlantı yükleme sırasında kesilirse sunucu artık yarım dosyayı işlemeye çalışmıyor; telefona "dosya tam gelmedi"
diyor ya da (bağlantı tamamen koptuysa) tek satırlık bir kayıt bırakıyor. Beklenmeyen her hata da telefona mesaj
olarak dönüyor.
