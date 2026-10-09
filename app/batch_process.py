"""Run the phone pipeline on every page of every PDF / image in a folder and save the results.

    .venv/bin/python -B app/batch_process.py <girdi_klasoru> <cikti_klasoru> [--reference yol/004.png]

Output folder:
    ozet.csv          one row per page: reliability, warnings, alignment and reading diagnostics, counts
    cevaplar.csv      one row per question: answer, status, weak flag, the five bubble scores
    rapor.html        open in a browser: summary table + every page's overlay and warnings
    sayfalar/         <dosya>_s<NN>.jpg (answer-area overlay) and <dosya>_s<NN>.json (full result)
"""
from pathlib import Path
import argparse
import csv
import html
import json
import sys
import time

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pipeline  # noqa: E402
import run_experiment  # noqa: E402  (importable after pipeline set the path)

SUBJECT_NAMES = pipeline.SUBJECT_NAMES


def pages(path):
    """Yields (page_number, BGR image) for every page of a PDF, or once for an image file."""
    if path.suffix.lower() == ".pdf":
        import pymupdf
        doc = pymupdf.open(path)
        for i, page in enumerate(doc, start=1):
            zoom = 4000 / page.rect.height
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csRGB)
            rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3)
            yield i, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    else:
        im = cv2.imread(str(path))
        if im is not None:
            yield 1, im


def summary_row(name, page, result, seconds):
    d = result["diagnostics"]
    s = result["summary"]
    row = dict(dosya=name, sayfa=page, durum="ok", guvenilir="evet" if result["reliable"] else "HAYIR",
               tekrar_tara_sebebi=" | ".join(result["rescan_reasons"]),
               uyarilar=" | ".join(result["warnings"]), notlar=" | ".join(result["notes"]),
               eslesen_marker=d["markers_matched"], hizalama=d["homography"]["used"],
               en_dusuk_kapsama=min(v for v in d["verified"].values() if v is not None),
               en_kotu_bolge_kayma=max(r["offset"] for r in d["regions"]),
               gorunmeyen=sum(v["invisible"] for v in result["summary"].values()),
               esik=d["reading"]["threshold"], tipik_bos=d["reading"]["typical_empty"],
               tipik_isaret=d["reading"]["typical_mark"],
               isaretli=sum(v["marked"] for v in s.values()), zayif=sum(v["weak"] for v in s.values()),
               bos=sum(v["blank"] for v in s.values()), coklu=sum(v["ambiguous"] for v in s.values()),
               sure_sn=round(seconds, 2))
    for key, v in s.items():
        row[f"{key}_isaretli"] = v["marked"]
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--reference", type=Path, help="reference scan if dataset/flat_front/004.png is not on disk")
    args = p.parse_args()
    if args.reference:
        run_experiment.REFERENCE = str(args.reference.resolve())
    pipeline.reference()

    files = sorted(f for f in args.input.iterdir()
                   if f.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"} and not f.name.startswith("."))
    out_pages = args.output / "sayfalar"
    out_pages.mkdir(parents=True, exist_ok=True)

    rows, answer_rows, cards = [], [], []
    for f in files:
        for page, original in pages(f):
            tag = f"{f.stem}_s{page:02d}"
            started = time.time()
            try:
                result, overlay, _ = pipeline.process_image(original)
            except (ValueError, cv2.error, RuntimeError) as err:
                rows.append(dict(dosya=f.name, sayfa=page, durum="HATA", guvenilir="HAYIR", tekrar_tara_sebebi=str(err)))
                cards.append(f'<article class="bad"><h3>{html.escape(tag)}</h3><p>İşlenemedi: {html.escape(str(err))}</p></article>')
                print(f"{tag}: HATA {err}", flush=True)
                continue
            seconds = time.time() - started
            cv2.imwrite(str(out_pages / f"{tag}.jpg"), overlay, [cv2.IMWRITE_JPEG_QUALITY, 80])
            (out_pages / f"{tag}.json").write_text(json.dumps(dict(result, dosya=f.name, sayfa=page),
                                                              ensure_ascii=False, indent=2))
            row = summary_row(f.name, page, result, seconds)
            rows.append(row)
            for subject, qs in result["answers"].items():
                for q in qs:
                    answer_rows.append(dict(dosya=f.name, sayfa=page, ders=SUBJECT_NAMES[subject], soru=q["question"],
                                            cevap=q["answer"] or "", durum=q["status"], zayif="evet" if q["weak"] else "",
                                            skorlar_ABCDE=" ".join(f"{v:.0f}" for v in q["scores"])))
            msgs = "".join(f'<p class="r">⛔ {html.escape(x)}</p>' for x in result["rescan_reasons"])
            msgs += "".join(f'<p class="w">⚠ {html.escape(x)}</p>' for x in result["warnings"])
            msgs += "".join(f'<p class="n">ℹ︎ {html.escape(x)}</p>' for x in result["notes"])
            counts = " · ".join(f"{SUBJECT_NAMES[k]} {v['marked']}" for k, v in result["summary"].items())
            cls = "" if result["reliable"] else "bad"
            cards.append(f'<article id="{tag}" class="{cls}"><h3>{html.escape(tag)}</h3>'
                         f'<p>İşaretli: {counts} · zayıf {row["zayif"]} · çoklu {row["coklu"]} · '
                         f'en düşük kapsama %{100 * row["en_dusuk_kapsama"]:.0f} · eşik {row["esik"]:.2f}</p>{msgs}'
                         f'<a href="sayfalar/{tag}.jpg"><img loading="lazy" src="sayfalar/{tag}.jpg"></a></article>')
            print(f"{tag}: {'güvenilir' if result['reliable'] else 'GÜVENİLMEZ'} işaretli {row['isaretli']} "
                  f"zayıf {row['zayif']} çoklu {row['coklu']} ({seconds:.1f} sn)", flush=True)

    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(args.output / "ozet.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    with open(args.output / "cevaplar.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(answer_rows[0]) if answer_rows else ["dosya"])
        w.writeheader()
        w.writerows(answer_rows)

    ok = [r for r in rows if r["durum"] == "ok"]
    table = "".join(
        f'<tr class="{"" if r.get("guvenilir") == "evet" else "bad"}"><td><a href="#{html.escape(Path(r["dosya"]).stem)}_s{r["sayfa"]:02d}">'
        f'{html.escape(r["dosya"])} s.{r["sayfa"]}</a></td><td>{r.get("guvenilir", "")}</td><td>{r.get("isaretli", "")}</td>'
        f'<td>{r.get("zayif", "")}</td><td>{r.get("coklu", "")}</td><td>{r.get("en_dusuk_kapsama", "")}</td>'
        f'<td>{html.escape(r.get("tekrar_tara_sebebi", "") or r.get("uyarilar", ""))}</td></tr>' for r in rows)
    page_html = f"""<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Toplu okuma raporu</title><style>
body{{font:15px/1.5 -apple-system,system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;background:#f4f5f7;color:#172331}}
article,table{{background:#fff;border-radius:10px}} article{{padding:16px;margin:16px 0}} article.bad{{border:2px solid #e3a19c}}
table{{border-collapse:collapse;width:100%;font-size:13px}} td,th{{padding:6px 8px;border-bottom:1px solid #e6e8eb;text-align:left}}
tr.bad td{{background:#fdecea}} img{{max-width:100%;max-height:900px;display:block;margin-top:8px}}
.r{{color:#b3261e}} .w{{color:#8a5a00}} .n{{color:#5b6673}} p{{margin:4px 0}}
</style><h1>Toplu okuma raporu</h1>
<p>{len(files)} dosya, {len(rows)} sayfa. Güvenilir: {sum(r.get("guvenilir") == "evet" for r in rows)},
güvenilmez: {sum(r.get("guvenilir") != "evet" for r in rows)}, hata: {len(rows) - len(ok)}.
Resimlerde yeşil ince halka = boş, kırmızı kalın = işaretli, turuncu kalın = zayıf işaret.
Cevap anahtarı olmadığı için doğruluk ölçülmedi.</p>
<table><tr><th>Sayfa</th><th>Güvenilir</th><th>İşaretli</th><th>Zayıf</th><th>Çoklu</th><th>En düşük kapsama</th><th>Sebep / uyarı</th></tr>{table}</table>
{''.join(cards)}</html>"""
    (args.output / "rapor.html").write_text(page_html, encoding="utf-8")
    print(f"\n{len(rows)} sayfa -> {args.output}", flush=True)


if __name__ == "__main__":
    main()
