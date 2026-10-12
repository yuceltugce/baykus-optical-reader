"""Would a smaller upload change the result? Simulate the phone shrinking the scan before sending it.

    .venv/bin/python -B experiments/speed/compare_upload_size.py

The pipeline works at 2000 px height anyway (pipeline.to_working). Every photo is resized to 2000 px with
INTER_AREA and re-encoded as JPEG at QUALITY, then processed; answers, retake decisions, questions to confirm
and errors against experiments/marker_relative/truth.json are compared with the original photo.
"""
from pathlib import Path
import sys

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))
sys.path.insert(0, str(HERE.parents[0] / "marker_relative"))
import evaluate  # noqa: E402
import pipeline  # noqa: E402

QUALITIES = [92, 95]


def shrink(im, quality):
    h, w = im.shape[:2]
    small = cv2.resize(im, (round(w * 2000 / h), 2000), interpolation=cv2.INTER_AREA) if h > 2000 else im
    ok, jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return cv2.imdecode(jpg, cv2.IMREAD_COLOR), len(jpg)


def outcome(im, sheets, page_sheet, group, tag):
    try:
        r, _, _ = pipeline.process_image(im)
    except pipeline.MarkersNotFound:
        return ("markers_not_found",), None, None
    sheet = next((s for s in sheets if s["id"] == page_sheet.get(tag)), None) if group == "iphone" \
        else evaluate.best_sheet(r, sheets)
    key = (bool(r["retake"]), {s: [(q["answer"], q["status"]) for q in rows] for s, rows in r["answers"].items()},
           sorted((c["subject"], c["question"]) for c in r["confirm"]))
    return key, (evaluate.errors(r, sheet) if sheet else None), bool(r["retake"])


def main():
    pipeline.reference()
    sheets, page_sheet = evaluate.load_truth()
    stats = {q: dict(same=0, diff=[], err=0, err_orig=0, retake=0, retake_orig=0, bytes=0) for q in QUALITIES}
    n = 0
    for group, tag, im in evaluate.sources():
        n += 1
        base, err0, rt0 = outcome(im, sheets, page_sheet, group, tag)
        for q in QUALITIES:
            small, size = shrink(im, q)
            new, err1, rt1 = outcome(small, sheets, page_sheet, group, tag)
            s = stats[q]
            s["bytes"] += size
            if new == base:
                s["same"] += 1
            else:
                s["diff"].append((group, tag, err0, err1, rt0, rt1))
            shown0, shown1 = rt0 is False, rt1 is False
            s["err_orig"] += (err0 or 0) if shown0 else 0
            s["err"] += (err1 or 0) if shown1 else 0
            s["retake_orig"] += rt0 is not False
            s["retake"] += rt1 is not False
        print(f"{group:9s} {tag:28s} done", flush=True)
    for q, s in stats.items():
        print(f"\nJPEG {q}: mean upload {s['bytes'] / n / 1e6:.2f} MB | identical result {s['same']}/{n} | "
              f"wrong answers on shown pages {s['err_orig']} -> {s['err']} | retake/no markers {s['retake_orig']} -> {s['retake']}")
        for d in s["diff"]:
            print("   different:", d)


if __name__ == "__main__":
    main()
