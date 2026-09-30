# E0 — Global homography

**Deney adı:** E0 — Global homography

**Amaç:** Tek bir global perspektif dönüşümü (4+ köşe markerından homography) bütün balonları hizalamaya yeter mi?

**Kullanılan girdi:** `dataset/*/*.png` — referans hariç 40 tarama (40 başarıyla işlendi). Tüm ölçüler yüksekliği 2000 px'e indirilmiş görüntüde, piksel cinsinden. Bir balon çapı ≈ 22 px.

**Başlangıç hizalaması:** korumalı RANSAC. RANSAC'ın kurduğu dönüşüm kararsızsa (koşul sayısı > 5000), bütün markerlarla kurulan dönüşüm kullanılır. Bu çalıştırmada 0 görüntüde bütün markerlara dönüldü.

**Referans:** `dataset/flat_front/004.png` + `reference/template.json` (830 balon merkezi, E1'de onarılmış geçici şablon). Bu tarama fiziksel ground truth değildir. Ölçümler otomatik kontur eşleşmelerine göre yapılır (soru % 5 == 1 satırları eğitim, diğerleri ölçüm).

**Değiştirilen şey:** Hiçbir düzeltme yok; başlangıç noktası. H_all tüm eşleşen markerları, H_ransac 3 px RANSAC inlier'larını kullanır.

**Kullanılmayan şey:** TPS, balon konturları, ders bazlı bölme.

**Çıktı:** `comparison.jpg` (yeşil halka = tespit edilen balon, kırmızı artı = yöntemin tahmini), `metrics.json`, `config.json`, `source/`.

## Sonuç — ders bazında

Görüntü başına held-out medyan hatanın, görüntüler üzerinden medyanı (px). Küçük = iyi.

| Yöntem | turkce | sosyal | matematik | fen |
|---|---:|---:|---:|---:|
| H_all | 1.19 | 1.42 | 1.42 | 1.51 |
| H_ransac | 1.16 | 1.37 | 1.58 | 1.63 |


## Sonuç — dikey bant (üst / orta / alt satırlar)

| Yöntem | üst | orta | alt |
|---|---:|---:|---:|
| H_all | 1.18 | 1.24 | 1.43 |
| H_ransac | 1.26 | 1.45 | 1.93 |


## Nereye bakmalı?

comparison.jpg: kırmızı artılar (tahmin) yeşil halkaların (tespit edilen balon) ortasında mı? Özellikle alt satırlar ve sağ bloklar (Matematik/Fen).


## Başarılı olduğu durum

Ölçüt: Tüm derslerde medyan hata < 0.5 px ve kırmızı artılar halkaların içinde kalıyorsa global model yeterlidir; sonraki deneylere gerek yok.

- **H_all** vs H_ransac: 48 (görüntü, ders) çiftinde >0.1 px daha iyi, 46 çiftte daha kötü (toplam 94 farklı çift).

## Başarısız olduğu durum

Ölçüt: Hata 1 px'in üzerinde ve bloktan bloğa/üstten alta artıyorsa kağıt düzlem değildir; global model yetmez.

- H_all kötüleştirdi: `dataset/curved_angled/008.png` fen: 3.73 → 13.46 px
- H_all kötüleştirdi: `dataset/curved_angled/008.png` matematik: 2.07 → 10.86 px
- H_all kötüleştirdi: `dataset/curved_angled/008.png` sosyal: 1.11 → 7.86 px
- H_all kötüleştirdi: `dataset/curved_angled/008.png` turkce: 1.23 → 6.40 px
- H_all kötüleştirdi: `dataset/curved_angled/009.png` fen: 4.37 → 7.72 px

İnceleme gereken 7 görüntü (kapsama < %80 veya yerel model kurulamadı → H'ye geri düştü). Bunlar başarı sayılmaz:

- `dataset/curved_angled/006.png`: kapsama turkce %94, sosyal %92, matematik %77, fen %26
- `dataset/curved_angled/008.png`: kapsama turkce %88, sosyal %78, matematik %85, fen %78
- `dataset/curved_angled/010.png`: kapsama turkce %100, sosyal %93, matematik %89, fen %56
- `dataset/curved_front/006.png`: kapsama turkce %61, sosyal %8, matematik %11, fen %6
- `dataset/curved_front/010.png`: kapsama turkce %96, sosyal %86, matematik %91, fen %63
- `dataset/flat_angled/009.png`: kapsama turkce %99, sosyal %81, matematik %85, fen %51
- `dataset/flat_front/009.png`: kapsama turkce %91, sosyal %39, matematik %49, fen %20

## Sonraki karar

Global model yetmiyorsa daha esnek bir warp dene (E1 — marker TPS).


---
*Bu rapor `run_experiment.py` tarafından üretildi. Rakamlar insan etiketli ground truth değildir; eşleşmeler başlangıç H'sinin 10 px çevresinden seçildiği için büyük hatalar dışarıda kalabilir.*
