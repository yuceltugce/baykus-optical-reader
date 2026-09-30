# Telefon denemelerinde çıkan iki sorun

iPhone ile gönderilen yeni formlarda uygulama iki farklı şekilde hata yaptı. Kayıtlar: `app/uploads/`.

## 1. Bir soruda bütün şıklar işaretli okundu

**Örnek:** `20260928-165952-809327` — 84 soru "birden fazla şık işaretli" çıktı. Hizalama doğruydu, halkalar balonların üstündeydi.

**Neden:** Okuma kuralı sabit bir parlaklık eşiği kullanıyor: gri tonu 170'ten koyu piksel "kalem izi" sayılıyor. Bu
fotoğraf karanlık çekilmiş; kağıdın kendi parlaklığı 170 civarında (iyi taramalarda ~250). Balonların içindeki pembe
baskı da gri tona çevrilince koyu görünüyor. Sonuç: boş balonlar da %30–65 "dolu" ölçülüyor, %50'yi geçenler
işaretli sayılıyor.

**Deneyeceğimiz çözüm:**
- **Kırmızı kanalı kullanmak.** Optik formlar pembe basılır; kırmızı kanalda pembe baskı neredeyse beyazdır,
  kurşun kalem ise koyu kalır.
- **Eşiği kağıda göre belirlemek.** Her bölgede kağıdın kendi parlaklığını tahmin edip ondan belirgin koyu
  pikselleri kalem saymak.
- **Eşiği her kağıdın kendi skor dağılımından hesaplamak (Otsu).** Tek bir sabit ayar her durumda çalışmıyor:
  kağıda göre eşik bu fotoğrafı düzeltti (84 → 2 belirsiz soru), ama açık kalemli bir formu bozdu (19 → 2 okunan
  cevap). OMRChecker'daki yaklaşım da bu.

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

**Hâlâ açık:** Gölgeli fotoğrafın *okuması* sorun 1'deki sebeple bozuk (73 belirsiz soru); uygulama şimdi bunu
"tekrar tarayın" diye gösteriyor.

## Ortak ders

İki durumda da uygulama yanlış sonucu ekranda gösterdi; karanlık formda hiç uyarı vermedi. Artık sonucun üstünde
kırmızı bir **"Bu sonuca güvenmeyin — formu tekrar tarayın"** bandı çıkıyor, eğer:
- bir derste balonların yarısından azı bulunabildiyse (hizalama güvenilmez), ya da
- soruların %10'undan fazlası "birden fazla şık işaretli" okunduysa (okuma eşiği bu fotoğrafa uymuyor).

14 denemede bu band tam olarak üç sorunlu formda çıkıyor: açık kalemli "Zor deneme", karanlık form ve gölgeli form.

## Ek düzeltme: yarım kalan yüklemeler

Bağlantı yükleme sırasında kesilirse sunucu artık yarım dosyayı işlemeye çalışmıyor; telefona "dosya tam gelmedi"
diyor ya da (bağlantı tamamen koptuysa) tek satırlık bir kayıt bırakıyor. Beklenmeyen her hata da telefona mesaj
olarak dönüyor.
