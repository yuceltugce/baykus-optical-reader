# DIAG — Kenarlar neden oturmuyor? (hata haritası)

**Amaç:** E0'daki global homography'nin (H_ransac) balonlarda bıraktığı hatanın *nedenini* görmek.
Yöntem denemiyoruz; sadece hatanın nerede, hangi yönde ve hangi fotoğraf grubunda büyüdüğüne bakıyoruz.

**Ne çizildi:** Her balon için "H_ransac'ın tahmini → fotoğrafta tespit edilen basılı halka" farkı bir ok.
Ok boyu = hata × 25. Renk: yeşil <1, sarı 1–2, turuncu 2–4, kırmızı >4 px (2000 px yükseklikte; balon ≈ 22 px).
Mavi kareler referans markerlar. Hiçbir şey bu noktalara uydurulmadı; saf teşhis.

**Çalıştırma:** `../../.venv/bin/python diagnose_error_map.py --overwrite` (bu klasörden)

## Çıktılar

- `group_mean_error_map.jpg` — 4 grubun ortalama ok haritası (ana resim)
- `mean_<grup>.jpg` — aynısı tam boy
- `per_image/*.jpg` — her fotoğraf ayrı
- `metrics.json` — grup/fotoğraf bazında medyan hata, satır bandı, ders, model R²

## Grup bazında hata (px, medyan)

| Grup | Genel | Üst | Orta | Alt | Türkçe | Sosyal | Mat | Fen |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| flat_front | 0.96 | 0.97 | 0.92 | 0.90 | 0.56 | 0.86 | 1.14 | 1.65 |
| flat_angled | 1.91 | 1.47 | 2.05 | 2.84 | 2.07 | 2.23 | 1.88 | 1.78 |
| curved_front | 1.37 | 1.27 | 1.31 | 1.50 | 1.18 | 1.39 | 1.47 | 1.54 |
| curved_angled | 1.60 | 1.44 | 1.65 | 2.78 | 1.15 | 1.23 | 2.03 | 1.85 |

## Bulgular

1. **Fen, markerların kapsadığı alanın büyük ölçüde dışında.** Referansta Fen'in 200 balonunun 162'si,
   Matematik'in 14'ü marker dış bükey örtüsünün (convex hull) dışında (eski E0 kaydı,
   `bubbles_outside_inlier_hull`). Orada homography interpolasyon değil **ekstrapolasyon** yapıyor; her türlü
   model hatası orada büyüyor. flat_front haritasında hata soldan sağa açıkça artıyor (Türkçe 0.56 → Fen 1.65).
2. **Ana neden kağıdın kıvrık olması değil.** En büyük hata *düz* kağıdın açılı çekiminde (flat_angled 1.91),
   kıvrık kağıdın önden çekiminden (curved_front 1.37) daha büyük. Hata, çekimin referans çekimden
   (flat_front/004, o da bir fotoğraf) ne kadar farklı olduğuyla birlikte büyüyor.
3. **Açılı çekimlerde hata aşağı doğru büyüyor** (flat_angled alt satırlar 2.84, curved_angled 2.78 px) ve
   ortalama oklar tutarlı tek bir yöne bakıyor: rastgele gürültü değil, sistematik bir bozulma.
4. **Grup içi fark çok büyük.** flat_angled/001 0.62 px, flat_angled/006 5.81 px. Aynı koşul adı altında çok
   farklı çekimler var.
5. **Girdi görüntüleri ham kamera fotoğrafı değil.** Fotoğraflar iPhone belge tarayıcısıyla çekildi (ekip
   tarafından doğrulandı): kağıt kenarına kırpılmış, dikdörtgene getirilmiş, ~9000 px yüksek, PDF olarak kaydedilmiş.
   Tarayıcı kağıdın kenarlarından kendi perspektif düzeltmesini zaten yapıyor; bizim gördüğümüz hata kısmen *onun*
   bıraktığı bozulma. Referans (flat_front/004) da aynı yolla elde edildi.

## Lens testi neden sonuçsuz

İki küçük model hatanın ne kadarını açıklıyor (R², 0–1):

| Grup | Radyal (lens, 2 parametre) | Blok kayması (8 parametre) |
|---|---:|---:|
| flat_front | 0.60 | 0.73 |
| flat_angled | 0.67 | 0.69 |
| curved_front | 0.54 | 0.64 |
| curved_angled | 0.53 | 0.45 |

İkisi de hatanın yarısından fazlasını açıklıyor, hiçbiri açıkça kazanmıyor. Ayrıca radyal model lens merkezini
görüntü ortası varsayıyor; görüntüler iPhone tarayıcısında kırpılıp düzleştirildiği için bu varsayım geçersiz. **Lens bozulması ne
doğrulandı ne dışlandı.** Kesin test için aynı telefonla ham (uygulamadan geçmemiş) fotoğraf + kalibrasyon gerekir.

## Sonuç (mentöre)

Kenar hatasının iki doğrulanmış bileşeni var: (1) Fen bloğu marker desteğinin dışında, orada hizalama
ekstrapolasyon; (2) hata çekim açısıyla büyüyor, kağıt kıvrımından daha çok. Üçüncü bileşen: bütün girdiler (referans
dahil) iPhone belge tarayıcısının kendi düzeltmesinden geçmiş; kaldırılmayan bozulmayı biz miras alıyoruz.

**Sonraki karar:** Ham kamera fotoğrafları ve tarayıcıdan alınmış gerçek düz bir referans ile teşhisi tekrarla.
Form tasarımı değiştirilebiliyorsa Fen'in sağına marker eklemek en ucuz çözüm olabilir.
