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
def detect_markers(im):
    """Threshold -> opening -> square-ish, solid, isolated blobs."""
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
def detect_bubble_contours(im):
    """Multi-threshold ellipse fit of printed bubble outlines on the answer area."""
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    candidates = []
    for threshold in [140, 165, 185, 205]:
        mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]
        for c in cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)[0]:
            if len(c) < 5:
                continue
            x, y, w, h = cv2.boundingRect(c)
            if x < im.shape[1] * .48 or y < im.shape[0] * .29:
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
    """
    measured = np.full((len(pred), 2), np.nan)
    valid = np.zeros(len(pred), bool)
    if len(candidates) == 0:
        return measured, valid
    costs = np.linalg.norm(pred[:, None] - candidates[None, :], axis=2)
    ri, ci = linear_sum_assignment(costs)
    for r, c in zip(ri, ci):
        ordered = np.sort(costs[r])
        gap = ordered[1] - ordered[0] if len(ordered) > 1 else 100
        if costs[r, c] <= gate and c == np.argmin(costs[r]) and gap >= margin:
            measured[r] = candidates[c]
            valid[r] = True
    return measured, valid


def warp_points(H, pts):
    return cv2.perspectiveTransform(np.asarray(pts, dtype=np.float64)[:, None, :], H).reshape(-1, 2)
