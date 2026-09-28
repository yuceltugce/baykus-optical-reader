# E2 — Local contour correction

**Deney adı:** E2 — Local contour correction

**Amaç:** Her ders bloğunun kendi basılı balon konturlarını yerel kontrol noktası yapmak hatayı azaltır mı?

**Kullanılan girdi:** `dataset/*/*.png` — referans hariç 40 tarama (40 başarıyla işlendi). Tüm ölçüler yüksekliği 2000 px'e indirilmiş görüntüde, piksel cinsinden. Bir balon çapı ≈ 22 px.

**Referans:** `dataset/flat_front/004.png` + `reference/template.json` (830 balon merkezi, E1'de onarılmış geçici şablon). Bu tarama fiziksel ground truth değildir. Ölçümler otomatik kontur eşleşmelerine göre yapılır (soru % 5 == 1 satırları eğitim, diğerleri ölçüm).

**Değiştirilen şey:** Global H'nin üstüne, her derste eğitim satırlarından (1, 6, 11, ... sorular) kurulan yumuşak TPS düzeltme alanı. Ölçüm yalnız diğer satırlarda.

**Kullanılmayan şey:** Ders başına bağımsız perspektif (E3), insan etiketli ground truth (E4).

**Çıktı:** `comparison.jpg` (yeşil halka = tespit edilen balon, kırmızı artı = yöntemin tahmini), `metrics.json`, `config.json`, `source/`.

## Sonuç — ders bazında

Görüntü başına held-out medyan hatanın, görüntüler üzerinden medyanı (px). Küçük = iyi.

| Yöntem | turkce | sosyal | matematik | fen |
|---|---:|---:|---:|---:|
| H_ransac | 1.16 | 1.37 | 1.58 | 1.63 |
| H_local_contours | 0.30 | 0.29 | 0.30 | 0.36 |


## Sonuç — dikey bant (üst / orta / alt satırlar)

| Yöntem | üst | orta | alt |
|---|---:|---:|---:|
| H_ransac | 1.26 | 1.45 | 1.93 |
| H_local_contours | 0.31 | 0.28 | 0.31 |


## Nereye bakmalı?

REPORT.md 'Başarısız olduğu durum' listesi (fallback olan dersler) ve metrics.json -> aggregate.by_subject.


## Başarılı olduğu durum

Ölçüt: Held-out satırlarda hata tüm derslerde belirgin düşer ve fallback az görülür.

- **H_local_contours** vs H_ransac: 155 (görüntü, ders) çiftinde >0.1 px daha iyi, 0 çiftte daha kötü (toplam 155 farklı çift).

## Başarısız olduğu durum

Ölçüt: Kontur tespiti düşük kapsama verirse (bulanık/düşük kontrast görüntüler) düzeltme kurulamaz ve H'ye geri düşer.

- H_local_contours: H_ransac'a göre >0.1 px kötüleştiği hiçbir (görüntü, ders) çifti yok.

İnceleme gereken 7 görüntü (kapsama < %80 veya yerel model kurulamadı → H'ye geri düştü). Bunlar başarı sayılmaz:

- `dataset/curved_angled/006.png`: kapsama turkce %94, sosyal %92, matematik %77, fen %26; fallback: fen
- `dataset/curved_angled/008.png`: kapsama turkce %88, sosyal %78, matematik %85, fen %78
- `dataset/curved_angled/010.png`: kapsama turkce %100, sosyal %93, matematik %89, fen %56
- `dataset/curved_front/006.png`: kapsama turkce %61, sosyal %8, matematik %11, fen %6; fallback: fen, matematik, sosyal
- `dataset/curved_front/010.png`: kapsama turkce %96, sosyal %86, matematik %91, fen %63
- `dataset/flat_angled/009.png`: kapsama turkce %99, sosyal %81, matematik %85, fen %51
- `dataset/flat_front/009.png`: kapsama turkce %91, sosyal %39, matematik %49, fen %20; fallback: fen

## Sonraki karar

Fikir işe yarıyorsa tam piece-wise warp olarak yaz (E3); düşük kapsamalı görüntüleri ayrı incele.


---
*Bu rapor `run_experiment.py` tarafından üretildi. Rakamlar insan etiketli ground truth değildir; eşleşmeler başlangıç H'sinin 10 px çevresinden seçildiği için büyük hatalar dışarıda kalabilir.*
