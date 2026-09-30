"""Phone photo -> aligned bubble centres (E2) -> filled / empty -> answers.

Alignment is exactly the E2 method from experiments/edge_alignment_v2
(global RANSAC homography from corner markers + per-subject TPS correction
from the printed bubble rings). Reading re-uses the idea and thresholds of
src/baykus_optik/reader.py: share of dark pixels inside a small disc.
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

SAMPLE_RADIUS = 8          # px at 2000 px height; bubble radius ~11, printed ring stays outside
INK_BRIGHTNESS = 170       # darker than this = pencil (reader.py)
FILL_THRESHOLD = 50.0      # % dark pixels to count as marked (reader.py, calibrated bimodal gap)
CLEAR_WINNER_MARGIN = 20.0
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
    H_all, H, inliers, homography_info = homography.fit_checked(src, dst)
    base = common.warp_points(H, ref["points"])
    obs, ok = common.associate(base, common.detect_bubble_contours(im))
    ok &= ref["ref_valid"]
    ctx = dict(ref_points=ref["points"], subjects=ref["subjects"], subject_names=common.SUBJECTS,
               src=src, dst=dst, H_all=H_all, H_ransac=H, inliers=inliers, base=base,
               obs=obs, ok=ok, train_rows=ref["questions"] % 5 == 1, fits={})
    centres = local_contour.predict(ctx)["H_local_contours"]
    coverage = {s: float(ok[ref["subjects"] == s].mean()) for s in common.SUBJECTS}
    return centres, dict(markers_matched=int(len(ri)), marker_inliers=int(inliers.sum()), homography=homography_info,
                         coverage=coverage, local_fit=ctx["fits"]["H_local_contours"])


def darkness(gray, centres):
    """% of pixels darker than INK_BRIGHTNESS inside a disc around each centre."""
    yy, xx = np.mgrid[-SAMPLE_RADIUS:SAMPLE_RADIUS + 1, -SAMPLE_RADIUS:SAMPLE_RADIUS + 1]
    disc = xx ** 2 + yy ** 2 <= SAMPLE_RADIUS ** 2
    out = np.zeros(len(centres))
    for i, (x, y) in enumerate(np.round(centres).astype(int)):
        patch = gray[y - SAMPLE_RADIUS:y + SAMPLE_RADIUS + 1, x - SAMPLE_RADIUS:x + SAMPLE_RADIUS + 1]
        if patch.shape == disc.shape:
            out[i] = 100.0 * (patch[disc] < INK_BRIGHTNESS).mean()
    return out


def read_answers(scores, ref):
    answers = {}
    for s in common.SUBJECTS:
        rows = []
        for q in range(1, int(ref["questions"][ref["subjects"] == s].max()) + 1):
            idx = np.where((ref["subjects"] == s) & (ref["questions"] == q))[0]
            sc = scores[idx]
            order = np.argsort(-sc)
            marked = sc >= FILL_THRESHOLD
            if not marked.any():
                status, answer = "blank", None
            elif marked.sum() == 1 or sc[order[0]] - sc[order[1]] >= CLEAR_WINNER_MARGIN:
                status, answer = "single", "ABCDE"[order[0]]
            else:
                status, answer = "ambiguous", "".join("ABCDE"[k] for k in np.where(marked)[0])
            rows.append(dict(question=q, answer=answer, status=status, scores=[round(float(v), 1) for v in sc]))
        answers[s] = rows
    return answers


def draw(im, centres, scores, ref):
    """Photo crop of the answer area: ring = where we think each bubble is, filled = read as marked."""
    out = im.copy()
    for (x, y), sc in zip(np.round(centres).astype(int), scores):
        if sc >= FILL_THRESHOLD:
            cv2.circle(out, (x, y), 10, (0, 0, 230), 3, cv2.LINE_AA)
        else:
            cv2.circle(out, (x, y), 10, (40, 170, 40), 1, cv2.LINE_AA)
    x0, y0 = np.floor(centres.min(0)).astype(int) - 40
    x1, y1 = np.ceil(centres.max(0)).astype(int) + 40
    h, w = out.shape[:2]
    return out[max(y0, 0):min(y1, h), max(x0, 0):min(x1, w)]


def process(data: bytes, filename: str):
    ref = reference()
    original = decode(data, filename)
    im = to_working(original)
    centres, diag = align(im, ref)
    scores = darkness(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), centres)
    answers = read_answers(scores, ref)
    warnings = [f"{s}: balonların sadece %{100 * c:.0f}'i otomatik doğrulanabildi" for s, c in diag["coverage"].items()
                if c < COVERAGE_WARNING]
    warnings += [f"{s}: yerel düzeltme kurulamadı, sadece global hizalama kullanıldı ({f.get('reason', '')})"
                 for s, f in diag["local_fit"].items() if f["status"] != "fitted"]
    notes = []
    h = diag["homography"]
    if h["used"] == "all_markers":
        notes.append(f"RANSAC {h['markers']} köşe işaretinden yalnızca {h['ransac_inliers']} tanesine güvendi ve "
                     f"kurduğu dönüşüm kararsızdı (koşul sayısı {h['ransac_condition']}). Bunun yerine bütün köşe "
                     "işaretleriyle hizalandı.")
    rescan = [f"{s}: balonların yalnızca %{100 * c:.0f}'i bulunabildi, hizalama güvenilir değil"
              for s, c in diag["coverage"].items() if c < COVERAGE_RESCAN]
    n_questions = sum(len(rows) for rows in answers.values())
    n_ambiguous = sum(r["status"] == "ambiguous" for rows in answers.values() for r in rows)
    if n_ambiguous > AMBIGUOUS_RESCAN * n_questions:
        rescan.append(f"{n_ambiguous} soruda birden fazla şık işaretli okundu; fotoğrafın ışığı okuma eşiğine uymuyor "
                      "olabilir (ör. çok karanlık)")
    result = dict(input_size=list(original.shape[1::-1]), diagnostics=diag, warnings=warnings, notes=notes,
                  reliable=not rescan, rescan_reasons=rescan, answers=answers,
                  summary={s: dict(marked=sum(r["status"] == "single" for r in rows),
                                   blank=sum(r["status"] == "blank" for r in rows),
                                   ambiguous=sum(r["status"] == "ambiguous" for r in rows))
                           for s, rows in answers.items()})
    return result, draw(im, centres, scores, ref), im
