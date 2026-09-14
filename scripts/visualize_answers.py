"""Tüm pipeline'ı (fotoğraf -> kanonik görüntü -> okunan cevaplar) çalıştırıp
sonucu görsel olarak doğrulamak için işaretli/boş/belirsiz balonları
renklendirip kaydeder + özet istatistik yazdırır."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2
from baykus_optik.pipeline import process_photo_file
from baykus_optik.template import bubble_center
from baykus_optik.reader import read_all, AnswerStatus

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"
OUT = Path(__file__).resolve().parents[1] / "outputs" / "answers"
OUT.mkdir(parents=True, exist_ok=True)

for img_path in sorted(SAMPLES.glob("*.jpg")):
    oriented = process_photo_file(str(img_path))
    results = read_all(oriented)

    vis = oriented.copy()
    n_single = n_blank = n_ambig = 0
    for r in results:
        # column'u yeniden bulmamız lazım (sadece key saklı) -- görselleştirme
        # için COLUMNS listesinden eşleşeni arayalım.
        from baykus_optik.template import COLUMNS
        column = next(c for c in COLUMNS if c.key == r.column_key)

        if r.status == AnswerStatus.SINGLE:
            n_single += 1
            x, y = bubble_center(column, r.question_no, r.answer)
            cv2.circle(vis, (int(x), int(y)), 12, (0, 200, 0), 2)
        elif r.status == AnswerStatus.AMBIGUOUS:
            n_ambig += 1
            x, y = bubble_center(column, r.question_no, "C")  # sorunun ortasına işaret koy
            cv2.putText(vis, "?", (int(x) - 40, int(y) + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        else:
            n_blank += 1

    out_path = OUT / img_path.name
    cv2.imwrite(str(out_path), vis)
    print(f"{img_path.name}: tek-cevap={n_single} boş={n_blank} belirsiz={n_ambig} -> {out_path}")
