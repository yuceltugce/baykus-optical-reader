"""Şablondaki (template.py) her balonun hesaplanan konumunu referans görüntü
üzerine küçük bir daire olarak çizip kaydeder -- gözle "gerçekten balonların
ortasına denk geliyor mu?" diye doğrulamak için."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2
from baykus_optik.template import iter_bubbles

img = cv2.imread("outputs/warped_IMG_6046.jpg")
vis = img.copy()
for column, q, letter, x, y in iter_bubbles():
    color = (0, 0, 255) if letter == "A" else (0, 200, 0)
    cv2.circle(vis, (int(x), int(y)), 3, color, -1)

cv2.imwrite("outputs/template_overlay_full.jpg", vis)

# Ayrıca soru 1, 20, 40, 46 civarını yakınlaştırılmış olarak kaydet (hızlı göz kontrolü için)
for q in [1, 20, 40, 46]:
    y_center = 870.0 + (q - 1) * 21.538
    y0, y1 = int(y_center - 30), int(y_center + 30)
    crop = vis[y0:y1, 600:1300]
    crop_up = cv2.resize(crop, (crop.shape[1] * 2, crop.shape[0] * 2))
    cv2.imwrite(f"outputs/template_check_q{q}.png", crop_up)

print("kaydedildi: outputs/template_overlay_full.jpg, outputs/template_check_q*.png")
