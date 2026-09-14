import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2
from baykus_optik.paper import find_paper_quad, warp_paper

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)

for img_path in sorted(SAMPLES.glob("*.jpg")):
    img = cv2.imread(str(img_path))
    quad = find_paper_quad(img, debug_path=str(OUT / f"quad_{img_path.stem}.jpg"))
    if quad is None:
        print(f"{img_path.name}: kağıt bulunamadı")
        continue
    warped = warp_paper(img, quad)
    cv2.imwrite(str(OUT / f"warped_{img_path.stem}.jpg"), warped)
    print(f"{img_path.name}: OK -> warped_{img_path.stem}.jpg")
