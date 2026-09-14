"""
Yön referans kenar-haritasını (orientation reference) oluşturur.

Bunu SADECE BİR KEZ, elle doğrulanmış "kesinlikle doğru yönlü" bir
görüntüden çalıştırman yeterli -- sonuç `src/baykus_optik/orientation_reference_edges.png`
olarak kaydedilir ve repo ile birlikte taşınır (tekrar üretmen gerekmez).

Kullanım:
    python3 scripts/setup_orientation_reference.py outputs/warped_IMG_6046.jpg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cv2
from baykus_optik.orientation import save_reference_edges

if __name__ == "__main__":
    ref_path = sys.argv[1] if len(sys.argv) > 1 else "outputs/warped_IMG_6046.jpg"
    ref_img = cv2.imread(ref_path)
    if ref_img is None:
        raise SystemExit(f"Görüntü okunamadı: {ref_path}")

    save_reference_edges(ref_img)
    print("Referans kenar haritası kaydedildi: src/baykus_optik/orientation_reference_edges.png")
