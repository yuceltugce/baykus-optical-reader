"""Shared image, marker and bubble utilities used by every experiment.

Everything here is copied (behaviour-for-behaviour) from the archived
scripts/edge_baseline.py (E0) and scripts/edge_refinement.py (E1) so that the
v2 numbers are directly comparable to the archived runs.
"""
from pathlib import Path
import hashlib
import json

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

WORKING_HEIGHT = 2000
SUBJECTS = ["turkce", "sosyal", "matematik", "fen"]
GROUPS = ["flat_front", "flat_angled", "curved_front", "curved_angled"]


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_image(path):
    """Read an image and resize it so its height is WORKING_HEIGHT px."""
    im = cv2.imread(str(path))
    if im is None:
        raise ValueError(f"Cannot read {path}")
    h, w = im.shape[:2]
    scale = WORKING_HEIGHT / h
    return cv2.resize(im, (round(w * scale), WORKING_HEIGHT), interpolation=cv2.INTER_AREA)


def save_image(path, im):
    if not cv2.imwrite(str(path), im):
        raise IOError(path)


def load_template(path):
    """Reference bubble centres (frozen copy of the E1 repaired template)."""
    t = json.loads(Path(path).read_text())
    bubbles = t["bubbles"]
    points = np.array([[b["x"], b["y"]] for b in bubbles], dtype=np.float64)
    subjects = np.array([b["subject"] for b in bubbles])
    questions = np.array([b["question"] for b in bubbles])
    return bubbles, points, subjects, questions


# --------------------------------------------------------------------------
# Corner markers (black squares)
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Lighting-independent input for the detectors
# --------------------------------------------------------------------------
# The iPhone document scanner brightens white-background pages so much that black markers come out light
# grey (darkest pixels 140-166 instead of 85-118) and pink rings very faint. Fixed grey thresholds then
# find nothing. With ADAPTIVE the detectors work on a "paper-flattened" channel instead: each pixel divided
# by the local paper brightness (large morphological closing), so paper is 255 everywhere and a mark keeps
# its contrast to the paper around it, whatever the exposure or shadow. Set ADAPTIVE = False for the old,
# fixed-threshold behaviour (used for before/after comparisons).
ADAPTIVE = True
PAPER_KERNEL = 61                 # px; larger than a marker (~22 px) and a bubble, so both are closed away
MARKER_DARKNESS_SHARE = .5        # marker threshold = this share of the page's darkest relative darkness
MARKER_DARKNESS_LIMITS = (.18, .35)
RING_THRESHOLDS = [140, 165, 185, 205, 225]   # on the paper-flattened green channel (pink absorbs green)


# Rows whose bubbles may be used as control points of the local (E2) correction. Every 5th row (1, 6, 11,
# ...) as before; with ANCHOR_LAST_ROW also the last row of each subject. Türkçe/Matematik/Fen have 40
# questions, so their last control row used to be 36 and the TPS had to extrapolate over 37-40: on 149 phone
# scans the error there was about twice the mid-block error (Fen 0.66 vs 0.32 px, worst page 6.7 px), while
# Sosyal - whose rows 41 and 46 are control rows - showed no increase (0.26 vs 0.29 px).
ANCHOR_LAST_ROW = True


def anchor_rows(subjects, questions):
    rows = questions % 5 == 1
    if ANCHOR_LAST_ROW:
        for s in np.unique(subjects):
            sel = subjects == s
            rows |= sel & (questions == questions[sel].max())
    return rows


def paper_flattened(channel):
    """uint8 image with the local paper brightness divided out (paper -> 255)."""
    ch = channel.astype(np.float32)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (PAPER_KERNEL, PAPER_KERNEL))
    paper = cv2.GaussianBlur(cv2.morphologyEx(ch, cv2.MORPH_CLOSE, kernel), (0, 0), 2)
    return np.clip(ch / np.maximum(paper, 1) * 255, 0, 255).astype(np.uint8)


# Marker detection / matching method (experiment/marker-relative-size).
#   "base":     darkness threshold tied to the page's darkest pixels; matching on image-size-normalised
#               coordinates. A black table in the photo becomes the "darkest thing", tightens the threshold, and
#               a faintly printed marker (bottom-right on some sheets, ~40 % darker than paper instead of ~65 %)
#               loses its edges and fails the fill test.
#   "relative": a marker only has to be RELATIVE_DARKNESS darker than the paper around it; false candidates are
#               removed by size instead: all markers are printed the same size, so candidates far from the common
#               marker size are dropped.
#   "relative_ref": as "relative", but the marker size is taken from the reference sheet (EXPECTED_MARKER_SIDE,
#               set once when the reference is prepared) instead of "the size most candidates share": with the
#               loose threshold, small square blobs (~14 px: form boxes, pencil) can outnumber the ~10 real
#               markers (~24 px) and win that vote (Batch1 s07: 1 of 10 markers left). Only the size is used,
#               never an expected position.
MARKER_METHOD = "base"
EXPECTED_MARKER_SIDE = None
#   "image":  match on coordinates divided by the image size (crop-dependent).
#   "marker": match in units of the mean marker size, after finding the offset by voting (crop-independent).
MATCH_METHOD = "image"
RELATIVE_DARKNESS = .20           # "relative": candidate must be >= 20 % darker than the local paper
SIZE_TOLERANCE = .30              # "relative": keep candidates whose side is within +-30 % of the common side


def _marker_candidates(im, mask):
    """Square-ish, solid blobs of the mask: [(centre, side, extent)]."""
    out = []
    for c in cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]:
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        extent = area / (w * h)
        if not 0.00003 <= area / (im.shape[0] * im.shape[1]) <= 0.0008:
            continue
        if not 0.6 <= w / h <= 1.6 or extent < 0.82:
            continue
        if len(cv2.approxPolyDP(c, 0.03 * cv2.arcLength(c, True), True)) > 6:
            continue
        out.append((np.array([x + w / 2, y + h / 2]), float(np.sqrt(area)), extent))
    return out


def _common_side(sides):
    """The side length most candidates agree on (+-SIZE_TOLERANCE); robust to a few odd-sized blobs."""
    sides = np.asarray(sides)
    support = [((sides >= s * (1 - SIZE_TOLERANCE)) & (sides <= s * (1 + SIZE_TOLERANCE))).sum() for s in sides]
    best = sides[np.asarray(support) == max(support)]
    return float(np.median(best))


def detect_markers_sized(im):
    """Corner markers: (centres N x 2, side lengths N). Threshold -> opening -> square-ish, solid, isolated."""
    flat = cv2.GaussianBlur(paper_flattened(im[:, :, 2]), (3, 3), 0) if ADAPTIVE else None
    if ADAPTIVE and MARKER_METHOD in ("relative", "relative_ref"):
        t = 255 * (1 - RELATIVE_DARKNESS)
        mask = cv2.threshold(flat, t, 255, cv2.THRESH_BINARY_INV)[1]
    elif ADAPTIVE:
        # Black markers stay dark in the red channel, where the pink print is weakest.
        darkest = 1 - np.percentile(flat, .1) / 255            # relative darkness of the darkest 0.1 %
        lo, hi = MARKER_DARKNESS_LIMITS
        t = 255 * (1 - np.clip(MARKER_DARKNESS_SHARE * darkest, lo, hi))
        mask = cv2.threshold(flat, t, 255, cv2.THRESH_BINARY_INV)[1]
    else:
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        mask = cv2.threshold(cv2.GaussianBlur(gray, (3, 3), 0), 140, 255, cv2.THRESH_BINARY_INV)[1]
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    candidates = _marker_candidates(im, mask)
    if MARKER_METHOD in ("relative", "relative_ref") and candidates:
        sides = np.array([s for _, s, _ in candidates])
        if MARKER_METHOD == "relative_ref" and EXPECTED_MARKER_SIDE:
            near = sides[(sides >= .6 * EXPECTED_MARKER_SIDE) & (sides <= 1.5 * EXPECTED_MARKER_SIDE)]
            side = float(np.median(near)) if len(near) else EXPECTED_MARKER_SIDE
        else:
            side = _common_side(sides)
        candidates = [c for c in candidates if abs(c[1] - side) <= SIZE_TOLERANCE * side]
    dedup = []
    for p, s, e in sorted(candidates, key=lambda z: -z[2]):
        if all(np.linalg.norm(p - q) > 15 for q, _ in dedup):
            dedup.append((p, s))
    isolated = [(p, s) for i, (p, s) in enumerate(dedup)
                if all(i == j or np.linalg.norm(p - q) >= 60 for j, (q, _) in enumerate(dedup))]
    isolated.sort(key=lambda z: (z[0][1], z[0][0]))
    centres = np.array([p for p, _ in isolated], dtype=np.float32).reshape(-1, 2)
    return centres, np.array([s for _, s in isolated], dtype=np.float32)


def detect_markers(im):
    return detect_markers_sized(im)[0]


def match_markers(ref_markers, ref_shape, markers, shape, gate=0.06, ref_sides=None, sides=None):
    """Hungarian matching of photo markers to reference markers. Returns (ref_idx, sample_idx)."""
    if MATCH_METHOD == "marker" and ref_sides is not None and sides is not None and len(markers) >= 3:
        return _match_in_marker_units(ref_markers, ref_sides, markers, sides)
    a = ref_markers / np.array(ref_shape[1::-1])
    b = markers / np.array(shape[1::-1])
    cost = np.linalg.norm(a[:, None] - b[None], axis=2)
    ri, ci = linear_sum_assignment(cost)
    keep = cost[ri, ci] < gate
    return ri[keep], ci[keep]


def _match_in_marker_units(ref_markers, ref_sides, markers, sides, vote_gate=4.0, gate=1.5):
    """Crop-independent matching. Scale = photo marker size / reference marker size; offset by voting (every
    reference/photo pair proposes an offset, the one most other markers agree with wins); then an affine fit on
    the agreed pairs absorbs small rotation/perspective, and the final Hungarian gate is `gate` marker sides."""
    unit = float(np.median(ref_sides))
    scale = float(np.median(sides)) / unit
    p = markers / scale                                         # photo markers in reference pixels
    best = None
    for i in range(len(ref_markers)):
        for j in range(len(p)):
            off = p[j] - ref_markers[i]
            d = np.linalg.norm((p - off)[None] - ref_markers[:, None], axis=2).min(1) / unit
            score = ((d < vote_gate).sum(), -np.minimum(d, vote_gate).sum())
            if best is None or score > best[0]:
                best = (score, off)
    moved = ref_markers + best[1]
    cost = np.linalg.norm(moved[:, None] - p[None], axis=2) / unit
    ri, ci = linear_sum_assignment(np.minimum(cost, vote_gate + 1))
    keep = cost[ri, ci] < vote_gate
    ri, ci = ri[keep], ci[keep]
    if len(ri) >= 3:                                            # refine with an affine fit, then match tightly
        A, _ = cv2.estimateAffine2D(ref_markers[ri].astype(np.float32), p[ci].astype(np.float32))
        if A is not None:
            moved = ref_markers @ A[:, :2].T + A[:, 2]
            cost = np.linalg.norm(moved[:, None] - p[None], axis=2) / unit
            ri, ci = linear_sum_assignment(np.minimum(cost, gate + 1))
            keep = cost[ri, ci] < gate
            ri, ci = ri[keep], ci[keep]
    return ri, ci


# --------------------------------------------------------------------------
# Printed bubble contours (used as automatic pseudo-labels and local anchors)
# --------------------------------------------------------------------------
def answer_region(ref_points, H=None, pad=30):
    """Quadrilateral around the answer bubbles, in the photo's coordinates.

    The bounding box of the reference bubble centres, padded by `pad` px (bubble radius ~11 plus room for the
    few-pixel errors of the global H), is carried into the photo by the homography H. Unlike fixed page
    fractions, this follows each photo's own crop and tilt.
    """
    (x0, y0), (x1, y1) = ref_points.min(0) - pad, ref_points.max(0) + pad
    corners = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64)
    return corners if H is None else warp_points(H, corners)


def detect_bubble_contours(im, region=None):
    """Multi-threshold ellipse fit of printed bubble outlines on the answer area.

    region: quadrilateral from answer_region(); only contours whose box centre lies inside are used.
    Without it the old fixed rule applies (right of 48% of the width, below 29% of the height), which drops
    the top answer row when the scanner crops a tilted sheet differently (flat_angled/006).
    """
    if ADAPTIVE:
        gray, thresholds = paper_flattened(im[:, :, 1]), RING_THRESHOLDS
    else:
        gray, thresholds = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), [140, 165, 185, 205]
    poly = None if region is None else np.asarray(region, np.float32).reshape(-1, 1, 2)
    candidates = []
    for threshold in thresholds:
        mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]
        for c in cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]:
            if len(c) < 5:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if poly is None:
                if x < im.shape[1] * .48 or y < im.shape[0] * .29:
                    continue
            elif cv2.pointPolygonTest(poly, (x + w / 2, y + h / 2), False) < 0:
                continue
            if not (16 <= w <= 31 and 16 <= h <= 31 and .72 < w / h < 1.38):
                continue
            (cx, cy), (a, b), _ = cv2.fitEllipse(c)
            if min(a, b) < 15 or max(a, b) > 32 or min(a, b) / max(a, b) < .70:
                continue
            quality = abs(1 - cv2.contourArea(c) / (np.pi * a * b / 4))
            if quality > .20:
                continue
            candidates.append((quality, np.array([cx, cy])))
    result, bins = [], {}
    for _, p in sorted(candidates, key=lambda z: z[0]):
        cell = tuple((p // 6).astype(int))
        near = [q for dx in [-1, 0, 1] for dy in [-1, 0, 1] for q in bins.get((cell[0] + dx, cell[1] + dy), [])]
        if all(np.linalg.norm(p - q) > 6 for q in near):
            result.append(p)
            bins.setdefault(cell, []).append(p)
    return np.array(result, np.float64).reshape(-1, 2)


def associate(pred, candidates, gate=10, margin=3):
    """One-to-one match of predicted centres to detected contours.

    A match is kept only if it is within `gate` px, is the nearest candidate,
    and the runner-up is at least `margin` px further away (unambiguous).

    Costs beyond the gate are clipped to one constant before the assignment.
    Without that, Hungarian (which must give every bubble some candidate and
    minimises the total) can let a bubble whose ring was not found (e.g.
    pencil-filled) take its neighbour's ring, that neighbour take the next
    one, and so on down the column, because the chain ends near a spare
    candidate. Every bubble in the chain then loses its own ring. With
    clipped costs any out-of-gate assignment costs the same, so a chain can
    never be cheaper.
    """
    measured = np.full((len(pred), 2), np.nan)
    valid = np.zeros(len(pred), bool)
    if len(candidates) == 0:
        return measured, valid
    costs = np.linalg.norm(pred[:, None] - candidates[None, :], axis=2)
    ri, ci = linear_sum_assignment(np.minimum(costs, gate + 1))
    for r, c in zip(ri, ci):
        ordered = np.sort(costs[r])
        gap = ordered[1] - ordered[0] if len(ordered) > 1 else 100
        if costs[r, c] <= gate and c == np.argmin(costs[r]) and gap >= margin:
            measured[r] = candidates[c]
            valid[r] = True
    return measured, valid


def warp_points(H, pts):
    return cv2.perspectiveTransform(np.asarray(pts, dtype=np.float64)[:, None, :], H).reshape(-1, 2)
