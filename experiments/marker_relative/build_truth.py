"""Per-sheet answer truth for evaluating reading/alignment changes.

The 149 iPhone pages (optic-data/Batch1-7.pdf) are photos of only 4 physical sheets. Pages are grouped by
answer similarity; a sheet's truth is the majority answer of its reliable pages. Questions where that
majority disagrees with the eye-checked Gemini block answers (half / erased marks, rule still open) are
listed as disputed and left out of scoring.

    .venv/bin/python -B experiments/marker_relative/build_truth.py <results folder with sayfalar/*.json> <model_sonuclari folder> [...]
    -> experiments/marker_relative/truth.json
"""
from pathlib import Path
import collections
import json
import re
import sys

HERE = Path(__file__).resolve().parent
SUBJECT_OF = {"Turkce": "turkce", "Sosyal": "sosyal", "Matematik": "matematik", "Fen": "fen"}
GEMINI = "google_gemini-3.8-flash"


def answers(result):
    return {f"{s}|{q['question']}": q["answer"] or "-" for s, rows in result["answers"].items() for q in rows}


def similarity(a, b):
    keys = [k for k in a if a[k] != "-" or b[k] != "-"]
    return sum(a[k] == b[k] for k in keys) / max(len(keys), 1)


def gemini_answers(folders):
    out = {}
    for folder in folders:
        for f in sorted(Path(folder).glob(f"*__{GEMINI}__*.json")):
            page, subject = f.name.split("__")[0].rsplit("_", 1)
            d = json.loads(f.read_text())
            if "choices" not in d:
                continue
            text = d["choices"][0]["message"]["content"] or ""
            for q, a in re.findall(r"(\d+)\s*[:=]\s*([A-Ea-e?\-]+)", text):
                out.setdefault(page, {})[f"{SUBJECT_OF[subject]}|{int(q)}"] = "-" if a.endswith("?") else a.upper()
    return out


def main():
    results_dir, model_dirs = Path(sys.argv[1]), sys.argv[2:]
    pages = {f.stem: json.loads(f.read_text()) for f in sorted((results_dir / "sayfalar").glob("Batch*.json"))}
    ans = {p: answers(r) for p, r in pages.items()}
    groups = []
    for p in ans:
        best = max(groups, key=lambda g: similarity(ans[p], ans[g[0]]), default=None)
        if best and similarity(ans[p], ans[best[0]]) > .5:
            best.append(p)
        else:
            groups.append([p])
    groups = sorted(groups, key=len, reverse=True)
    sheets = [g for g in groups if len(g) >= 10]
    gem = gemini_answers(model_dirs)
    out = dict(note=__doc__.split("\n\n")[1], sheets=[])
    for i, g in enumerate(sheets):
        good = [p for p in g if pages[p]["reliable"]] or g
        truth, weak_majority = {}, []
        for k in ans[g[0]]:
            (a, n), = collections.Counter(ans[p][k] for p in good).most_common(1)
            truth[k] = a
            if n < .7 * len(good):
                weak_majority.append(k)
        disputed = set(weak_majority)
        for p in g:
            if p in gem:
                disputed |= {k for k, v in gem[p].items() if v != truth.get(k)}
        out["sheets"].append(dict(id=i + 1, pages=g, reliable_pages=len(good), truth=truth,
                                  disputed=sorted(disputed), gemini_checked=[p for p in g if p in gem]))
        print(f"sheet {i + 1}: {len(g)} pages ({len(good)} reliable), disputed {len(disputed)}, "
              f"gemini-checked pages {[p for p in g if p in gem]}")
    out["ungrouped"] = [p for g in groups if len(g) < 10 for p in g]
    print("ungrouped:", out["ungrouped"])
    (HERE / "truth.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
