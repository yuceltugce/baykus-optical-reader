"""Aşama 1 uçtan uca: ham telefon fotoğrafı -> düzleştirilmiş + doğru yönde
kanonik OPTİK-129 görüntüsü (1700x2400, portre).

Bu dosya sadece paper.py ve orientation.py'ı sırayla çağıran ince bir
"orkestra" katmanı -- asıl mantık o iki dosyada. Amaç: pipeline.py'ı import
eden kodun (ör. bir web sunucusu) `find_paper_quad`, `warp_paper`,
`fix_orientation` gibi iç detaylarla uğraşmadan tek bir `process_photo()`
çağrısıyla iş görebilmesi.

Bundan sonraki aşama (Faz 2): bu kanonik görüntü üzerinde sabit piksel
koordinatlarıyla tanımlı balon şablonunu kullanarak her sorunun cevabını
okumak (bkz. template.py, reader.py).
"""
from __future__ import annotations

import cv2
import numpy as np

from .paper import find_paper_quad, warp_paper
from .orientation import fix_orientation


class PaperNotFoundError(Exception):
    """find_paper_quad hiçbir yöntemle makul bir dörtgen bulamadığında
    fırlatılır (ör. fotoğrafta form hiç yoksa, ya da çok bulanık/karanlıksa).
    Çağıran taraf (ör. web sunucusu) bunu yakalayıp kullanıcıya "fotoğrafı
    tekrar çek" gibi bir mesaj gösterebilir."""
    pass


def process_photo(img_bgr: np.ndarray, debug_dir=None) -> np.ndarray:
    """Ham fotoğraftan kanonik (düzleştirilmiş + doğru yönde) form görüntüsü üretir.

    `debug_dir` verilirse (ör. "outputs/debug"), ara adımların çıktılarını
    (bulunan köşeler, düzleştirilmiş-ama-yönü-düzeltilmemiş hal, nihai hal)
    o klasöre kaydeder -- pipeline'ın hangi adımda ne yaptığını görmek için
    kullanışlı, üretimde gerekmez.
    """
    # Adım 1+2: kağıdın 4 köşesini bul, sonra sabit 1700x2400 tuvale warp et.
    quad = find_paper_quad(
        img_bgr, debug_path=f"{debug_dir}/quad.jpg" if debug_dir else None
    )
    if quad is None:
        raise PaperNotFoundError("Fotoğrafta kağıt/form bulunamadı.")
    warped = warp_paper(img_bgr, quad)

    # Adım 3: 0/90/180/270 yön belirsizliğini çöz.
    oriented = fix_orientation(warped)

    if debug_dir:
        cv2.imwrite(f"{debug_dir}/warped.jpg", warped)
        cv2.imwrite(f"{debug_dir}/oriented.jpg", oriented)

    return oriented


def process_photo_file(path: str, debug_dir=None) -> np.ndarray:
    """process_photo'nun dosya yolundan çalışan kısa yol versiyonu."""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Görüntü okunamadı: {path}")
    return process_photo(img, debug_dir=debug_dir)
