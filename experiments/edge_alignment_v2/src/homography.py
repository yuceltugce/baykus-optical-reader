"""E0 — one global perspective transform from the corner markers.

Idea: the sheet is a plane, so a single 3x3 homography H should map every
reference point to the photo. If the paper is curved, one H cannot fit
everywhere and the error grows away from the marker support.

Guarded RANSAC: RANSAC assumes "most markers are exact, a few are grossly
wrong". When the page is very slightly non-planar (sub-millimetre), ALL
markers are a few pixels off instead; a 3 px RANSAC then can keep a small,
badly spread subset and the resulting H extrapolates wildly (seen on the
shadowed phone photo: 5/9 inliers, condition number 22 440, Fen off by up to
120 px). Such an H is ill-conditioned, so that is what we check; then the
least-squares H over all markers is used.

The number of discarded markers alone is NOT a good signal: on the curved
scan dataset/curved_angled/008 RANSAC keeps 6/10 well-spread markers
(condition 111) and that H is clearly better than the all-marker one
(Fen 3.7 vs 8.0 px), because there the markers genuinely disagree.
"""
import cv2
import numpy as np

from common import warp_points

MAX_CONDITION = 5000        # well-spread marker sets give ~50-1500 on this form (40 scans + 14 phone tries)


def fit_checked(src, dst, seed=42, ransac_px=3.0):
    """Returns (H_all, H, inlier_mask, info). H is RANSAC's, or H_all if RANSAC looks broken."""
    cv2.setRNGSeed(seed)
    H_ransac, mask = cv2.findHomography(src, dst, cv2.RANSAC, ransac_px)
    H_all, _ = cv2.findHomography(src, dst, 0)
    if H_ransac is None or H_all is None:
        raise ValueError("homography failed")
    inliers = mask.ravel().astype(bool)
    condition = float(np.linalg.cond(H_ransac))
    info = dict(ransac_inliers=int(inliers.sum()), markers=len(src), ransac_condition=round(condition))
    if condition > MAX_CONDITION:
        info.update(used="all_markers", reason=f"RANSAC kept {int(inliers.sum())}/{len(src)} markers and its "
                                               f"homography is ill-conditioned ({condition:.0f})")
        return H_all, H_all, np.ones(len(src), bool), info
    info.update(used="ransac")
    return H_all, H_ransac, inliers, info


def fit(src, dst, seed=42, ransac_px=3.0):
    """Returns (H_all, H, inlier_mask); see fit_checked."""
    return fit_checked(src, dst, seed, ransac_px)[:3]


def predict(ctx):
    return {
        "H_all": warp_points(ctx["H_all"], ctx["ref_points"]),
        "H_ransac": ctx["base"],
    }
