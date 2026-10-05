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

Neither is the condition number alone: after the detectors became lighting-
adaptive, the same shadowed photo gave a RANSAC subset of 6/10 markers with
condition 342 that still put only 387 of 830 bubbles on a printed ring
(all markers: 820). So fit_verified() lets the 830 printed bubble rings
decide: both candidate homographies (RANSAC's, unless ill-conditioned, and
the all-marker one) are checked against the rings detected in the photo, and
the one that lands more bubbles within 10 px of a ring wins (ties: RANSAC).
It is RANSAC's own idea - keep the model most points agree with - applied
with ~800 bubbles instead of ~10 markers.
"""
import cv2
import numpy as np

try:            # as part of the src package: share the one src.common module (and its ADAPTIVE flag)
    from .common import answer_region, associate, detect_bubble_contours, warp_points
except ImportError:  # imported as a top-level module
    from common import answer_region, associate, detect_bubble_contours, warp_points

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


def fit_verified(src, dst, im, ref_points, ref_valid, seed=42, ransac_px=3.0):
    """Pick between RANSAC's and the all-marker homography by agreement with the printed bubble rings.

    Returns (H_all, H, inlier_mask, info, observed_centres, observed_ok) where observed_* are the ring
    matches for the chosen H (exactly what the caller would otherwise compute with associate()).
    """
    H_all, H_guarded, inliers, info = fit_checked(src, dst, seed, ransac_px)
    options = [("ransac", H_guarded, inliers)] if info["used"] == "ransac" else []
    options.append(("all_markers", H_all, np.ones(len(src), bool)))
    best = None
    for name, H, inl in options:
        base = warp_points(H, ref_points)
        obs, ok = associate(base, detect_bubble_contours(im, answer_region(ref_points, H)))
        ok &= ref_valid
        info[f"rings_{name}"] = int(ok.sum())
        if best is None or ok.sum() > best[4].sum():
            best = (name, H, inl, obs, ok)
    name, H, inl, obs, ok = best
    if name == "all_markers" and info["used"] == "ransac":
        info["reason"] = (f"RANSAC's homography put {info['rings_ransac']} bubbles on a printed ring, "
                          f"all markers {info['rings_all_markers']}")
    info["used"] = name
    return H_all, H, inl, info, obs, ok


def fit(src, dst, seed=42, ransac_px=3.0):
    """Returns (H_all, H, inlier_mask); see fit_checked."""
    return fit_checked(src, dst, seed, ransac_px)[:3]


def predict(ctx):
    return {
        "H_all": warp_points(ctx["H_all"], ctx["ref_points"]),
        "H_ransac": ctx["base"],
    }
