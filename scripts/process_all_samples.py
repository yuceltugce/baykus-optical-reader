"""Tüm data/samples/*.jpg dosyalarını uçtan uca pipeline'dan geçirir."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2
from baykus_optik.pipeline import process_photo_file, PaperNotFoundError

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"
OUT = Path(__file__).resolve().parents[1] / "outputs" / "final"
OUT.mkdir(parents=True, exist_ok=True)

for img_path in sorted(SAMPLES.glob("*.jpg")):
    try:
        result = process_photo_file(str(img_path))
    except PaperNotFoundError as e:
        print(f"{img_path.name}: BAŞARISIZ -- {e}")
        continue
    out_path = OUT / img_path.name
    cv2.imwrite(str(out_path), result)
    print(f"{img_path.name}: OK -> {out_path}")
