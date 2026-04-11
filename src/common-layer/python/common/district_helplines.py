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

APPEND_HELPLINE = os.environ.get('APPEND_DISTRICT_HELPLINE', 'false').lower() == 'true'

# Generic helpline data (production includes comprehensive district-specific data)
HELPLINES = {
    'Latur': {
        'hi': '\n\n📞 कृषि सहायता:\n• किसान कॉल सेंटर: 1800-180-1551',
        'mr': '\n\n📞 शेती मदत:\n• किसान कॉल सेंटर: 1800-180-1551',
        'te': '\n\n📞 వ్యవసాయ సహాయం:\n• కిసాన్ కాల్ సెంటర్: 1800-180-1551',
        'en': '\n\n📞 Agricultural Support:\n• Kisan Call Centre: 1800-180-1551'
    }
}

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
    if not APPEND_HELPLINE:
        return text
    
    # Generic implementation - production has sophisticated keyword matching
    keywords = ['buy', 'purchase', 'where', 'dealer', 'खरीद', 'कहाँ', 'विक्रेता']
    if any(kw in query.lower() for kw in keywords):
        helpline = HELPLINES.get(district, HELPLINES['Latur'])
        return text + helpline.get(dialect, helpline['en'])
    
    return text

# Note: Full implementation available under commercial license
# Contact: prasad@prasadtilloo.com
