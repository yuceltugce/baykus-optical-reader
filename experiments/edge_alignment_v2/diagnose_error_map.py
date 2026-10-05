"""Diagnosis: WHY do the edges not line up after the global homography?

    python diagnose_error_map.py            # all 40 scans -> runs/DIAG_error_map/
    python diagnose_error_map.py --overwrite

For every bubble we take the E0 prediction (reference centre warped by
H_ransac) and the detected printed ring, and draw the difference as an arrow
(the residual = what the homography could not explain). The arrow pattern
tells the cause apart:

  lens distortion   arrows point radially away from / towards the photo centre,
                    same pattern on flat and curved paper
  paper curvature   arrows grow smoothly along the sheet (e.g. downwards) and
                    are clearly larger on the curved groups than on flat ones
  block shift       all arrows inside one subject block point the same way

Two tiny models are fitted to the residuals of each photo and the share of
residual energy each explains (R^2) is reported:

  radial   d = (a + b*r^2) * (p - c)    2 parameters, c = photo centre
  block    d = mean shift per subject   8 parameters
"""
from pathlib import Path
import argparse
import json
import shutil
import statistics
import sys

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_experiment import ROOT, REFERENCE, prepare_reference  # noqa: E402
from src import common, homography  # noqa: E402

ARROW_SCALE = 25          # 1 px of residual is drawn as a 25 px arrow
COLOURS = [(1, (60, 170, 60)), (2, (0, 190, 230)), (4, (0, 120, 255)), (1e9, (40, 40, 220))]  # BGR


def colour(mag):
    return next(c for limit, c in COLOURS if mag < limit)


def residuals(path, ref):
    """Residual of every confidently detected bubble, in photo and reference frames."""
    im = common.load_image(path)
    markers = common.detect_markers(im)
    ri, ci = common.match_markers(ref["markers"], ref["image"].shape, markers, im.shape)
    if len(ri) < 6:
        raise ValueError(f"only {len(ri)} matched markers")
    src, dst = ref["markers"][ri].astype(float), markers[ci].astype(float)
    _, H, _, _, obs, ok = homography.fit_verified(src, dst, im, ref["points"], ref["ref_valid"])
    base = common.warp_points(H, ref["points"])
    # Same arrow expressed in the reference frame, so every photo is drawn on one layout.
    obs_ref = np.full_like(obs, np.nan)
    obs_ref[ok] = common.warp_points(np.linalg.inv(H), obs[ok])
    return dict(im_shape=im.shape, base=base, ok=ok, d_photo=obs - base, d_ref=obs_ref - ref["points"])


def r2(d, fitted):
    return float(1 - np.sum((d - fitted) ** 2) / np.sum(d ** 2))


def fit_models(res, subjects, shape):
    """Explained share of residual energy by a radial-lens and a per-block-shift model."""
    ok = res["ok"]
    d = res["d_photo"][ok]
    c = np.array([shape[1] / 2, shape[0] / 2])
    p = (res["base"][ok] - c) / shape[0]              # normalised to image height
    r_sq = np.sum(p ** 2, axis=1, keepdims=True)
    A = np.hstack([p, p * r_sq])                       # [px, py, px*r^2, py*r^2]
    coef, *_ = np.linalg.lstsq(np.vstack([A[:, [0, 2]], A[:, [1, 3]]]),
                               np.concatenate([d[:, 0], d[:, 1]]), rcond=None)
    radial = np.column_stack([A[:, [0, 2]] @ coef, A[:, [1, 3]] @ coef])
    block = np.zeros_like(d)
    for s in common.SUBJECTS:
        sel = subjects[ok] == s
        if sel.any():
            block[sel] = d[sel].mean(0)
    return dict(radial_r2=r2(d, radial), block_r2=r2(d, block))


def draw_map(ref, fields, title, subtitle):
    """Arrows on a faded reference sheet. fields: residual vectors in the reference frame."""
    canvas = cv2.addWeighted(ref["image"], .35, np.full_like(ref["image"], 255), .65, 0)
    for p, d in zip(ref["points"], fields):
        if np.isnan(d).any():
            continue
        a = tuple(np.round(p).astype(int))
        b = tuple(np.round(p + ARROW_SCALE * d).astype(int))
        cv2.arrowedLine(canvas, a, b, colour(float(np.linalg.norm(d))), 2, cv2.LINE_AA, tipLength=.3)
    for m in ref["markers"]:
        cv2.rectangle(canvas, tuple((m - 14).astype(int)), tuple((m + 14).astype(int)), (200, 60, 0), 3)
    legend = np.full((150, canvas.shape[1], 3), 255, np.uint8)
    cv2.putText(legend, title, (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2)
    cv2.putText(legend, subtitle, (20, 85), cv2.FONT_HERSHEY_SIMPLEX, .75, (60, 60, 60), 2)
    x = 20
    for text, col in [("< 1 px", COLOURS[0][1]), ("1-2 px", COLOURS[1][1]), ("2-4 px", COLOURS[2][1]),
                      ("> 4 px", COLOURS[3][1]), ("kare = marker", (200, 60, 0))]:
        cv2.arrowedLine(legend, (x, 122), (x + 40, 122), col, 3, tipLength=.3)
        cv2.putText(legend, text, (x + 50, 130), cv2.FONT_HERSHEY_SIMPLEX, .7, (0, 0, 0), 2)
        x += 220
    return np.vstack([legend, canvas])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args()
    out = HERE / "runs" / "DIAG_error_map"
    report = None
    if out.exists():
        if not args.overwrite:
            sys.exit(f"{out} already exists. Use --overwrite to replace it.")
        if (out / "REPORT.md").exists():       # hand-written interpretation; keep it across re-runs
            report = (out / "REPORT.md").read_text()
        shutil.rmtree(out)
    (out / "per_image").mkdir(parents=True)
    if report is not None:
        (out / "REPORT.md").write_text(report)

    ref = prepare_reference()
    paths = [p for p in sorted((ROOT / "dataset").glob("*/*.png")) if p != ROOT / REFERENCE]
    per_image, by_group = {}, {g: [] for g in common.GROUPS}
    for path in paths:
        rel = str(path.relative_to(ROOT))
        try:
            res = residuals(path, ref)
        except (ValueError, cv2.error) as err:
            per_image[rel] = dict(status="failed", reason=str(err))
            continue
        ok, mag = res["ok"], np.linalg.norm(res["d_photo"], axis=1)

        def med(sel):
            return float(np.median(mag[ok & sel])) if (ok & sel).any() else None

        stats = dict(status="ok", group=path.parent.name, n=int(ok.sum()), median_px=med(np.ones_like(ok)),
                     by_subject={s: med(ref["subjects"] == s) for s in common.SUBJECTS},
                     by_band={b: med(ref["band"] == b) for b in ["üst", "orta", "alt"]},
                     **fit_models(res, ref["subjects"], res["im_shape"]))
        per_image[rel] = stats
        by_group[path.parent.name].append(res["d_ref"])
        name = f"{path.parent.name}_{path.stem}"
        sub = f"medyan {stats['median_px']:.2f} px | radyal R2={stats['radial_r2']:.2f} blok R2={stats['block_r2']:.2f}"
        cv2.imwrite(str(out / "per_image" / f"{name}.jpg"), draw_map(ref, res["d_ref"], rel, sub),
                    [cv2.IMWRITE_JPEG_QUALITY, 80])
        print(rel, sub, flush=True)

    # Average arrow field per group: random noise cancels, the systematic pattern stays.
    panels, groups = [], {}
    for g in common.GROUPS:
        rows = [s for s in per_image.values() if s.get("group") == g]
        if not rows:
            continue

        def gmed(key, part):
            return statistics.median(r[key][part] for r in rows if r[key][part] is not None)

        groups[g] = dict(images=len(rows), median_px=statistics.median(r["median_px"] for r in rows),
                         by_band={b: gmed("by_band", b) for b in ["üst", "orta", "alt"]},
                         by_subject={s: gmed("by_subject", s) for s in common.SUBJECTS},
                         radial_r2=statistics.median(r["radial_r2"] for r in rows),
                         block_r2=statistics.median(r["block_r2"] for r in rows))
        mean = np.nanmean(np.stack(by_group[g]), axis=0)
        panel = draw_map(ref, mean, f"{g}: {len(rows)} fotografin ortalama oku",
                         f"medyan {groups[g]['median_px']:.2f} px | radyal R2={groups[g]['radial_r2']:.2f} "
                         f"blok R2={groups[g]['block_r2']:.2f}")
        cv2.imwrite(str(out / f"mean_{g}.jpg"), panel, [cv2.IMWRITE_JPEG_QUALITY, 85])
        panels.append(panel)
    grid = np.vstack([np.hstack(panels[i:i + 2]) for i in range(0, len(panels), 2)])
    grid = cv2.resize(grid, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(out / "group_mean_error_map.jpg"), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])

    (out / "metrics.json").write_text(json.dumps(dict(
        residual="detected ring centre minus H_ransac prediction; all confidently detected bubbles, nothing fitted to them",
        by_group=groups, per_image=per_image), ensure_ascii=False, indent=2))
    shutil.copy2(Path(__file__), out / "source_diagnose_error_map.py")
    print(json.dumps(groups, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
