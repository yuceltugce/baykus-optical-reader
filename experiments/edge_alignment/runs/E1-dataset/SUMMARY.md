# E1 — Deney sonucu

Referans dışındaki 40 görüntüde altı geometrik yöntem karşılaştırıldı. Aşağıdaki rakamlar görüntü başına medyan hataların medyanıdır; birim, yüksekliği 2000 piksele indirilmiş görüntüde pikseldir. Fiziksel form kimlikleri bilinmediği için 40 bağımsız kağıt üzerinde genelleme iddiası yoktur.

| Yöntem | Türkçe | Sosyal | Matematik | Fen |
|---|---:|---:|---:|---:|
| H_all | 1.19 | 1.42 | 1.42 | 1.51 |
| H_ransac | 1.16 | 1.37 | 1.58 | 1.63 |
| TPS_markers | 1.10 | 1.52 | 2.19 | 3.46 |
| H_TPS_all | 1.09 | 1.52 | 1.67 | 1.75 |
| H_TPS_inliers | 1.08 | 1.46 | 1.92 | 1.85 |
| H_local_contours | 0.30 | 0.29 | 0.30 | 0.36 |

## Nasıl yorumlanmalı?

- Ölçülenler otomatik kontur eşleşmeleridir, insan etiketli ground truth değildir. Eşleşmeler başlangıç homografisinin 10 px çevresinden seçildi; büyük hatalar dışarıda kalabilir. Bütün yöntemler aynı değerlendirme noktalarında karşılaştırıldı.
- Yerel model 1, 6, 11, ... satırlarını kullanır. Bu satırlar ölçümden çıkarılmıştır. Bu bir satır ayırma deneyidir; bağımsız kağıt testi değildir.
- Yeni TPS uygulaması SciPy RBFInterpolator ile yazıldı; eski OpenCV notebook sürümünün birebir yeniden çalıştırılması değildir. Saf TPS markerlara tam oturur; residual TPS yumuşatılmıştır.
- Yerel kontur düzeltmesi bu ölçümde umut verici. Ancak yeterli kontrol noktası bulunamayan bloklarda başlangıç homografisine döner. Bu durum sessiz başarı sayılmamalıdır.
- Referanstaki 16 belirsiz merkezin 15'i çoklu eşik + elips tespitiyle düzeltildi ve yakın planları görsel olarak incelendi. Sosyal 44-E otomatik olarak doğrulanamadı; ölçümden dışlandı. Diğer otomatik merkezler de tarayıcıdan alınmış kesin koordinatlar değildir.
- Beş geometri testi geçti: projektif ileri/geri dönüşüm, görülmeyen noktalarda affine artık alanı, belirsiz/uzak aday reddi, eşleşme tekilliği, dejenere kontrol noktalarının reddi.

## Ek inceleme gereken görüntüler

Herhangi bir derste nominal ölçüm noktalarının %80'inden azı eşleşiyorsa veya yerel model kurulamıyorsa aşağıda listelenir. Bu eşik deneysel bir inceleme kuralıdır, kalibre edilmiş güven skoru değildir.

- dataset/curved_angled/006.png: matematik, fen; kapsama turkce %94, sosyal %92, matematik %77, fen %26
- dataset/curved_angled/008.png: sosyal, fen; kapsama turkce %88, sosyal %78, matematik %85, fen %78
- dataset/curved_angled/010.png: fen; kapsama turkce %100, sosyal %92, matematik %89, fen %56
- dataset/curved_front/006.png: turkce, sosyal, matematik, fen; kapsama turkce %61, sosyal %8, matematik %11, fen %6
- dataset/curved_front/010.png: fen; kapsama turkce %96, sosyal %86, matematik %91, fen %63
- dataset/flat_angled/009.png: fen; kapsama turkce %99, sosyal %81, matematik %85, fen %51
- dataset/flat_front/009.png: sosyal, matematik, fen; kapsama turkce %91, sosyal %39, matematik %49, fen %20

## Sonraki adım

Özellikle düşük kapsamalı görüntülerde kontrast/bulanıklık ve eşleşme hatasını ayır; gerçek merkezleri elle işaretlenmiş küçük bir kontrol kümesi hazırla. Boş/dolu balonlar ve farklı fiziksel kağıtlar ayrı izlenmeli. Yerel yöntem ancak bu kontrolle doğrulandıktan sonra telefon–PC okuyucu akışına bağlanmalı. Hiçbir cevap doğruluğu yüzdesi bu deneyden çıkarılmadı.
