# Baykuş Optik — Kenar hizalama deneyleri

**Soru:** Eğik çekilmiş ya da kıvrılmış bir optik formun fotoğrafında, her cevap balonunun merkezini ne kadar doğru
bulabiliyoruz; hangi hizalama yöntemi kenardaki ders bloklarında (Matematik, Fen) bile tutarlı kalıyor?

**Veri:** 4 grup × ~10 tarama = 40 görüntü (`flat_front`, `flat_angled`, `curved_front`, `curved_angled`).
Referans: `flat_front/004.png`. 830 balon (Türkçe 40, Sosyal 46, Matematik 40, Fen 40 soru × 5 şık).

## Özet

| Deney | Ne test ediyor? | Sonuç |
|---|---|---|
| E0 — Global homography | Köşe markerlarından tek perspektif dönüşüm yeterli mi? | Hayır. Hata 1.2–1.6 px ve alt satırlara doğru artıyor (1.26 → 1.93 px). |
| E1 — Marker TPS | Aynı markerlarla esnek (TPS) warp daha iyi mi? | Kararsız. Türkçe'de biraz iyileşiyor, Fen'de bozuluyor (1.63 → 3.46 px); bazı taramalarda 6–14 px'e çıkıyor. |
| E2 — Local contour | Her dersin kendi basılı balonlarını yerel kontrol noktası yapmak işe yarıyor mu? | En iyi sonuç: tüm derslerde 0.29–0.36 px, üst/orta/alt farkı yok. 160 (görüntü, ders) çiftinin 155'inde iyileşme, hiç kötüleşme yok. |
| E3 — Piece-wise warp | Her derse ayrı bir homography vermek yetiyor mu? | H'den çok daha iyi (0.39–0.53 px) ama E2'den kötü, özellikle alt satırlarda (0.55 vs 0.31). Bloklar kendi içinde de düz değil. |
| E4 — Ground-truth validation | Sonuçlar gerçekten doğru mu? | Henüz yapılmadı: tarayıcıdan elde edilecek düz referans ve elle işaretlenmiş merkezler bekleniyor. |

Tüm rakamlar: held-out satırlarda, görüntü başına medyan hatanın 40 görüntü üzerinden medyanı. Birim piksel,
yüksekliği 2000 px'e ölçeklenmiş görüntüde (bir balon ≈ 22 px, yani 0.3 px ≈ balon çapının %1.5'i).

### Ders bazında hata (px, küçük = iyi)

| Yöntem | Deney | Türkçe | Sosyal | Matematik | Fen |
|---|---|---:|---:|---:|---:|
| H_all | E0 | 1.19 | 1.42 | 1.42 | 1.51 |
| H_ransac | E0 (her deneyde baseline) | 1.16 | 1.37 | 1.58 | 1.63 |
| TPS_markers | E1 | 1.10 | 1.52 | 2.19 | 3.46 |
| H_TPS_all | E1 | 1.09 | 1.52 | 1.67 | 1.75 |
| H_TPS_inliers | E1 | 1.08 | 1.46 | 1.92 | 1.85 |
| **H_local_contours** | **E2** | **0.30** | **0.29** | **0.30** | **0.36** |
| piecewise_H | E3 | 0.39 | 0.51 | 0.45 | 0.53 |

### Satır bandına göre hata (px) — kenar etkisi

| Yöntem | Üst satırlar | Orta | Alt satırlar |
|---|---:|---:|---:|
| H_ransac | 1.26 | 1.45 | 1.93 |
| TPS_markers | 1.47 | 2.05 | 1.85 |
| H_TPS_all | 1.08 | 1.90 | 1.64 |
| H_local_contours | 0.31 | 0.28 | 0.31 |
| piecewise_H | 0.41 | 0.40 | 0.55 |

## Teşhis: kenarlar neden oturmuyor?

Ayrıntı: [`runs/DIAG_error_map/REPORT.md`](runs/DIAG_error_map/REPORT.md), ana resim
`runs/DIAG_error_map/group_mean_error_map.jpg`. Global homography'nin her balonda bıraktığı hata ok olarak çizildi.

1. **Fen, markerların kapsadığı alanın dışında.** Referansta Fen'in 200 balonunun 162'si marker dış bükey örtüsünün
   dışında kalıyor. Orada homography ekstrapolasyon yapıyor. Düz-önden çekimde bile hata soldan sağa büyüyor
   (Türkçe 0.56 → Fen 1.65 px).
2. **Asıl etken kağıt kıvrımı değil, çekim açısı.** Düz kağıdın açılı çekimi (1.91 px), kıvrık kağıdın önden
   çekiminden (1.37 px) daha kötü. Açılı çekimlerde hata aşağı doğru ve tek yönde büyüyor, yani sistematik.
3. **Girdiler ham fotoğraf değil.** Tüm görüntüler (referans dahil) iPhone belge tarayıcısıyla çekildi; tarayıcı
   kağıdı zaten kırpıp kendi yöntemiyle düzleştiriyor. Biz onun bıraktığı bozulmayı düzeltmeye çalışıyoruz.
   Lens bozulması ne doğrulandı ne dışlandı.

## Hikâye: her deney bir öncekinden neden çıktı?

1. **E0.** Önce global homography ile başlangıç hatasını ölçtüm. Kağıt tam bir düzlem olsaydı tek bir 3×3 matris
   yeterdi. Hata ~1.5 px ve alt satırlarda artıyor: kağıt eğri, markerlar da yalnız kenarda olduğu için ders
   bloklarının içini yeterince desteklemiyor.
2. **E1.** Daha esnek bir model olarak marker'lardan Thin-Plate Spline denedim. TPS kontrol noktalarından geçen en
   yumuşak bükülmedir; ama kontrol noktaları hâlâ yalnız kenardaki markerlar. Bu yüzden markerlar arasında tahmin
   yapıp aşırı bükülüyor: Türkçe'de biraz iyileşirken Matematik/Fen'de kararsızlaşıyor
   (ör. `curved_angled/008` Fen 3.7 → 13.8 px). **Sonuç:** Sorun modelin esnekliği değil, kontrol noktalarının yeri.
3. **E2.** Kontrol noktasını içeriden aldım: her dersin kendi basılı balon halkaları. Her derste yalnızca 1, 6, 11,
   … soruları kontrol noktası yaptım, ölçümü diğer satırlarda yaptım. Global H'nin üzerine ders başına yumuşak bir
   düzeltme alanı kuruldu. Hata tüm derslerde ve tüm satır bantlarında ~0.3 px'e düştü.
4. **E3.** Aynı fikri daha sade bir modelle denedim: her derse ayrı bir homography (piece-wise warp). E0'a göre
   büyük iyileşme var, ama E2'nin gerisinde kalıyor ve alt satırlarda hata tekrar artıyor. Yani bir ders bloğu bile
   tam düzlem değil. Blok içindeki eğrilik için E2'deki gibi yumuşak düzeltme gerekiyor.
5. **E4 (sıradaki).** Bütün bu ölçümler otomatik kontur tespitine dayanıyor, gerçek ground truth değil. Seçilen
   yöntemin gerçekten doğru olduğunu, taranmış düz referans ve elle işaretlenmiş merkezlerle doğrulamak gerekiyor.

## Bu sonuçlara ne kadar güvenebiliriz?

- **Otomatik etiket, ground truth değil.** "Gözlenen merkez" fotoğraftaki basılı halkaya elips uydurularak bulundu.
  E2/E3 kontrol noktaları ile ölçüm noktaları farklı satırlar, ama ikisi de aynı dedektörden geliyor. Bu yüzden E2'nin
  0.3 px'i "dedektörle tutarlı" demek, "gerçekte 0.3 px doğru" demek değil.
- **Seçim yanlılığı.** Etiketler, başlangıç H'sinin 10 px çevresinden seçildi; çok büyük kaymalar ölçüme hiç
  girmeyebilir.
- **Kapsama sorunu olan 7 görüntü.** `curved_front/006`, `flat_front/009`, `curved_angled/006` gibi taramalarda bazı
  derslerde balonların %80'inden azı tespit edilebildi. Beş (görüntü, ders) çiftinde yerel model hiç kurulamadı ve
  H'ye geri düştü. Bunlar başarı sayılmıyor, her `REPORT.md`'de listeli.
- **Bağımsızlık.** 40 tarama 40 ayrı kağıt değil; fiziksel form kimlikleri henüz etiketlenmedi.
- **Cevap doğruluğu yok.** Bu deneyler yalnız geometri; hiçbir "doğru okunan cevap %" iddiası yok.

## Sonraki adımlar

1. **E4 — ground truth:** Tarayıcıdan alınmış düz referans + küçük bir görüntü kümesinde elle işaretlenmiş balon
   merkezleri. E0–E3'ü bu gerçek etiketlerle tekrar ölç.
2. Düşük kapsamalı 7 görüntüde sorunun kaynağını ayır: kontrast/bulanıklık mı, eşleştirme hatası mı?
3. E2 doğrulanırsa okuyucu akışına bağla; bağlarken "yerel model kurulamadı" durumunu sessizce geçme, kullanıcıya bildir.

## Tekrar üretme

```sh
.venv/bin/python experiments/edge_alignment_v2/run_experiment.py --experiment all --overwrite
```

Her deneyin ayrıntılı raporu: [`runs/E0/REPORT.md`](runs/E0/REPORT.md), [`runs/E1/REPORT.md`](runs/E1/REPORT.md),
[`runs/E2/REPORT.md`](runs/E2/REPORT.md), [`runs/E3/REPORT.md`](runs/E3/REPORT.md). Protokol ayrıntısı:
[`README.md`](README.md). Eski (arşiv) deneyler: `experiments/edge_alignment/`, git etiketi
`archive/old-notebook-experiments`. v2 kodu eski E0/E1 sonuçlarını 40 görüntüde birebir yeniden üretir.
