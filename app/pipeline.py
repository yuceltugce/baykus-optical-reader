"""Phone photo -> aligned bubble centres (E2) -> filled / empty -> answers.

Alignment is exactly the E2 method from experiments/edge_alignment_v2
(global RANSAC homography from corner markers + per-subject TPS correction
from the printed bubble rings). Reading: see reading.py (red channel, darkness
relative to the local paper, threshold from this sheet's own empty bubbles).
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

COVERAGE_WARNING = .8
COVERAGE_RESCAN = .5        # below this in any subject the alignment itself is not trusted
AMBIGUOUS_RESCAN = .10      # >10% multi-marked questions: reading threshold does not fit this photo

_REF = None


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
        raise ValueError(f"Sadece {len(ri)} köşe işareti eşleşti (en az 6 gerekli). "
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


def read_answers(scores, t, weak_below, ref):
    """Per-question decision with the sheet's own threshold (see reading.py)."""
    answers = {}
    for s in common.SUBJECTS:
        rows = []
        for q in range(1, int(ref["questions"][ref["subjects"] == s].max()) + 1):
            sc = scores[(ref["subjects"] == s) & (ref["questions"] == q)]
            status, answer, weak = reading.decide(sc, t, weak_below)
            rows.append(dict(question=q, answer=answer, status=status, weak=weak,
                             scores=[round(100 * float(v), 1) for v in sc]))
        answers[s] = rows
    return answers


def draw(im, centres, scores, t, weak_below):
    """Answer-area crop. Thin green = bubble position, thick red = marked, thick orange = weak mark."""
    out = im.copy()
    for (x, y), sc in zip(np.round(centres).astype(int), scores):
        if sc >= weak_below:
            cv2.circle(out, (x, y), 10, (0, 0, 230), 3, cv2.LINE_AA)
        elif sc >= t:
            cv2.circle(out, (x, y), 10, (0, 140, 255), 3, cv2.LINE_AA)
        else:
            cv2.circle(out, (x, y), 10, (40, 170, 40), 1, cv2.LINE_AA)
    x0, y0 = np.floor(centres.min(0)).astype(int) - 40
    x1, y1 = np.ceil(centres.max(0)).astype(int) + 40
    h, w = out.shape[:2]
    return out[max(y0, 0):min(y1, h), max(x0, 0):min(x1, w)]


def process(data: bytes, filename: str):
    return process_image(decode(data, filename))


def process_image(original):
    """Full pipeline on an already decoded BGR image (used by the server and by batch_process.py)."""
    ref = reference()
    im = to_working(original)
    centres, diag = align(im, ref)
    scores = reading.bubble_scores(im, centres)
    t, weak_below, reading_info = reading.sheet_threshold(scores)
    diag["reading"] = reading_info
    answers = read_answers(scores, t, weak_below, ref)
    warnings = [f"{s}: balonların sadece %{100 * c:.0f}'i otomatik doğrulanabildi" for s, c in diag["coverage"].items()
                if c < COVERAGE_WARNING]
    warnings += [f"{s}: yerel düzeltme kurulamadı, sadece global hizalama kullanıldı ({f.get('reason', '')})"
                 for s, f in diag["local_fit"].items() if f["status"] != "fitted"]
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
    rescan = [f"{s}: balonların yalnızca %{100 * c:.0f}'i bulunabildi, hizalama güvenilir değil"
              for s, c in diag["coverage"].items() if c < COVERAGE_RESCAN]
    n_questions = sum(len(rows) for rows in answers.values())
    n_ambiguous = sum(r["status"] == "ambiguous" for rows in answers.values() for r in rows)
    n_weak = sum(r["weak"] for rows in answers.values() for r in rows)
    if n_ambiguous > AMBIGUOUS_RESCAN * n_questions:
        rescan.append(f"{n_ambiguous} soruda birden fazla şık işaretli okundu")
    for problem in reading_info["problems"]:
        if problem.startswith("işaretli ve boş"):
            rescan.append("Okuma: " + problem)
        else:
            warnings.append("Okuma: " + problem + "; zayıf işaretleri kontrol edin")
    if n_weak:
        notes.append(f"{n_weak} soruda zayıf işaret var (çok açık, yarım ya da X ile işaretlenmiş olabilir); "
                     "resimde turuncu halkayla gösterildi.")
    result = dict(input_size=list(original.shape[1::-1]), diagnostics=diag, warnings=warnings, notes=notes,
                  reliable=not rescan, rescan_reasons=rescan, answers=answers,
                  summary={s: dict(marked=sum(r["status"] == "single" for r in rows),
                                   weak=sum(r["weak"] for r in rows),
                                   blank=sum(r["status"] == "blank" for r in rows),
                                   ambiguous=sum(r["status"] == "ambiguous" for r in rows))
                           for s, rows in answers.items()})
    return result, draw(im, centres, scores, t, weak_below), im
