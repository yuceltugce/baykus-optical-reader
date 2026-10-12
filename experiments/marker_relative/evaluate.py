"""Compare marker detection / matching variants on every photo we have.

    .venv/bin/python -B experiments/marker_relative/evaluate.py [--limit N]

Variants (common.MARKER_METHOD / common.MATCH_METHOD):
    base             current main: darkness threshold tied to the page's darkest pixels, image-normalised matching
    relative         marker only has to be 20 % darker than the local paper; odd-sized candidates dropped
    relative_ref     as relative, but the marker size comes from the reference sheet, not a vote
    (matching in marker-size units was tried too and dropped: 9 iPhone pages lost their markers)

Per photo and variant: matched markers, false markers (matched but > FALSE_PX from the final homography),
retake decision, share of bubbles on a printed ring, worst shifted region, wrong answers against truth.json
(iPhone pages by sheet; other photos are assigned to the sheet whose truth they match best).
Writes results.csv and prints a summary plus every photo whose outcome differs from base.
"""
from pathlib import Path
import argparse
import csv
import glob
import json
import sys
import time

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "app"))
import batch_process  # noqa: E402
import pipeline  # noqa: E402

common, homography = pipeline.common, pipeline.homography
DATA = Path.home() / "Desktop" / "optic-data"
REDMI = Path.home() / "Downloads" / "optics-redmi"
VARIANTS = {"base": ("base", "image"), "relative": ("relative", "image"), "relative_ref": ("relative_ref", "image")}
FALSE_PX = 8.0


def sources(limit=None):
    """(group, tag, BGR image) for every photo."""
    n = 0
    for f in sorted(DATA.glob("Batch*.pdf")):
        for page, im in batch_process.pages(f):
            yield "iphone", f"{f.stem}_s{page:02d}", im
            n += 1
            if limit and n >= limit:
                return
    for f in sorted(REDMI.glob("*.jpg")):
        if "(1)" not in f.name:
            yield "redmi", f.stem.replace("IMG_20261005_", "R"), cv2.imread(str(f))
    for f in sorted((ROOT / "dataset").glob("*/*.png")):
        yield "dataset", f"{f.parent.name}/{f.stem}", cv2.imread(str(f))
    for f in sorted(glob.glob(str(ROOT / "app/uploads/202610[1-3]*/input.*"))):
        yield "phone_app", Path(f).parent.name, pipeline.decode(open(f, "rb").read(), f)


def load_truth():
    t = json.loads((HERE / "truth.json").read_text())
    page_sheet = {p: s["id"] for s in t["sheets"] for p in s["pages"]}
    return t["sheets"], page_sheet


def errors(result, sheet):
    ans = {f"{s}|{q['question']}": (q["answer"] or "-") for s, rows in result["answers"].items() for q in rows
           if q["status"] != "invisible"}
    return sum(1 for k, v in sheet["truth"].items() if k not in sheet["disputed"] and k in ans and ans[k] != v)


def best_sheet(result, sheets):
    ans = {f"{s}|{q['question']}": (q["answer"] or "-") for s, rows in result["answers"].items() for q in rows}
    scores = [sum(ans.get(k) == v for k, v in s["truth"].items() if v != "-") / max(1, sum(v != "-" for v in s["truth"].values()))
              for s in sheets]
    i = int(np.argmax(scores))
    return sheets[i] if scores[i] > .6 else None


def run_variant(name, im, refs):
    common.MARKER_METHOD, common.MATCH_METHOD = VARIANTS[name]
    pipeline._REF = refs[name]
    ref = refs[name]
    common.EXPECTED_MARKER_SIDE = ref["expected_side"]
    rec = dict(variant=name)
    try:
        result, _, work = pipeline.process_image(im)
    except pipeline.MarkersNotFound:
        return dict(rec, status="markers_not_found", markers=None), None
    # false markers: matched, but far from where the final homography puts them
    markers, sides = common.detect_markers_sized(work)
    ri, ci = common.match_markers(ref["markers"], ref["image"].shape, markers, work.shape,
                                  ref_sides=ref["marker_sides"], sides=sides)
    _, H, *_ = homography.fit_verified(ref["markers"][ri].astype(float), markers[ci].astype(float), work,
                                       ref["points"], ref["ref_valid"])
    resid = np.linalg.norm(common.warp_points(H, ref["markers"][ri].astype(float)) - markers[ci], axis=1)
    d = result["diagnostics"]
    rec.update(status="retake" if result["retake"] else "ok", markers=d["markers_matched"],
               false_markers=int((resid > FALSE_PX).sum()), max_marker_resid=round(float(resid.max()), 1),
               on_ring=round(float(np.mean([v for v in d["verified"].values() if v is not None])), 3),
               worst_offset=max(r["offset"] for r in d["regions"]), H=d["homography"]["used"])
    return rec, result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int)
    args = p.parse_args()
    sheets, page_sheet = load_truth()
    refs = {}
    for name in VARIANTS:
        common.MARKER_METHOD, common.MATCH_METHOD = VARIANTS[name]
        pipeline._REF = None
        refs[name] = pipeline.reference()
        refs[name]["expected_side"] = common.EXPECTED_MARKER_SIDE
        print(f"{name}: {len(refs[name]['markers'])} reference markers", flush=True)
    rows = []
    started = time.time()
    for group, tag, im in sources(args.limit):
        sheet = None
        per = {}
        for name in VARIANTS:
            rec, result = run_variant(name, im, refs)
            if result is not None and sheet is None:
                sheet = next((s for s in sheets if s["id"] == page_sheet.get(tag)), None) if group == "iphone" \
                    else best_sheet(result, sheets)
            rec["errors"] = errors(result, sheet) if (result is not None and sheet) else None
            rec.update(group=group, tag=tag, sheet=sheet["id"] if sheet else None)
            per[name] = rec
            rows.append(rec)
        line = " | ".join(f"{n}: {r['status']}, m{r['markers']}, err {r['errors']}" for n, r in per.items())
        print(f"{tag:28s} {line}", flush=True)
    keys = ["group", "tag", "sheet", "variant", "status", "markers", "false_markers", "max_marker_resid", "on_ring",
            "worst_offset", "H", "errors"]
    with open(HERE / "results.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    summarize(rows)
    print(f"\n{len(rows) // len(VARIANTS)} photos, {time.time() - started:.0f} s -> {HERE / 'results.csv'}")


def summarize(rows):
    print("\nSUMMARY (per group)")
    groups = sorted({r["group"] for r in rows})
    for g in groups:
        print(f"\n  {g}")
        for name in VARIANTS:
            rs = [r for r in rows if r["group"] == g and r["variant"] == name]
            err = [r["errors"] for r in rs if r["errors"] is not None]
            print(f"    {name:16s} photos {len(rs):3d} | ok {sum(r['status'] == 'ok' for r in rs):3d}, "
                  f"retake {sum(r['status'] == 'retake' for r in rs):3d}, no markers "
                  f"{sum(r['status'] == 'markers_not_found' for r in rs):2d} | false markers "
                  f"{sum(r.get('false_markers') or 0 for r in rs):3d} | wrong answers {sum(err):4d} "
                  f"(on {len(err)} photos with truth)")
    print("\nPHOTOS WHOSE OUTCOME DIFFERS FROM BASE")
    by = {}
    for r in rows:
        by.setdefault((r["group"], r["tag"]), {})[r["variant"]] = r
    for (g, tag), v in by.items():
        b = v["base"]
        for name in VARIANTS:
            if name == "base":
                continue
            o = v[name]
            if (o["status"], o["errors"], o.get("false_markers")) != (b["status"], b["errors"], b.get("false_markers")):
                print(f"  {g:9s} {tag:28s} {name:16s} {b['status']}/err {b['errors']}/false {b.get('false_markers')}"
                      f"  ->  {o['status']}/err {o['errors']}/false {o.get('false_markers')}")


if __name__ == "__main__":
    main()
