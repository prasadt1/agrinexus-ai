"""
Output filter for farmer-facing advice.

The product identifies the pest or problem and gives non-chemical steps. It does
not name pesticide products, active ingredients, formulation strengths or doses
on any channel; chemical choice and rate are referred to the farmer's KVK.
Prompts ask the model for this, but prompts are not a control: every advice
message passes through filter_advice() before it is sent or spoken.

A sentence (or numbered step) that names an active ingredient, a brand or a chemical
class (e.g. "pyrethroids"), gives a formulation strength (e.g. "50% EC"), or gives a
dilution (e.g. "2 ml per litre") is dropped. A bare quantity ("500 g", "10 litres") is dropped only when the same
sentence is about spraying, mixing, a pesticide, neem or a trap, so fertilizer
and irrigation amounts survive. Neem, sticky traps and pheromone traps are
allowed as practices; a quantity attached to them is not.
"""
import os
import re
from typing import Dict, List, Optional, Set, Tuple

from common.district_helplines import KISAN_CALL_CENTRE, REFERRAL_LINES, referral_footer
from common.source_line import is_source_line, strip_source_lines

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
    "azadirachtin", "cartap", "dichlorvos", "methomyl", "chlorfenapyr", "dicofol",
    "pendimethalin", "atrazine", "chlorothalonil", "streptocycline", "validamycin",
    "sulfoxaflor", "etofenprox", "pymetrozine",
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
    "कार्टाप", "कारटाप", "डायक्लोरव्हॉस", "डायक्लोरवॉस", "डाइक्लोरवास", "डायक्लोरवास",
    "मेथोमिल", "मिथोमिल", "मेथोमाइल", "क्लोरफेनापायर", "क्लोरफेनपायर", "क्लोरफेनापिर",
    "डायकोफॉल", "डाइकोफोल", "डायकोफोल", "पेंडीमेथालिन", "पेंडिमेथालिन", "पेंडीमिथेलिन",
    "अॅट्राझिन", "अॅट्राझीन", "एट्राजीन", "एट्राजिन", "अट्राझिन",
    "क्लोरोथॅलोनिल", "क्लोरोथालोनिल", "क्लोरोथैलोनिल",
    "स्ट्रेप्टोसायक्लिन", "स्ट्रेप्टोसाइक्लिन", "स्ट्रेप्टोसायक्लीन",
    "व्हॅलिडामायसिन", "वैलिडामाइसिन", "वॅलिडामायसिन", "व्हॅलिडामायसीन",
    "सल्फोक्साफ्लोर", "सल्फॉक्साफ्लोर", "इटोफेनप्रॉक्स", "एटोफेनप्रोक्स", "पायमेट्रोझिन", "पाइमेट्रोजीन",
    # Telugu
    "ఇమిడాక్లోప్రిడ్", "థయామెథాక్సామ్", "థియామెథాక్సామ్", "ప్రొఫెనోఫాస్", "ప్రోఫెనోఫాస్",
    "సైపర్‌మెత్రిన్", "సైపర్మెత్రిన్", "క్లోరాంట్రానిలిప్రోల్", "క్లోరంట్రానిలిప్రోల్",
    "స్పినోసాడ్", "క్వినాల్‌ఫాస్", "క్వినాల్ఫాస్", "డైమిథోయేట్", "డైమెథోయేట్",
    "ఎసిఫేట్", "అసిఫేట్", "ఎమామెక్టిన్", "ఫిప్రోనిల్", "లాంబ్డా", "సైహలోత్రిన్",
    "బుప్రోఫెజిన్", "డయాఫెంథియురాన్", "డయాఫెన్థియురాన్", "క్లోర్‌పైరిఫాస్", "క్లోర్పైరిఫాస్",
    "మాంకోజెబ్", "కార్బెండజిమ్",
    "కార్టాప్", "డైక్లోర్వాస్", "డైక్లోరోవాస్", "మెథోమిల్", "క్లోర్ఫెనాపైర్", "డైకోఫాల్",
    "పెండిమిథాలిన్", "పెండిమెథాలిన్", "అట్రాజిన్", "ఆట్రాజిన్", "క్లోరోథలోనిల్",
    "స్ట్రెప్టోసైక్లిన్", "వాలిడామైసిన్",
)
# Banned for manufacture, import and use in India (CIB&RC list). Named so a banned
# active is removed even when no class ending or other list covers it.
_BANNED_IN_INDIA = (
    "aldicarb", "aldrin", "benzene hexachloride", "bhc", "calcium cyanide", "chlordane",
    "copper acetoarsenite", "dibromochloropropane", "dieldrin", "endrin", "ethyl mercury chloride",
    "ethyl parathion", "heptachlor", "lindane", "maleic hydrazide", "menazone", "nitrofen",
    "paraquat dimethyl sulphate", "pentachloronitrobenzene", "pentachlorophenol",
    "phenyl mercury acetate", "sodium methane arsonate", "tetradifon", "toxaphene", "camphechlor",
    "benomyl", "carbaryl", "diazinon", "fenarimol", "fenthion", "linuron", "methyl parathion",
    "thiometon", "tridemorph", "trifluralin", "alachlor", "dichlorvos", "phorate", "phosphamidon",
    "triazophos", "trichlorfon", "endosulfan", "ddt",
    "एंडोसल्फान", "एन्डोसल्फान", "एंडोसल्फॉन", "लिंडेन", "लिंडेन", "डीडीटी", "बीएचसी", "फोरेट",
    "फॉस्फामिडॉन", "फॉस्फामिडोन", "फास्फामिडान", "पैराथियान", "पॅराथिऑन", "पॅराथियॉन",
    "ऍल्ड्रिन", "अॅल्ड्रिन", "एल्ड्रिन", "डिल्ड्रिन", "डायल्ड्रिन", "क्लोरडेन", "क्लोर्डेन", "हेप्टाक्लोर",
    "ఎండోసల్ఫాన్", "లిండేన్", "డిడిటి", "డీడీటీ", "ఫోరేట్", "పారాథియాన్", "ఆల్డ్రిన్", "డైల్డ్రిన్",
)

# Brand names seen in replies ("जसे की कॉन्फिडॉर") and common equivalents.
_BRANDS = (
    "confidor", "actara", "coragen", "ampligo", "ulala", "pegasus", "tracer",
    "rogor", "karate", "regent", "lannate",
    "कॉन्फिडॉर", "कॉन्फिडोर", "अॅक्टारा", "ऍक्टारा", "एक्टारा", "कोराजेन", "कोरेजन",
    "కాన్ఫిడార్", "ఆక్టారా", "కొరాజెన్",
)

# Short brand names that are also parts of ordinary words (रोगर in रोगराई) only match
# when no letter of the same script follows.
_BOUNDED_BRANDS_INDIC = (
    "रोगर", "रोगोर", "कराटे", "रीजेंट", "रिजेंट", "लॅनेट", "लैनेट", "लेनेट",
    "రోగర్", "కరాటే", "రీజెంట్", "లానేట్",
)
_BOUNDED_INDIC_RE = re.compile(
    r"(?:" + "|".join(re.escape(_normalize(t)) for t in _BOUNDED_BRANDS_INDIC) + r")(?![\u0900-\u097F\u0C00-\u0C7F])"
)
_TWO_FOUR_D_RE = re.compile(r"(?<!\d)2\s*,\s*4\s*-?\s*(?:d(?![a-z])|डी|డి)")

# Fallback for actives not in the lists: most share a name ending by chemical class.
_SUFFIX_LATIN_RE = re.compile(
    r"\b[a-z]+(?:fos|phos|thrin|conazole|cloprid|amiprid|carb|mectin|iliprole|diamide|thoate"
    r"|achlor|fop|uron|buzin|zeb|ineb|mycin|apyr|pyrad|meton|thion|sulfuron)\b"
)
_SUFFIX_INDIC_RE = re.compile(
    r"[\u0900-\u097F]{2,}(?:" + "|".join(re.escape(_normalize(x)) for x in (
        "फॉस", "थ्रिन", "थ्रीन", "कोनाझोल", "कोनाजोल", "क्लोप्रिड", "क्लोप्रीड", "मिप्रिड",
        "मेक्टिन", "थोएट", "मायसिन", "माइसिन", "लाक्लोर", "युरॉन", "बुझिन", "बुजिन",
    )) + r")"
    r"|[\u0C00-\u0C7F]{2,}(?:" + "|".join(re.escape(_normalize(x)) for x in (
        "ఫాస్", "త్రిన్", "కోనజోల్", "క్లోప్రిడ్", "మైసిన్", "మెక్టిన్", "థోయేట్",
    )) + r")"
)

# Chemical classes. A class is not a product, but a sentence that names one still tells
# the farmer which kind of chemical to use or to avoid, and that choice belongs to the KVK.
_CLASS_LATIN_RE = re.compile(
    r"(?<![a-z])(?:pyrethr(?:oid|in)s?|organo-?phosph(?:ate|orus)[a-z]*|organo-?chlorines?"
    r"|neonicotinoids?|neonics?|carbamates?|diamides?|triazoles?|strobilurins?"
    r"|benzimidazoles?|avermectins?|sulfonylureas?)(?![a-z])"
)
# Devanagari stems as the class names are usually transliterated. Telugu is not covered.
_CLASS_INDIC = tuple(
    _normalize(x)
    for x in (
        "पायरेथ्र", "पाइरेथ्र", "पायरिथ्र", "ऑर्गनोफॉस्फ", "ऑर्गेनोफॉस्फ", "ऑर्गॅनोफॉस्फ",
        "निओनिकोटिन", "नियोनिकोटिन", "कार्बामेट",
    )
)

_LATIN_TERMS = tuple(_normalize(t) for t in _ACTIVES_LATIN + _BANNED_IN_INDIA + _BRANDS if t.isascii())
_INDIC_TERMS = tuple(dict.fromkeys(
    _normalize(t) for t in _ACTIVES_INDIC + _BANNED_IN_INDIA + _BRANDS if not t.isascii()
))
_LATIN_RE = re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(t) for t in _LATIN_TERMS) + r")")

_FORMULATION_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:ppm(?![a-z])|पीपीएम|%\s*(?:ec|sl|wg|wdg|sc|wp|sg|sp|gr|cs|od|ew|fs|zc|ds|ws)(?![a-z])"
    r"|%?\s*(?:ec|sl|wg|wdg|sc|wp|sg|od|ew|zc)(?![a-z])"
    r"|%?\s*-?\s*(?:ईसी|ई\.सी\.|एसएल|एस\.एल\.|डब्ल्यूजी|डब्लूजी|डब्ल्यूडीजी|डब्ल्यूपी|डब्लूपी|एससी|एस\.सी\.|एसजी|ఈసీ|ఎస్ఎల్|డబ్ల్యూజీ|డబ్ల్యూపీ|ఎస్సీ))"
)

_NUMBER_WORDS = tuple(
    sorted(
        {
            _normalize(w)
            for w in (
                "one", "two", "three", "four", "five", "six", "ten", "half", "quarter",
                "एक", "दो", "तीन", "चार", "पांच", "पाँच", "आधा", "आधी", "आधे", "डेढ़", "ढाई", "सवा",
                "दोन", "पाच", "अर्धा", "अर्धी", "अर्धे", "दीड", "अडीच", "सव्वा", "पाव",
                "ఒక", "ఒకటి", "రెండు", "మూడు", "నాలుగు", "ఐదు", "అర",
            )
        },
        key=len,
        reverse=True,
    )
)
_NUM = (
    r"(?:\d+(?:[.,]\d+)?|(?<![a-z\u0900-\u097F\u0C00-\u0C7F])(?:"
    + "|".join(re.escape(w) for w in _NUMBER_WORDS)
    + r")(?:\s+an?(?=\s))?)"
)
_QTY = _NUM + r"(?:\s*(?:-|–|to|or|ते|से|किंवा|या)\s*" + _NUM + r")?"
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
_SMALL_UNIT = r"(?:" + "|".join(
    re.escape(_normalize(u)) for u in sorted(
        ("millilitres", "milliliters", "millilitre", "milliliter", "ml", "grams", "gram", "gms", "gm", "g",
         "litres", "liters", "litre", "liter", "ltr", "l",
         "मिलीलीटर", "मिलीलिटर", "मि.ली.", "मि.ली", "मिली", "मिलि", "ग्रॅम", "ग्राम", "ग्रा", "लिटर", "लीटर",
         "మి.లీ", "మిల్లీలీటర్", "మిలీ", "గ్రాములు", "గ్రాము", "గ్రా", "లీటర్లు", "లీటర్", "లీటరు"),
        key=len, reverse=True)
) + r")(?![a-z])"
_AREA = r"(?:acres?|ha(?![a-z])|hectares?|एकर|एकड़|एकड|हेक्टर|हेक्टेयर|हेक्टेअर|ఎకరా|ఎకరాకు|ఎకరానికి|హెక్టారు|హెక్టార్)"
_AREA_DOSE_RE = re.compile(
    _QTY + r"\s*" + _SMALL_UNIT + r"\s*" + _PER + r"\s*(?:an?\s+)?" + _AREA
    + r"|" + _AREA + r"\s*(?:" + _PER + r"\s*)?" + _QTY + r"\s*" + _SMALL_UNIT
)

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

# Apply/use verbs count as spray context unless the sentence is about fertilizer, seed or
# irrigation, so "Apply 50 kg urea per acre" survives but "Apply 200 ml per acre" does not.
_USE_VERBS = tuple(
    _normalize(w)
    for w in (
        "apply", "use", "dose", "drench",
        "वापर", "टाका", "टाकावे", "द्यावे", "डालें", "डाले", "डालना", "इस्तेमाल", "प्रयोग", "उपयोग",
        "వాడ", "ఉపయోగ", "వేయ", "చల్ల",
    )
)
_FERTILIZER_OR_SEED = tuple(
    _normalize(w)
    for w in (
        "urea", "dap", "potash", "fertili", "compost", "manure", "fym", "seed", "npk",
        "युरिया", "यूरिया", "खत", "खाद", "डीएपी", "पोटॅश", "पोटाश", "शेणखत", "कंपोस्ट", "बियाणे", "बीज",
        "ఎరువు", "యూరియా", "విత్తన", "కంపోస్ట్",
    )
)
# Irrigation amounts are not doses; this exempts only the apply/use verb rule, so a
# dilution in water is still caught by _DILUTION_RE.
_WATER = tuple(
    _normalize(w)
    for w in ("water", "irrigat", "पाणी", "पाण्य", "पानी", "सिंचन", "सिंचाई", "నీరు", "నీటి", "నీళ్ళు")
)

_ABBREVIATIONS = tuple(_normalize(a) for a in ("मि", "ली", "ग्रा", "कि", "मि.ली", "कि.ग्रा", "డా", "మి", "e.g", "i.e", "approx", "dr", "no"))
_ENUM_RE = re.compile(r"(?:^|(?<=[\s,;:]))(\(?)([0-9०-९౦-౯]{1,2})([).])(?=\s)")
_LABEL_RE = re.compile(r"^\s*\*[^*\n]+\*\s*")

# A step that only says to do it again refers to the step before it; when that step
# was removed, the repeat is dropped too. Repeating a check or inspection stands alone.
_REPEAT_LATIN_RE = re.compile(r"(?<![a-z])(?:repeat\w*|re-?appl\w*|again|more times?)(?![a-z])")
_REPEAT_INDIC = tuple(
    _normalize(w)
    for w in ("दोहरा", "दोबारा", "फिर से", "पुनः", "पुन्हा", "మళ్ళీ", "మళ్లీ", "పునరావృత")
)
_MONITOR = tuple(
    _normalize(w)
    for w in (
        "check", "inspect", "monitor", "scout", "count", "observe",
        "तपास", "जांच", "जाँच", "निरीक्षण", "देखें", "पाहणी", "పరిశీల", "తనిఖీ", "గమనించ",
    )
)


def _is_orphan_repeat(segment: str) -> bool:
    norm = _normalize(segment)
    if not (_REPEAT_LATIN_RE.search(norm) or any(w in norm for w in _REPEAT_INDIC)):
        return False
    return not any(w in norm for w in _MONITOR)


def classify(segment: str) -> Set[str]:
    """Kinds of chemical advice found in one sentence: active, class, formulation, dose."""
    norm = _normalize(segment)
    kinds: Set[str] = set()
    if (
        _LATIN_RE.search(norm)
        or any(t in norm for t in _INDIC_TERMS)
        or _BOUNDED_INDIC_RE.search(norm)
        or _TWO_FOUR_D_RE.search(norm)
        or _SUFFIX_LATIN_RE.search(norm)
        or _SUFFIX_INDIC_RE.search(norm)
    ):
        kinds.add("active")
    if _CLASS_LATIN_RE.search(norm) or any(t in norm for t in _CLASS_INDIC):
        kinds.add("class")
    if _FORMULATION_RE.search(norm):
        kinds.add("formulation")
    fertilizer = any(w in norm for w in _FERTILIZER_OR_SEED)
    spray = any(w in norm for w in _SPRAY_CONTEXT) or (
        not fertilizer
        and not any(w in norm for w in _WATER)
        and any(w in norm for w in _USE_VERBS)
    )
    if (
        _DILUTION_RE.search(norm)
        or (_AREA_DOSE_RE.search(norm) and not fertilizer)
        or (_QUANTITY_RE.search(norm) and spray)
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


def _renumber(parts: List[str], counter: List[int]) -> List[str]:
    """
    Number steps 1, 2, 3 across the whole message. counter is [current, last original].
    A heading ending in ":" or an original number that does not go up starts a new list.
    """
    out = []
    for p in parts:
        m = _ENUM_RE.match(p)
        if not m and p.strip().endswith(":"):
            counter[:] = [0, 0]
        if m:
            digits = m.group(2)
            original = int(digits.translate(_DIGITS))
            counter[0] = 1 if counter[0] == 0 or original <= counter[1] else counter[0] + 1
            counter[1] = original
            n = counter[0]
            if digits[0] in "०१२३४५६७८९":
                num = str(n).translate(str.maketrans("0123456789", "०१२३४५६७८९"))
            elif digits[0] in "౦౧౨౩౪౫౬౭౮౯":
                num = str(n).translate(str.maketrans("0123456789", "౦౧౨౩౪౫౬౭౮౯"))
            else:
                num = str(n)
            p = f"{m.group(1)}{num}{m.group(3)}" + p[m.end():]
        out.append(p)
    return out


def _split_line(line: str, hits: List[Tuple[str, Set[str]]], state: Dict[str, int]):
    """Return (label, kept segments, removed anything) for one line, or None for a blank line."""
    label_m = _LABEL_RE.match(line)
    label = label_m.group(0) if label_m else ""
    body = line[len(label):]
    if not body.strip():
        return None
    kept = []
    segments = _segments(body)
    for seg in segments:
        kinds = classify(seg)
        orphan = not kinds and state["after_removal"] and _is_orphan_repeat(seg)
        if kinds or orphan:
            if kinds:
                hits.append((seg.strip(), kinds))
            else:
                state["orphans"] += 1
            state["after_removal"] = 1
            end = re.search(r"[।.?!॥]$", seg.strip())
            if end and kept:
                prev = re.sub(r"[\s,;:]+$", "", kept[-1])
                if not re.search(r"[।.?!॥]$", prev):
                    prev += end.group()
                kept[-1] = prev + " "
        else:
            kept.append(seg)
            if seg.strip():
                state["after_removal"] = 0
    return label, kept, len(kept) != len(segments)


def _join_line(line: str, label: str, kept: List[str], removed: bool) -> Optional[str]:
    if not removed:
        return label + "".join(kept)
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


# A spray question is about a product ("which spray, how much") or about timing ("is now a
# good time to spray"). The nudge itself tells farmers when the weather suits spraying, so a
# timing question must never get the pesticide-policy reply. Words below are normalized stems.
_SPRAY_WORDS = tuple(_normalize(w) for w in (
    "spray", "spraying", "फवार", "छिडक", "छिड़क", "स्प्रे", "పిచికారీ", "స్ప్రే",
))
_PRODUCT_WORDS = tuple(_normalize(w) for w in (
    # which / what product, how much, dose, name, brand
    "which", "what pesticide", "what insecticide", "what fungicide", "what herbicide", "what chemical",
    "what spray", "what should i spray", "what to spray", "what can i spray", "how much", "how many ml",
    "dose", "dosage", "quantity", "per litre", "per liter", "per acre", "per hectare", "name of", "brand",
    "recommend a", "suggest a", "best pesticide", "best insecticide", "best spray",
    "कौन सा", "कौन सी", "कौनसा", "कौनसी", "कौन से", "किस", "कितना", "कितनी", "कितने", "मात्रा", "नाम", "कौन",
    "कोणते", "कोणती", "कोणता", "कोणत्या", "किती", "प्रमाण", "नाव", "कुठले", "कुठली",
    "ఏ ", "ఏది", "ఎంత", "మోతాదు", "పేరు", "ఏ మందు", "ఏ పురుగుమందు",
))
_TIMING_WORDS = tuple(_normalize(w) for w in (
    "when", "right time", "good time", "best time", "safe to spray", "safe time", "weather", "today",
    "tomorrow", "tonight", "now", "this morning", "this evening", "this week",
    "कब", "समय", "सही वक्त", "आज", "कल", "अभी", "अब", "मौसम", "सुबह", "शाम",
    "केव्हा", "कधी", "वेळ", "आज", "उद्या", "आता", "हवामान", "सकाळी", "संध्याकाळी",
    "ఎప్పుడు", "సమయం", "ఈరోజు", "ఈ రోజు", "రేపు", "ఇప్పుడు", "వాతావరణం", "ఉదయం", "సాయంత్రం",
))
# Near-term references that make a timing question answerable from the weather, by day.
_TODAY_WORDS = tuple(_normalize(w) for w in (
    "today", "tonight", "now", "right now", "this morning", "this evening", "this afternoon",
    "आज", "अभी", "अब", "आता", "ఈరోజు", "ఈ రోజు", "ఇప్పుడు", "ఇవాళ",
))
_TOMORROW_WORDS = tuple(_normalize(w) for w in (
    "tomorrow", "कल", "उद्या", "రేపు",
))
_TIME_ONLY_WORDS = tuple(_normalize(w) for w in (
    # "is it the right time to spray?" with no day named: read as now
    "right time", "good time", "सही समय", "अच्छा समय", "सही वक्त", "योग्य वेळ", "चांगली वेळ",
    "సరైన సమయం", "మంచి సమయం",
))
_WHEN_WORDS = tuple(_normalize(w) for w in (
    # a general "when should I spray?" is agronomy for the knowledge base, not a weather check
    "when", "कब", "केव्हा", "कधी", "ఎప్పుడు",
))


def spray_question_kind(text: str) -> Optional[str]:
    """
    "product": asks which pesticide or spray to use, or how much.
    "timing":  asks when, or whether now, today or tomorrow is a good time to spray.
    None:      not a spray or pesticide question.
    A question that names a product and a time ("which spray tomorrow?") is "product".
    """
    t = _normalize(text or "")
    if not any(w in t for w in _PESTICIDE_QUESTION):
        return None
    if any(w in t for w in _PRODUCT_WORDS):
        return "product"
    if any(w in t for w in _TIMING_WORDS):
        return "timing"
    return "product"


def spray_timing_day(text: str) -> Optional[str]:
    """
    For a timing question: "today" or "tomorrow" when the farmer names a day (or asks about
    now), None for a general question ("when should I spray after rain?") that the knowledge
    base answers. Only meaningful when spray_question_kind() is "timing" and the question
    mentions spraying.
    """
    t = _normalize(text or "")
    if not any(w in t for w in _SPRAY_WORDS):
        return None
    if any(w in t for w in _TOMORROW_WORDS):
        return "tomorrow"
    if any(w in t for w in _TODAY_WORDS):
        return "today"
    if any(w in t for w in _TIME_ONLY_WORDS) and not any(w in t for w in _WHEN_WORDS):
        return "today"
    return None


def is_pesticide_question(text: str) -> bool:
    """True for a question about which pesticide or spray to use, or how much; not for timing."""
    return spray_question_kind(text) == "product"


def pesticide_policy(dialect: str) -> str:
    return PESTICIDE_POLICY.get((dialect or "en").strip().lower(), PESTICIDE_POLICY["en"])


def _has_referral(text: str) -> bool:
    return any(line in text for lines in REFERRAL_LINES.values() for line in lines.values())


# The knowledge-base model writes Markdown bold (**text**). WhatsApp bold is *text*,
# and the web chat shows text as typed, so the markers would show on screen.
_MD_BOLD_RE = re.compile(r"\*\*(?=\S)([^*\n]+?)(?<=\S)\*\*")


def _channel_markup(text: str, channel: str) -> str:
    if "**" not in text:
        return text
    return _MD_BOLD_RE.sub(r"\1" if channel.startswith("web") else r"*\1*", text)


# "I cannot recommend specific pesticide names or doses, but here are ..." at the start
# of an answer to a question that did not ask for a pesticide. English only: the other
# languages rely on the prompt.
_REFUSAL_OPENER_RE = re.compile(
    r"^\s*(?:i|we)\s+"
    r"(?:cannot|can['\u2019]?t|can\s+not|(?:am|are)\s+(?:unable|not\s+able)\s+to|do\s+not|don['\u2019]?t|will\s+not|won['\u2019]?t)\s+"
    r"(?:recommend|give|provide|name|suggest|share|advise)\b"
    r"[^.!?\n]*?\b(?:pesticid|insecticid|fungicid|herbicid|chemical)[^.!?\n]*?"
    r"(?:[,;]\s*(?:but|however)\b,?\s*|[.!]\s+(?:(?:however|but|instead)\b,?\s*)?)",
    re.IGNORECASE,
)


def _strip_refusal_opener(text: str) -> str:
    m = _REFUSAL_OPENER_RE.match(text)
    if not m:
        return text
    rest = text[m.end():].lstrip()
    if not re.search(r"\w", rest):
        return text
    return rest[0].upper() + rest[1:]


# A closing sentence from the model that sends the farmer to the KVK for chemical
# control. The referral footer says the same, so the farmer would read it twice.
_KVK_MARKERS = tuple(
    _normalize(w) for w in ("kvk", "krishi vigyan", "कृषि विज्ञान", "कृषी विज्ञान", "కృషి విజ్ఞాన")
)
_REFERRAL_TOPIC_LATIN_RE = re.compile(
    r"(?<![a-z])(?:chemicals?|pesticides?|insecticides?|fungicides?|herbicides?|products?|doses?|dosage)(?![a-z])"
)
_REFERRAL_TOPIC_INDIC = tuple(
    _normalize(w)
    for w in (
        "रासायनिक", "रसायन", "कीटनाशक", "कीटकनाशक", "किटकनाशक", "औषध", "दवा",
        "రసాయన", "పురుగుమందు", "మందు",
    )
)
_REFERRAL_VERB_LATIN_RE = re.compile(
    r"(?<![a-z])(?:contact|consult|ask|visit|call|reach out to|check with|speak (?:to|with)|talk to)(?![a-z])"
)
# "विचार" covers the Marathi "विचारा" / "विचारून पहा" (ask); "पूछ" the Hindi "पूछें".
_REFERRAL_VERB_INDIC = tuple(
    _normalize(w) for w in ("संपर्क", "सल्ला", "सलाह", "विचार", "पूछ", "సంప్రదించ", "అడగ")
)


# The system's own source line lists retrieved file names, some of which carry a hash
# ("soybean-04-855fe8ec.pdf") that reads as a formulation code ("8ec"). Such a line is
# left alone; a source line with anything other than file names is filtered as usual.
_FILE_NAME_RE = re.compile(r"[\w.\-]+\.(?:pdf|txt|md|docx?|html?|csv|json)", re.IGNORECASE)


def _is_file_source_line(line: str) -> bool:
    if not is_source_line(line):
        return False
    names = line.split(":", 1)[-1].replace("…", "").split(",")
    names = [n.strip() for n in names if n.strip()]
    return bool(names) and all(_FILE_NAME_RE.fullmatch(n) for n in names)


def names_kvk(text: str) -> bool:
    norm = _normalize(text)
    return any(k in norm for k in _KVK_MARKERS)


def _is_model_referral(segment: str) -> bool:
    norm = _normalize(segment)
    return (
        any(k in norm for k in _KVK_MARKERS)
        and bool(_REFERRAL_TOPIC_LATIN_RE.search(norm) or any(w in norm for w in _REFERRAL_TOPIC_INDIC))
        and bool(_REFERRAL_VERB_LATIN_RE.search(norm) or any(w in norm for w in _REFERRAL_VERB_INDIC))
    )


def _drop_model_referral(text: str) -> str:
    """Drop the model's own KVK referral when it is the last sentence before any source line."""
    lines = text.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if not line.strip() or is_source_line(line):
            continue
        segments = _segments(line)
        if not segments or not _is_model_referral(segments[-1]):
            return text
        lines[i] = "".join(segments[:-1]).rstrip()
        out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        return out if re.search(r"\w", strip_source_lines(out)) else text
    return text


def filter_advice(
    text: str,
    dialect: str,
    channel: str,
    kind: str = "answer",
    district: Optional[str] = None,
    add_referral: bool = True,
    question: Optional[str] = None,
    source_line: Optional[str] = None,
) -> str:
    """
    Remove chemical product and dose advice from a farmer-facing message and make
    sure it ends with the KVK referral. kind is "photo" or "answer" (text/voice).

    Also tidies what the model wrote around the advice: Markdown bold becomes the
    channel's own (WhatsApp *bold*, none on the web chat), the model's own closing
    KVK referral is dropped when the footer follows, and, when the farmer's question
    is passed and did not ask about a pesticide, an opening "I cannot recommend
    pesticides" sentence is dropped.

    source_line is the system's own line naming the cited documents. It goes after the
    advice and before the referral footer, and is not filtered: document titles are not
    advice, and a title such as "Neonicotinoid use in cotton" would otherwise be removed.
    """
    if not text:
        return text
    text = _channel_markup(text, channel)
    if question is not None and not is_pesticide_question(question):
        text = _strip_refusal_opener(text)
    hits: List[Tuple[str, Set[str]]] = []
    state = {"after_removal": 0, "orphans": 0}
    lines = text.split("\n")
    parsed = [None if _is_file_source_line(line) else _split_line(line, hits, state) for line in lines]
    counter = [0, 0]
    out_lines = []
    for line, p in zip(lines, parsed):
        if p is None or not (hits or state["orphans"]):
            out_lines.append(line)
            continue
        label, kept, removed = p
        filtered = _join_line(line, label, _renumber(kept, counter), removed)
        if filtered is not None:
            out_lines.append(filtered)
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(out_lines)).strip()

    if hits:
        kinds = sorted({k for _, ks in hits for k in ks})
        print(f"Advice filter removed {len(hits)} segment(s) channel={channel} kinds={','.join(kinds)}")
        _emit_metric(channel, hits)
    if state["orphans"]:
        print(f"Advice filter removed {state['orphans']} repeat step(s) left without their step channel={channel}")

    if add_referral:
        out = _drop_model_referral(out)
    if source_line:
        out = (out + "\n\n" + source_line.strip()).strip()
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
