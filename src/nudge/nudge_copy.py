"""
Contextual Nudge Templates - Proprietary Component

This module contains district-specific, crop-specific, and weather-aware
behavioral nudge templates in multiple Indian languages.

The actual implementation includes:
- 12 district-specific templates (Latur, Jalna, Nagpur, etc.)
- 8 crop-specific variations (Cotton, Wheat, Soybean, Rice, etc.)
- Weather-aware phrasing (wind speed, rainfall, temperature)
- Cultural context adaptation
- Reminder escalation logic (T+24h, T+48h)
- Completion acknowledgements

This public version provides generic examples only.

For licensing enquiries: prasad@prasadtilloo.com
Copyright (C) 2026 Prasad Tilloo. All rights reserved.
"""

def get_nudge_message(dialect: str, district: str, crop: str, wind_speed: float) -> str:
    """
    Generate contextual nudge message.
    
    Production version includes sophisticated templates with:
    - District labels and local context
    - Crop-specific advice
    - Weather condition phrasing
    - Cultural appropriateness
    
    This stub returns a generic message.
    """
    generic_messages = {
        'hi': f'मौसम अनुकूल है। हवा {wind_speed} km/h है। कृपया स्प्रे करें।',
        'mr': f'हवामान अनुकूल आहे. वारा {wind_speed} km/h आहे. कृपया फवारणी करा.',
        'te': f'వాతావరణం అనుకూలంగా ఉంది. గాలి {wind_speed} km/h. దయచేసి స్ప్రే చేయండి.',
        'en': f'Weather is favorable. Wind: {wind_speed} km/h. Please spray.'
    }
    
    return generic_messages.get(dialect, generic_messages['en'])

def get_reminder_message(dialect: str, reminder_type: str, district: str, crop: str) -> str:
    """
    Generate reminder message (T+24h or T+48h).
    
    Production version includes escalation logic and context-aware phrasing.
    """
    generic_reminders = {
        'hi': 'याद दिलाना: कृपया स्प्रे करें।',
        'mr': 'आठवण: कृपया फवारणी करा.',
        'te': 'గుర్తు: దయచేసి స్ప్రే చేయండి.',
        'en': 'Reminder: Please spray.'
    }
    
    return generic_reminders.get(dialect, generic_reminders['en'])

# Note: Full implementation available under commercial license
# Contact: prasad@prasadtilloo.com
