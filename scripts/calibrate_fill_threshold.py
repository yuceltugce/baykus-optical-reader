"""FILL_THRESHOLD değerini seçmek için: tüm örnek fotoğraflardaki tüm
balonların koyuluk skorlarını topla, histogramı (min/max/dağılım) yazdır.
İdeal eşik, "boş balonlar" öbeği ile "dolu balonlar" öbeği arasındaki
boşluğa denk gelmeli.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2
import numpy as np
from baykus_optik.pipeline import process_photo_file
from baykus_optik.template import COLUMNS, BUBBLE_LETTERS, bubble_center
from baykus_optik.reader import _bubble_fill_score

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"

all_scores = []
for img_path in sorted(SAMPLES.glob("*.jpg")):
    oriented = process_photo_file(str(img_path))
    gray = cv2.cvtColor(oriented, cv2.COLOR_BGR2GRAY)
    for column in COLUMNS:
        for q in range(1, column.n_questions + 1):
            for letter in BUBBLE_LETTERS:
                x, y = bubble_center(column, q, letter)
                all_scores.append(_bubble_fill_score(gray, x, y))

scores = np.array(all_scores)
print("toplam balon sayısı:", len(scores))
print("min/max:", scores.min(), scores.max())
print("percentile'lar:")
for p in [10, 25, 40, 50, 60, 70, 75, 80, 85, 90, 95, 99]:
    print(f"  p{p}: {np.percentile(scores, p):.1f}")

# basit histogram (20'lik kutular)
hist, edges = np.histogram(scores, bins=20, range=(0, 200))
for h, e0, e1 in zip(hist, edges[:-1], edges[1:]):
    print(f"{e0:5.0f}-{e1:5.0f}: {'#' * (h // 20)} ({h})")
