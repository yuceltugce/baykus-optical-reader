"""Filled / empty decision for every bubble, robust to dark photos, shadows and light pencil.

Why not a fixed threshold (the old rule "gray < 170 is ink, >= 50% ink = marked")?
  * dark photo: the paper itself is ~170 gray, so empty bubbles look 30-65% "inked"
  * shadow: one part of the sheet is darker than the rest
  * light pencil: marks stay lighter than 170 and are missed
Three classical ideas fix this:

1. Dropout colour. The form is printed in pink/magenta. In the RED channel that
   ink is almost white, while graphite is dark in every channel, so the red
   channel keeps the pencil and drops the printed letters and rings.
2. Relative darkness. Estimate the local paper brightness everywhere (a large
   morphological closing removes all thin/small dark things, leaving paper +
   shadow), then measure each pixel as "how much darker than the paper here":
   (paper - pixel) / paper. A shadow darkens paper and pencil alike, so the
   ratio stays the same.
3. Per-sheet threshold from the EMPTY bubbles. At most one option per question
   is marked, so >= 80% of the 830 bubbles are empty and the median score is a
   reliable "typical empty bubble"; the robust spread (MAD) tells how much
   empty bubbles vary on this photo. A bubble is marked when it is clearly
   darker than that: threshold = median + max(6 * spread, 0.08).
   (A first version put the threshold midway between the empty and marked
   cluster means. That failed when one sheet has both very dark and light
   marks: the dark ones pull the marked mean up and light marks at ~0.30
   fell below a 0.36 threshold.)
   Marks only slightly above the threshold (below the midpoint between the
   threshold and a typical mark) are reported as "weak": half-filled, very
   light or partly erased bubbles that a person should look at.
"""
import cv2
import numpy as np

SAMPLE_RADIUS = 8            # px at 2000 px height; bubble radius ~11 so the printed ring stays outside
PAPER_KERNEL = 61            # px; much larger than a bubble (22 px) so marks are closed away
PAPER_BLUR = 2               # px sigma; only smooths the blocky closing. A large blur (tried 15) smears a
                             # sharp shadow edge and makes empty bubbles next to it look dark.
EMPTY_SPREADS = 6            # threshold this many robust standard deviations above the typical empty bubble
MIN_GAP = .08                # ... but at least this far above it (very clean scans have a tiny spread)
TYPICAL_MARK = .55           # darkness of a normal pencil mark when the sheet has too few marks to measure
MIN_SEPARATION = .15         # typical mark must be this much darker than a typical empty bubble
MAX_NEAR_THRESHOLD = .03     # >3% of bubbles within +-0.03 of the threshold: reading not trusted

_YY, _XX = np.mgrid[-SAMPLE_RADIUS:SAMPLE_RADIUS + 1, -SAMPLE_RADIUS:SAMPLE_RADIUS + 1]
_DISC = _XX ** 2 + _YY ** 2 <= SAMPLE_RADIUS ** 2


def relative_darkness_map(im):
    """0 = as bright as the local paper, 1 = black. Red channel, paper estimated by closing."""
    red = im[:, :, 2].astype(np.float32)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (PAPER_KERNEL, PAPER_KERNEL))
    paper = cv2.GaussianBlur(cv2.morphologyEx(red, cv2.MORPH_CLOSE, kernel), (0, 0), PAPER_BLUR)
    return np.clip((paper - red) / np.maximum(paper, 1), 0, 1)


def bubble_scores(im, centres):
    """Mean relative darkness inside a small disc around every bubble centre (0..1)."""
    rel = relative_darkness_map(im)
    out = np.zeros(len(centres))
    for i, (x, y) in enumerate(np.round(centres).astype(int)):
        patch = rel[y - SAMPLE_RADIUS:y + SAMPLE_RADIUS + 1, x - SAMPLE_RADIUS:x + SAMPLE_RADIUS + 1]
        if patch.shape == _DISC.shape:
            out[i] = float(patch[_DISC].mean())
    return out


def sheet_threshold(scores):
    """Threshold from the empty-bubble statistics of this sheet. Returns (t, weak_below, info)."""
    empty = float(np.median(scores))
    spread = 1.4826 * float(np.median(np.abs(scores - empty)))        # robust standard deviation (MAD)
    t = empty + max(EMPTY_SPREADS * spread, MIN_GAP)
    marks = scores[scores >= t]
    typical_mark = float(np.median(marks)) if len(marks) >= 10 else TYPICAL_MARK
    weak_below = (t + typical_mark) / 2
    near = int((np.abs(scores - t) < .03).sum())
    info = dict(threshold=round(t, 3), typical_empty=round(empty, 3), empty_spread=round(spread, 3),
                typical_mark=round(typical_mark, 3), weak_below=round(weak_below, 3),
                marked_bubbles=int(len(marks)), near_threshold=near)
    problems = []
    if typical_mark - empty < MIN_SEPARATION:
        problems.append("işaretli ve boş balonların koyuluğu birbirine çok yakın")
    if near > MAX_NEAR_THRESHOLD * len(scores):
        problems.append(f"{near} balon dolu/boş sınırına çok yakın")
    info["problems"] = problems
    return t, weak_below, info


def decide(question_scores, t, weak_below):
    """(status, answer, weak). A second mark only counts if it is closer to the top mark than to t."""
    order = np.argsort(-question_scores)
    marked = question_scores >= t
    if not marked.any():
        return "blank", None, False
    top, second = question_scores[order[0]], question_scores[order[1]]
    if marked.sum() == 1 or second < (t + top) / 2:
        return "single", "ABCDE"[order[0]], bool(top < weak_below)
    return "ambiguous", "".join("ABCDE"[k] for k in np.where(marked)[0]), False


def legacy_scores(im, centres, ink_brightness=170):
    """Old rule, kept only for comparison: % of gray pixels darker than 170 (0..1)."""
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    out = np.zeros(len(centres))
    for i, (x, y) in enumerate(np.round(centres).astype(int)):
        patch = gray[y - SAMPLE_RADIUS:y + SAMPLE_RADIUS + 1, x - SAMPLE_RADIUS:x + SAMPLE_RADIUS + 1]
        if patch.shape == _DISC.shape:
            out[i] = float((patch[_DISC] < ink_brightness).mean())
    return out


def legacy_decide(question_scores, fill=.5, margin=.2):
    order = np.argsort(-question_scores)
    marked = question_scores >= fill
    if not marked.any():
        return "blank", None
    if marked.sum() == 1 or question_scores[order[0]] - question_scores[order[1]] >= margin:
        return "single", "ABCDE"[order[0]]
    return "ambiguous", "".join("ABCDE"[k] for k in np.where(marked)[0])
