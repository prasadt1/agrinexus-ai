"""
District Helplines - Proprietary Component

This module contains curated agricultural helpline data for districts
in Maharashtra and other Indian states.

The actual implementation includes:
- KVK (Krishi Vigyan Kendra) contact details
- District agriculture office numbers
- Pesticide dealer information
- Emergency helplines
- Multi-language support

This public version provides generic examples only.

For licensing enquiries: prasad@prasadtilloo.com
Copyright (C) 2026 Prasad Tilloo. All rights reserved.
"""

import os

# Generic helpline data (production includes comprehensive district-specific data)
HELPLINES = {
    'Latur': {
        'hi': '\n\n📞 कृषि सहायता (लातूर):\n• किसान कॉल सेंटर: 1800-180-1551',
        'mr': '\n\n📞 शेती मदत (लातूर):\n• किसान कॉल सेंटर: 1800-180-1551',
        'te': '\n\n📞 వ్యవసాయ సహాయం (లాతూర్):\n• కిసాన్ కాల్ సెంటర్: 1800-180-1551',
        'en': '\n\n📞 Agricultural Support (Latur):\n• Kisan Call Centre: 1800-180-1551',
    },
    'Nagpur': {
        'hi': '\n\n📞 कृषि सहायता (नागपुर):\n• किसान कॉल सेंटर: 1800-180-1551',
        'mr': '\n\n📞 शेती मदत (नागपूर):\n• किसान कॉल सेंटर: 1800-180-1551',
        'te': '\n\n📞 వ్యవసాయ సహాయం (నాగ్‌పూర్):\n• కిసాన్ కాల్ సెంటర్: 1800-180-1551',
        'en': '\n\n📞 Agricultural Support (Nagpur):\n• Kisan Call Centre: 1800-180-1551',
    },
    'Jalna': {
        'hi': '\n\n📞 कृषि सहायता (जालना):\n• किसान कॉल सेंटर: 1800-180-1551',
        'mr': '\n\n📞 शेती मदत (जालना):\n• किसान कॉल सेंटर: 1800-180-1551',
        'te': '\n\n📞 వ్యవసాయ సహాయం (జల్నా):\n• కిసాన్ కాల్ సెంటర్: 1800-180-1551',
        'en': '\n\n📞 Agricultural Support (Jalna):\n• Kisan Call Centre: 1800-180-1551',
    },
}


KISAN_CALL_CENTRE = '1800-180-1551'

NATIONAL_HELPLINE = {
    'hi': f'📞 किसान कॉल सेंटर: {KISAN_CALL_CENTRE}',
    'mr': f'📞 किसान कॉल सेंटर: {KISAN_CALL_CENTRE}',
    'te': f'📞 కిసాన్ కాల్ సెంటర్: {KISAN_CALL_CENTRE}',
    'en': f'📞 Kisan Call Centre: {KISAN_CALL_CENTRE}',
}

# Closing line on every advice message. The product does not name pesticides or
# doses; chemical choice and rate are referred to the farmer's KVK.
REFERRAL_LINES = {
    'photo': {
        'hi': 'यह आपकी फोटो की स्वचालित जाँच है और यह गलत हो सकती है। सही कीटनाशक और उसकी मात्रा के लिए अपने नज़दीकी कृषि विज्ञान केंद्र (KVK) से संपर्क करें।',
        'mr': 'हे तुमच्या फोटोचे स्वयंचलित वाचन आहे आणि ते चुकीचे असू शकते. योग्य कीटकनाशक आणि त्याचे प्रमाण यासाठी जवळच्या कृषी विज्ञान केंद्राशी (KVK) संपर्क साधा.',
        'te': 'ఇది మీ ఫోటో యొక్క ఆటోమేటిక్ విశ్లేషణ, ఇది తప్పు కావచ్చు. సరైన పురుగుమందు మరియు దాని పరిమాణం కోసం మీ సమీప కృషి విజ్ఞాన కేంద్రాన్ని (KVK) సంప్రదించండి.',
        'en': 'This is an automated reading of your photo and it can be wrong. For the correct pesticide and quantity, contact your nearest KVK (Krishi Vigyan Kendra).',
    },
    'answer': {
        'hi': 'यह स्वचालित जवाब है और यह गलत हो सकता है। सही कीटनाशक और उसकी मात्रा के लिए अपने नज़दीकी कृषि विज्ञान केंद्र (KVK) से संपर्क करें।',
        'mr': 'हे स्वयंचलित उत्तर आहे आणि ते चुकीचे असू शकते. योग्य कीटकनाशक आणि त्याचे प्रमाण यासाठी जवळच्या कृषी विज्ञान केंद्राशी (KVK) संपर्क साधा.',
        'te': 'ఇది ఆటోమేటిక్ సమాధానం, ఇది తప్పు కావచ్చు. సరైన పురుగుమందు మరియు దాని పరిమాణం కోసం మీ సమీప కృషి విజ్ఞాన కేంద్రాన్ని (KVK) సంప్రదించండి.',
        'en': 'This is an automated answer and it can be wrong. For the correct pesticide and quantity, contact your nearest KVK (Krishi Vigyan Kendra).',
    },
}


def referral_line(dialect: str, kind: str = 'answer') -> str:
    lines = REFERRAL_LINES.get(kind, REFERRAL_LINES['answer'])
    return lines.get(dialect, lines['en'])


def referral_footer(dialect: str, kind: str = 'answer', district: str = None) -> str:
    """KVK referral plus one contact block: the district block when curated, else national."""
    curated = HELPLINES.get(district or '')
    contact = (curated.get(dialect, curated['en']) if curated else NATIONAL_HELPLINE.get(dialect, NATIONAL_HELPLINE['en'])).strip()
    return f"\n\n{referral_line(dialect, kind)}\n{contact}"


def wants_where_to_buy_hint(query: str) -> bool:
    """True when the farmer is asking where to obtain inputs (dealers, purchase location)."""
    ql = query.lower()
    english = ('buy', 'purchase', 'where', 'dealer')
    if any(kw in ql for kw in english):
        return True
    devanagari = ('खरीद', 'कहाँ', 'कहां', 'विक्रेता')
    return any(kw in query for kw in devanagari)


def maybe_append_helpline_footer(text: str, query: str, dialect: str, district: str) -> str:
    """
    Append district-specific helpline information if relevant.
    
    Production version includes:
    - Keyword detection (buy, purchase, where, dealer, etc.)
    - District-specific KVK and agriculture office contacts
    - Pesticide dealer information
    - Emergency helplines
    
    This stub returns generic Kisan Call Centre only.
    """
    if os.environ.get('APPEND_DISTRICT_HELPLINE', 'false').lower() != 'true':
        return text

    if KISAN_CALL_CENTRE in text:
        return text

    if not wants_where_to_buy_hint(query):
        return text

    helpline = HELPLINES.get(district)
    if not helpline:
        return text

    return text + helpline.get(dialect, helpline['en'])

# Note: Full implementation available under commercial license
# Contact: prasad@prasadtilloo.com
