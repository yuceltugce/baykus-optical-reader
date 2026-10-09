"""Phone photo -> aligned bubble centres (E2) -> filled / empty -> answers.

Alignment is exactly the E2 method from experiments/edge_alignment_v2
(global RANSAC homography from corner markers + per-subject TPS correction
from the printed bubble rings). Reading: see reading.py (red channel, darkness
relative to the local paper, each option compared with the other options of its question).
"""
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "experiments" / "edge_alignment_v2"
sys.path[:0] = [str(V2), str(V2 / "src")]

from run_experiment import prepare_reference  # noqa: E402
from src import common, homography, local_contour  # noqa: E402

import reading  # noqa: E402

SUBJECT_NAMES = {"turkce": "Türkçe", "sosyal": "Sosyal", "matematik": "Matematik", "fen": "Fen"}
AMBIGUOUS_RESCAN = .10      # >10% multi-marked questions: reading threshold does not fit this photo

# Final-position check. After alignment every bubble should sit on its printed ring. Per region (subject x 10
# questions) we count bubbles whose nearest detected ring is 5-14 px away ("offset": real misalignment) and
# bubbles with no ring within 14 px ("unseen": faint print, nothing to verify against). On 149 phone scans the
# worst region of the 144 pages judged well aligned by eye had at most 6.7 % offset bubbles, the 5 pages with
# visible shifts had 16-66 %; 12 % sits between (small margin, re-check on new data). An earlier, subject-wide
# check before the local correction missed a shifted Fen bottom (Batch6 s11) and raised false alarms.
ON_RING_PX = 5              # reading disc radius is 8 px; beyond ~5 px the disc starts to leave the bubble
OFFSET_MAX_PX = 14          # half the bubble spacing: farther rings belong to a neighbour
REGION_ROWS = 10
OFFSET_RESCAN = .12         # >= this share of offset bubbles in any region: alignment not trusted
UNSEEN_WARNING = .5         # >= this share of unseen bubbles in a region: alignment could not be verified
EDGE_MARGIN_PX = 13         # bubble radius (~11) + 2: a bubble closer to the image border is not fully visible

_REF = None


class MarkersNotFound(ValueError):
    """Too few corner markers: the photo cannot be aligned (cut off, upside down, too dark)."""


def reference():
    global _REF
    if _REF is None:
        _REF = prepare_reference()
    return _REF


def decode(data: bytes, filename: str):
    """JPEG/PNG bytes or a PDF (first page, e.g. iPhone document scanner) -> BGR image."""
    if data[:4] == b"%PDF" or filename.lower().endswith(".pdf"):
        import pymupdf
        page = pymupdf.open(stream=data, filetype="pdf")[0]
        zoom = 4000 / page.rect.height          # plenty above the 2000 px working height
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csRGB)
        rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        raise ValueError("Dosya okunamadı (JPEG, PNG veya PDF gönderin).")
    return im


def to_working(im):
    h, w = im.shape[:2]
    return cv2.resize(im, (round(w * common.WORKING_HEIGHT / h), common.WORKING_HEIGHT), interpolation=cv2.INTER_AREA)


def align(im, ref):
    """E2: returns bubble centres in photo coordinates + diagnostics."""
    markers = common.detect_markers(im)
    ri, ci = common.match_markers(ref["markers"], ref["image"].shape, markers, im.shape)
    if len(ri) < 6:
        raise MarkersNotFound(f"Sadece {len(ri)} köşe işareti eşleşti (en az 6 gerekli). "
                              "Formun tamamı görünüyor mu, doğru yönde mi?")
    src, dst = ref["markers"][ri].astype(float), markers[ci].astype(float)
    H_all, H, inliers, homography_info, obs, ok = homography.fit_verified(
        src, dst, im, ref["points"], ref["ref_valid"])
    base = common.warp_points(H, ref["points"])
    ctx = dict(ref_points=ref["points"], subjects=ref["subjects"], subject_names=common.SUBJECTS,
               src=src, dst=dst, H_all=H_all, H_ransac=H, inliers=inliers, base=base,
               obs=obs, ok=ok, train_rows=common.anchor_rows(ref["subjects"], ref["questions"]), fits={})
    centres = local_contour.predict(ctx)["H_local_contours"]
    coverage = {s: float(ok[ref["subjects"] == s].mean()) for s in common.SUBJECTS}
    return centres, dict(markers_matched=int(len(ri)), marker_inliers=int(inliers.sum()), homography=homography_info,
                         coverage=coverage, local_fit=ctx["fits"]["H_local_contours"])


def visible_bubbles(centres, shape):
    """False for bubbles not fully inside the photo (e.g. the scanner app cut off the bottom of the sheet)."""
    h, w = shape[:2]
    m = EDGE_MARGIN_PX
    return (centres[:, 0] >= m) & (centres[:, 1] >= m) & (centres[:, 0] < w - m) & (centres[:, 1] < h - m)


def final_position_check(im, centres, ref, visible):
    """Per (subject, 10-question region): share of bubbles on / offset from / without a printed ring."""
    lo, hi = centres.min(0) - 30, centres.max(0) + 30
    rings = common.detect_bubble_contours(im, np.array([lo, [hi[0], lo[1]], hi, [lo[0], hi[1]]]))
    if len(rings):
        nearest = np.linalg.norm(centres[:, None] - rings[None], axis=2).min(1)
    else:
        nearest = np.full(len(centres), np.inf)
    on, offset = nearest <= ON_RING_PX, (nearest > ON_RING_PX) & (nearest <= OFFSET_MAX_PX)
    usable = visible & ref["ref_valid"]
    region = (ref["questions"] - 1) // REGION_ROWS
    regions, per_subject = [], {}
    for s in common.SUBJECTS:
        sel_s = (ref["subjects"] == s) & usable
        per_subject[s] = round(float(on[sel_s].mean()), 3) if sel_s.any() else None
        for r in np.unique(region[ref["subjects"] == s]):
            sel = sel_s & (region == r)
            if sel.any():
                q = ref["questions"][(ref["subjects"] == s) & (region == r)]
                regions.append(dict(subject=s, first=int(q.min()), last=int(q.max()), n=int(sel.sum()),
                                    on=round(float(on[sel].mean()), 3), offset=round(float(offset[sel].mean()), 3),
                                    unseen=round(float((~on[sel] & ~offset[sel]).mean()), 3)))
    return per_subject, regions


def question_groups(ref, visible):
    """[(subject, question, bubble indices A..E)] for every question, and the subset fully inside the photo."""
    groups = [(s, q, np.where((ref["subjects"] == s) & (ref["questions"] == q))[0])
              for s in common.SUBJECTS for q in range(1, int(ref["questions"][ref["subjects"] == s].max()) + 1)]
    return groups, [g for g in groups if visible[g[2]].all()]


def contrasts(scores, groups):
    """Per-bubble row contrast (darkness above the median option of its own question)."""
    out = np.zeros_like(scores)
    for _, _, idx in groups:
        out[idx] = reading.row_contrast(scores[idx])
    return out


def read_answers(scores, t, weak_below, ref, visible):
    """Per-question decision with the sheet's own row-contrast threshold (see reading.py)."""
    answers = {}
    for s in common.SUBJECTS:
        rows = []
        for q in range(1, int(ref["questions"][ref["subjects"] == s].max()) + 1):
            sel = (ref["subjects"] == s) & (ref["questions"] == q)
            sc = scores[sel]
            if not visible[sel].all():
                rows.append(dict(question=q, answer=None, status="invisible", weak=False,
                                 scores=[round(100 * float(v), 1) for v in sc]))
                continue
            status, answer, weak = reading.decide(sc, t, weak_below)
            rows.append(dict(question=q, answer=answer, status=status, weak=weak,
                             scores=[round(100 * float(v), 1) for v in sc]))
        answers[s] = rows
    return answers


def draw(im, centres, contrast, t, weak_below):
    """Answer-area crop and its top-left corner in the photo.
    Thin green = bubble position, thick red = marked, thick orange = weak mark."""
    out = im.copy()
    for (x, y), sc in zip(np.round(centres).astype(int), contrast):
        if sc >= weak_below:
            cv2.circle(out, (x, y), 10, (0, 0, 230), 3, cv2.LINE_AA)
        elif sc >= t:
            cv2.circle(out, (x, y), 10, (0, 140, 255), 3, cv2.LINE_AA)
        else:
            cv2.circle(out, (x, y), 10, (40, 170, 40), 1, cv2.LINE_AA)
    h, w = out.shape[:2]
    x0, y0 = np.maximum(np.floor(centres.min(0)).astype(int) - 40, 0)
    x1, y1 = np.ceil(centres.max(0)).astype(int) + 40
    return out[y0:min(y1, h), x0:min(x1, w)], (int(x0), int(y0))


# Messages for the student. Technical reasons stay in rescan_reasons / warnings (batch reports, saved results).
RETAKE_TEXT = {
    "alignment": "Formun bir bölgesi düzgün hizalanamadı. Kağıt bükülmüş ya da bir köşesi kalkık olabilir. "
                 "Kağıdı düz bir masaya koyup tekrar tara.",
    "cut": "Formun bir kısmı fotoğrafın dışında kalmış. Formun dört köşesi de görünecek şekilde tekrar tara.",
    "shadow": "Fotoğrafta gölge ya da parlama var gibi görünüyor. Formu gölgesiz, eşit ışıkta tekrar tara.",
    "markers": "Formun köşe işaretleri bulunamadı. Formun tamamı görünsün ve form düz (ters değil) dursun; "
               "sonra tekrar tara.",
}


def confirm_list(answers, centres, ref, shape):
    """Questions the student should confirm: weak single marks and multiple marks.
    box = the question's row (number + 5 bubbles) in working-photo coordinates; the crop is taken from the
    photo without our circles so the student sees the pencil mark itself."""
    out = []
    h, w = shape[:2]
    for s, rows in answers.items():
        for r in rows:
            if not (r["weak"] or r["status"] == "ambiguous"):
                continue
            c = centres[(ref["subjects"] == s) & (ref["questions"] == r["question"])]
            x0, y0 = np.floor(c.min(0) - [45, 18]).astype(int)
            x1, y1 = np.ceil(c.max(0) + [18, 18]).astype(int)
            out.append(dict(subject=s, question=r["question"], reason="multiple" if r["status"] == "ambiguous" else "weak",
                            suggested=r["answer"], box=[max(int(x0), 0), max(int(y0), 0), min(int(x1), w), min(int(y1), h)]))
    return out


def process(data: bytes, filename: str):
    return process_image(decode(data, filename))


def process_image(original):
    """Full pipeline on an already decoded BGR image (used by the server and by batch_process.py)."""
    ref = reference()
    im = to_working(original)
    centres, diag = align(im, ref)
    visible = visible_bubbles(centres, im.shape)
    scores = reading.bubble_scores(im, centres)
    groups, readable = question_groups(ref, visible)
    t, weak_below, reading_info = reading.sheet_threshold([scores[idx] for _, _, idx in readable])
    diag["reading"] = reading_info
    answers = read_answers(scores, t, weak_below, ref, visible)
    diag["verified"], diag["regions"] = final_position_check(im, centres, ref, visible)
    warnings = [f"{s}: yerel düzeltme kurulamadı, sadece global hizalama kullanıldı ({f.get('reason', '')})"
                for s, f in diag["local_fit"].items() if f["status"] != "fitted"]
    unverified = [SUBJECT_NAMES[s] for s, f in diag["local_fit"].items() if f["status"] != "fitted"]
    rescan, retake = [], []          # technical reasons / student-facing reason codes (see RETAKE_TEXT)
    for r in diag["regions"]:
        where = f"{r['subject']} {r['first']}-{r['last']}. sorular"
        if r["offset"] >= OFFSET_RESCAN:
            rescan.append(f"{where}: balonların %{100 * r['offset']:.0f}'i basılı halkasından {ON_RING_PX}-"
                          f"{OFFSET_MAX_PX} px kaymış, hizalama güvenilir değil")
            retake.append("alignment")
        elif r["unseen"] >= UNSEEN_WARNING:
            warnings.append(f"{where}: balonların %{100 * r['unseen']:.0f}'inde basılı halka görülemedi "
                            "(soluk baskı?), hizalama doğrulanamadı")
            unverified.append(f"{SUBJECT_NAMES[r['subject']]} {r['first']}-{r['last']}")
    n_invisible = sum(r["status"] == "invisible" for rows in answers.values() for r in rows)
    if n_invisible:
        rescan.append(f"{n_invisible} soru fotoğrafın dışında kalıyor (sayfa kırpılmış olabilir); bu sorular "
                      "\"görünmüyor\" olarak işaretlendi")
        retake.append("cut")
    notes = []
    h = diag["homography"]
    if h["used"] == "all_markers" and "rings_ransac" in h:
        notes.append(f"RANSAC'ın seçtiği {h['ransac_inliers']} köşe işaretiyle kurulan hizalama {h['rings_ransac']} "
                     f"balonu basılı halkasına oturttu, bütün köşe işaretleriyle kurulan {h['rings_all_markers']} "
                     "balonu. Daha iyi oturan ikincisi kullanıldı.")
    elif h["used"] == "all_markers":
        notes.append(f"RANSAC {h['markers']} köşe işaretinden yalnızca {h['ransac_inliers']} tanesine güvendi ve "
                     f"kurduğu dönüşüm kararsızdı (koşul sayısı {h['ransac_condition']}). Bunun yerine bütün köşe "
                     "işaretleriyle hizalandı.")
    n_questions = sum(len(rows) for rows in answers.values())
    n_ambiguous = sum(r["status"] == "ambiguous" for rows in answers.values() for r in rows)
    n_weak = sum(r["weak"] for rows in answers.values() for r in rows)
    n_three = sum(r["status"] == "ambiguous" and len(r["answer"]) >= 3 for rows in answers.values() for r in rows)
    if n_ambiguous > AMBIGUOUS_RESCAN * n_questions:
        rescan.append(f"{n_ambiguous} soruda birden fazla şık işaretli okundu")
        retake.append("shadow")
    elif n_three:
        rescan.append(f"{n_three} soruda 3 ya da daha fazla şık işaretli okundu (gölge ya da leke olabilir)")
        retake.append("shadow")
    for problem in reading_info["problems"]:     # light pencil stays light on a new photo: warn, do not ask to rescan
        warnings.append("Okuma: " + problem + "; turuncu (zayıf) işaretleri kontrol edin")
    if n_weak:
        notes.append(f"{n_weak} soruda zayıf işaret var (çok açık, yarım ya da X ile işaretlenmiş olabilir); "
                     "resimde turuncu halkayla gösterildi.")
    # Problems a new photo would not fix: shown with the result, in the student's words.
    issues = []
    if reading_info["typical_mark"] < reading.LIGHT_MARKS:
        issues.append("Kalem işaretleri çok açık. Okuma yapıldı ama bazı işaretler belirsiz kalmış olabilir; "
                      "bir dahaki sefere kalemle daha koyu doldur.")
    if unverified:
        issues.append("Formun şu bölgelerinde basılı halkalar soluk olduğu için yerleşim doğrulanamadı: "
                      + ", ".join(unverified) + ". İşaretli fotoğrafta yeşil halkaların balonların üstünde "
                      "durduğunu kontrol et.")
    result = dict(input_size=list(original.shape[1::-1]), diagnostics=diag, warnings=warnings, notes=notes,
                  reliable=not rescan, rescan_reasons=rescan, answers=answers,
                  retake=[RETAKE_TEXT[c] for c in dict.fromkeys(retake)], issues=issues,
                  summary={s: dict(marked=sum(r["status"] == "single" for r in rows),
                                   weak=sum(r["weak"] for r in rows),
                                   blank=sum(r["status"] == "blank" for r in rows),
                                   ambiguous=sum(r["status"] == "ambiguous" for r in rows),
                                   invisible=sum(r["status"] == "invisible" for r in rows))
                           for s, rows in answers.items()})
    contrast = contrasts(scores, groups)
    overlay, _ = draw(im, centres[visible], contrast[visible], t, weak_below)
    result["confirm"] = confirm_list(answers, centres, ref, im.shape)
    return result, overlay, im
