"""E2 — local correction from each subject block's own printed bubbles.

Idea: the markers are far from the answer columns, but the printed bubble
outlines are *inside* each block. Use a few of them (training rows) as extra
control points and fit a smooth TPS correction field on top of the global H,
separately per subject. Rows used for fitting are excluded from evaluation.
"""
import numpy as np

from tps import residual_tps


# outlier_px: a control point whose shift differs from the block's median shift by more than this is treated
# as a wrong ring match and dropped. 6 px was too strict for sheets whose lower part shifts differently from
# the upper part: it dropped exactly the bottom control rows that carry that deformation (Batch5 s21, Fen rows
# 37-39 stayed 5.2 px off). 10 px (the ring matching gate) fixes that page (1.3 px) on 149 phone scans with
# unchanged medians; ring matches are already gated and unambiguous, so gross wrong matches are rare.
def predict(ctx, min_anchors=10, outlier_px=10, max_correction_px=12, smoothing=.01):
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
