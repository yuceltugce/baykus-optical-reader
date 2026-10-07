"""Cut one image per subject block from scanned pages, for trying vision models (see model_dene.py).

    .venv/bin/python app/model_kirp.py <cikti_klasoru> <dosya.pdf>:<sayfa> [<dosya.pdf>:<sayfa> ...] [--reference 004.png]

Block bounds come from the reference template carried by the GLOBAL homography only, with generous padding
(about 1.5 rows above/below, extra room on the left for the question numbers). An earlier version used our
final bubble centres; where those were wrong (shadowed bottom of Batch6 s11 Sosyal) the crop cut off rows
45-46, so the models never saw them. Crops are taken from the full-resolution page, not the 2000 px copy.
Also writes <page>_bizim_cevaplar.txt with what our pipeline read, in the format model_dene.py compares.
"""
from pathlib import Path
import argparse
import sys

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import batch_process  # noqa: E402
import pipeline  # noqa: E402
import run_experiment  # noqa: E402
from src import common, homography  # noqa: E402

NAMES = {"turkce": "Turkce", "sosyal": "Sosyal", "matematik": "Matematik", "fen": "Fen"}
PAD_ROWS = 1.5          # rows of padding above and below the block
PAD_LEFT = 1.45         # row spacings on the left: keeps the question numbers, not the neighbour block's E column
PAD_RIGHT = 0.6           # row spacings on the right: not the next block's question numbers


def block_crops(original, ref):
    """{subject: crop of the full-resolution page} using the global homography only."""
    im = pipeline.to_working(original)
    markers = common.detect_markers(im)
    ri, ci = common.match_markers(ref["markers"], ref["image"].shape, markers, im.shape)
    if len(ri) < 6:
        raise ValueError(f"only {len(ri)} markers matched")
    src, dst = ref["markers"][ri].astype(float), markers[ci].astype(float)
    _, H, _, _, _, _ = homography.fit_verified(src, dst, im, ref["points"], ref["ref_valid"])
    scale = original.shape[0] / im.shape[0]                 # working (2000 px) -> full resolution
    crops = {}
    for s in NAMES:
        sel = ref["subjects"] == s
        pts = ref["points"][sel]
        # Row spacing from the question numbers. (Taking unique y values does not work: bubbles of one row
        # differ by 1-2 px in y, which gave a 1 px "spacing" for Türkçe and cut off its question numbers.)
        step = (pts[:, 1].max() - pts[:, 1].min()) / (ref["questions"][sel].max() - 1)
        (x0, y0), (x1, y1) = pts.min(0), pts.max(0)
        x0, x1 = x0 - PAD_LEFT * step, x1 + PAD_RIGHT * step
        y0, y1 = y0 - PAD_ROWS * step, y1 + PAD_ROWS * step
        corners = common.warp_points(H, np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])) * scale
        (cx0, cy0), (cx1, cy1) = np.floor(corners.min(0)).astype(int), np.ceil(corners.max(0)).astype(int)
        h, w = original.shape[:2]
        crops[s] = original[max(cy0, 0):min(cy1, h), max(cx0, 0):min(cx1, w)]
    return crops


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("output", type=Path)
    p.add_argument("pages", nargs="+", help="dosya.pdf:sayfa")
    p.add_argument("--reference", type=Path)
    args = p.parse_args()
    if args.reference:
        run_experiment.REFERENCE = str(args.reference.resolve())
    ref = pipeline.reference()
    args.output.mkdir(parents=True, exist_ok=True)
    for spec in args.pages:
        path, page = spec.rsplit(":", 1)
        path, page = Path(path), int(page)
        original = dict(batch_process.pages(path))[page]
        tag = f"{path.stem}_s{page:02d}"
        result, _, _ = pipeline.process_image(original)
        lines = [f"{tag} — bizim sistemin okuduğu cevaplar (güvenilir: {'evet' if result['reliable'] else 'HAYIR'})", ""]
        for s, crop in block_crops(original, ref).items():
            fn = f"{tag}_{NAMES[s]}.png"
            cv2.imwrite(str(args.output / fn), crop)
            ans = {q["question"]: (q["answer"] or "-") + ("?" if q["weak"] else "") for q in result["answers"][s]}
            lines.append(f"{NAMES[s]} ({fn}): " + " ".join(f"{k}:{v}" for k, v in ans.items()))
            print(f"{fn}: {crop.shape[1]}x{crop.shape[0]}")
        (args.output / f"{tag}_bizim_cevaplar.txt").write_text(
            "\n".join(lines) + '\n\n"-" = boş, "?" = zayıf işaret, birden çok harf = çoklu işaret\n', encoding="utf-8")


if __name__ == "__main__":
    main()
