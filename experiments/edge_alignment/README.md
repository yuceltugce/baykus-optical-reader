> **Arşiv.** Bu klasör eski deney kaydıdır ve değiştirilmez. Güncel, düzenli sürüm: [`../edge_alignment_v2/`](../edge_alignment_v2/README.md). Git etiketi: `archive/old-notebook-experiments`.

# E0 — Kenar hizalama başlangıç deneyi

Referans: `dataset/flat_front/004.png`. Bu tarama fiziksel ground truth değildir.

## Çalıştırma

Proje kökünde:

```sh
.venv/bin/python scripts/edge_baseline.py --root . --output experiments/edge_alignment/runs/E0-new
```

Tüm 41 görüntü için `--all` eklenebilir. Çıktı klasörü mevcutsa işlem durur; eski deney üzerine yazılmaz.

## Yöntem

- Notebook'taki marker dedektörü taşındı: yükseklik 2000 px, eşik 140, 5x5 açma, extent 0.82, yakın adayları birleştirme ve izolasyon filtresi.
- Normalize yakınlık + Hungarian eşleştirme, 0.06 kapısı. Aynı yönde ve kabaca kırpılmış taramalar varsayılır; serbest kamera fotoğrafı için henüz uygun değildir. Eşleşmeler görsel inceleme gerektirir.
- Aynı eşleşmelerle tüm noktaları kullanan homografi ve 3 px eşikli RANSAC homografisi karşılaştırılır. TPS ve cevap okuma yoktur.
- Her balon ayrı ayrı dönüştürülür. Tek A noktası + sabit dx kullanılmaz.
- Geçici şablon: Türkçe 40, Sosyal 46, Matematik 40, Fen 40; toplam 830 balon. Elle seçilmiş köşe merkezleri arasında başlangıç ızgarası kurulur, en yakın uygun konturla en fazla 10 px düzeltilir. Kontur merkezi kesin gerçek merkez sayılmaz. Referansta doğrulanamayanlar kırmızı işaretlenir.
- 2000 px çalışma uzayı ile orijinal görüntü boyutları JSON'da kayıtlıdır. Orijinal x/y dönüşümünde iki eksenin ölçeği ayrı kullanılmalıdır.
- Marker artık hatası eğitim noktalarında ölçülür, balon doğruluğu değildir. Bağımsız balon ground truth hatası kasıtlı olarak null bırakılır.
- Fiziksel form kimlikleri henüz bilinmiyor; manifestte null. Farklı doldurulmuş formlar cevap eşitliğiyle karşılaştırılmaz.

## Kayıt ve sınırlar

Her run görüntü bindirmeleri, üst/orta/alt kırpmalar, marker eşleşmeleri, H matrisleri, inlier bilgisi, referans şablonu ve SHA-256 veri envanteri üretir. Kod kimliği, başlangıç commit'i, OpenCV sürümü ve parametreler de kayıtlıdır. Sabit isimler, seed ve değişmeyen girdiler aynı geometriyi üretmelidir.

E0-first: 5 px kontur araması, 670/830 kontur eşleşmesi; orta satırlarda şablon kayması gözle görüldü.
E0-refined: 10 px kontur araması, 814/830; bu düzeltme yalnız referans şablonunu iyileştirir, hedef görüntü hizalamasını değil.
E0-v2-review: aynı geometri, destek çokgenleri ve açık görsel etiketler eklenmiş inceleme sürümü.

Sonraki deney: kırmızı referans merkezlerinin ve her ders üst/orta/alt kontrol noktalarının insan tarafından doğrulanması; düzeltmede kullanılmayan noktalarda balon çapına normalize hata ölçümü. Sonra homografi/TPS/yerel çizgi-kontur hizalama karşılaştırması. Henüz bir yöntem kazanan ilan edilmez.
