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


def detect_markers(im):
    """Threshold -> opening -> square-ish, solid, isolated blobs."""
    if ADAPTIVE:
        # Black markers stay dark in the red channel, where the pink print is weakest.
        flat = cv2.GaussianBlur(paper_flattened(im[:, :, 2]), (3, 3), 0)
        darkest = 1 - np.percentile(flat, .1) / 255            # relative darkness of the darkest 0.1 %
        lo, hi = MARKER_DARKNESS_LIMITS
        t = 255 * (1 - np.clip(MARKER_DARKNESS_SHARE * darkest, lo, hi))
        mask = cv2.threshold(flat, t, 255, cv2.THRESH_BINARY_INV)[1]
    else:
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        mask = cv2.threshold(cv2.GaussianBlur(gray, (3, 3), 0), 140, 255, cv2.THRESH_BINARY_INV)[1]
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    candidates = []
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
        candidates.append((np.array([x + w / 2, y + h / 2]), extent))
    dedup = []
    for p, _ in sorted(candidates, key=lambda z: -z[1]):
        if all(np.linalg.norm(p - q) > 15 for q in dedup):
            dedup.append(p)
    isolated = [p for i, p in enumerate(dedup)
                if all(i == j or np.linalg.norm(p - q) >= 60 for j, q in enumerate(dedup))]
    return np.array(sorted(isolated, key=lambda p: (p[1], p[0])), dtype=np.float32).reshape(-1, 2)


def match_markers(ref_markers, ref_shape, markers, shape, gate=0.06):
    """Hungarian matching on normalised coordinates. Returns (ref_idx, sample_idx)."""
    a = ref_markers / np.array(ref_shape[1::-1])
    b = markers / np.array(shape[1::-1])
    cost = np.linalg.norm(a[:, None] - b[None], axis=2)
    ri, ci = linear_sum_assignment(cost)
    keep = cost[ri, ci] < gate
    return ri[keep], ci[keep]


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
