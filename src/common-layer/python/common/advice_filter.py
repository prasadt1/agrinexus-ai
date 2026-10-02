"""
Output filter for farmer-facing advice.

The product identifies the pest or problem and gives non-chemical steps. It does
not name pesticide products, active ingredients, formulation strengths or doses
on any channel; chemical choice and rate are referred to the farmer's KVK.
Prompts ask the model for this, but prompts are not a control: every advice
message passes through filter_advice() before it is sent or spoken.

A sentence (or numbered step) that names an active ingredient or brand, gives a
formulation strength (e.g. "50% EC"), or gives a dilution (e.g. "2 ml per litre")
is dropped. A bare quantity ("500 g", "10 litres") is dropped only when the same
sentence is about spraying, mixing, a pesticide, neem or a trap, so fertilizer
and irrigation amounts survive. Neem, sticky traps and pheromone traps are
allowed as practices; a quantity attached to them is not.
"""
import os
import re
from typing import Dict, List, Optional, Set, Tuple

from common.district_helplines import KISAN_CALL_CENTRE, REFERRAL_LINES, referral_footer

METRIC_NAMESPACE = "AgriNexus/Advice"
METRIC_NAME = "AdviceFilterHit"

_DIGITS = str.maketrans("०१२३४५६७८९౦౧౨౩౪౫౬౭౮౯", "01234567890123456789")

_CHAR_FOLDS = (
    ("\u200c", ""), ("\u200d", ""), ("\u093c", ""),      # ZWNJ, ZWJ, nukta
    ("ॅ", "े"), ("ॉ", "ो"), ("ँ", "ं"), ("ऍ", "ए"), ("ऑ", "ओ"),
    ("न्", "ं"), ("म्", "ं"),
)


def _normalize(text: str) -> str:
    """Fold spelling variants so one stem matches the model's different transliterations."""
    out = (text or "").lower().translate(_DIGITS)
    for a, b in _CHAR_FOLDS:
        out = out.replace(a, b)
    return out


# Active ingredients the model has produced in replays and live replies, plus
# common ones from the same classes. Devanagari and Telugu entries are stems
# as written in Marathi, Hindi and Telugu replies.
_ACTIVES_LATIN = (
    "imidacloprid", "thiamethoxam", "profenofos", "cypermethrin", "chlorantraniliprole",
    "spinosad", "quinalphos", "dimethoate", "acephate", "emamectin", "fipronil",
    "cyhalothrin", "buprofezin", "diafenthiuron", "chlorpyrifos", "monocrotophos",
    "triazophos", "indoxacarb", "flubendiamide", "novaluron", "malathion", "carbaryl",
    "carbofuran", "phorate", "acetamiprid", "clothianidin", "dinotefuran", "flonicamid",
    "pyriproxyfen", "spiromesifen", "bifenthrin", "deltamethrin", "fenvalerate",
    "endosulfan", "paraquat", "glyphosate", "mancozeb", "carbendazim", "hexaconazole",
    "propiconazole", "tebuconazole", "copper oxychloride", "metalaxyl", "thiophanate",
    "tricyclazole", "azoxystrobin", "spinetoram", "lufenuron", "thiodicarb",
    "azadirachtin",
)
_ACTIVES_INDIC = (
    # Devanagari (Marathi / Hindi)
    "इमिडाक्लोप्रिड", "इमिडाक्लोप्रीड", "इमिडॅक्लोप्रिड",
    "थायामेथॉक्झाम", "थायामेथोक्साम", "थायमेथोक्साम", "थियामेथोक्साम", "थायोमेथॉक्झाम",
    "प्रोफेनोफॉस", "प्रोफेनोफोस",
    "सायपरमेथ्रिन", "साइपरमेथ्रिन", "सायपरमेथ्रीन",
    "क्लोरँट्रानिलिप्रोल", "क्लोरॅन्ट्रानिलिप्रोल", "क्लोरेंट्रानिलिप्रोल", "क्लोरान्ट्रानिलिप्रोल",
    "स्पिनोसॅड", "स्पिनोसैड", "स्पिनोसाड",
    "क्विनॉलफॉस", "क्विनालफॉस", "क्विनालफोस",
    "डायमेथोएट", "डाइमेथोएट", "डायमिथोएट",
    "अॅसिफेट", "ऍसिफेट", "एसिफेट", "असिफेट",
    "इमामेक्टिन", "इमामेक्टीन", "एमामेक्टिन",
    "फिप्रोनिल", "फिप्रोनील",
    "सायहॅलोथ्रिन", "साइहैलोथ्रिन", "सायहलोथ्रिन", "लॅम्बडा", "लैम्बडा", "लॅम्ब्डा",
    "बुप्रोफेझिन", "बुप्रोफेजिन", "ब्युप्रोफेझिन",
    "डायफेंथियुरॉन", "डायफेन्थियुरॉन", "डायफेंथियूरॉन", "डाइफेंथियूरॉन",
    "क्लोरपायरीफॉस", "क्लोरपायरिफॉस", "क्लोरपायरीफोस", "क्लोरोपायरीफॉस",
    "मोनोक्रोटोफॉस", "ट्रायझोफॉस", "इंडोक्झाकार्ब", "इंडोक्साकार्ब", "फ्लुबेंडियामाइड",
    "अझाडिरेक्टिन", "अॅझाडिरॅक्टिन", "एज़ाडिरेक्टिन", "एजाडिरेक्टिन", "अजाडिरेक्टिन",
    "मॅलेथिऑन", "मैलाथियान", "मॅन्कोझेब", "मैन्कोजेब", "कार्बेन्डाझिम", "कार्बेन्डाजिम",
    "हेक्झाकोनाझोल", "हेक्साकोनाजोल", "प्रोपिकोनाझोल", "अॅसिटामिप्रिड", "एसिटामिप्रिड",
    "कॉपर ऑक्सिक्लोराईड", "कॉपर ऑक्सीक्लोराइड",
    # Telugu
    "ఇమిడాక్లోప్రిడ్", "థయామెథాక్సామ్", "థియామెథాక్సామ్", "ప్రొఫెనోఫాస్", "ప్రోఫెనోఫాస్",
    "సైపర్‌మెత్రిన్", "సైపర్మెత్రిన్", "క్లోరాంట్రానిలిప్రోల్", "క్లోరంట్రానిలిప్రోల్",
    "స్పినోసాడ్", "క్వినాల్‌ఫాస్", "క్వినాల్ఫాస్", "డైమిథోయేట్", "డైమెథోయేట్",
    "ఎసిఫేట్", "అసిఫేట్", "ఎమామెక్టిన్", "ఫిప్రోనిల్", "లాంబ్డా", "సైహలోత్రిన్",
    "బుప్రోఫెజిన్", "డయాఫెంథియురాన్", "డయాఫెన్థియురాన్", "క్లోర్‌పైరిఫాస్", "క్లోర్పైరిఫాస్",
    "మాంకోజెబ్", "కార్బెండజిమ్",
)
# Brand names seen in replies ("जसे की कॉन्फिडॉर") and common equivalents.
_BRANDS = (
    "confidor", "actara", "coragen", "ampligo", "ulala", "pegasus", "tracer",
    "कॉन्फिडॉर", "कॉन्फिडोर", "अॅक्टारा", "ऍक्टारा", "एक्टारा", "कोराजेन", "कोरेजन",
    "కాన్ఫిడార్", "ఆక్టారా", "కొరాజెన్",
)

_LATIN_TERMS = tuple(_normalize(t) for t in _ACTIVES_LATIN + _BRANDS if t.isascii())
_INDIC_TERMS = tuple(dict.fromkeys(_normalize(t) for t in _ACTIVES_INDIC + _BRANDS if not t.isascii()))
_LATIN_RE = re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(t) for t in _LATIN_TERMS) + r")")

_FORMULATION_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:ppm(?![a-z])|पीपीएम|%\s*(?:ec|sl|wg|wdg|sc|wp|sg|sp|gr|cs|od|ew|fs|zc|ds|ws)(?![a-z])"
    r"|%?\s*(?:ec|sl|wg|wdg|sc|wp|sg|od|ew|zc)(?![a-z])"
    r"|%?\s*-?\s*(?:ईसी|ई\.सी\.|एसएल|एस\.एल\.|डब्ल्यूजी|डब्लूजी|डब्ल्यूडीजी|डब्ल्यूपी|डब्लूपी|एससी|एस\.सी\.|एसजी|ఈసీ|ఎస్ఎల్|డబ్ల్యూజీ|డబ్ల్యూపీ|ఎస్సీ))"
)

_QTY = r"\d+(?:[.,]\d+)?(?:\s*(?:-|–|to|ते|से)\s*\d+(?:[.,]\d+)?)?"
_UNITS = tuple(
    sorted(
        {
            _normalize(u)
            for u in (
                "millilitres", "milliliters", "millilitre", "milliliter", "ml",
                "grams", "gram", "gms", "gm", "g", "kgs", "kg", "kilograms", "kilogram",
                "litres", "liters", "litre", "liter", "ltr", "lit", "lt", "l",
                "मिलीलीटर", "मिलीलिटर", "मि.ली.", "मि.ली", "मिली", "मिलि",
                "ग्रॅम", "ग्राम", "ग्रा.", "ग्रा", "किलोग्राम", "किलो", "कि.ग्रा.", "किग्रा",
                "लिटर", "लीटर", "ली.",
                "మి.లీ", "మిల్లీలీటర్", "మిల్లీ", "మిలీ", "గ్రాములు", "గ్రాము", "గ్రా",
                "కిలోగ్రాములు", "కిలో", "లీటర్లు", "లీటర్", "లీటరు", "లీ",
            )
        },
        key=len,
        reverse=True,
    )
)
_UNIT = r"(?:" + "|".join(re.escape(u) for u in _UNITS) + r")(?![a-z])"
_PER = r"(?:/|per|प्रति|प्रती|ప్రతి|in|मध्ये|में)"
_LITRE = r"(?:लिटर|लीटर|litre|liter|ltr|lit|l(?![a-z])|लि|लीटर|లీటర్|లీటరు|లీ|pump|tank|पंप|टाकी|టాంక్)"

_DILUTION_RE = re.compile(_QTY + r"\s*" + _UNIT + r"\s*" + _PER + r"\s*(?:" + _QTY + r"\s*)?" + _LITRE)
_QUANTITY_RE = re.compile(_QTY + r"\s*" + _UNIT)

_SPRAY_CONTEXT = tuple(
    _normalize(w)
    for w in (
        "spray", "mix", "dilute", "pesticide", "insecticide", "fungicide", "herbicide",
        "neem", "trap",
        "फवार", "मिसळ", "कीटकनाशक", "कीटनाशक", "किटकनाशक", "बुरशीनाशक", "फफूंदनाशक", "तणनाशक",
        "छिडक", "छिड़क", "घोल", "स्प्रे", "निंबोळी", "लिंबोळी", "नीम", "कडुलिंब", "कडूलिंब",
        "सापळ", "ट्रॅप", "ट्रैप",
        "పిచికారీ", "స్ప్రే", "కలిపి", "కలప", "పురుగుమందు", "క్రిమిసంహారక", "వేప", "ట్రాప్", "ఎర",
    )
)

_ABBREVIATIONS = tuple(_normalize(a) for a in ("मि", "ली", "ग्रा", "कि", "मि.ली", "कि.ग्रा", "డా", "మి", "e.g", "i.e", "approx", "dr", "no"))
_ENUM_RE = re.compile(r"(?:^|(?<=[\s,;:]))(\(?)([0-9०-९౦-౯]{1,2})([).])(?=\s)")
_LABEL_RE = re.compile(r"^\s*\*[^*\n]+\*\s*")


def classify(segment: str) -> Set[str]:
    """Kinds of chemical advice found in one sentence: active, formulation, dose."""
    norm = _normalize(segment)
    kinds: Set[str] = set()
    if _LATIN_RE.search(norm) or any(t in norm for t in _INDIC_TERMS):
        kinds.add("active")
    if _FORMULATION_RE.search(norm):
        kinds.add("formulation")
    if _DILUTION_RE.search(norm) or (
        _QUANTITY_RE.search(norm) and any(w in norm for w in _SPRAY_CONTEXT)
    ):
        kinds.add("dose")
    return kinds


def _segments(text: str) -> List[str]:
    """Split a line into sentences and numbered steps, keeping all original characters."""
    cuts = {0, len(text)}
    for m in re.finditer(r"[।?!॥]|\.(?=\s|$)", text):
        if m.group() == ".":
            tok = re.search(r"(\S+)$", text[: m.start()])
            t = _normalize(tok.group(1).lstrip("(")) if tok else ""
            if t.isdigit() or any(t == a or t.endswith(a) and len(t) <= len(a) + 3 for a in _ABBREVIATIONS):
                continue
            if text[: m.start()][-1:].isdigit() and text[m.end(): m.end() + 1].isdigit():
                continue
        cuts.add(m.end())
    for m in _ENUM_RE.finditer(text):
        cuts.add(m.start())
    ordered = sorted(cuts)
    return [text[a:b] for a, b in zip(ordered, ordered[1:]) if text[a:b]]


def _renumber(parts: List[str]) -> List[str]:
    n = 0
    out = []
    for p in parts:
        m = _ENUM_RE.match(p)
        if m:
            n += 1
            digits = m.group(2)
            if digits[0] in "०१२३४५६७८९":
                num = str(n).translate(str.maketrans("0123456789", "०१२३४५६७८९"))
            elif digits[0] in "౦౧౨౩౪౫౬౭౮౯":
                num = str(n).translate(str.maketrans("0123456789", "౦౧౨౩౪౫౬౭౮౯"))
            else:
                num = str(n)
            p = f"{m.group(1)}{num}{m.group(3)}" + p[m.end():]
        out.append(p)
    return out


def _filter_line(line: str, hits: List[Tuple[str, Set[str]]]) -> Optional[str]:
    label_m = _LABEL_RE.match(line)
    label = label_m.group(0) if label_m else ""
    body = line[len(label):]
    if not body.strip():
        return line
    kept = []
    segments = _segments(body)
    for seg in segments:
        kinds = classify(seg)
        if kinds:
            hits.append((seg.strip(), kinds))
            end = re.search(r"[।.?!॥]$", seg.strip())
            if end and kept:
                prev = re.sub(r"[\s,;:]+$", "", kept[-1])
                if not re.search(r"[।.?!॥]$", prev):
                    prev += end.group()
                kept[-1] = prev + " "
        else:
            kept.append(seg)
    if len(kept) == len(segments):
        return line
    kept = _renumber(kept)
    joined = re.sub(r" {2,}", " ", "".join(kept)).strip()
    joined = re.sub(r"[\s,;:]+$", "", joined)
    if joined and not re.search(r"[।.?!॥]$", joined):
        joined += "।" if re.search(r"[\u0900-\u097F]", joined) and "।" in line else "."
    if not joined or re.fullmatch(r"[^\w\u0900-\u0D7F]*", joined):
        return label.rstrip() + " —" if label else None
    return label + joined


_PESTICIDE_QUESTION = tuple(
    _normalize(w)
    for w in (
        "spray", "pesticide", "insecticide", "fungicide", "herbicide", "weedicide", "chemical", "dose", "neem",
        "फवार", "कीटकनाशक", "कीटनाशक", "किटकनाशक", "बुरशीनाशक", "फफूंदनाशक", "तणनाशक", "खरपतवारनाशक",
        "छिडक", "छिड़क", "स्प्रे", "औषध", "दवा", "दवाई", "निंबोळी", "लिंबोळी", "नीम", "कडुलिंब", "कडूलिंब",
        "పిచికారీ", "స్ప్రే", "పురుగుమందు", "క్రిమిసంహారక", "మందు", "వేప",
    )
)

# Used instead of a knowledge-base refusal when the farmer asked about a pesticide or spray,
# so the reply states the policy rather than implying the system would answer if it knew.
PESTICIDE_POLICY = {
    "en": (
        "I can't give pesticide names or quantities. Send a photo of the affected plant and "
        "I will try to identify the pest or disease."
    ),
    "hi": (
        "मैं कीटनाशक के नाम या मात्रा नहीं बता सकता। प्रभावित पौधे की फोटो भेजें, "
        "मैं कीट या रोग पहचानने की कोशिश करूँगा।"
    ),
    "mr": (
        "मी कीटकनाशकांची नावे किंवा प्रमाण सांगू शकत नाही. बाधित झाडाचा फोटो पाठवा, "
        "मी कीड किंवा रोग ओळखण्याचा प्रयत्न करेन."
    ),
    "te": (
        "నేను పురుగుమందుల పేర్లు లేదా మోతాదులు చెప్పలేను. ప్రభావిత మొక్క ఫోటో పంపండి, "
        "పురుగు లేదా తెగులును గుర్తించడానికి ప్రయత్నిస్తాను."
    ),
}


def is_pesticide_question(text: str) -> bool:
    t = _normalize(text or "")
    return any(w in t for w in _PESTICIDE_QUESTION)


def pesticide_policy(dialect: str) -> str:
    return PESTICIDE_POLICY.get((dialect or "en").strip().lower(), PESTICIDE_POLICY["en"])


def _has_referral(text: str) -> bool:
    return any(line in text for lines in REFERRAL_LINES.values() for line in lines.values())


def filter_advice(
    text: str,
    dialect: str,
    channel: str,
    kind: str = "answer",
    district: Optional[str] = None,
    add_referral: bool = True,
) -> str:
    """
    Remove chemical product and dose advice from a farmer-facing message and make
    sure it ends with the KVK referral. kind is "photo" or "answer" (text/voice).
    """
    if not text:
        return text
    hits: List[Tuple[str, Set[str]]] = []
    out_lines = []
    for line in text.split("\n"):
        filtered = _filter_line(line, hits)
        if filtered is not None:
            out_lines.append(filtered)
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(out_lines)).strip()

    if hits:
        kinds = sorted({k for _, ks in hits for k in ks})
        print(f"Advice filter removed {len(hits)} segment(s) channel={channel} kinds={','.join(kinds)}")
        _emit_metric(channel, hits)

    if add_referral and not _has_referral(out):
        footer = referral_footer(dialect, kind, district)
        if KISAN_CALL_CENTRE in out:
            footer = "\n\n" + footer.strip().split("\n")[0]
        out = out + footer
    return out


_cloudwatch = None


def _emit_metric(channel: str, hits: List[Tuple[str, Set[str]]]) -> None:
    global _cloudwatch
    counts: Dict[str, int] = {}
    for _, kinds in hits:
        for k in kinds:
            counts[k] = counts.get(k, 0) + 1
    try:
        if _cloudwatch is None:
            import boto3

            _cloudwatch = boto3.client("cloudwatch", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        _cloudwatch.put_metric_data(
            Namespace=METRIC_NAMESPACE,
            MetricData=[
                {
                    "MetricName": METRIC_NAME,
                    "Dimensions": [{"Name": "Channel", "Value": channel}, {"Name": "Kind", "Value": k}],
                    "Value": float(v),
                    "Unit": "Count",
                }
                for k, v in sorted(counts.items())
            ]
            + [
                {
                    "MetricName": METRIC_NAME,
                    "Dimensions": [{"Name": "Channel", "Value": channel}],
                    "Value": 1.0,
                    "Unit": "Count",
                }
            ],
        )
    except Exception as e:
        print(f"Advice filter metric failed: {type(e).__name__}: {e}")
