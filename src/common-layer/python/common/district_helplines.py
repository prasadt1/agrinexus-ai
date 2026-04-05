"""
Curated district-aware helpline snippets for purchase / where-to-buy style questions.
Not live market data — static KVK-style guidance; numbers should be verified on official portals.
"""

import os
import re
from typing import Optional

# District keys match onboarding `location` (VALID_DISTRICTS subset with copy prepared).
CURATED_DISTRICTS = frozenset({"Latur", "Jalna", "Nagpur"})

# National Kisan Call Centre (India) — widely published; still ask users to verify on official sites.
_KCC = "1800-180-1551"

DISTRICT_HELPLINES = {
    "Latur": {
        "hi": (
            f"📍 लातूर: बीज/दवा खरीद या प्रमाणित विक्रेता के लिए नज़दीकी KVK या जिला कृषि अधिकारी कार्यालय से संपर्क करें। "
            f"किसान कॉल सेंटर: {_KCC} (नंबर आधिकारिक पोर्टल पर सत्यापित करें)।"
        ),
        "mr": (
            f"📍 लातूर: बियाणे/ औषध खरेदीसाठी जवळच्या KVK किंवा जिल्हा कृषी अधिकारी कार्यालयाशी संपर्क साधा. "
            f"किसान कॉल सेंटर: {_KCC}."
        ),
        "te": (
            f"📍 లాతూర్: విత్తనాలు/మందుల కొనుగోలు కోసం సమీప KVK లేదా జిల్లా వ్యవసాయ అధికారి కార్యాలయాన్ని సంప్రదించండి. "
            f"రైతు కాల్ సెంటర్: {_KCC}."
        ),
        "en": (
            f"📍 Latur: For seeds, crop protection, or a licensed supplier, contact your nearest KVK or the "
            f"district agriculture office. Kisan Call Centre: {_KCC} (verify on the official portal)."
        ),
    },
    "Jalna": {
        "hi": (
            f"📍 जालना: खरीद/प्रमाणित विक्रेता जानकारी के लिए KVK जालना या जिला कृषि कार्यालय से मिलें। "
            f"किसान कॉल सेंटर: {_KCC}।"
        ),
        "mr": (
            f"📍 जालना: खरेदीसाठी KVK जालना किंवा जिल्हा कृषी कार्यालयाशी संपर्क करा. किसान कॉल सेंटर: {_KCC}."
        ),
        "te": (
            f"📍 జాల్నా: కొనుగోలు కోసం సమీప KVK లేదా జిల్లా వ్యవసాయ కార్యాలయాన్ని సంప్రదించండి. "
            f"రైతు కాల్ సెంటర్: {_KCC}."
        ),
        "en": (
            f"📍 Jalna: For purchase guidance, contact KVK Jalna or the district agriculture office. "
            f"Kisan Call Centre: {_KCC}."
        ),
    },
    "Nagpur": {
        "hi": (
            f"📍 नागपुर: इनपुट खरीद व सलाह के लिए संबंधित KVK या जिला कृषि कार्यालय से संपर्क करें। "
            f"किसान कॉल सेंटर: {_KCC}।"
        ),
        "mr": (
            f"📍 नागपूर: इनपुट खरेदीसाठी KVK किंवा जिल्हा कृषी कार्यालयाशी संपर्क साधा. किसान कॉल सेंटर: {_KCC}."
        ),
        "te": (
            f"📍 నాగపూర్: ఇన్‌పుట్‌ల కొనుగోలు కోసం KVK లేదా జిల్లా వ్యవసాయ కార్యాలయాన్ని సంప్రదించండి. "
            f"రైతు కాల్ సెంటర్: {_KCC}."
        ),
        "en": (
            f"📍 Nagpur: For inputs and purchase guidance, contact the relevant KVK or the district agriculture office. "
            f"Kisan Call Centre: {_KCC}."
        ),
    },
}

# User query signals: where to buy / dealer / shop — not generic agronomy.
_ASCII_HINT_PATTERNS = (
    re.compile(r"where\s+to\s+buy", re.I),
    re.compile(r"where\s+can\s+i\s+(buy|get|purchase|find)", re.I),
    re.compile(r"where\s+(do\s+i|can\s+we)\s+buy", re.I),
    re.compile(r"\b(buy|purchase|purchasing)\b.*\b(seed|pesticide|fertilizer|fertiliser|input|product)s?\b", re.I),
    re.compile(r"\b(seed|pesticide|fertilizer|fertiliser|input)s?\b.*\b(buy|purchase|shop|dealer|supplier)\b", re.I),
    re.compile(r"\b(dealer|retailer|supplier|duk[aā]n|shop)\b", re.I),
    re.compile(r"\b(kharid|khareed|khareedi|khareedna|kirana)\b", re.I),
)

_UNICODE_HINT_SUBSTRINGS = (
    "खरीद",
    "खरीदने",
    "कहाँ मिल",
    "कहा मिल",
    "दुकान",
    "डीलर",
    "विक्रेता",
    "खरेदी",
    "दुकानदार",
    "కొనుగోలు",
    "ఎక్కడ దొరుకు",
    "దుకాణం",
)


def wants_where_to_buy_hint(user_query: str) -> bool:
    """True if the farmer is asking about buying inputs, dealers, or where to obtain products."""
    t = (user_query or "").strip()
    if len(t) < 2:
        return False
    for pat in _ASCII_HINT_PATTERNS:
        if pat.search(t):
            return True
    for s in _UNICODE_HINT_SUBSTRINGS:
        if s in t:
            return True
    return False


def _helpline_block(district_key: str, dialect: str) -> Optional[str]:
    if district_key not in DISTRICT_HELPLINES:
        return None
    row = DISTRICT_HELPLINES[district_key]
    return row.get(dialect) or row.get("en")


MAX_WHATSAPP_TEXT = 4096


def maybe_append_helpline_footer(
    response_text: str,
    user_query: str,
    dialect: str,
    location: Optional[str],
) -> str:
    """
    Append curated district helpline when the user asked a purchase/where-to-buy style question
    and we have copy for their district.
    """
    if os.environ.get("APPEND_DISTRICT_HELPLINE", "true").lower() not in ("1", "true", "yes"):
        return response_text
    loc = (location or "").strip()
    if loc not in CURATED_DISTRICTS:
        return response_text
    if not wants_where_to_buy_hint(user_query):
        return response_text
    footer = _helpline_block(loc, dialect)
    if not footer:
        return response_text
    base = (response_text or "").rstrip()
    sep = "\n\n"
    combined = f"{base}{sep}{footer}"
    if len(combined) <= MAX_WHATSAPP_TEXT:
        return combined
    room = MAX_WHATSAPP_TEXT - len(sep) - len(footer) - 5
    if room < 120:
        return (base + sep + footer)[:MAX_WHATSAPP_TEXT]
    trimmed = base[:room].rstrip() + "\n…"
    return f"{trimmed}{sep}{footer}"
