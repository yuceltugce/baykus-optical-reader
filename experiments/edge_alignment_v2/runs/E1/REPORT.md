# E1 — Marker TPS

**Deney adı:** E1 — Marker TPS

**Amaç:** Aynı markerlarla esnek bir Thin-Plate Spline warp, global homography'nin kenar hatalarını azaltır mı?

**Kullanılan girdi:** `dataset/*/*.png` — referans hariç 40 tarama (40 başarıyla işlendi). Tüm ölçüler yüksekliği 2000 px'e indirilmiş görüntüde, piksel cinsinden. Bir balon çapı ≈ 22 px.

**Başlangıç hizalaması:** korumalı RANSAC. RANSAC'ın kurduğu dönüşüm kararsızsa (koşul sayısı > 5000), bütün markerlarla kurulan dönüşüm kullanılır. Bu çalıştırmada 0 görüntüde bütün markerlara dönüldü.

**Referans:** `dataset/flat_front/004.png` + `reference/template.json` (830 balon merkezi, E1'de onarılmış geçici şablon). Bu tarama fiziksel ground truth değildir. Ölçümler otomatik kontur eşleşmelerine göre yapılır (soru % 5 == 1 satırları eğitim, diğerleri ölçüm).

**Değiştirilen şey:** Homography yerine (veya üstüne) markerlardan TPS. Kontrol noktaları hâlâ yalnız kenardaki markerlar.

**Kullanılmayan şey:** Balon konturları, ders bazlı bölme.

**Çıktı:** `comparison.jpg` (yeşil halka = tespit edilen balon, kırmızı artı = yöntemin tahmini), `metrics.json`, `config.json`, `source/`.

## Sonuç — ders bazında

Görüntü başına held-out medyan hatanın, görüntüler üzerinden medyanı (px). Küçük = iyi.

| Yöntem | turkce | sosyal | matematik | fen |
|---|---:|---:|---:|---:|
| H_ransac | 1.16 | 1.37 | 1.58 | 1.63 |
| TPS_markers | 1.10 | 1.52 | 2.19 | 3.46 |
| H_TPS_all | 1.09 | 1.52 | 1.67 | 1.75 |
| H_TPS_inliers | 1.08 | 1.46 | 1.92 | 1.83 |


## Sonuç — dikey bant (üst / orta / alt satırlar)

| Yöntem | üst | orta | alt |
|---|---:|---:|---:|
| H_ransac | 1.26 | 1.45 | 1.93 |
| TPS_markers | 1.47 | 2.05 | 1.85 |
| H_TPS_all | 1.08 | 1.90 | 1.64 |
| H_TPS_inliers | 1.01 | 1.92 | 2.00 |


## Nereye bakmalı?

metrics.json -> aggregate.by_subject; comparison.jpg'de TPS_markers sütununda Matematik/Fen alt satırları.


## Başarılı olduğu durum

Ölçüt: TPS varyantları her derste H_ransac'tan düşük hata verir ve hiçbir derste bozulmazsa esnek marker warp yeterlidir.

- **TPS_markers** vs H_ransac: 58 (görüntü, ders) çiftinde >0.1 px daha iyi, 88 çiftte daha kötü (toplam 146 farklı çift).
- **H_TPS_all** vs H_ransac: 59 (görüntü, ders) çiftinde >0.1 px daha iyi, 83 çiftte daha kötü (toplam 142 farklı çift).
- **H_TPS_inliers** vs H_ransac: 58 (görüntü, ders) çiftinde >0.1 px daha iyi, 72 çiftte daha kötü (toplam 130 farklı çift).

## Başarısız olduğu durum

Ölçüt: Bir derste iyileşip başka derste (özellikle markerlardan uzak Matematik/Fen) belirgin kötüleşirse, marker desteği iç bölgeler için yetersizdir.

- TPS_markers kötüleştirdi: `dataset/curved_angled/007.png` fen: 1.37 → 8.16 px
- TPS_markers kötüleştirdi: `dataset/curved_front/004.png` fen: 0.88 → 6.55 px
- TPS_markers kötüleştirdi: `dataset/flat_front/001.png` fen: 2.17 → 7.30 px
- TPS_markers kötüleştirdi: `dataset/flat_front/002.png` fen: 1.84 → 6.13 px
- TPS_markers kötüleştirdi: `dataset/curved_angled/009.png` fen: 4.37 → 8.49 px
- H_TPS_all kötüleştirdi: `dataset/curved_angled/008.png` fen: 3.73 → 13.80 px
- H_TPS_all kötüleştirdi: `dataset/curved_angled/008.png` matematik: 2.07 → 9.95 px
- H_TPS_all kötüleştirdi: `dataset/curved_angled/008.png` sosyal: 1.11 → 5.76 px
- H_TPS_all kötüleştirdi: `dataset/curved_front/006.png` fen: 1.23 → 3.87 px
- H_TPS_all kötüleştirdi: `dataset/curved_angled/009.png` fen: 4.37 → 6.94 px
- H_TPS_inliers kötüleştirdi: `dataset/flat_front/001.png` fen: 2.17 → 3.17 px
- H_TPS_inliers kötüleştirdi: `dataset/curved_front/005.png` matematik: 1.20 → 2.19 px
- H_TPS_inliers kötüleştirdi: `dataset/flat_front/003.png` fen: 0.69 → 1.67 px
- H_TPS_inliers kötüleştirdi: `dataset/curved_front/005.png` fen: 1.35 → 2.32 px
- H_TPS_inliers kötüleştirdi: `dataset/flat_front/001.png` matematik: 1.96 → 2.91 px

İnceleme gereken 7 görüntü (kapsama < %80 veya yerel model kurulamadı → H'ye geri düştü). Bunlar başarı sayılmaz:

- `dataset/curved_angled/006.png`: kapsama turkce %94, sosyal %92, matematik %77, fen %26
- `dataset/curved_angled/008.png`: kapsama turkce %88, sosyal %78, matematik %85, fen %78
- `dataset/curved_angled/010.png`: kapsama turkce %100, sosyal %93, matematik %89, fen %56
- `dataset/curved_front/006.png`: kapsama turkce %61, sosyal %8, matematik %11, fen %6
- `dataset/curved_front/010.png`: kapsama turkce %96, sosyal %86, matematik %91, fen %63
- `dataset/flat_angled/009.png`: kapsama turkce %99, sosyal %81, matematik %85, fen %51
- `dataset/flat_front/009.png`: kapsama turkce %91, sosyal %39, matematik %49, fen %20

## Sonraki karar

Marker'lar içeriyi temsil etmiyorsa kontrol noktasını içeriden al: her dersin kendi basılı balonları (E2).


---
*Bu rapor `run_experiment.py` tarafından üretildi. Rakamlar insan etiketli ground truth değildir; eşleşmeler başlangıç H'sinin 10 px çevresinden seçildiği için büyük hatalar dışarıda kalabilir.*
