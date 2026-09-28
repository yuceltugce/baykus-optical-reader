"""Single entry point for the edge-alignment experiments.

    python run_experiment.py --experiment E0          # all 40 scans
    python run_experiment.py --experiment E2 --quick  # 4 scans, fast check
    python run_experiment.py --experiment all

Each run writes runs/<ID>/ with:
    config.json     parameters + code/data identity
    metrics.json    per-image and aggregate errors
    comparison.jpg  visual side-by-side of the methods
    REPORT.md       the standard experiment report
    source/         exact code that produced the run

Evaluation protocol (identical for every experiment, so numbers compare):
  1. Global RANSAC homography from corner markers -> initial guess `base`.
  2. Printed bubble contours near `base` (<=10 px, unambiguous) become
     automatic pseudo-labels. They are NOT human ground truth.
  3. Rows 1, 6, 11, ... (question % 5 == 1) may be used for fitting;
     all other rows are held out and are the only rows measured.
"""
from pathlib import Path
import argparse
import json
import shutil
import statistics
import subprocess
import sys

import cv2
import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from src import common, homography, local_contour, piecewise, tps  # noqa: E402

REFERENCE = "dataset/flat_front/004.png"
TEMPLATE = HERE / "reference" / "template.json"
EXPERIMENTS = {
    "E0": "E0_homography.json",
    "E1": "E1_tps.json",
    "E2": "E2_local_contour.json",
    "E3": "E3_piecewise.json",
}
METHOD_MODULE = {
    "H_all": homography, "H_ransac": homography,
    "TPS_markers": tps, "H_TPS_all": tps, "H_TPS_inliers": tps,
    "H_local_contours": local_contour,
    "piecewise_H": piecewise,
}
SHOWCASE = [f"dataset/{g}/001.png" for g in common.GROUPS]
CROP_Y = {"üst": 620, "orta": 1150, "alt": 1700}   # reference-frame rows of the crops
CROP_X = (705, 1390)                               # covers all four subject blocks
BUBBLE_DIAMETER_PX = 22
COVERAGE_REVIEW = .8


# --------------------------------------------------------------------------
# Reference (computed once per run)
# --------------------------------------------------------------------------
def prepare_reference():
    ref = common.load_image(ROOT / REFERENCE)
    bubbles, points, subjects, questions = common.load_template(TEMPLATE)
    # Only bubbles whose reference centre is itself confirmed by a contour are ever evaluated.
    _, ref_valid = common.associate(points, common.detect_bubble_contours(ref))
    rows_per_subject = {s: int(questions[subjects == s].max()) for s in common.SUBJECTS}
    rel = np.array([(q - 1) / (rows_per_subject[s] - 1) for q, s in zip(questions, subjects)])
    band = np.where(rel < 1 / 3, "üst", np.where(rel < 2 / 3, "orta", "alt"))
    return dict(image=ref, markers=common.detect_markers(ref), points=points, subjects=subjects,
                questions=questions, ref_valid=ref_valid, band=band, n_bubbles=len(bubbles))


# --------------------------------------------------------------------------
# One image
# --------------------------------------------------------------------------
def process_image(path, ref, methods):
    im = common.load_image(path)
    markers = common.detect_markers(im)
    ri, ci = common.match_markers(ref["markers"], ref["image"].shape, markers, im.shape)
    if len(ri) < 6:
        raise ValueError(f"only {len(ri)} matched markers (need 6)")
    src, dst = ref["markers"][ri].astype(float), markers[ci].astype(float)
    H_all, H_ransac, inliers = homography.fit(src, dst)
    base = common.warp_points(H_ransac, ref["points"])

    # Pseudo-labels are frozen from `base` BEFORE any method runs.
    obs, ok = common.associate(base, common.detect_bubble_contours(im))
    ok &= ref["ref_valid"]
    train_rows = ref["questions"] % 5 == 1
    evaluation = ok & ~train_rows

    ctx = dict(ref_points=ref["points"], subjects=ref["subjects"], subject_names=common.SUBJECTS,
               src=src, dst=dst, H_all=H_all, H_ransac=H_ransac, inliers=inliers, base=base,
               obs=obs, ok=ok, train_rows=train_rows, fits={})
    predictions = {}
    for module in dict.fromkeys(METHOD_MODULE[m] for m in methods):
        predictions.update(module.predict(ctx))
    predictions = {m: predictions[m] for m in methods}

    metrics = {}
    for m, pred in predictions.items():
        dist = np.linalg.norm(pred - obs, axis=1)
        metrics[m] = dict(
            by_subject={s: summarize(dist[evaluation & (ref["subjects"] == s)]) for s in common.SUBJECTS},
            by_band={b: summarize(dist[evaluation & (ref["band"] == b)]) for b in CROP_Y},
        )
    expected = {s: int((~train_rows & ref["ref_valid"] & (ref["subjects"] == s)).sum()) for s in common.SUBJECTS}
    coverage = {s: metrics[methods[0]]["by_subject"][s]["n"] / expected[s] for s in common.SUBJECTS}
    record = dict(status="ok", matched_markers=int(len(ri)), marker_inliers=int(inliers.sum()),
                  coverage=coverage, fits=ctx["fits"], metrics=metrics)
    return record, dict(im=im, H=H_ransac, obs=obs, evaluation=evaluation, predictions=predictions)


def summarize(dist):
    if len(dist) == 0:
        return dict(n=0, median_px=None, p95_px=None)
    return dict(n=int(len(dist)), median_px=float(np.median(dist)), p95_px=float(np.percentile(dist, 95)))


# --------------------------------------------------------------------------
# Visuals
# --------------------------------------------------------------------------
def comparison_panel(name, vis, ref_shape, methods):
    """Rows = üst/orta/alt crops, columns = methods, all in the reference frame."""
    rows = []
    for band, y in CROP_Y.items():
        tiles = []
        for m in methods:
            canvas = vis["im"].copy()
            for i in np.where(vis["evaluation"])[0]:
                cv2.circle(canvas, tuple(np.round(vis["obs"][i]).astype(int)), 6, (0, 170, 0), 1, cv2.LINE_AA)
                cv2.drawMarker(canvas, tuple(np.round(vis["predictions"][m][i]).astype(int)),
                               (0, 0, 255), cv2.MARKER_CROSS, 9, 1)
            # The same global H is only used to *display* every method in one frame.
            canon = cv2.warpPerspective(canvas, np.linalg.inv(vis["H"]), (ref_shape[1], ref_shape[0]),
                                        borderValue=(255, 255, 255))
            tile = canon[y - 65:y + 65, CROP_X[0]:CROP_X[1]]
            label = np.full((26, tile.shape[1], 3), 255, np.uint8)
            cv2.putText(label, f"{m}  |  {band}", (6, 19), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 0), 1)
            tiles.append(np.vstack([label, tile]))
            tiles.append(np.full((tiles[-1].shape[0], 6, 3), 200, np.uint8))
        rows.append(np.hstack(tiles[:-1]))
    header = np.full((34, rows[0].shape[1], 3), 235, np.uint8)
    cv2.putText(header, name, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, .75, (0, 0, 0), 2)
    return np.vstack([header] + rows + [np.full((10, rows[0].shape[1], 3), 255, np.uint8)])


# --------------------------------------------------------------------------
# Aggregation + report
# --------------------------------------------------------------------------
def aggregate(records, methods):
    ok = [r for r in records.values() if r["status"] == "ok"]

    def med(m, key, part):
        vals = [r["metrics"][m][key][part]["median_px"] for r in ok if r["metrics"][m][key][part]["n"]]
        return statistics.median(vals) if vals else None

    agg = {m: dict(by_subject={s: med(m, "by_subject", s) for s in common.SUBJECTS},
                   by_band={b: med(m, "by_band", b) for b in CROP_Y}) for m in methods}
    return agg


def review_flags(records):
    flags = []
    for image, r in records.items():
        if r["status"] != "ok":
            flags.append(dict(image=image, reason=r["reason"]))
            continue
        low = [s for s, c in r["coverage"].items() if c < COVERAGE_REVIEW]
        fallback = sorted({s for fits in r["fits"].values() for s, f in fits.items() if f["status"] != "fitted"})
        if low or fallback:
            flags.append(dict(image=image, low_coverage=low, fallback=fallback,
                              coverage={s: round(c, 2) for s, c in r["coverage"].items()}))
    return flags


def win_loss(records, method, baseline, tol=.1):
    """Per (image, subject): did `method` beat the baseline by more than `tol` px?"""
    better, worse = [], []
    for image, r in records.items():
        if r["status"] != "ok":
            continue
        for s in common.SUBJECTS:
            a = r["metrics"][method]["by_subject"][s]["median_px"]
            b = r["metrics"][baseline]["by_subject"][s]["median_px"]
            if a is None or b is None:
                continue
            if a < b - tol:
                better.append((image, s, b, a))
            elif a > b + tol:
                worse.append((image, s, b, a))
    return better, worse


def fmt(v):
    return "—" if v is None else f"{v:.2f}"


def table(agg, methods, key, cols):
    head = "| Yöntem | " + " | ".join(cols) + " |\n|---|" + "---:|" * len(cols) + "\n"
    return head + "".join(f"| {m} | " + " | ".join(fmt(agg[m][key][c]) for c in cols) + " |\n" for m in methods)


def write_report(out, cfg, records, agg, flags, n_images):
    methods, baseline = cfg["methods"], cfg["baseline"]
    lines = [f"# {cfg['name']}\n",
             f"**Deney adı:** {cfg['name']}\n",
             f"**Amaç:** {cfg['question']}\n",
             f"**Kullanılan girdi:** `dataset/*/*.png` — referans hariç {n_images} tarama "
             f"({sum(r['status'] == 'ok' for r in records.values())} başarıyla işlendi). "
             f"Tüm ölçüler yüksekliği {common.WORKING_HEIGHT} px'e indirilmiş görüntüde, piksel cinsinden. "
             f"Bir balon çapı ≈ {BUBBLE_DIAMETER_PX} px.\n",
             f"**Referans:** `{REFERENCE}` + `reference/template.json` (830 balon merkezi, E1'de onarılmış geçici şablon). "
             "Bu tarama fiziksel ground truth değildir. Ölçümler otomatik kontur eşleşmelerine göre yapılır "
             "(soru % 5 == 1 satırları eğitim, diğerleri ölçüm).\n",
             f"**Değiştirilen şey:** {cfg['changed']}\n",
             f"**Kullanılmayan şey:** {cfg['not_used']}\n",
             "**Çıktı:** `comparison.jpg` (yeşil halka = tespit edilen balon, kırmızı artı = yöntemin tahmini), "
             "`metrics.json`, `config.json`, `source/`.\n",
             "## Sonuç — ders bazında\n",
             "Görüntü başına held-out medyan hatanın, görüntüler üzerinden medyanı (px). Küçük = iyi.\n",
             table(agg, methods, "by_subject", common.SUBJECTS),
             "\n## Sonuç — dikey bant (üst / orta / alt satırlar)\n",
             table(agg, methods, "by_band", list(CROP_Y)),
             f"\n## Nereye bakmalı?\n\n{cfg['look_at']}\n"]

    lines.append("\n## Başarılı olduğu durum\n")
    lines.append(f"Ölçüt: {cfg['good_if']}\n")
    for m in methods:
        if m == baseline:
            continue
        better, worse = win_loss(records, m, baseline)
        total = len(better) + len(worse)
        lines.append(f"- **{m}** vs {baseline}: {len(better)} (görüntü, ders) çiftinde >0.1 px daha iyi, "
                     f"{len(worse)} çiftte daha kötü" + (f" (toplam {total} farklı çift)." if total else "."))
    lines.append("\n## Başarısız olduğu durum\n")
    lines.append(f"Ölçüt: {cfg['bad_if']}\n")
    for m in methods:
        if m == baseline:
            continue
        _, worse = win_loss(records, m, baseline)
        if not worse:
            lines.append(f"- {m}: {baseline}'a göre >0.1 px kötüleştiği hiçbir (görüntü, ders) çifti yok.")
        for image, s, b, a in sorted(worse, key=lambda w: w[2] - w[3])[:5]:
            lines.append(f"- {m} kötüleştirdi: `{image}` {s}: {b:.2f} → {a:.2f} px")
    if flags:
        lines.append(f"\nİnceleme gereken {len(flags)} görüntü (kapsama < %{int(COVERAGE_REVIEW * 100)} "
                     "veya yerel model kurulamadı → H'ye geri düştü). Bunlar başarı sayılmaz:\n")
        for f in flags:
            if "reason" in f:
                lines.append(f"- `{f['image']}`: işlenemedi — {f['reason']}")
            else:
                cov = ", ".join(f"{s} %{100 * c:.0f}" for s, c in f["coverage"].items())
                extra = f"; fallback: {', '.join(f['fallback'])}" if f["fallback"] else ""
                lines.append(f"- `{f['image']}`: kapsama {cov}{extra}")
    lines.append(f"\n## Sonraki karar\n\n{cfg['next_decision']}\n")
    lines.append("\n---\n*Bu rapor `run_experiment.py` tarafından üretildi. Rakamlar insan etiketli ground truth "
                 "değildir; eşleşmeler başlangıç H'sinin 10 px çevresinden seçildiği için büyük hatalar dışarıda kalabilir.*\n")
    (out / "REPORT.md").write_text("\n".join(lines))


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def run(exp_id, quick, overwrite):
    cfg = json.loads((HERE / "configs" / EXPERIMENTS[exp_id]).read_text())
    out = HERE / "runs" / exp_id
    if out.exists():
        if not overwrite:
            sys.exit(f"{out} already exists. Use --overwrite to replace it.")
        shutil.rmtree(out)
    out.mkdir(parents=True)

    ref = prepare_reference()
    paths = [ROOT / p for p in SHOWCASE] if quick else sorted((ROOT / "dataset").glob("*/*.png"))
    paths = [p for p in paths if p != ROOT / REFERENCE]

    records, panels = {}, []
    for path in paths:
        rel = str(path.relative_to(ROOT))
        try:
            record, vis = process_image(path, ref, cfg["methods"])
            if rel in SHOWCASE:
                panels.append(comparison_panel(rel, vis, ref["image"].shape, cfg["methods"]))
            print(f"{exp_id} {rel}: ok", flush=True)
        except (ValueError, np.linalg.LinAlgError, cv2.error) as err:
            record = dict(status="failed", reason=str(err))
            print(f"{exp_id} {rel}: FAILED {err}", flush=True)
        records[rel] = record

    agg = aggregate(records, cfg["methods"])
    flags = review_flags(records)
    if panels:
        width = max(p.shape[1] for p in panels)
        panels = [np.pad(p, ((0, 0), (0, width - p.shape[1]), (0, 0)), constant_values=255) for p in panels]
        common.save_image(out / "comparison.jpg", np.vstack(panels))

    shutil.copytree(HERE / "src", out / "source" / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(Path(__file__), out / "source" / "run_experiment.py")
    run_config = dict(cfg, runtime=dict(
        images=len(paths), quick=quick, reference=REFERENCE, template=str(TEMPLATE.relative_to(ROOT)),
        template_sha256=common.sha256(TEMPLATE), git_commit=git_commit(), opencv=cv2.__version__,
        scipy=scipy.__version__, numpy=np.__version__, working_height=common.WORKING_HEIGHT,
        train_rows="question % 5 == 1", pseudo_label_gate_px=10, ambiguity_margin_px=3,
        ransac_threshold_px=3.0, seed=42, ground_truth=False,
        dataset_sha256={str(p.relative_to(ROOT)): common.sha256(p) for p in [ROOT / REFERENCE] + paths}))
    (out / "config.json").write_text(json.dumps(run_config, ensure_ascii=False, indent=2))
    (out / "metrics.json").write_text(json.dumps(dict(
        aggregation="median over images of per-image held-out median distance (px)",
        aggregate=agg, review_required=flags, per_image=records), ensure_ascii=False, indent=2))
    write_report(out, cfg, records, agg, flags, len(paths))
    print(f"\n{cfg['name']} -> {out.relative_to(ROOT)}")
    print(table(agg, cfg["methods"], "by_subject", common.SUBJECTS))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--experiment", required=True, choices=[*EXPERIMENTS, "all"])
    p.add_argument("--quick", action="store_true", help="only the 4 showcase scans (one per group)")
    p.add_argument("--overwrite", action="store_true", help="replace an existing runs/<ID> folder")
    args = p.parse_args()
    for exp_id in (EXPERIMENTS if args.experiment == "all" else [args.experiment]):
        run(exp_id, args.quick, args.overwrite)


if __name__ == "__main__":
    main()
