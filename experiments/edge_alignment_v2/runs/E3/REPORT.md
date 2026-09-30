# E3 — Piece-wise warp

**Deney adı:** E3 — Piece-wise warp

**Amaç:** Her ders bloğuna ayrı bir homography vermek (global H + düzeltme yerine) daha iyi veya daha sade mi?

**Kullanılan girdi:** `dataset/*/*.png` — referans hariç 40 tarama (40 başarıyla işlendi). Tüm ölçüler yüksekliği 2000 px'e indirilmiş görüntüde, piksel cinsinden. Bir balon çapı ≈ 22 px.

**Başlangıç hizalaması:** korumalı RANSAC. RANSAC'ın kurduğu dönüşüm kararsızsa (koşul sayısı > 5000), bütün markerlarla kurulan dönüşüm kullanılır. Bu çalıştırmada 0 görüntüde bütün markerlara dönüldü.

**Referans:** `dataset/flat_front/004.png` + `reference/template.json` (830 balon merkezi, E1'de onarılmış geçici şablon). Bu tarama fiziksel ground truth değildir. Ölçümler otomatik kontur eşleşmelerine göre yapılır (soru % 5 == 1 satırları eğitim, diğerleri ölçüm).

**Değiştirilen şey:** Blok içinde global H atılır; referans balon merkezleri -> tespit edilen konturlar arasında ders başına 3x3 homography (RANSAC 2 px).

**Kullanılmayan şey:** Blok içi eğrilik (her blok düzlem kabul edilir), insan etiketli ground truth.

**Çıktı:** `comparison.jpg` (yeşil halka = tespit edilen balon, kırmızı artı = yöntemin tahmini), `metrics.json`, `config.json`, `source/`.

## Sonuç — ders bazında

Görüntü başına held-out medyan hatanın, görüntüler üzerinden medyanı (px). Küçük = iyi.

| Yöntem | turkce | sosyal | matematik | fen |
|---|---:|---:|---:|---:|
| H_ransac | 1.16 | 1.37 | 1.58 | 1.63 |
| H_local_contours | 0.30 | 0.29 | 0.30 | 0.36 |
| piecewise_H | 0.39 | 0.51 | 0.45 | 0.53 |


## Sonuç — dikey bant (üst / orta / alt satırlar)

| Yöntem | üst | orta | alt |
|---|---:|---:|---:|
| H_ransac | 1.26 | 1.45 | 1.93 |
| H_local_contours | 0.31 | 0.28 | 0.31 |
| piecewise_H | 0.41 | 0.40 | 0.55 |


## Nereye bakmalı?

metrics.json -> aggregate.by_band (üst/orta/alt) ve by_subject; piecewise_H ile H_local_contours farkı.


## Başarılı olduğu durum

Ölçüt: piecewise_H, H_local_contours'a yakın veya daha iyi ve bantlar arasında (üst/orta/alt) fark küçükse: blok başına düzlem varsayımı yeterli, daha sade model seçilebilir.

- **H_local_contours** vs H_ransac: 155 (görüntü, ders) çiftinde >0.1 px daha iyi, 0 çiftte daha kötü (toplam 155 farklı çift).
- **piecewise_H** vs H_ransac: 152 (görüntü, ders) çiftinde >0.1 px daha iyi, 0 çiftte daha kötü (toplam 152 farklı çift).

## Başarısız olduğu durum

Ölçüt: Alt/üst bantlarda H_local_contours'tan belirgin kötüyse blok içinde de eğrilik vardır; TPS düzeltmesi gerekir.

- H_local_contours: H_ransac'a göre >0.1 px kötüleştiği hiçbir (görüntü, ders) çifti yok.
- piecewise_H: H_ransac'a göre >0.1 px kötüleştiği hiçbir (görüntü, ders) çifti yok.

İnceleme gereken 7 görüntü (kapsama < %80 veya yerel model kurulamadı → H'ye geri düştü). Bunlar başarı sayılmaz:

- `dataset/curved_angled/006.png`: kapsama turkce %94, sosyal %92, matematik %77, fen %26; fallback: fen
- `dataset/curved_angled/008.png`: kapsama turkce %88, sosyal %78, matematik %85, fen %78
- `dataset/curved_angled/010.png`: kapsama turkce %100, sosyal %93, matematik %89, fen %56
- `dataset/curved_front/006.png`: kapsama turkce %61, sosyal %8, matematik %11, fen %6; fallback: fen, matematik, sosyal
- `dataset/curved_front/010.png`: kapsama turkce %96, sosyal %86, matematik %91, fen %63
- `dataset/flat_angled/009.png`: kapsama turkce %99, sosyal %81, matematik %85, fen %51
- `dataset/flat_front/009.png`: kapsama turkce %91, sosyal %39, matematik %49, fen %20; fallback: fen

## Sonraki karar

Hangi yöntem seçilirse seçilsin taranmış düz referansla gerçek ground truth doğrulaması (E4).


---
*Bu rapor `run_experiment.py` tarafından üretildi. Rakamlar insan etiketli ground truth değildir; eşleşmeler başlangıç H'sinin 10 px çevresinden seçildiği için büyük hatalar dışarıda kalabilir.*
