"""E3 — piece-wise warp: every subject block gets its own homography.

Idea: a curved sheet is roughly *piece-wise* planar. Instead of one global
H plus a correction field (E2), fit an independent 3x3 homography per
subject block, from reference bubble centres (training rows) to the bubble
contours detected in the photo. Each block is then a small, nearly flat
plane with its own perspective.

Difference to E2: E2 keeps the global H and adds a smooth residual; E3
throws the global H away inside each block (it is only used to find the
anchors and as a fallback).
"""
import cv2
import numpy as np

from common import warp_points


def fit_block(ref_pts, obs_pts, ransac_px=2.0, seed=42):
    cv2.setRNGSeed(seed)
    H, mask = cv2.findHomography(ref_pts, obs_pts, cv2.RANSAC, ransac_px)
    if H is None or not np.isfinite(H).all():
        raise ValueError("block homography failed")
    return H, mask.ravel().astype(bool)


def predict(ctx, min_anchors=10, max_correction_px=12):
    ref, base, obs = ctx["ref_points"], ctx["base"], ctx["obs"]
    subjects, train = ctx["subjects"], ctx["train_rows"] & ctx["ok"]
    out = base.copy()
    fits, block_H = {}, {}
    for subject in ctx["subject_names"]:
        block = subjects == subject
        fit = block & train
        if fit.sum() < min_anchors:
            fits[subject] = dict(status="fallback_to_H", reason=f"{int(fit.sum())} anchors")
            continue
        try:
            H, inl = fit_block(ref[fit], obs[fit])
        except (ValueError, cv2.error) as err:
            fits[subject] = dict(status="fallback_to_H", reason=str(err))
            continue
        pred = warp_points(H, ref[block])
        # Same safety rule as E2: large jumps away from the global H are refused.
        good = np.linalg.norm(pred - base[block], axis=1) <= max_correction_px
        block_pts = out[block]
        block_pts[good] = pred[good]
        out[block] = block_pts
        block_H[subject] = H
        fits[subject] = dict(status="fitted", anchors=int(fit.sum()), inliers=int(inl.sum()),
                             rejected_predictions=int((~good).sum()))
    ctx["fits"]["piecewise_H"] = fits
    ctx["block_H"] = block_H
    return {"piecewise_H": out}
