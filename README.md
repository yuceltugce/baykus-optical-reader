# Baykuş Optik — optik cevap formu okuyucu

Testofis "OPTİK-129" cevap kağıdını telefonla taranmış fotoğraftan okur: köşe işaretleriyle hizalar, basılı balon
halkalarıyla ince ayar yapar, her sorunun işaretli şıkkını bulur ve sonuca güvenilip güvenilmeyeceğini söyler.

## Klasörler

| Klasör | Ne var |
|---|---|
| [`app/`](app/) | **Çalışan uygulama.** Telefondan tarama gönderilen web sunucusu, okuma kodu, toplu işleme, testler. Başlangıç noktası: [`app/README.md`](app/README.md) |
| [`experiments/edge_alignment_v2/`](experiments/edge_alignment_v2/) | Hizalama yöntemleri (E0–E3) ve uygulamanın kullandığı hizalama kodu (`src/`), referans şablon (`reference/template.json`). Raporlar: [`EXPERIMENTS.md`](experiments/edge_alignment_v2/EXPERIMENTS.md) |
| `dataset/` | 41 taranmış form (düz/bükük × önden/açılı), git'te değil. `flat_front/004.png` uygulamanın **referans** görüntüsüdür. Görüntüler kodun çalıştığı boyutta (2000 px yükseklik) saklanır. |

## Hızlı başlangıç

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -B app/server.py                 # telefondan tarama: ekrandaki https adresini açın
.venv/bin/python -B app/batch_process.py <pdf/resim klasörü> <çıktı klasörü>   # toplu okuma + rapor.html
.venv/bin/python -B -m unittest discover -s app/tests
```

## Nasıl çalışıyor (kısaca)

1. **Hizalama** — köşe işaretleri (marker) bulunur, referansla eşleştirilip homography kurulur (RANSAC, halka
   sayısıyla doğrulanır); sonra her ders basılı balon halkalarına göre yerel olarak düzeltilir (TPS).
2. **Okuma** ([`app/reading.py`](app/reading.py)) — kırmızı kanal (pembe baskı kaybolur, kurşun kalır), kağıda göre
   koyuluk, her şık aynı sorunun diğer şıklarıyla karşılaştırılır (gölge ve açık kaleme dayanıklı).
3. **Güvenilirlik** — bölgesel halka kontrolü (kayma), fotoğraf dışında kalan sorular, 3+ şık işaretli sorular
   "tekrar tarayın" der; açık kalem ve sınırda kalan işaretler uyarı verir.

Saha denemeleri, ölçümler ve bilinen sınırlar: [`app/SAHA_DENEMELERI.md`](app/SAHA_DENEMELERI.md).

## Arşiv

Ana daldan kaldırılan eski çalışmalar git etiketlerinde duruyor:

- `archive/temizlik-oncesi` — temizlikten hemen önceki tam hal: kaynak PDF'ler (`Flat_front.pdf` vb.; `dataset/`
  taramalarının asıl kaynağı), eski defter (`main.ipynb`), `scripts/`, `src/`, ilk hizalama deneyleri.
- `archive/faz1-2-kagit-tespiti` — ilk yaklaşım: ham fotoğrafta kağıt tespiti, perspektif ve 0/90/180/270° yön
  düzeltme (`src/baykus_optik`).
- `archive/old-notebook-experiments` — ilk hizalama deneyleri (`experiments/edge_alignment/`).

Görmek için: `git checkout <etiket>` (geri dönmek için `git checkout main`).
