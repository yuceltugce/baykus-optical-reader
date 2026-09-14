"""
Aşama 1: Fotoğraftaki kağıdı (arka plandan bağımsız) bulup perspektifini düzeltme.

NEDEN BÖYLE (tasarım kararının hikayesi):
İlk denemede küçük siyah kare marker'ları (markers.py) doğrudan TÜM fotoğrafta
aramayı denedik. Kumaşlı arka planlarda (kanepe vb.) bu felaketti: kumaşın
dokusu da küçük koyu lekeler ürettiği için yüzlerce "sahte marker" bulunuyordu
ve gerçek köşeleri ayıklamak imkansız hale geliyordu.

Bunun yerine iki aşamalı bir strateji kullanıyoruz:
  1) Önce BÜYÜK ve kolay ayırt edilir bir hedefi bul: kağıdın/formun kendisi
     (bu dosya, `find_paper_quad`).
  2) Kağıt bir kez düzleştirilip arka plan devre dışı kalınca, küçük
     detayları (balonlar, marker'lar) o TEMİZ görüntü üzerinde aramak
     çok daha güvenilir hale geliyor.

Kağıdı bulmak için TEK bir yöntem yerine İKİ farklı yöntem deniyoruz, çünkü
hiçbiri tek başına her arka planda güvenilir değil:
  - Yöntem A (_find_quad_by_brightness): kağıt parlak/beyaz, arka plan koyu
    varsayımıyla çalışır. Kumaş arka planlarda genelde iyi çalışır ama tahta
    masa gibi kağıtla benzer parlaklıktaki arka planlarda kağıt+masa tek bir
    blob'a birleşip başarısız olabilir.
  - Yöntem B (_find_quad_by_black_border): formun üzerine zaten basılı olan
    KALIN SİYAH ÇERÇEVEYİ arar. Bu çerçeve her zaman siyah basıldığı için
    arka plan ne olursa olsun (tahta da olsa kumaş da olsa) güvenilir --
    tahta masa fotoğraflarında (Yöntem A'nın zayıf olduğu durum) devreye
    giren asıl kurtarıcı bu.
Her ikisinin sonucu da `_quad_is_plausible` ile "gerçekten bir kağıda benziyor
mu?" diye süzülüyor; ilk geçen kazanıyor.
"""
from __future__ import annotations

import cv2
import numpy as np


def _order_points(pts: np.ndarray) -> np.ndarray:
    """4 köşe noktasını tutarlı bir sıraya (tl, tr, br, bl) koyar.

    Bu ŞART: `cv2.getPerspectiveTransform` 4 kaynak noktayı 4 hedef noktayla
    eşleştirirken SIRAYA güveniyor, köşelerin gerçek konumuna bakmıyor. Yani
    noktaları hangi sırada verirsek, dönüşüm de "bu nokta hedefteki o köşeye
    gitsin" diye o sırayla eşleştiriyor. `cv2.findContours` / `approxPolyDP`
    köşeleri KEYFİ bir sırayla döndürür (görüntüdeki taranma sırasına göre),
    bu yüzden köşeleri kendimiz "hangisi sol-üst, hangisi sağ-üst..." diye
    etiketlememiz gerekiyor.

    Basit bir geometri hilesi kullanıyoruz:
      - x+y TOPLAMI en küçük olan nokta  -> sol-üst   (ikisi de küçük)
      - x+y TOPLAMI en büyük olan nokta  -> sağ-alt   (ikisi de büyük)
      - x-y FARKI en küçük olan nokta    -> sağ-üst   (x büyük, y küçük)
      - x-y FARKI en büyük olan nokta    -> sol-alt   (x küçük, y büyük)
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left: x+y en küçük
    rect[2] = pts[np.argmax(s)]  # bottom-right: x+y en büyük
    diff = np.diff(pts, axis=1).flatten()
    rect[1] = pts[np.argmin(diff)]  # top-right: x-y en küçük
    rect[3] = pts[np.argmax(diff)]  # bottom-left: x-y en büyük
    return rect


def _quad_is_plausible(ordered: np.ndarray, img_shape, min_frac=0.12, max_frac=0.99) -> bool:
    """Bulunan dörtgenin gerçekten kağıda benzeyip benzemediğini kontrol eder.

    Bu fonksiyon olmadan pipeline "bir şeyler buldum" deyip saçma sonuçları
    da kabul ederdi. İki basit ama etkili kontrol yapıyoruz:

    1) ALAN ORANI: dörtgenin alanı, tüm fotoğrafın makul bir kısmı olmalı
       (ne fotoğrafın tamamı -- muhtemelen arka planla karışmış bir blob --
       ne de mikroskobik küçük bir gürültü parçası).
       NOT: Kenara yakın/değen dörtgenleri BİLEREK reddetmiyoruz -- öğrenci
       kağıdı kadraja tam sığdırıp çekebilir, bu normal ve geçerli bir çekim.

    2) EN/BOY ORANI: Kağıt+arka plan karışıp tek bir kocaman blob'a
       dönüştüyse (ör. tahta masa kağıtla aynı parlaklıkta olduğunda),
       dörtgen neredeyse tüm kareyi kaplar ve şeklinin en/boy oranı A4
       benzeri bir kağıda hiç benzemez (ör. fotoğrafın kendi oranına eşit
       çıkar). Gerçek kağıt oranına ('en/boy ~1.3-1.5, veya form fotoğrafta
       90° dönük çekildiyse bunun tersi) yakın olmasını istiyoruz.
    """
    h, w = img_shape[:2]
    area = cv2.contourArea(ordered.astype(np.float32))
    frac = area / (h * w)
    if not (min_frac <= frac <= max_frac):
        return False

    # Dörtgenin 4 kenarının gerçek piksel uzunluklarını ölç (perspektif
    # nedeniyle üst/alt kenar birebir eşit olmayabilir, o yüzden ortalama
    # alıyoruz).
    tl, tr, br, bl = ordered
    top = np.linalg.norm(tr - tl)
    bottom = np.linalg.norm(br - bl)
    left = np.linalg.norm(bl - tl)
    right = np.linalg.norm(br - tr)
    width = (top + bottom) / 2
    height = (left + right) / 2
    if width < 1 or height < 1:
        return False
    ratio = max(width, height) / min(width, height)
    # Fiziksel form ~A4 oranına yakın (~1.3-1.5); fotoğraf 90 derece dönük
    # çekilmiş olabileceğinden aynı oranın tersini de (genişlik>yükseklik
    # şeklinde) kabul ediyoruz -- max/min almamızın sebebi bu. Perspektif
    # bozulması (açılı çekim) için de biraz tolerans bıraktık.
    if not (1.1 <= ratio <= 1.9):
        return False

    # Ekstra sağlık kontrolü: gerçek bir kağıdın köşeleri her zaman DIŞBÜKEY
    # (convex) bir dörtgen oluşturur. Köşe sırası karışmışsa veya tespit
    # bozuksa dörtgen "kelebek" şeklinde (self-intersecting) çıkabilir.
    if not cv2.isContourConvex(ordered.astype(np.int32).reshape(-1, 1, 2)):
        return False
    return True


def _find_quad_by_brightness(small: np.ndarray) -> np.ndarray | None:
    """Yöntem A: kağıt (parlak) / arka plan (koyu) ayrımı (Otsu eşikleme).

    Otsu eşiklemesi: sabit bir parlaklık eşiği (ör. "128'den büyükse beyaz
    say") yerine, görüntünün kendi histogramına bakıp "bu görüntü için en
    iyi eşik" değerini OTOMATİK hesaplar. Böylece farklı ışık koşullarında
    (karanlık oda, güneşli masa...) elle eşik ayarlamamıza gerek kalmıyor.
    """
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)  # JPEG/kamera gürültüsünü yumuşat
    _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Morfolojik işlemler -- ikili (0/255) maskeyi "temizlemek" için:
    #   CLOSE (önce genişlet, sonra aşındır): maskedeki küçük DELİKLERİ
    #     kapatır (ör. kağıt üzerindeki koyu yazı/çizgiler nedeniyle "beyaz"
    #     bölgede oluşan küçük siyah boşluklar).
    #   OPEN (önce aşındır, sonra genişlet): küçük GÜRÜLTÜ noktalarını siler
    #     (arka planda şans eseri parlak çıkan minik lekeler gibi).
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Maskedeki ayrık beyaz bölgelerin (contour/kontur) dış sınırlarını bul.
    # RETR_EXTERNAL: sadece en dıştaki sınırları istiyoruz, içteki delikleri
    # (ör. yazı harflerinin içi) önemsemiyoruz.
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    # En büyük alanlı kontur muhtemelen kağıdın kendisi (arka plandaki küçük
    # parlak lekelerden çok daha büyük olmalı).
    largest = max(contours, key=cv2.contourArea)
    return largest


def _find_quad_by_black_border(small: np.ndarray) -> np.ndarray | None:
    """Yöntem B: formun üzerine basılı kalın SİYAH çerçeveyi bulur.

    Arka plan ne olursa olsun (tahta, kumaş, vs.) bu çerçeve hep koyu siyah
    basıldığı için parlaklık tabanlı yöntemin başarısız olduğu durumlarda
    (arka plan kağıt kadar parlaksa, ör. açık renkli tahta masa) daha
    güvenilir çalışır.
    """
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    # Sadece çok koyu (siyah) pikselleri al: eşik değeri sabit 80 (0-255
    # skalasında) -- form baskısındaki siyah çerçeve neredeyse her zaman
    # bundan koyu, arka planlar (tahta/kumaş) genelde bundan açık.
    _, mask = cv2.threshold(blur, 80, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    # Çerçeve çizgisi ince olduğu için parçalar halinde kopuk çıkabilir;
    # CLOSE ile bu kopuklukları birleştirip tek bir bütün dörtgen elde
    # etmeye çalışıyoruz.
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    return largest


def find_paper_quad(img_bgr: np.ndarray, debug_path: str | None = None) -> np.ndarray | None:
    """Fotoğraftaki kağıdın (ya da formun basılı siyah çerçevesinin) 4 köşesini bulur.

    Dönüş: (4,2) float32 array, orijinal (tam çözünürlük) görüntü
    koordinatlarında, (tl,tr,br,bl) sıralı. Bulunamazsa None.
    """
    h, w = img_bgr.shape[:2]
    # Kontur tespiti için görüntüyü küçültüyoruz -- hem çok daha hızlı olur
    # hem de gereksiz yüksek çözünürlük kontur tespitine bir şey katmıyor
    # (sonuçta kaba bir dörtgen arıyoruz). Köşeleri bulduktan sonra `/ scale`
    # ile tekrar orijinal (tam) çözünürlüğe çeviriyoruz.
    max_dim = 1500
    scale = max_dim / max(h, w)
    small = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    ordered = None
    # Önce Yöntem B (siyah çerçeve), o başarısız/mantıksız olursa Yöntem A
    # (parlaklık) dene. Sıra önemli: siyah çerçeve arka plandan daha
    # bağımsız olduğu için önceliği ona veriyoruz.
    for finder in (_find_quad_by_black_border, _find_quad_by_brightness):
        largest = finder(small)
        if largest is None:
            continue

        # Bulduğumuz kontur genelde pürüzlü/çok noktalı bir eğri (kağıdın
        # kenarındaki küçük kıvrımlar, JPEG pikselleşmesi vb. yüzünden).
        # approxPolyDP bu eğriyi -- verilen tolerans (epsilon) içinde -- daha
        # AZ köşeli bir çokgene sadeleştirir. Gerçek bir dikdörtgen için bu
        # genelde tam 4 nokta verir.
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
        if len(approx) != 4:
            # Sadeleştirme tam 4 köşeye inmediyse (ör. çerçeve bir yerden
            # kopuk kaldığı için 5-6 köşeli çıktıysa), en iyi uyan döndürülmüş
            # dikdörtgeni (minAreaRect) yedek plan olarak kullan.
            rect = cv2.minAreaRect(largest)
            box = cv2.boxPoints(rect)
            approx = box.reshape(-1, 1, 2)

        pts_small = approx.reshape(-1, 2).astype(np.float32)
        pts_full = pts_small / scale  # küçültülmüş koordinatlardan gerçek koordinatlara
        candidate = _order_points(pts_full)
        if _quad_is_plausible(candidate, img_bgr.shape):
            ordered = candidate
            break  # bu yöntem işe yaradı, diğerini denemeye gerek yok

    if ordered is None:
        return None

    if debug_path:
        # Bulunan köşeleri ve dörtgeni orijinal fotoğrafın üzerine çizip
        # kaydediyoruz -- gözle "doğru köşeleri mi buldu?" diye kontrol
        # etmek için. Üretimde kullanılmıyor, sadece geliştirme/debug amaçlı.
        vis = img_bgr.copy()
        for i, (x, y) in enumerate(ordered):
            cv2.circle(vis, (int(x), int(y)), 20, (0, 0, 255), -1)
            cv2.putText(vis, str(i), (int(x) + 25, int(y)), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 4)
        cv2.polylines(vis, [ordered.astype(int)], True, (0, 255, 0), 4)
        disp_scale = 1400 / max(vis.shape[:2])
        vis_small = cv2.resize(vis, (int(vis.shape[1] * disp_scale), int(vis.shape[0] * disp_scale)))
        cv2.imwrite(debug_path, vis_small)

    return ordered


def warp_paper(img_bgr: np.ndarray, quad: np.ndarray, short_side: int = 1700, long_side: int = 2400) -> np.ndarray:
    """quad (tl,tr,br,bl) köşelerini kullanarak kağıdı sabit boyutlu bir
    dikdörtgene düzleştirir.

    Bu, "perspektif düzeltme"nin kendisi: fotoğrafta eğik/açılı duran
    dörtgeni, tam karşıdan çekilmiş gibi düzgün bir dikdörtgene dönüştürür.
    `cv2.getPerspectiveTransform`, 4 kaynak noktayı (quad) 4 hedef noktayla
    (dst -- hedef tuvalin tam köşeleri) eşleştiren 3x3'lük bir dönüşüm
    matrisi (homografi) hesaplıyor; `warpPerspective` de görüntünün her
    pikselini bu matrisle yeniden örnekleyip hedef tuvale "döküyor".

    NEDEN out_w/out_h SABİT DEĞİL, QUAD'IN ŞEKLİNE GÖRE SEÇİLİYOR (bug
    düzeltmesi -- önceki halinde out_w/out_h hep sabit 1700x2400'dü):
    `find_paper_quad`, köşeleri SADECE fotoğraftaki geometrik konumlarına
    (x+y toplamı en küçük -> "sol-üst" vb.) göre etiketliyor; fotoğrafın
    kendisi hangi açıyla çekilmiş olursa olsun. Yani telefon yatay tutulup
    çekildiyse, quad'ın "tl-tr kenarı" (bizim GENİŞLİK dediğimiz) aslında
    kağıdın fiziksel UZUN kenarı olabilir. Eğer bunu körü körüne sabit
    1700(dar)x2400(uzun) tuvale sıkıştırırsak, görüntü SIKIŞTIRILIP
    ESNETİLİR (yamuk/orantısız çıkar) -- perspektif matrisi bunu "sessizce"
    yapar, gözle bakınca hemen fark edilmeyebilir ama koordinatlar kayar.
    Çözüm: tuvalin boyutunu, quad'ın KENDİ ölçülen en/boy oranına göre seç
    (uzun ölçülen kenar -> long_side, kısa ölçülen kenar -> short_side).
    Böylece hiçbir zaman esnetme olmaz; sonuç bazen "dar-uzun" (1700x2400)
    bazen "geniş-kısa" (2400x1700) çıkar. Hangisi çıkarsa çıksın, bir sonraki
    adım olan `orientation.fix_orientation` içeriği doğru yöne çevirdiğinde
    (0/90/180/270), SONUÇ HER ZAMAN 1700x2400 (portre) ile biter -- çünkü
    içerik dik durması için 90 derece dönmesi gerekiyorsa, bu tam olarak
    "geniş-kısa" tuvalin "dar-uzun" tuvale dönüşmesi demektir.
    """
    tl, tr, br, bl = quad
    measured_w = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    measured_h = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2

    if measured_w >= measured_h:
        out_w, out_h = long_side, short_side  # quad kendi içinde "yatık" ölçülmüş
    else:
        out_w, out_h = short_side, long_side  # quad kendi içinde "dik" ölçülmüş

    dst = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(quad, dst)
    return cv2.warpPerspective(img_bgr, M, (out_w, out_h))
