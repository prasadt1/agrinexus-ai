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

    if not wants_where_to_buy_hint(query):
        return text

    helpline = HELPLINES.get(district)
    if not helpline:
        return text

    return text + helpline.get(dialect, helpline['en'])

# Note: Full implementation available under commercial license
# Contact: prasad@prasadtilloo.com
