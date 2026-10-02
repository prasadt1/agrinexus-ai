#!/usr/bin/env python3
"""
Fixed vision replay set: run sample photos through the processor vision path
against real Bedrock, N times each, and write every result to a JSON file.

WhatsApp download and S3 writes are stubbed; only Bedrock is called. Needs AWS
credentials with bedrock:InvokeModel. Costs one vision call per run.

Two paths per photo:
  first     process_image_message() with the profile crop (assume / ask / direct)
  confirmed diagnose path after a farmer taps a crop, which is also what the
            re:Invent sample photo returns

Usage:
  python3 scripts/vision-replay.py
  python3 scripts/vision-replay.py --runs 10 --confirmed-runs 3 --dialect mr
  python3 scripts/vision-replay.py --photo F --out /tmp/replay.json

"names_product" matches a short list of common active ingredients (Latin and Marathi /
Hindi spellings). "gives_dose" matches a rate such as "2 मिली/लिटर" or "0.3 ml/L", or a
formulation code such as EC / SL / WG. Both are heuristics; check the stored text.

Flags are taken twice: on the model's raw recommendations ("model_*", how often the
prompt is ignored) and on "farmer_text", the reply after the same advice filter the
handler applies before sending ("farmer_*"). The filter metric is stubbed, not sent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parents[1]
CANDIDATES = REPO / "docs" / "try" / "sample-photo-candidates"
PHOTOS = {
    "F": CANDIDATES / "F-usda-ars-pink-bollworm-cotton-boll-k10075-6.jpg",
    "G": CANDIDATES / "G-csiro-bemisia-tabaci-watermelon-leaf.jpg",
}

DOSE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:मिली|ml|mL|ग्रॅम|ग्राम|g|gm)\s*(?:/|प्रति)\s*(?:लिटर|लीटर|liter|litre|L|एकर|acre)",
    re.IGNORECASE,
)
FORMULATION = re.compile(r"\d+\s*%?\s*(?:EC|SL|WG|WP|SC|WDG|एसएल|ईसी|डब्ल्यूजी)")
ACTIVES = (
    "imidacloprid", "इमिडाक्लोप्रिड", "thiamethoxam", "थायामेथॉक्झाम", "थायमेथोक्साम",
    "acetamiprid", "ॲसिटामिप्रिड", "एसिटामिप्रिड", "dimethoate", "डायमिथोएट",
    "spinosad", "स्पिनोसॅड", "स्पिनोसैड", "emamectin", "इमामेक्टिन",
    "chlorantraniliprole", "क्लोरॅन्ट्रानिलिप्रोल", "क्लोरएंट्रानिलिप्रोल",
    "quinalphos", "क्विनालफॉस", "profenofos", "प्रोफेनोफॉस",
    "cypermethrin", "सायपरमेथ्रिन", "chlorpyrifos", "क्लोरपायरीफॉस",
    "carbofuran", "कार्बोफ्युरान", "cartap", "कार्टाप", "flonicamid", "फ्लोनिकामिड",
    "pyriproxyfen", "पायरीप्रॉक्सिफेन", "diafenthiuron", "डायफेन्थियुरॉन",
)
PHOTO_WORDS = ("फोटो", "photo")
PEST_WORDS = {
    "F": ("गुलाबी", "बोंडअळी", "बोंड अळी", "बॉलवर्म", "इल्ली", "इळ", "bollworm", "caterpillar", "larva"),
    "G": ("पांढरी माशी", "पांढऱ्या माश", "व्हाईटफ्लाय", "whitefl"),
}


def _setup_env() -> None:
    os.environ.setdefault("TABLE_NAME", "replay")
    os.environ.setdefault("KNOWLEDGE_BASE_ID", "replay")
    os.environ.setdefault("GUARDRAIL_ID", "")
    os.environ.setdefault("GUARDRAIL_VERSION", "1")
    os.environ.setdefault("TEMP_AUDIO_BUCKET", "replay-bucket")
    os.environ.setdefault("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
    os.environ.setdefault("VISION_RELEVANCE_GATE_ENABLED", "false")
    os.environ.setdefault("VISION_QUALITY_GATE_ENABLED", "false")
    for p in (REPO / "src" / "processor", REPO / "src" / "common-layer" / "python"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


def _flags(recommendations: str) -> dict:
    low = recommendations.lower()
    return {
        "names_product": any(a in low for a in ACTIVES),
        "gives_dose": bool(DOSE.search(recommendations) or FORMULATION.search(recommendations)),
        "asks_photo": any(w in low for w in PHOTO_WORDS),
    }


def _farmer_flags(photo: str, raw_rec: str, farmer_text: str, kind_referral: bool, dialect: str) -> dict:
    from common import advice_filter, district_helplines

    model = _flags(raw_rec)
    farmer = _flags(farmer_text)
    rec_line = next((l for l in farmer_text.split("\n") if "Recommendations" in l), "")
    rec_body = rec_line.split(":*", 1)[-1].strip() if rec_line else ""
    return {
        "model_names_product": model["names_product"],
        "model_gives_dose": model["gives_dose"],
        "model_filter_kinds": sorted({k for s in re.split(r"(?<=[.।])\s+", raw_rec) for k in advice_filter.classify(s)}),
        "farmer_names_product": farmer["names_product"] or any(
            "active" in advice_filter.classify(l) for l in farmer_text.split("\n")
        ),
        "farmer_gives_dose": farmer["gives_dose"] or any(
            advice_filter.classify(l) & {"dose", "formulation"} for l in farmer_text.split("\n")
        ),
        "farmer_pest_named": any(w in farmer_text.lower() for w in PEST_WORDS.get(photo, ())),
        "farmer_non_chemical_steps": bool(rec_body) and rec_body != "—",
        "farmer_referral": district_helplines.referral_line(dialect, "photo") in farmer_text,
        "referral_expected": kind_referral,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photo", action="append", choices=sorted(PHOTOS), help="repeatable; default all")
    ap.add_argument("--runs", type=int, default=10, help="first-pass runs per photo")
    ap.add_argument("--confirmed-runs", type=int, default=3, help="confirmed-crop runs per photo")
    ap.add_argument("--dialect", default="mr")
    ap.add_argument("--crop", default="Cotton", help="profile crop, and the crop tapped on the confirmed path")
    ap.add_argument("--workers", type=int, default=4, help="parallel confirmed-path calls")
    ap.add_argument("--out", default=f"/tmp/vision-replay-{time.strftime('%Y%m%d-%H%M%S')}.json")
    args = ap.parse_args()

    _setup_env()
    import analyzer  # noqa: E402
    from enforcement import format_crop_message  # noqa: E402
    from common import advice_filter  # noqa: E402

    advice_filter._cloudwatch = MagicMock()

    analyzer.TEMP_BUCKET = os.environ["TEMP_AUDIO_BUCKET"]
    fake_s3 = MagicMock()
    fake_s3.put_object.return_value = {}
    analyzer.s3 = fake_s3
    vision_call = analyzer.analyze_crop_image
    first_pass_lock = threading.Lock()

    def first_pass(image: bytes, tag: str) -> dict:
        # process_image_message reads module globals, so patch them one run at a time.
        calls: list = []

        def spy(*a, **k):
            v = vision_call(*a, **k)
            calls.append(v)
            return v

        with first_pass_lock:
            analyzer.download_whatsapp_image = lambda _mid: image
            analyzer.analyze_crop_image = spy
            try:
                out = analyzer.process_image_message(
                    {"image": {"id": tag}, "from": "replay"},
                    {"dialect": args.dialect, "crop": args.crop, "district": "Latur", "phone_number": "replay"},
                )
            finally:
                analyzer.analyze_crop_image = vision_call
        # calls[0] is the blind first pass (crop inference); on the assume branch a
        # second call diagnoses with the assumed crop, and that is what the farmer sees.
        blind = calls[0] if calls else {}
        shown = calls[-1] if calls else {}
        pending = out.get("pending_crop_confirm") or {}
        rec = shown.get("recommendations") or ""
        # Same call the handler makes before sending.
        referral = not pending or bool(pending.get("assumed"))
        farmer_text = advice_filter.filter_advice(
            out.get("text") or "", args.dialect, "replay", kind="photo", district="Latur", add_referral=referral
        )
        return {
            "branch": "ask" if out.get("buttons") else ("assume" if pending.get("assumed") else "direct"),
            "vision_calls": len(calls),
            "inferred_crop": blind.get("inferred_crop"),
            "crop_confidence": blind.get("crop_confidence"),
            "insects_visible": shown.get("insects_visible"),
            "buttons": out.get("buttons"),
            "diagnosis": shown.get("diagnosis"),
            "recommendations": rec,
            "confidence_text": shown.get("confidence_text"),
            "reply_text": out.get("text"),
            "farmer_text": farmer_text,
            **_flags(rec),
            **_farmer_flags(tag[0], rec, farmer_text, referral, args.dialect),
        }

    def confirmed(image: bytes, photo: str) -> dict:
        v = vision_call(image, args.dialect, args.crop, district="Latur", confirmed_crop=True)
        rec = v.get("recommendations") or ""
        reply = format_crop_message(v, args.crop, args.dialect, assumed=False)
        farmer_text = advice_filter.filter_advice(reply, args.dialect, "replay", kind="photo", district="Latur")
        return {
            "inferred_crop": v.get("inferred_crop"),
            "insects_visible": v.get("insects_visible"),
            "diagnosis": v.get("diagnosis"),
            "recommendations": rec,
            "confidence_text": v.get("confidence_text"),
            "reply_text": reply,
            "farmer_text": farmer_text,
            **_flags(rec),
            **_farmer_flags(photo, rec, farmer_text, True, args.dialect),
        }

    photos = args.photo or sorted(PHOTOS)
    jobs = []
    for name in photos:
        image = PHOTOS[name].read_bytes()
        jobs += [("first", name, i, image) for i in range(args.runs)]
        jobs += [("confirmed", name, i, image) for i in range(args.confirmed_runs)]

    def run(job):
        path, name, i, image = job
        try:
            r = first_pass(image, f"{name}{i}") if path == "first" else confirmed(image, name)
        except Exception as e:
            r = {"error": f"{type(e).__name__}: {e}"}
        return {"photo": name, "path": path, "run": i + 1, **r}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run, jobs))

    meta = {
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": os.environ["BEDROCK_MODEL_ID"],
        "dialect": args.dialect,
        "crop": args.crop,
        "runs": args.runs,
        "confirmed_runs": args.confirmed_runs,
    }
    Path(args.out).write_text(json.dumps({"meta": meta, "results": results}, ensure_ascii=False, indent=2))

    print(f"\nWrote {args.out}\n")
    for name in photos:
        mine = [r for r in results if r["photo"] == name]
        first = [r for r in mine if r["path"] == "first" and "error" not in r]
        conf = [r for r in mine if r["path"] == "confirmed" and "error" not in r]
        errors = [r for r in mine if "error" in r]
        branches = {b: sum(r["branch"] == b for r in first) for b in ("assume", "ask", "direct")}
        crops: dict = {}
        for r in first:
            crops[r["inferred_crop"]] = crops.get(r["inferred_crop"], 0) + 1
        insects: dict = {}
        for r in first + conf:
            for x in r.get("insects_visible") or []:
                insects[x] = insects.get(x, 0) + 1
        def rates(rows):
            n = len(rows)
            c = lambda k: f"{sum(bool(r.get(k)) for r in rows)}/{n}"  # noqa: E731
            return (f"model: product={c('model_names_product')} dose={c('model_gives_dose')}"
                    f" filter_would_fire={sum(bool(r.get('model_filter_kinds')) for r in rows)}/{n}\n"
                    f"              farmer: product={c('farmer_names_product')} dose={c('farmer_gives_dose')}"
                    f" pest_named={c('farmer_pest_named')} non_chemical_steps={c('farmer_non_chemical_steps')}"
                    f" referral={c('farmer_referral')} asks_photo={c('asks_photo')}")

        print(f"Photo {name}")
        print(f"  first pass  n={len(first)}  branches={branches}  inferred_crop={crops}")
        print(f"              {rates(first)}")
        print(f"  confirmed   n={len(conf)}  {rates(conf)}")
        print(f"  insects     {insects}")
        if errors:
            print(f"  errors      {len(errors)}: {errors[0]['error'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
