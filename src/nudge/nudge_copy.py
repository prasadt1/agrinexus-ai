"""
Shared localized copy for weather nudges and reminders (crop, district, context hints).
Hints are non-prescriptive (no product names) — accuracy for demos without regulated advice.
"""

from typing import Tuple

# Canonical district keys from onboarding (location field)
DISTRICT_LABELS = {
    "Latur": {"hi": "लातूर", "mr": "लातूर", "te": "లాతూర్", "en": "Latur"},
    "Jalna": {"hi": "जालना", "mr": "जालना", "te": "జాల్నా", "en": "Jalna"},
    "Nagpur": {"hi": "नागपुर", "mr": "नागपूर", "te": "నాగపూర్", "en": "Nagpur"},
}

# Crop name + spray category (pesticide vs fungicide) per dialect
CROP_INFO = {
    "Cotton": {
        "hi": ("कपास", "कीटनाशक"),
        "mr": ("कापूस", "कीटकनाशक"),
        "te": ("పత్తి", "పురుగుమందు"),
        "en": ("cotton", "pesticide"),
    },
    "Wheat": {
        "hi": ("गेहूं", "फफूंदनाशक"),
        "mr": ("गहू", "बुरशीनाशक"),
        "te": ("గోధుమ", "శిలీంధ్రనాశని"),
        "en": ("wheat", "fungicide"),
    },
    "Soybean": {
        "hi": ("सोयाबीन", "कीटनाशक"),
        "mr": ("सोयाबीन", "कीटकनाशक"),
        "te": ("సోయాబీన్", "పురుగుమందు"),
        "en": ("soybean", "pesticide"),
    },
    "Maize": {
        "hi": ("मक्का", "कीटनाशक"),
        "mr": ("मका", "कीटकनाशक"),
        "te": ("మొక్కజొన్న", "పురుగుమందు"),
        "en": ("maize", "pesticide"),
    },
}

# Short relevance line per crop (extension-style, not a product recommendation)
CROP_CONTEXT_HINT = {
    "Cotton": {
        "hi": "बोलवर्म व सकिंग कीटों पर निगरानी रखें; उत्पाद स्थानीय KVK/डीलर से चुनें।",
        "mr": "बोलवर्म व सकिंग कीटकांवर लक्ष ठेवा; कीटकनाशक स्थानिक KVK/डीलर कडून निवडा.",
        "te": "బోల్‌వార్మ్, సకింగ్ పురుగులపై గమనం; మందులను స్థానిక KVK/డీలర్ సలహా మేరకు.",
        "en": "Watch bollworm & sucking pests; choose products with your local KVK/dealer.",
    },
    "Wheat": {
        "hi": "पत्ती/चेपी पर फफूंद व जंग के लक्षण देखें; फफूंदनाशक समय पर KVK सलाह से।",
        "mr": "पान/पानांवर गोळा/तांबेरंगी ठिपके तपासा; बुरशीनाशक वेळेवर KVK सल्ल्यानुसार.",
        "te": "ఆకు/తెగుళ్లు మరియు పురుగుల లక్షణాలు గమనించండి; శిలీంధ్ర నివారణకు KVK సలహా.",
        "en": "Scout for rust & foliar disease; time fungicide with local KVK guidance.",
    },
    "Soybean": {
        "hi": "फली छेदक व पत्ती खाने वाले कीटों की जांच करें; स्प्रे KVK अनुसार।",
        "mr": "शेंगा छेदक व पानखाणारे कीट तपासा; फवारणी KVK सल्ल्यानुसार.",
        "te": "కాయలు తినే పురుగులు, ఆకు నష్టం గమనించండి; స్ప్రే KVK సూచన మేరకు.",
        "en": "Check pod borers & defoliators; spray timing per local KVK.",
    },
    "Maize": {
        "hi": "तना छेदक व फौजी इल्ली की गतिविधि देखें; नियंत्रण KVK सिफारिश अनुसार।",
        "mr": "पान मोडणारे व लष्करी अळीची चिन्हे तपासा; नियंत्रण KVK शिफारशीनुसार.",
        "te": "కంకి పురుగు, సైనిక పురుగు గమనించండి; నియంత్రణ KVK సూచన ప్రకారం.",
        "en": "Watch stem borers & fall armyworm signs; control per KVK advice.",
    },
}

NUDGE_TEMPLATES = {
    "hi": (
        "📍 {district} | {crop}\n"
        "{context_hint}\n\n"
        "आज {spray_type} स्प्रे के लिए मौसम अनुकूल है — हवा {wind_speed} km/h, बारिश नहीं। "
        "क्या आपने स्प्रे कर दिया?"
    ),
    "mr": (
        "📍 {district} | {crop}\n"
        "{context_hint}\n\n"
        "आज {spray_type} फवारणीसाठी हवामान अनुकूल आहे — वारा {wind_speed} km/h, पाऊस नाही. "
        "तुम्ही फवारणी केली का?"
    ),
    "te": (
        "📍 {district} | {crop}\n"
        "{context_hint}\n\n"
        "ఈరోజు {spray_type} స్ప్రేకు వాతావరణం అనుకూలం — గాలి {wind_speed} km/h, వర్షం లేదు. "
        "మీరు స్ప్రే చేశారా?"
    ),
    "en": (
        "📍 {district} | {crop}\n"
        "{context_hint}\n\n"
        "Good spray weather now — wind {wind_speed} km/h, no rain. "
        "Have you completed your {spray_type} spray?"
    ),
}

REMINDER_TEMPLATES = {
    "hi": {
        "T+24h": "📍 {district} — {crop}: कल {spray_type} स्प्रे की बात याद है? {hint_short} — क्या हो गया?",
        "T+48h": "📍 {district} — अंतिम याद: {crop} में {spray_type} स्प्रे बाकी है। {hint_short} कृपया जल्द करें।",
    },
    "mr": {
        "T+24h": "📍 {district} — {crop}: कालची {spray_type} फवारणी आठवते का? {hint_short} झाले का?",
        "T+48h": "📍 {district} — शेवटची आठवण: {crop} साठी {spray_type} फवारणी बाकी. {hint_short} लवकर करा.",
    },
    "te": {
        "T+24h": "📍 {district} — {crop}: నిన్న {spray_type} స్ప్రే గుర్తుందా? {hint_short} అయ్యిందా?",
        "T+48h": "📍 {district} — చివరి గుర్తు: {crop}లో {spray_type} స్ప్రే మిగిలి ఉంది. {hint_short} త్వరగా చేయండి.",
    },
    "en": {
        "T+24h": "📍 {district} — {crop}: Reminder on your {spray_type} spray. {hint_short} Done?",
        "T+48h": "📍 {district} — Final reminder: {spray_type} spray for {crop} still pending. {hint_short} Please act soon.",
    },
}

REMINDER_HINT_SHORT = {
    "Cotton": {
        "hi": "कीट दबाव देखें।",
        "mr": "कीटक दाब तपासा.",
        "te": "పురుగు ఒత్తిడి గమనించండి.",
        "en": "Check pest pressure.",
    },
    "Wheat": {
        "hi": "फफूंद लक्षण देखें।",
        "mr": "बुरशी लक्षणे तपासा.",
        "te": "శిలీంధ్ర లక్షణాలు చూడండి.",
        "en": "Scout for disease.",
    },
    "Soybean": {
        "hi": "फली/पत्ती नुकसान देखें।",
        "mr": "शेंगा/पान नुकसान तपासा.",
        "te": "కాయ/ఆకు నష్టం చూడండి.",
        "en": "Check pods & leaves.",
    },
    "Maize": {
        "hi": "तना/पत्ती नुकसान देखें।",
        "mr": "पान/पान नुकसान तपासा.",
        "te": "కాండం/ఆకు నష్టం చూడండి.",
        "en": "Check stalk & leaves.",
    },
}


def district_display(district_key: str, dialect: str) -> str:
    if not district_key:
        return ""
    row = DISTRICT_LABELS.get(district_key, {})
    return row.get(dialect) or row.get("en") or district_key


def crop_terms(crop: str, dialect: str) -> Tuple[str, str]:
    data = CROP_INFO.get(crop, CROP_INFO["Cotton"])
    return data.get(dialect, data["hi"])


def context_hint(crop: str, dialect: str) -> str:
    row = CROP_CONTEXT_HINT.get(crop, CROP_CONTEXT_HINT["Cotton"])
    return row.get(dialect, row["en"])


def reminder_hint_short(crop: str, dialect: str) -> str:
    row = REMINDER_HINT_SHORT.get(crop, REMINDER_HINT_SHORT["Cotton"])
    return row.get(dialect, row["en"])


def build_nudge_message(
    dialect: str,
    district_key: str,
    crop: str,
    wind_speed: float,
) -> str:
    crop_name, spray_type = crop_terms(crop, dialect)
    district = district_display(district_key, dialect) or district_key or "—"
    hint = context_hint(crop, dialect)
    tmpl = NUDGE_TEMPLATES.get(dialect, NUDGE_TEMPLATES["hi"])
    return tmpl.format(
        district=district,
        crop=crop_name,
        context_hint=hint,
        spray_type=spray_type,
        wind_speed=round(wind_speed, 1),
    )


def build_reminder_message(
    dialect: str,
    reminder_type: str,
    district_key: str,
    crop: str,
) -> str:
    crop_name, spray_type = crop_terms(crop, dialect)
    district = district_display(district_key, dialect) or district_key or "—"
    hint_short = reminder_hint_short(crop, dialect)
    templates = REMINDER_TEMPLATES.get(dialect, REMINDER_TEMPLATES["hi"])
    tmpl = templates.get(reminder_type, templates["T+24h"])
    return tmpl.format(
        district=district,
        crop=crop_name,
        spray_type=spray_type,
        hint_short=hint_short,
    )
