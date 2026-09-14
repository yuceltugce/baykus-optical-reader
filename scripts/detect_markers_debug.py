"""Hızlı debug: örnek fotoğraflarda kare marker tespiti çalışıyor mu diye bak."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2
from baykus_optik.markers import find_square_markers, pick_corner_markers

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(exist_ok=True)

for img_path in sorted(SAMPLES.glob("*.jpg")):
    img = cv2.imread(str(img_path))
    debug_path = OUT / f"debug_{img_path.stem}.jpg"
    markers = find_square_markers(img, debug_path=str(debug_path))
    corners = pick_corner_markers(markers, img.shape)
    print(f"{img_path.name}: {len(markers)} aday marker bulundu")
    if corners:
        vis = img.copy()
        scale_disp = 1800 / max(img.shape[:2])
        for name, m in corners.items():
            cv2.circle(vis, (int(m.cx), int(m.cy)), 25, (0, 0, 255), 8)
            cv2.putText(vis, name, (int(m.cx) + 30, int(m.cy)), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
        small = cv2.resize(vis, (int(vis.shape[1] * scale_disp), int(vis.shape[0] * scale_disp)))
        cv2.imwrite(str(OUT / f"corners_{img_path.stem}.jpg"), small)
    else:
        print("  -> 4 köşe seçilemedi (marker sayısı yetersiz)")
