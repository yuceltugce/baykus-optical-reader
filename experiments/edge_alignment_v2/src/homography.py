"""E0 — one global perspective transform from the corner markers.

Idea: the sheet is a plane, so a single 3x3 homography H should map every
reference point to the photo. If the paper is curved, one H cannot fit
everywhere and the error grows away from the marker support.
"""
import cv2
import numpy as np

from common import warp_points


def fit(src, dst, seed=42, ransac_px=3.0):
    """Returns (H_all, H_ransac, inlier_mask). src/dst: matched marker centres."""
    cv2.setRNGSeed(seed)
    H_ransac, mask = cv2.findHomography(src, dst, cv2.RANSAC, ransac_px)
    H_all, _ = cv2.findHomography(src, dst, 0)
    if H_ransac is None or H_all is None:
        raise ValueError("homography failed")
    return H_all, H_ransac, mask.ravel().astype(bool)


def predict(ctx):
    return {
        "H_all": warp_points(ctx["H_all"], ctx["ref_points"]),
        "H_ransac": ctx["base"],
    }
