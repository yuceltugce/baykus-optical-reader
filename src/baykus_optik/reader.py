"""
Faz 2 (devam): Her balonun DOLU mu BOŞ mu olduğuna karar verme.

Fikir çok basit: her balonun merkezinde küçük bir DAİRESEL bölge örnekleyip
("bu daire içindeki pikseller ortalama ne kadar koyu?") bir "koyuluk skoru"
hesaplıyoruz. Kurşun kalemle taranmış (işaretlenmiş) bir balonun içi koyu
gri/siyah olur, boş bir balonun içi ise sadece ince bir baskı çizgisinden
ibarettir (çoğunlukla beyaz). Sonra her SORU için 5 seçeneğin skorlarını
karşılaştırıp hangisinin (varsa) işaretli olduğuna karar veriyoruz.

Mutlak bir eşik (ör. "skor > 80 ise doluydu") yerine HEM mutlak eşik HEM DE
GÖRECELİ karşılaştırma kullanıyoruz -- çünkü:
  - Sadece mutlak eşik kullanırsak: hafif gölge/parlaklık farkı olan
    fotoğraflarda tüm satır "biraz koyu" görünüp yanlışlıkla "dolu" sayılabilir.
  - Sadece göreceli karşılaştırma kullanırsak (en koyu olanı seç): öğrenci o
    soruyu hiç işaretlememişse bile en koyu (ama aslında boş) seçeneği
    "cevap" diye seçmiş oluruz.
Bu yüzden önce mutlak eşikle "gerçekten işaretlenmiş mi" diye süzüyoruz,
SONRA görecelilikle "birden fazla işaretliyse en belirgini hangisi" diye
karar veriyoruz.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np

from .template import COLUMNS, BUBBLE_LETTERS, bubble_center, SubjectColumn


# Bir balonun içini örneklerken kullanılan dairenin yarıçapı (piksel).
# Balonun kendi çapından (~22px) küçük tutuyoruz ki komşu balonun/çizginin
# taşmasını almayalım, ama içi temsil edecek kadar da büyük olsun.
SAMPLE_RADIUS = 9

# Bir pikselin "mürekkep" (kalem izi) sayılması için parlaklık eşiği
# (0=siyah, 255=beyaz). Bunun altındaki pikseller "koyu/işaretli" sayılır.
INK_BRIGHTNESS_THRESHOLD = 170

# Bir balonun "işaretlenmiş" sayılması için gereken minimum "mürekkep yüzdesi"
# (bkz. _bubble_darkness -- 0 = balon içi tamamen boş, 100 = tamamen dolu).
#
# Bu değer keyfi seçilmedi: scripts/calibrate_fill_threshold.py ile 4 örnek
# fotoğraftaki ~3440 balonun TAMAMININ skorunu çıkarıp histogramına bakıldı.
# Dağılım son derece net bir şekilde İKİ TEPELİ (bimodal) çıktı: BOŞ balonlar
# ~%10-25 aralığında yığılıyor (sadece baskı çizgisi + harf), DOLU balonların
# BÜYÜK ÇOĞUNLUĞU ise tam %100'de (öğrenci taraması balonun tamamını
# kaplıyor). İkisi arasında (~%30-90) neredeyse hiç örnek yok -- yani eşiği
# nereye koyarsak koyalım (30 ile 90 arası) sonuç hemen hemen aynı. Ortasına
# yakın bir yer seçtik.
FILL_THRESHOLD = 50.0

# Aynı soruda iki seçenek de eşiği geçmişse ama biri diğerinden belirgin
# şekilde daha koyuysa (ör. öğrenci önce yanlış işaretleyip hafifçe silmiş),
# aradaki fark bu değerden büyükse "tek işaretli" say, değilse "çift
# işaretli / belirsiz" olarak işaretle. (0-100'lük mürekkep-yüzdesi skalasında.)
CLEAR_WINNER_MARGIN = 20.0

# Şablon koordinatı ile balonun GERÇEK merkezi arasında birkaç piksellik
# (~3-8px) fark olabiliyor -- kağıt fiziksel olarak tam düz değilse
# (hafif kıvrık/dalgalı), 4 köşeden hesaplanan tek bir düzlem dönüşümü
# (homografi) sayfanın ORTASINDAKİ küçük sapmaları tam düzeltemiyor. Bunu
# telafi etmek için tek bir noktada örneklemek yerine, tahmin edilen
# merkezin etrafında küçük bir alanı TARAYIP en yüksek skoru buluyoruz --
# yani "yakınında bir yerde koyu bir şey var mı?" diye soruyoruz, "tam
# burada mı?" diye değil. Bu, birkaç piksellik kalibrasyon hatasına karşı
# çok daha dayanıklı.
LOCAL_SEARCH_RADIUS = 8


class AnswerStatus(Enum):
    SINGLE = "single"      # tek, net bir şık işaretli
    BLANK = "blank"          # hiçbir şık işaretlenmemiş
    AMBIGUOUS = "ambiguous"  # birden fazla şık işaretli (ya da çok yakın skorlu)


@dataclass
class QuestionResult:
    column_key: str
    question_no: int
    status: AnswerStatus
    answer: str | None       # status==SINGLE ise 'A'..'E', değilse None
    scores: dict[str, float]  # her şık için ham koyuluk skoru (debug/eşik ayarı için)


def _bubble_darkness(gray: np.ndarray, x: float, y: float, radius: int = SAMPLE_RADIUS) -> float:
    """(x,y) merkezli, `radius` yarıçaplı dairesel bölgenin ne kadarının
    "mürekkep" (koyu piksel) olduğunu, YÜZDE olarak döndürür (0-100).

    İLK DENEME (artık kullanılmıyor) dairedeki piksellerin ORTALAMA
    parlaklığına bakıyordu. Bu, boş/dolu ayrımını beklenenden çok daha
    BULANIK hale getirdi: gerçekten işaretli bir balonda bile öğrencinin
    kalem taraması balonun her noktasını eşit koyulukta doldurmuyor (kenarlara
    doğru daha açık, taramanın yönüne göre çizgili/eşitsiz), bu yüzden
    ORTALAMA parlaklık, gerçekte dolu bir balonu bile "yarı koyu" gibi
    gösterip boş balonlarla arasındaki farkı küçültüyordu.

    Bunun yerine dairedeki her pikseli TEK TEK "mürekkep mi, değil mi" diye
    (bir parlaklık eşiğiyle) sınıflandırıp, mürekkep sayılan piksellerin
    ORANINI hesaplıyoruz. Bu metrik çok daha net ayrışıyor: boş bir balonda
    (sadece ince baskı çizgisi + harf) bu oran ~%15-20 çıkarken, gerçekten
    taranmış bir balonda ~%60-70'e çıkıyor -- aradaki fark, ortalama
    parlaklık yönteminden çok daha büyük ve güvenilir.
    """
    h, w = gray.shape[:2]
    xi, yi = int(round(x)), int(round(y))
    x0, x1 = max(0, xi - radius), min(w, xi + radius + 1)
    y0, y1 = max(0, yi - radius), min(h, yi + radius + 1)
    if x1 <= x0 or y1 <= y0:
        return 0.0

    patch = gray[y0:y1, x0:x1]
    # Dairesel maske: patch içindeki her pikselin (x,y) merkeze olan
    # uzaklığını hesaplayıp yarıçaptan küçük olanları seçiyoruz. Dikdörtgen
    # (kare) bir kırpma yerine bunu kullanmamızın sebebi: balonlar kare değil
    # daire, köşelerdeki alakasız pikselleri (komşu balon/çizgi parçaları)
    # hesaba katmamak istiyoruz.
    yy, xx = np.ogrid[y0:y1, x0:x1]
    mask = (xx - xi) ** 2 + (yy - yi) ** 2 <= radius ** 2
    if not mask.any():
        return 0.0

    pixels = patch[mask]
    ink_pixel_count = (pixels < INK_BRIGHTNESS_THRESHOLD).sum()
    return float(ink_pixel_count) / len(pixels) * 100.0


def _bubble_fill_score(gray: np.ndarray, x: float, y: float) -> float:
    """`_bubble_darkness`'ı tahmin edilen merkezin etrafında küçük bir alanda
    TARAYIP en yüksek skoru döndürür (bkz. LOCAL_SEARCH_RADIUS yorumu).

    2 piksellik adımlarla tarıyoruz (her pikseli değil) -- balon çapı ~22px
    olduğu için 2px'lik bir kayma sonucu neredeyse hiç değiştirmiyor, ama
    hesaplama süresini önemli ölçüde azaltıyor.
    """
    best = 0.0
    for dx in range(-LOCAL_SEARCH_RADIUS, LOCAL_SEARCH_RADIUS + 1, 2):
        for dy in range(-LOCAL_SEARCH_RADIUS, LOCAL_SEARCH_RADIUS + 1, 2):
            score = _bubble_darkness(gray, x + dx, y + dy)
            if score > best:
                best = score
    return best


def read_question(gray: np.ndarray, column: SubjectColumn, question_no: int) -> QuestionResult:
    """Tek bir sorunun 5 şıkkını okuyup hangisinin işaretli olduğuna karar verir."""
    scores = {}
    for letter in BUBBLE_LETTERS:
        x, y = bubble_center(column, question_no, letter)
        scores[letter] = _bubble_fill_score(gray, x, y)

    filled = {letter: s for letter, s in scores.items() if s >= FILL_THRESHOLD}

    if not filled:
        status, answer = AnswerStatus.BLANK, None
    elif len(filled) == 1:
        status, answer = AnswerStatus.SINGLE, next(iter(filled))
    else:
        # Birden fazla şık eşiği geçti -- aralarında AÇIK bir kazanan var mı
        # diye bak (en koyu ile ikincisi arasındaki fark yeterince büyükse
        # muhtemelen öğrenci bir şıkkı silip başka birini işaretlemiştir).
        ranked = sorted(filled.items(), key=lambda kv: kv[1], reverse=True)
        best_letter, best_score = ranked[0]
        second_score = ranked[1][1]
        if best_score - second_score >= CLEAR_WINNER_MARGIN:
            status, answer = AnswerStatus.SINGLE, best_letter
        else:
            status, answer = AnswerStatus.AMBIGUOUS, None

    return QuestionResult(column.key, question_no, status, answer, scores)


def read_all(gray_or_bgr: np.ndarray) -> list[QuestionResult]:
    """Kanonik (1700x2400) form görüntüsündeki TÜM soruları okur."""
    if gray_or_bgr.ndim == 3:
        gray = cv2.cvtColor(gray_or_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = gray_or_bgr

    results = []
    for column in COLUMNS:
        for q in range(1, column.n_questions + 1):
            results.append(read_question(gray, column, q))
    return results
