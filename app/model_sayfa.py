"""Send a WHOLE scanned page (no cropping) to a vision model on OpenRouter and score its answers.

    export OPENROUTER_API_KEY=...
    .venv/bin/python app/model_sayfa.py --model google/gemini-3.8-flash <dosya.pdf>:<sayfa> [...] [--yukseklik 3000]

Truth: the per-block answers of --dogru-model (default google/gemini-3.8-flash) saved by model_dene.py in <dogru_klasoru>/model_sonuclari/
(checked by eye; a "?" there means a half/unclear mark and counts as blank). Also compares with our pipeline
when --reference (or dataset/flat_front/004.png) is available. Prints cost, time and errors per page.
"""
from pathlib import Path
import argparse
import base64
import json
import os
import re
import sys
import time

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import batch_process  # noqa: E402
import model_dene  # noqa: E402

SUBJECTS = [("Turkce", "Türkçe", 40), ("Sosyal", "Sosyal", 46), ("Matematik", "Matematik", 40), ("Fen", "Fen", 40)]
PROMPT = (
    "Bu resim bir optik cevap formunun bütün sayfası. Sağ alttaki cevap alanında soldan sağa dört ders var:\n"
    "1) TÜRKÇE (Türk Dili ve Edebiyatı - Sosyal Bilimler-1): 40 soru\n"
    "2) SOSYAL BİLİMLER (Sosyal Bilimler-2): 46 soru\n"
    "3) TEMEL MATEMATİK: 40 soru\n"
    "4) FEN BİLİMLERİ: 40 soru\n"
    "Her soruda A, B, C, D, E şıkları var. Kurşun kalemle doldurulmuş balonları oku. Sayfanın diğer "
    "bölümlerini (öğrenci numarası, ad soyad vb.) okuma.\n"
    "Her soru için sadece işaretli şıkkı yaz. Hiçbir şık işaretli değilse \"-\" yaz. Birden fazla şık "
    "işaretliyse hepsini yaz (örneğin \"BD\"). Yarım ya da çok açık işaret görürsen şıkkın yanına \"?\" koy. "
    "Bir soru resimde görünmüyorsa \"X\" yaz.\n"
    "Cevabı sadece şu dört satır biçiminde ver, başka açıklama yazma:\n"
    "Türkçe: 1:C 2:A 3:- ... 40:B\n"
    "Sosyal: 1:... 46:...\n"
    "Matematik: 1:... 40:...\n"
    "Fen: 1:... 40:..."
)


def normalise(a):
    """Rule from the eye check: an answer the model marks with '?' (half/unclear mark) counts as blank."""
    return "-" if (a is None or a.endswith("?")) else a


def parse_page(text):
    out = {}
    for key, label, _ in SUBJECTS:
        m = re.search(rf"^\s*\**{label}\**\s*:(.*)$", text, re.MULTILINE | re.IGNORECASE)
        if m:
            out[key] = {int(q): a.upper() for q, a in re.findall(r"(\d+)\s*[:=]\s*([A-Ea-eXx?\-]+)", m.group(1))}
    return out


def truth_from_blocks(folder, tag, model):
    """Latest saved per-block answers of `model` for this page (checked by eye), or None."""
    res = folder / "model_sonuclari"
    truth = {}
    for key, _, _ in SUBJECTS:
        files = sorted(res.glob(f"{tag}_{key}__{model.replace('/', '_')}__*.json"))
        if not files:
            return None
        d = json.loads(files[-1].read_text(encoding="utf-8"))
        if "choices" not in d:
            return None
        truth[key] = model_dene.parse_answers(d["choices"][0]["message"]["content"] or "")
    return truth


def page_data_url(original, height):
    scale = height / original.shape[0]
    im = cv2.resize(original, (round(original.shape[1] * scale), height), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode(), im.shape[1::-1]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True)
    p.add_argument("pages", nargs="+", help="dosya.pdf:sayfa")
    p.add_argument("--yukseklik", type=int, default=3000, help="sent image height in px (default 3000)")
    p.add_argument("--dogru-klasoru", type=Path, default=Path("/Users/tugceyucel/Desktop/optic-data/model_deneme_zor"),
                   help="folder whose model_sonuclari/ holds the eye-checked per-block answers")
    p.add_argument("--dogru-model", default="google/gemini-3.8-flash",
                   help="model whose eye-checked per-block answers are the truth (default google/gemini-3.8-flash)")
    args = p.parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY tanımlı değil (aynı terminal penceresinde export edin).")

    total_cost = total_time = 0.0
    for spec in args.pages:
        path, page = spec.rsplit(":", 1)
        path, page = Path(path), int(page)
        tag = f"{path.stem}_s{page:02d}"
        original = dict(batch_process.pages(path))[page]
        url, size = page_data_url(original, args.yukseklik)
        body = dict(model=args.model, temperature=0, usage={"include": True},
                    messages=[{"role": "user", "content": [{"type": "text", "text": PROMPT},
                                                           {"type": "image_url", "image_url": {"url": url}}]}])
        print(f"\n=== {tag}  ({args.model}, tam sayfa {size[0]}x{size[1]})", flush=True)
        out = model_dene.post(body, key)
        save = args.dogru_klasoru / "model_sonuclari_tam_sayfa"
        save.mkdir(parents=True, exist_ok=True)
        (save / f"{tag}__{args.model.replace('/', '_')}__{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        if "error" in out:
            print("HATA:", out["error"])
            continue
        usage = out.get("usage", {})
        cost = float(usage.get("cost") or 0)
        total_cost += cost
        total_time += out["_seconds"]
        print(f"süre {out['_seconds']} sn | girdi {usage.get('prompt_tokens')} token, çıktı "
              f"{usage.get('completion_tokens')} token | maliyet ${cost:.5f}")
        text = out["choices"][0]["message"]["content"] or ""
        answers = parse_page(text)
        if len(answers) < 4:
            print("Cevap beklenen biçimde değil. Ham cevap:\n" + text[:1000])
            continue
        truth = truth_from_blocks(args.dogru_klasoru, tag, args.dogru_model)
        if truth is None:
            print("(Bu sayfa için gözle doğrulanmış blok sonuçları yok; yalnız cevaplar yazdırılıyor.)")
            for k, label, n in SUBJECTS:
                print(f"  {label}: " + " ".join(f"{q}:{answers[k].get(q, 'yok')}" for q in range(1, n + 1)))
            continue
        wrong = 0
        for k, label, n in SUBJECTS:
            diffs = [(q, normalise(truth[k].get(q)), answers[k].get(q, "yok"))
                     for q in range(1, n + 1) if normalise(truth[k].get(q)) != normalise(answers[k].get(q))]
            wrong += len(diffs)
            print(f"  {label:9s}: {n - len(diffs)}/{n} doğru" +
                  ("" if not diffs else "  | farklı: " + ", ".join(f"{q} (doğru {t}, model {a})" for q, t, a in diffs)))
        print(f"  TOPLAM: {166 - wrong}/166 doğru")
    print(f"\nToplam maliyet: ${total_cost:.4f} | toplam süre: {total_time:.1f} sn")


if __name__ == "__main__":
    main()
