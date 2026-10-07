"""Ask a vision model on OpenRouter to read one answer block and compare with our pipeline.

    export OPENROUTER_API_KEY=...        (never write the key into this file or into git)
    .venv/bin/python app/model_dene.py --model google/gemini-2.5-flash <resim.png> [<resim.png> ...]

For each image: sends the image + an instruction, prints the model's answers, compares them with the
answers our pipeline read (from the matching *_bizim_cevaplar.txt next to the image, if present) and
prints the tokens and cost OpenRouter reports. Every call is saved under <image folder>/model_sonuclari/.
Standard library only.
"""
from pathlib import Path
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = "https://openrouter.ai/api/v1/chat/completions"
PROMPT = (
    "Bu resim bir optik cevap formunun tek bir dersinin cevap alanı. Soldaki sayılar soru numaraları, her "
    "satırda A, B, C, D, E şıkları var. Sol ve sağ kenarda komşu bölümün parçaları (sayılar, balonlar) "
    "görünebilir; sadece soru numaralarının hemen sağındaki 5 sütunlu bloğu oku. Kurşun kalemle doldurulmuş "
    "balonları oku.\n"
    "Her soru için sadece işaretli şıkkı yaz. Hiçbir şık işaretli değilse \"-\" yaz. Birden fazla şık "
    "işaretliyse hepsini yaz (örneğin \"BD\"). Yarım ya da çok açık işaret görürsen şıkkın yanına \"?\" koy.\n"
    "Cevabı sadece şu biçimde ver, başka açıklama yazma:\n1:C 2:A 3:- 4:BD ..."
)
SUBJECT_OF_FILE = {"Turkce": "Turkce", "Sosyal": "Sosyal", "Matematik": "Matematik", "Fen": "Fen"}


def parse_answers(text):
    """'1:C 2:- 3:BD? ...' -> {1: 'C', 2: '-', 3: 'BD?'}"""
    return {int(q): a.upper() for q, a in re.findall(r"(\d+)\s*[:=]\s*([A-Ea-e?\-]+)", text)}


def our_answers(image):
    """Answers our pipeline read for the same block, from <page>_bizim_cevaplar.txt (written next to the crops)."""
    page, subject = image.stem.rsplit("_", 1)
    txt = image.with_name(f"{page}_bizim_cevaplar.txt")
    if not txt.exists():
        return None
    for line in txt.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{subject} ("):
            return parse_answers(line.split(":", 1)[1])
    return None


def image_data_url(image):
    """JPEG (quality 92) instead of the 1-2 MB PNG: same pixels for the model, 4-6x smaller request.
    A 1.8 MB PNG upload was cut off by the server ("Broken pipe"); price depends on pixel size, not bytes."""
    import cv2
    ok, jpg = cv2.imencode(".jpg", cv2.imread(str(image)), [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise ValueError(f"{image} okunamadı")
    return "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()


def verified_answers(image, model):
    """Latest saved answers of `model` for this block (eye-checked), with '?' (half/unclear mark) as blank."""
    files = sorted((image.parent / "model_sonuclari").glob(f"{image.stem}__{model.replace('/', '_')}__*.json"))
    for f in reversed(files):
        d = json.loads(f.read_text(encoding="utf-8"))
        if "choices" in d:
            return {q: ("-" if a.endswith("?") else a)
                    for q, a in parse_answers(d["choices"][0]["message"]["content"] or "").items()}
    return None


def ask(model, image, key):
    body = dict(model=model, temperature=0, usage={"include": True},
                messages=[{"role": "user", "content": [{"type": "text", "text": PROMPT},
                                                       {"type": "image_url", "image_url": {"url": image_data_url(image)}}]}])
    return post(body, key)


def post(body, key, attempts=3):
    """POST to OpenRouter with retries on network errors and 429/5xx. Returns the JSON or {'error': ...}."""
    data = json.dumps(body).encode()
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(API, data=data, method="POST",
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                              "X-Title": "Baykus Optik model denemesi"})
        started = time.time()
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                out = json.load(resp)
            out["_seconds"] = round(time.time() - started, 1)
            return out
        except urllib.error.HTTPError as err:
            if err.code not in (429, 500, 502, 503, 504) or attempt == attempts:
                return dict(error=f"HTTP {err.code}: {err.read().decode(errors='replace')[:400]}")
            reason = f"HTTP {err.code}"
        except (urllib.error.URLError, ConnectionError, TimeoutError) as err:   # network trouble, e.g. broken pipe
            if attempt == attempts:
                return dict(error=f"bağlantı hatası: {err}")
            reason = str(err)
        print(f"   ({reason}; {attempt}. deneme başarısız, {5 * attempt} sn sonra tekrar deneniyor)", flush=True)
        time.sleep(5 * attempt)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, help="e.g. google/gemini-2.5-flash (see openrouter.ai/models)")
    p.add_argument("images", nargs="+", type=Path)
    p.add_argument("--dogru-model", help="compare with this model's saved, eye-checked answers instead of our "
                                         "pipeline, e.g. google/gemini-3.8-flash ('?' counts as blank on both sides)")
    args = p.parse_args()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY tanımlı değil. Önce anahtarı çözüp export ile tanımlayın (aynı terminal penceresinde).")

    total_cost = 0.0
    for image in args.images:
        print(f"\n=== {image.name}  ({args.model})")
        out = ask(args.model, image, key)
        save_dir = image.parent / "model_sonuclari"
        save_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        (save_dir / f"{image.stem}__{args.model.replace('/', '_')}__{stamp}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        if "error" in out:
            print("HATA:", out["error"])
            continue
        text = out["choices"][0]["message"]["content"] or ""
        usage = out.get("usage", {})
        cost = float(usage.get("cost") or 0)
        total_cost += cost
        print(f"süre {out['_seconds']} sn | girdi {usage.get('prompt_tokens')} token, çıktı "
              f"{usage.get('completion_tokens')} token | maliyet ${cost:.5f}")
        model_ans = parse_answers(text)
        if not model_ans:
            print("Model cevabı beklenen biçimde değil. Ham cevap:\n" + text[:800])
            continue
        print("Model:", " ".join(f"{q}:{a}" for q, a in sorted(model_ans.items())))
        if args.dogru_model:
            truth = verified_answers(image, args.dogru_model)
            if truth is None:
                print(f"({args.dogru_model} için kayıtlı doğru cevap yok)")
                continue
            got = {q: ("-" if a.endswith("?") else a) for q, a in model_ans.items()}
            wrong = [(q, truth[q], got.get(q, "yok")) for q in sorted(truth) if got.get(q, "yok") != truth[q]]
            total_wrong = getattr(main, "wrong", 0) + len(wrong)
            main.wrong, main.asked = total_wrong, getattr(main, "asked", 0) + len(truth)
            print(f"Doğru cevaplarla ({args.dogru_model}, gözle doğrulanmış; \"?\" = boş): "
                  f"{len(truth) - len(wrong)}/{len(truth)} doğru")
            for q, t, a in wrong:
                print(f"   soru {q:2d}: doğru {t:4s} | model {a}")
            continue
        ours = our_answers(image)
        if ours is None:
            continue
        diffs = [(q, ours.get(q, "yok"), model_ans.get(q, "yok")) for q in sorted(set(ours) | set(model_ans))
                 if ours.get(q, "yok").rstrip("?") != model_ans.get(q, "yok").rstrip("?")]
        print(f"Bizim sistem ile {len(ours)} sorudan {len(diffs)} tanesinde farklı "
              "(\"?\" işaretleri göz ardı edildi):")
        for q, a, b in diffs:
            print(f"   soru {q:2d}: bizim {a:4s} | model {b}")
    if args.dogru_model and getattr(main, "asked", 0):
        print(f"\nTOPLAM: {main.asked - main.wrong}/{main.asked} doğru")
    print(f"Toplam maliyet: ${total_cost:.5f}")


if __name__ == "__main__":
    main()
