# Kenar hizalama deneyleri (v2)

## Problem

Optik formun fotoğrafındaki her cevap balonunun merkezini, düz referans taramadaki (`dataset/flat_front/004.png`)
karşılığıyla eşleştirmek istiyoruz. Kağıt eğik çekildiğinde veya kıvrıldığında, köşe markerlarından hesaplanan tek
bir dönüşüm, özellikle markerlardan uzak ders bloklarında (Matematik, Fen) balonları kaçırıyor. Bu klasör, bu hatayı
azaltmak için denenen fikirleri **tek protokol, tek giriş noktası, aynı rapor formatı** ile karşılaştırır.

Mentöre gösterilecek belge: **[EXPERIMENTS.md](EXPERIMENTS.md)**.

## Klasör yapısı

```
edge_alignment_v2/
├── README.md              bu dosya: problem, protokol, nasıl çalıştırılır
├── EXPERIMENTS.md         ana rapor (E0 → E4 hikâyesi)
├── run_experiment.py      tek giriş noktası
├── configs/               her deneyin amacı, yöntemleri, başarı/başarısızlık ölçütü
├── reference/template.json  830 balon merkezi (E1'de onarılmış geçici şablon, donduruldu)
├── src/
│   ├── common.py          görüntü yükleme, marker tespiti, balon konturu tespiti, eşleştirme
│   ├── homography.py      E0 — global homography
│   ├── tps.py             E1 — marker TPS
│   ├── local_contour.py   E2 — ders içi balon konturlarıyla yerel düzeltme
│   └── piecewise.py       E3 — her derse ayrı homography
├── tests/test_methods.py  sentetik veriyle birim testleri
└── runs/E0 … E3/          her çalıştırmanın çıktısı
```

## Çalıştırma

Proje kökünden (`baykus-optical-reader/`):

```sh
.venv/bin/python experiments/edge_alignment_v2/run_experiment.py --experiment E0
.venv/bin/python experiments/edge_alignment_v2/run_experiment.py --experiment E1
.venv/bin/python experiments/edge_alignment_v2/run_experiment.py --experiment E2
.venv/bin/python experiments/edge_alignment_v2/run_experiment.py --experiment E3
.venv/bin/python experiments/edge_alignment_v2/run_experiment.py --experiment all --overwrite
```

- Varsayılan: referans hariç 40 taramanın hepsi (tümü ~1–2 dk).
- `--quick`: yalnız 4 vitrin taraması (her gruptan `001.png`), hızlı kontrol için.
- `runs/<ID>` zaten varsa durur; üzerine yazmak için `--overwrite`.
- Testler: `cd experiments/edge_alignment_v2 && ../../.venv/bin/python -m unittest discover -s tests`

## Her çalıştırmanın bıraktığı dosyalar

| Dosya | İçinde ne var | Nasıl okunur |
|---|---|---|
| `REPORT.md` | Standart rapor: amaç, girdi, değiştirilen/kullanılmayan şey, sonuç tabloları, başarılı/başarısız durumlar, sonraki karar | **İlk buraya bak.** |
| `metrics.json` | `aggregate` (özet tablo), `review_required` (şüpheli görüntüler), `per_image` (her tarama, her yöntem, her ders için n / medyan / p95) | Tek bir taramayı merak edersen `per_image["dataset/…"]` |
| `comparison.jpg` | 4 vitrin taraması × üst/orta/alt satırlar × yöntemler. Yeşil halka = tespit edilen balon, kırmızı artı = yöntemin tahmini | Artı halkanın dışına taşıyorsa kaba hata. **~1 px'lik farklar bu ölçekte görünmez; onlar için tablolara bak.** |
| `config.json` | Deney ayarları + kod/veri kimliği (commit, kütüphane sürümleri, her girdinin SHA-256'sı) | Tekrar üretilebilirlik |
| `source/` | Bu çalıştırmayı üreten kodun birebir kopyası | Kod sonradan değişse de sonucun hangi koddan çıktığı bellidir |

## Ortak ölçüm protokolü

Bütün deneyler aynı noktalarda, aynı şekilde ölçülür; bu yüzden E0–E3 rakamları doğrudan karşılaştırılabilir.

1. **Başlangıç tahmini.** Köşe markerları tespit edilir, referansla eşleştirilir (Hungarian), 3 px RANSAC
   homography `H_ransac` hesaplanır. Referans balon merkezleri bu H ile fotoğrafa taşınır.
2. **Otomatik etiket (pseudo-label).** Fotoğraftaki basılı balon halkaları çoklu eşik + elips uydurma ile bulunur.
   Başlangıç tahminine ≤10 px uzaklıkta ve belirsiz olmayan (ikinci aday ≥3 px daha uzak) halka, o balonun
   "gözlenen merkezi" sayılır. Bu etiketler **bir kere, hiçbir yöntem çalışmadan önce** dondurulur.
3. **Eğitim / ölçüm ayrımı.** Soru numarası `% 5 == 1` olan satırlar (1, 6, 11, …) yerel yöntemlerin kontrol
   noktası olarak kullanabileceği satırlardır. Hata **yalnızca diğer satırlarda** ölçülür (held-out).
4. **Metrik.** Tahmin ile gözlenen merkez arasındaki uzaklık (px, 2000 px yüksekliğe ölçeklenmiş görüntüde; bir
   balon ≈ 22 px). Her görüntü için ders bazında medyan alınır, sonra 40 görüntünün medyanı raporlanır.
5. **İnceleme bayrağı.** Bir derste held-out balonların %80'inden azı etiketlenebildiyse veya yerel model
   kurulamayıp H'ye geri düştüyse, görüntü `REPORT.md`'de listelenir. Bu durumlar başarı sayılmaz.

### Bu protokolün sınırları (mentöre söylenecek)

- Etiketler **insan etiketli ground truth değil**; otomatik kontur tespitinden geliyor. Referans şablonu da taramadan
  otomatik çıkarıldı.
- Etiketler başlangıç H'sinin 10 px çevresinden seçildiği için çok büyük hatalar ölçüme hiç girmeyebilir.
- E2/E3'ün kontrol noktaları ile ölçüm noktaları farklı satırlar olsa da **aynı kontur dedektöründen** geliyor. Yani
  "yöntem dedektöre uyum sağlıyor" ile "yöntem gerçekten doğru" henüz ayırt edilemiyor. Bunu E4 çözecek.
- 40 tarama bağımsız 40 kağıt değil; fiziksel form kimlikleri henüz etiketlenmedi.

## Eski deneylerle ilişki

Eski E0/E1 kodu ve çıktıları silinmedi: `scripts/edge_baseline.py`, `scripts/edge_refinement.py`,
`experiments/edge_alignment/`. Git'te `archive/old-notebook-experiments` etiketiyle işaretlendi.

| Eski | Yeni |
|---|---|
| E0 (`H_all`, `H_ransac`) | E0 |
| E1'deki TPS varyantları | E1 |
| E1'deki `H_local_contours` | E2 |
| — | E3 (yeni) |

v2 kodu eski E1 mantığının birebir taşınmasıdır: 4 vitrin taramasında eski `E1-review` ile bütün yöntem ve derslerde
aynı n ve aynı medyan değerleri verdiği kontrol edildi.
