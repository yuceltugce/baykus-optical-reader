"""E2 — local correction from each subject block's own printed bubbles.

Idea: the markers are far from the answer columns, but the printed bubble
outlines are *inside* each block. Use a few of them (training rows) as extra
control points and fit a smooth TPS correction field on top of the global H,
separately per subject. Rows used for fitting are excluded from evaluation.
"""
import numpy as np

from .tps import residual_tps


def predict(ctx, min_anchors=10, outlier_px=6, max_correction_px=12, smoothing=.01):
    base, obs = ctx["base"], ctx["obs"]
    subjects, train = ctx["subjects"], ctx["train_rows"] & ctx["ok"]
    local = base.copy()
    fits = {}
    for subject in ctx["subject_names"]:
        block = subjects == subject
        fit = block & train
        if fit.sum() < min_anchors:
            fits[subject] = dict(status="fallback_to_H", reason=f"{int(fit.sum())} anchors")
            continue
        delta = obs[fit] - base[fit]
        idx = np.where(fit)[0][np.linalg.norm(delta - np.median(delta, 0), axis=1) < outlier_px]
        if len(idx) < min_anchors:
            fits[subject] = dict(status="fallback_to_H", reason=f"{len(idx)} anchors after outlier cut")
            continue
        correction = residual_tps(base[idx], obs[idx] - base[idx], base[block], smoothing=smoothing)
        # Refuse extreme extrapolation instead of silently claiming a correction.
        good = np.linalg.norm(correction, axis=1) <= max_correction_px
        block_pts = local[block]
        block_pts[good] += correction[good]
        local[block] = block_pts
        fits[subject] = dict(status="fitted", anchors=len(idx), rejected_predictions=int((~good).sum()))
    ctx["fits"]["H_local_contours"] = fits
    return {"H_local_contours": local}
