"""
Aşama 1.5: Düzleştirilmiş (warped) görüntünün doğru yönde olup olmadığını
tespit etme (0/90/180/270 derece belirsizliği).

`find_paper_quad`, kağıdın 4 köşesini SADECE fotoğraftaki geometrik
konumlarına göre (x+y toplamı en küçük olan -> "sol-üst" vb.) etiketliyor.
Fiziksel kağıt fotoğrafta döndürülmüş çekilmişse (örn. telefon yatay
tutulmuşsa), bu geometrik etiketleme ile formun GERÇEK "üst-sol"ü (başlık
barının olduğu köşe) her zaman örtüşmüyor -- bu yüzden bu modül gerekiyor.

YÖNTEMİN HİKAYESİ (2 başarısız deneme + 1 başarılı, öğrenmen için):

1) İLK DENEME -- sayfanın küçük bir "resmini" (thumbnail) referansla
   karşılaştırmak: İşe yaramadı, çünkü balon ızgarası çok TEKRARLAYAN bir
   desen (yüzlerce benzer daire) ve öğrenciden öğrenciye HANGİ balonların
   dolu olduğu değişiyor -- bu iki şey bir araya gelince "genel görünüm"
   karşılaştırması çok bulanık/güvenilmez sonuç verdi.

2) İKİNCİ DENEME -- sayfanın İKİ FARKLI köşesinden (ör. "OKUL KODU" kutusu,
   "OPTİK-129" yazısı) küçük, ayırt edici birer YAMA (patch) kesip
   `matchTemplate` ile aramak: Bu daha iyiydi ama KIRILGAN çıktı -- özellikle
   fiziksel sayfa kenarına yakın kesilen yamalarda, yamanın kenarına
   kaçınılmaz olarak biraz ARKA PLAN (kumaş/tahta) bulaşıyordu. Sonuç:
   `matchTemplate`, YANLIŞ döndürmelerde bile "kağıt kenarı + arka plan"
   geçişini başka bir yerde bulup sahte-yüksek skor veriyordu. 4 örnek
   fotoğraftan hep en az biri yanlış çıkıyordu, hangi ayarı denersek deneyelim.

3) ÇALIŞAN YÖNTEM -- TÜM sayfanın KENAR HARİTASINI (edge map) karşılaştırmak:
   Balonların dolu/boş olması piksel DEĞERİNİ değiştirir ama sayfanın YAPISAL
   iskeletini (kalın çerçeveler, sütun ayraç çizgileri, tablo kenarları)
   DEĞİŞTİRMEZ -- bu çizgiler her form kopyasında birebir aynı konumda.
   `cv2.Canny` ile önce görüntüyü "bu bir kenar mı, değil mi" (0/255) ikili
   bir haritaya indirgiyoruz -- böylece hangi balonun dolu olduğu (bir iç
   detay) elenmiş oluyor, sadece sayfanın sabit YAPISI kalıyor. Bu kenar
   haritasını referansla karşılaştırmak (normalize edilmiş nokta çarpımı --
   iki ikili görüntünün ne kadar "üst üste düştüğü") hem çok daha basit HEM
   DE 4 örnek fotoğrafın tamamında doğru sonuç verdi -- artık elle
   kalibre edilmiş köşe yamalarına da gerek kalmadı.
"""
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path

_REF_PATH = Path(__file__).resolve().parent / "orientation_reference_edges.png"
_THUMB_SIZE = (170, 240)  # (genişlik, yükseklik) -- sayfa oranına yakın, küçük tutuyoruz (hız)


def _edge_thumbnail(bgr: np.ndarray) -> np.ndarray:
    """Görüntüyü küçültüp kenar haritasına (0/255 ikili) çevirir.

    Küçültme, hem hızlandırıyor hem de ince/önemsiz detayları (kağıt
    dokusu, JPEG gürültüsü) siliyor; sadece KALIN, YAPISAL çizgiler
    (çerçeveler, ayraçlar) kenar haritasında belirgin kalıyor.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, _THUMB_SIZE, interpolation=cv2.INTER_AREA)
    edges = cv2.Canny(small, 50, 150)
    return edges.astype(np.float32)


def save_reference_edges(correctly_oriented_bgr: np.ndarray) -> None:
    """Doğru yönlü bir referans görüntüden kenar haritası şablonunu çıkarıp diske kaydeder."""
    edges = _edge_thumbnail(correctly_oriented_bgr)
    cv2.imwrite(str(_REF_PATH), edges.astype(np.uint8))


def _load_reference_edges() -> np.ndarray | None:
    if not _REF_PATH.exists():
        return None
    img = cv2.imread(str(_REF_PATH), cv2.IMREAD_GRAYSCALE)
    return img.astype(np.float32)


def _edge_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """İki kenar haritasının ne kadar "üst üste düştüğünü" ölçer.

    Normalize edilmiş nokta çarpımı (cosine similarity'nin ikili
    görüntülere uyarlanmış hali): pay, iki haritada da AYNI ANDA kenar olan
    piksel sayısıyla orantılı; payda, her haritanın kendi "toplam kenar
    miktarı"na göre normalize ediyor -- böylece bir görüntüde daha FAZLA
    kenar piksel olması (ör. daha net bir fotoğraf) tek başına skoru
    şişirmiyor, gerçekten AYNI KONUMDA örtüşme önemli oluyor.
    """
    num = float((a * b).sum())
    denom = float(np.sqrt((a ** 2).sum() * (b ** 2).sum())) + 1e-6
    return num / denom


def fix_orientation(warped_bgr: np.ndarray, debug: bool = False) -> np.ndarray:
    """4 olası döndürmenin kenar haritasını referansla karşılaştırıp en iyi eşleşeni seçer.

    Referans yoksa (setup_orientation_reference.py hiç çalıştırılmamışsa)
    görüntüyü olduğu gibi döndürür.
    """
    ref_edges = _load_reference_edges()
    if ref_edges is None:
        return warped_bgr

    rotations = {
        0: warped_bgr,
        90: cv2.rotate(warped_bgr, cv2.ROTATE_90_CLOCKWISE),
        180: cv2.rotate(warped_bgr, cv2.ROTATE_180),
        270: cv2.rotate(warped_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE),
    }

    scores = {angle: _edge_similarity(_edge_thumbnail(img), ref_edges) for angle, img in rotations.items()}
    best_angle = max(scores, key=scores.get)

    if debug:
        print("edge_scores:", {a: round(s, 3) for a, s in scores.items()}, "-> chosen", best_angle)

    return rotations[best_angle]
