"""
ROW1_Y / ROW_DY kalibrasyonu -- satır ARALARINDAKİ BOŞLUKLARI (gap) bularak.

Neden içerik-tepe (peak) yerine boşluk-çukur (gap/minima) kullanıyoruz:
bir satırın içindeki en koyu nokta o satırda HANGİ şıkkın işaretli olduğuna
göre kayar (yanlı), ama iki satır arasındaki boşluk öğrenci ne işaretlerse
işaretlesin hep neredeyse saf beyazdır -- çok daha güvenilir bir referans.

Bu scripti tekrar çalıştırman gerekmiyor (sonuç zaten template.py içinde
sabit olarak yazılı) -- ama form tasarımı değişirse ya da başka bir sütun/
form için aynı kalibrasyonu yapman gerekirse, yöntem burada.
"""
import cv2
import numpy as np

img = cv2.imread("outputs/warped_IMG_6046.jpg")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# TÜRKÇE sütununun 5 şıkkını da kapsayan dikey şerit (satır numarası hariç).
X0, X1 = 745, 865
Y0, Y1 = 855, 1730  # soru 1'in biraz üstünden, soru 40'ın biraz altına kadar

darkness = (255 - gray[:, X0:X1].astype(np.float64)).mean(axis=1)
y_range = np.arange(Y0, Y1)
vals = darkness[Y0:Y1]

# Yerel minimumları (satır arası boşluklar) bul: kendi 3'er piksellik
# komşuluğunda en açık (en düşük koyuluk) nokta VE mutlak olarak da
# yeterince açık (< 30) olmalı -- balonların İÇİ bile en azından bir miktar
# baskı/harf içerdiği için asla bu kadar açık olmuyor.
gaps = []
for i in range(3, len(vals) - 3):
    window = vals[i - 3:i + 4]
    if vals[i] == window.min() and vals[i] < 30:
        gaps.append(y_range[i])

# Birbirine çok yakın (aynı boşluğun birden fazla pikseli) tespitleri birleştir.
merged = []
for g in gaps:
    if merged and g - merged[-1] < 10:
        continue
    merged.append(g)
gaps = np.array(merged, dtype=float)
print(f"{len(gaps)} boşluk tespit edildi.")

# Ardışık boşluklar arası mesafenin medyanı = bir satırın dy'si (bazı
# boşluklar atlanmış olabilir, o zaman mesafe ~2x çıkar -- medyan bundan
# etkilenmez).
diffs = np.diff(gaps)
dy_estimate = np.median(diffs[diffs < 30])

# Her boşluğun "kaçıncı boşluk" olduğunu (index) dy_estimate'e göre yuvarlayarak
# bul, sonra gap(index) = a + b*index doğrusuna en küçük kareler ile fit et.
# Bu, TEK TEK iki noktaya güvenmek yerine TÜM boşlukları aynı anda kullanıp
# ölçüm gürültüsünü ortalıyor.
indices = np.round((gaps - gaps[0]) / dy_estimate).astype(int)
A = np.vstack([indices, np.ones_like(indices)]).T
b, a = np.linalg.lstsq(A, gaps, rcond=None)[0]

# gap(index) doğrusu satır ARALARINI veriyor; satır 1'in merkezi gap0 ile
# gap1'in tam ortasında (index=0.5), satır n'in merkezi index=(n-0.5)'te.
row1_y = a + b * 0.5
row_dy = b

print(f"ROW1_Y = {row1_y:.3f}")
print(f"ROW_DY = {row_dy:.3f}")
