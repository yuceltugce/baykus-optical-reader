"""
[TARİHÇE / ŞU AN PIPELINE'DA KULLANILMIYOR]

Bu, projedeki İLK denemeydi: cevap kağıdı üzerindeki küçük siyah kare
referans noktalarını (registration marks) doğrudan HAM (arka planlı)
fotoğrafta aramak.

Testofis OPTİK-129 formunda köşelere ve bölüm sınırlarına basılmış dolu
siyah kareler var. Fikir: bunları bulup en dıştaki 4 tanesini (sayfanın
gerçek 4 köşesine en yakın olanlar) kullanarak perspektif düzeltmesi yapmak.

NEDEN TERK EDİLDİ: Dokulu arka planlarda (ör. kanepe kumaşı) bu yaklaşım
işe yaramadı -- kumaşın dokusu da onlarca "sahte kare" gibi görünen küçük
koyu leke üretiyor (bkz. scripts/detect_markers_debug.py çıktıları), gerçek
4 köşeyi bunların arasından ayıklamak güvenilir değildi. Yerine paper.py'daki
iki-aşamalı strateji geldi: önce BÜYÜK kağıdı bul/düzleştir (paper.py), SONRA
gerekirse küçük detayları o TEMİZ (arka plansız) görüntüde ara. Bu dosya
gelecekte "ince hizalama" (fine alignment) için hâlâ faydalı olabilir --
örn. warp_paper sonrası kalan küçük kayıklıkları düzeltmek için -- o yüzden
silmedik, ama şu anki pipeline (pipeline.py) bunu çağırmıyor.
"""
from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class Marker:
    cx: float
    cy: float
    area: float
    w: float
    h: float


def _resize_for_detection(img: np.ndarray, max_dim: int = 1800):
    h, w = img.shape[:2]
    scale = max_dim / max(h, w)
    if scale >= 1.0:
        return img, 1.0
    small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return small, scale


def find_square_markers(img_bgr: np.ndarray, debug_path: str | None = None) -> list[Marker]:
    """Görüntüdeki dolu siyah kareleri (marker adaylarını) bulur.

    Döndürülen koordinatlar ORİJİNAL (full-res) görüntü koordinat sistemindedir.
    """
    small, scale = _resize_for_detection(img_bgr)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    # Adaptif eşikleme: farklı ışık koşullarında sabit eşikten daha sağlam.
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 35, 15
    )

    # Küçük gürültüleri temizle, kareleri biraz birleştir.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    clean = cv2.morphologyEx(clean, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(clean, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    h_small, w_small = gray.shape[:2]
    img_area = h_small * w_small

    candidates: list[Marker] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < img_area * 0.00012 or area > img_area * 0.006:
            # çok küçük (gürültü) ya da çok büyük (kutu/çerçeve) olanları ele
            continue
        x, y, w, h = cv2.boundingRect(c)
        if h == 0 or w == 0:
            continue
        aspect = w / h
        if not (0.6 <= aspect <= 1.6):
            continue
        # Doluluk oranı: gerçek dolu kareler bounding box'ı büyük oranda doldurur
        fill = area / (w * h)
        if fill < 0.55:
            continue
        cx, cy = x + w / 2, y + h / 2
        candidates.append(Marker(cx / scale, cy / scale, area / (scale ** 2), w / scale, h / scale))

    if debug_path:
        vis = small.copy()
        for c in contours:
            area = cv2.contourArea(c)
            x, y, w, h = cv2.boundingRect(c)
            if area < img_area * 0.00012 or area > img_area * 0.006:
                continue
            aspect = w / h if h else 0
            fill = area / (w * h) if w and h else 0
            color = (0, 0, 255)
            if 0.6 <= aspect <= 1.6 and fill >= 0.55:
                color = (0, 255, 0)
            cv2.rectangle(vis, (x, y), (x + w, y + h), color, 2)
        cv2.imwrite(debug_path, vis)

    return candidates


def pick_corner_markers(markers: list[Marker], img_shape) -> dict[str, Marker] | None:
    """Aday marker listesinden, sayfanın 4 gerçek köşesine en yakın 4 taneyi seçer.

    Basit yaklaşım: görüntünün 4 köşesine (0,0), (W,0), (0,H), (W,H) öklid
    mesafesi en küçük olan marker'ı o köşenin markerı say.
    """
    if len(markers) < 4:
        return None
    h, w = img_shape[:2]
    corners_ref = {
        "top_left": (0, 0),
        "top_right": (w, 0),
        "bottom_left": (0, h),
        "bottom_right": (w, h),
    }
    result = {}
    for name, (rx, ry) in corners_ref.items():
        best = min(markers, key=lambda m: (m.cx - rx) ** 2 + (m.cy - ry) ** 2)
        result[name] = best
    return result
