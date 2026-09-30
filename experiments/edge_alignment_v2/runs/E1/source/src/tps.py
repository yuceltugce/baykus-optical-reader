"""E1 — Thin-Plate Spline (TPS) warp driven by the corner markers.

Idea: a TPS is the smoothest 2D deformation that passes through (or near)
the control points, so it can bend with a curved sheet. The risk: markers
only sit on the border, so between/beyond them the spline extrapolates and
can overshoot (seen on Matematik/Fen).

Variants:
  TPS_markers     pure TPS through all markers (smoothing = 0)
  H_TPS_all       homography first, then a smoothed TPS on its residuals
  H_TPS_inliers   same, but only RANSAC-inlier markers
"""
import numpy as np
from scipy.interpolate import RBFInterpolator

from common import warp_points


def residual_tps(src, values, query, smoothing=.001):
    """Fit a TPS mapping src -> values (N,2) and evaluate it at query."""
    if len(src) < 4 or np.linalg.matrix_rank(src - src.mean(0)) < 2:
        raise ValueError("insufficient 2D control coverage")
    return RBFInterpolator(src / 1000, values, kernel="thin_plate_spline", smoothing=smoothing)(query / 1000)


def predict(ctx, smoothing=.001):
    src, dst, base, H = ctx["src"], ctx["dst"], ctx["base"], ctx["H_ransac"]
    mapped = warp_points(H, src)
    inl = ctx["inliers"]
    return {
        "TPS_markers": residual_tps(src, dst, ctx["ref_points"], smoothing=0),
        "H_TPS_all": base + residual_tps(mapped, dst - mapped, base, smoothing),
        "H_TPS_inliers": base + residual_tps(mapped[inl], (dst - mapped)[inl], base, smoothing),
    }
