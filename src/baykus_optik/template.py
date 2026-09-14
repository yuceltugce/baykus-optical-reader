"""
Faz 2: OPTİK-129 formunun ANA CEVAP TABLOSU (TÜRKÇE / SOSYAL BİLİMLER /
TEMEL MATEMATİK / FEN BİLİMLERİ, 40+46 soru) için piksel-koordinat şablonu.

Bu koordinatlar `outputs/warped_IMG_6046.jpg` (yani `pipeline.process_photo`
çıktısı, 1700x2400 kanonik görüntü) üzerinde elle kalibre edildi. Bu form
HAZIR ALINAN, hep aynı basılı şablon olduğu için ("biz üretmiyoruz" dedin) bu
koordinatlar HER fotoğraf için aynı kalıyor -- pipeline (paper.py +
orientation.py) her fotoğrafı zaten bu SABİT 1700x2400 çerçeveye oturtuyor.

KALİBRASYON NASIL YAPILDI (öğrenmen için, ileride başka bir form için
tekrarlaman gerekirse aynı yöntemi kullanabilirsin):

1) İLK DENEME başarısız oldu: sadece 2 komşu satırı (ör. soru 1 ve soru 2)
   elle ölçüp aradaki mesafeyi (dy) tüm tabloya (40-46 satır) yaymaya
   çalıştık. Bu YANLIŞ çıktı: perspektif düzeltmesi (warp_paper) mükemmel
   değil -- gerçek kağıt tam düz değil, kamera lensi hafif distorsiyon
   katıyor -- bu yüzden sayfanın en üstünde ölçülen küçük bir hata, sayfanın
   altına doğru BİRİKEREK (kümülatif olarak) büyüyor. 2 komşu satırdan
   ölçülen dy=26px ile ekstrapolasyon yaptığımızda 40. satır GERÇEKTE
   olduğundan ~200px aşağıda çıktı.

2) İKİNCİ DENEME de tam güvenilir çıkmadı: birkaç noktayı (soru 1, soru 40
   gibi) elle, yakınlaştırılmış piksel-ızgaralı crop'larla tek tek ölçüp
   aradaki mesafeyi satır sayısına bölerek dy bulmaya çalıştık. Bu ~21.5
   gibi MAKUL bir değer verdi ama tek tek satırları kontrol ettiğimizde
   (ör. soru 12) tahmin edilen y ile gerçek balon merkezi arasında hâlâ
   ~7-8 piksellik bir fark olduğu ortaya çıktı -- elle okuma hatası, kaç
   satır uzağa bakarsak bakalım birkaç pikseli aşamıyordu.

3) ÇALIŞAN YÖNTEM -- satır ARALARINDAKİ BOŞLUKLARI (gap) otomatik bulmak:
   Bir satırın İÇİNDEKİ en koyu nokta, o satırda HANGİ şıkkın işaretli
   olduğuna göre değişir (yanlı/güvenilmez bir referans). Ama iki satır
   ARASINDAKİ boşluk her zaman neredeyse saf beyazdır -- öğrenci ne
   işaretlerse işaretlesin değişmez. Tek bir dikey şeritte (x=745-865,
   TÜRKÇE'nin 5 şıkkı) her satırın koyuluk profilini çıkarıp YEREL
   MİNİMUMLARI (en açık noktalar = satır arası boşluklar) bulduk. 40 satır
   için TAM 37 boşluk tespit edildi ve ardışık boşluklar arası mesafe hep
   ~21-22 piksel çıktı (hiç "atlanmış" boşluk yok) -- yani bu üç yöntemin
   üçü de ~21.5-21.7 piksellik bir dy'de birleşti, ama boşluk-tabanlı
   yöntem doğrusal regresyonla (bkz. scripts/calibrate_rows.py) çok daha
   hassas bir ROW1_Y ve ROW_DY verdi (soru 12'deki 7-8 piksellik hata
   ~2 piksele indi). Bu değer soru 41-46 satırlarına kadar (hiçbir özel ek
   boşluk olmadan) doğrusal olarak uzanıyor -- yani TEK BİR formülle
   (ROW1_Y + (n-1)*ROW_DY) 46 satırın hepsi doğru çıkıyor.

Soru sütunları arası (x ekseni) mesafe çok daha kısa bir aralığa yayıldığı
(sadece 5 seçenek, ~90px) için kümülatif hata sorunu yaşanmadı; her blok
için sadece "A" seçeneğinin x konumunu ölçtük, aradaki dx (~22.3px) sabit.
"""
from __future__ import annotations
from dataclasses import dataclass

BUBBLE_LETTERS = ["A", "B", "C", "D", "E"]

# --- Satır (soru) geometrisi: TÜM sütunlarda ORTAK, çünkü aynı fiziksel
# satırlar tüm 4 ders sütununda yan yana basılı. ---
ROW1_Y = 863.22     # soru 1'in balon merkezlerinin y konumu
ROW_DY = 21.657     # iki soru arası dikey mesafe (bkz. yukarıdaki kalibrasyon notu; scripts/calibrate_rows.py)

# --- Sütun (ders bloğu) geometrisi ---
# Her blok kendi "A" seçeneğinin x konumuyla tanımlı; blok içindeki B/C/D/E
# bu x'ten +dx, +2dx, ... ile hesaplanıyor. n_questions: bazı bloklarda
# (SOSYAL BİLİMLER-2, FEN BİLİMLERİ) AYT oturumunda 46 soruya kadar çıkıyor,
# TÜRKÇE ve MATEMATİK her zaman 40'ta kalıyor.
COL_DX = 22.4


@dataclass(frozen=True)
class SubjectColumn:
    key: str            # kod içinde kullanılacak kısa isim
    tyt_label: str       # 1.OTURUM (TYT) başlığı
    ayt_label: str       # 2.OTURUM (AYT) başlığı -- aynı fiziksel balonlar, farklı anlam
    x_a: float            # bu bloktaki "A" seçeneğinin x konumu
    n_questions: int      # bu blokta kaç soru satırı var (40 ya da 46)


COLUMNS: list[SubjectColumn] = [
    SubjectColumn("turkce", "TÜRKÇE", "TÜRK DİLİ VE EDEBİYATI-SOSYAL BİLİMLER-1", x_a=760.0, n_questions=40),
    SubjectColumn("sosyal", "SOSYAL BİLİMLER", "SOSYAL BİLİMLER-2", x_a=894.0, n_questions=46),
    SubjectColumn("matematik", "TEMEL MATEMATİK", "MATEMATİK", x_a=1020.0, n_questions=40),
    SubjectColumn("fen", "FEN BİLİMLERİ", "FEN BİLİMLERİ", x_a=1152.0, n_questions=46),
]


def bubble_center(column: SubjectColumn, question_no: int, letter: str) -> tuple[float, float]:
    """1-indeksli soru numarası + şık harfinden (A-E) o balonun (x,y)
    piksel merkezini hesaplar (1700x2400 kanonik görüntü koordinatlarında)."""
    row_index = question_no - 1
    y = ROW1_Y + row_index * ROW_DY
    col_index = BUBBLE_LETTERS.index(letter)
    x = column.x_a + col_index * COL_DX
    return x, y


def iter_bubbles():
    """Şablondaki HER balonu (column, question_no, letter, x, y) olarak sırayla verir.
    Kalibrasyonu doğrulamak (görselleştirmek) veya tüm balonları taramak için kullanışlı."""
    for column in COLUMNS:
        for q in range(1, column.n_questions + 1):
            for letter in BUBBLE_LETTERS:
                x, y = bubble_center(column, q, letter)
                yield column, q, letter, x, y
