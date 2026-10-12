"""Detect the printed rings once instead of three times per photo: same results, how much faster?

    .venv/bin/python -B experiments/speed/compare_ring_once.py

Runs every photo (see experiments/marker_relative/evaluate.py sources) with homography.RING_DETECT_ONCE off and
on, compares answers, retake decisions, questions to confirm and the region check, and times both.
"""
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))
sys.path.insert(0, str(HERE.parents[0] / "marker_relative"))
import evaluate  # noqa: E402
import pipeline  # noqa: E402

homography = pipeline.homography


def run(im, once):
    homography.RING_DETECT_ONCE = once
    t = time.perf_counter()
    try:
        r, _, _ = pipeline.process_image(im)
    except pipeline.MarkersNotFound:
        return "markers_not_found", time.perf_counter() - t
    took = time.perf_counter() - t
    d = r["diagnostics"]
    key = (r["retake"], {s: [(q["answer"], q["status"], q["weak"]) for q in rows] for s, rows in r["answers"].items()},
           [(c["subject"], c["question"]) for c in r["confirm"]],
           [(x["subject"], x["first"], x["on"], x["offset"], x["unseen"]) for x in d["regions"]], d["homography"]["used"])
    return key, took


def main():
    pipeline.reference()
    times = {False: [], True: []}
    same = differ = 0
    diffs = []
    for group, tag, im in evaluate.sources():
        old, t_old = run(im, False)
        new, t_new = run(im, True)
        times[False].append(t_old)
        times[True].append(t_new)
        if old == new:
            same += 1
        else:
            differ += 1
            what = "marker" if "markers_not_found" in (old, new) else [
                n for n, a, b in zip(["retake", "answers", "confirm", "regions", "homography"], old, new) if a != b]
            diffs.append((group, tag, what))
        print(f"{group:9s} {tag:28s} {'same' if old == new else 'DIFFERENT'}  {1000 * t_old:5.0f} -> {1000 * t_new:5.0f} ms",
              flush=True)
    print(f"\n{same + differ} photos: identical {same}, different {differ}")
    for d in diffs:
        print("  different:", d)
    for once in (False, True):
        v = times[once]
        print(f"{'once' if once else 'three times'}: median {1000 * statistics.median(v):.0f} ms, "
              f"p90 {1000 * sorted(v)[int(.9 * len(v))]:.0f} ms, total {sum(v):.0f} s")


if __name__ == "__main__":
    main()
