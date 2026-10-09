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
3. Compare each option with the other options OF THE SAME QUESTION (row contrast).
   The five options of a question sit within ~110 px, so a shadow, a glare spot
   or a camera that darkens empty bubbles shifts all five together; the median
   option of the question is its own "empty" level. contrast = score - median.
   The contrast of a normal mark on THIS sheet (typical_mark) is the median
   top-contrast of the answered questions (answered vs blank split by Otsu).
   An option is marked when its contrast >= ROW_ALPHA * typical_mark, so light
   pencil on a light sheet and dark pencil on a dark sheet are judged alike.
   Measured on 4 sheets photographed 141 times (iPhone) + 18 Redmi photos against
   the per-sheet majority answers (Gemini-checked): wrong answers 273 -> 58 (iPhone)
   and 159 -> 6 (Redmi). ROW_ALPHA was chosen on the iPhone set; on the Redmi set
   0.30-0.35 was also best. Estimating the paper from the gaps between bubbles
   instead of the large closing did not help once the row contrast was used.
   (Replaced: one per-sheet threshold = median + max(6 * MAD spread, 0.08). It
   missed light pencil, lost every mark outside a hard shadow and read shadowed
   empty bubbles as marked.)
   Marks below the midpoint between the threshold and a typical mark are
   reported as "weak": half-filled, very light or partly erased bubbles that a
   person should look at.
"""
import cv2
import numpy as np

SAMPLE_RADIUS = 8            # px at 2000 px height; bubble radius ~11 so the printed ring stays outside
PAPER_KERNEL = 61            # px; much larger than a bubble (22 px) so marks are closed away
PAPER_BLUR = 2               # px sigma; only smooths the blocky closing. A large blur (tried 15) smears a
                             # sharp shadow edge and makes empty bubbles next to it look dark.
ROW_ALPHA = .30              # marked: contrast >= this share of the sheet's typical mark contrast
MIN_CONTRAST = .04           # ... and never below this (a sheet with almost no marks)
SECOND_MARK = .5             # a 2nd mark counts if it is past the threshold by half of the top mark's margin
TYPICAL_MARK = .30           # typical mark contrast when the sheet has too few answered questions to measure
LIGHT_MARKS = .15            # typical mark contrast below this: very light pencil, warn
NEAR_BAND = .10              # top contrast within +-0.10 * typical_mark of the threshold counts as "near"
MAX_NEAR = .08               # more than 8% of the questions near the threshold: warn

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


def row_contrast(question_scores):
    """Darkness of every option above the median option of the same question."""
    return question_scores - np.median(question_scores)


def otsu_split(values):
    """Value that best separates a 1-D sample into two groups (max between-class variance)."""
    x = np.sort(values)
    n = np.arange(1, len(x))
    left = np.cumsum(x)[:-1] / n
    right = (x.sum() - np.cumsum(x)[:-1]) / (len(x) - n)
    i = int(np.argmax(n * (len(x) - n) * (left - right) ** 2))
    return (x[i] + x[i + 1]) / 2


def sheet_threshold(questions):
    """Row-contrast threshold of this sheet from a list of per-question score arrays.
    Returns (t, weak_below, info); t and weak_below are contrasts (see row_contrast)."""
    tops = np.array([row_contrast(s).max() for s in questions])
    answered = tops[tops > otsu_split(tops)] if len(tops) > 1 else tops
    typical_mark = float(np.median(answered)) if len(answered) >= 10 else TYPICAL_MARK
    t = max(ROW_ALPHA * typical_mark, MIN_CONTRAST)
    weak_below = (t + typical_mark) / 2
    near = int((np.abs(tops - t) < NEAR_BAND * typical_mark).sum())
    info = dict(threshold=round(t, 3), typical_empty=round(float(np.median([np.median(s) for s in questions])), 3),
                typical_mark=round(typical_mark, 3), weak_below=round(weak_below, 3),
                answered_questions=int((tops >= t).sum()), near_threshold=near)
    problems = []
    if typical_mark < LIGHT_MARKS:
        problems.append("işaretler çok açık (kalem çok hafif bastırılmış)")
    if near > MAX_NEAR * len(questions):
        problems.append(f"{near} soru dolu/boş sınırına çok yakın")
    info["problems"] = problems
    return t, weak_below, info


def decide(question_scores, t, weak_below):
    """(status, answer, weak) from row contrast. A second mark counts only if it is past t by at least
    SECOND_MARK of the top mark's margin (a faint smudge next to a real mark does not)."""
    d = row_contrast(question_scores)
    order = np.argsort(-d)
    marked = d >= t
    if not marked.any():
        return "blank", None, False
    top, second = d[order[0]], d[order[1]]
    if marked.sum() == 1 or second < t + SECOND_MARK * (top - t):
        return "single", "ABCDE"[order[0]], bool(top < weak_below)
    return "ambiguous", "".join("ABCDE"[k] for k in np.where(marked)[0]), False
