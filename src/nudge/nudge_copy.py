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
from typing import Optional


def build_nudge_message(
    dialect: str,
    district: str,
    crop: str,
    wind_speed: float,
    context_hint_override: Optional[str] = None,
) -> str:
    """Public entry point used by sender (optional Bedrock liner appended)."""
    text = get_nudge_message(dialect, district, crop, wind_speed)
    if context_hint_override and str(context_hint_override).strip():
        return f"{text.rstrip()}\n\n{str(context_hint_override).strip()}"
    return text


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
    # Crop name translations
    crop_names = {
        'Cotton': {'hi': 'कपास', 'mr': 'कापूस', 'te': 'పత్తి', 'en': 'Cotton'},
        'Wheat': {'hi': 'गेहूं', 'mr': 'गहू', 'te': 'గోధుమ', 'en': 'Wheat'},
        'Soybean': {'hi': 'सोयाबीन', 'mr': 'सोयाबीन', 'te': 'సోయాబీన్', 'en': 'Soybean'},
        'Maize': {'hi': 'मक्का', 'mr': 'मका', 'te': 'మొక్కజొన్న', 'en': 'Maize'},
        'Rice': {'hi': 'धान', 'mr': 'भात', 'te': 'వరి', 'en': 'Rice'},
    }
    
    crop_local = crop_names.get(crop, {}).get(dialect, crop)

    # Wind speed arrives as a raw float; the m/s->km/h conversion upstream can
    # yield values like 23.508000000000003. Farmers see a clean whole number.
    try:
        wind = f"{round(float(wind_speed))}"
    except (TypeError, ValueError):
        wind = str(wind_speed)

    generic_messages = {
        'hi': f'{district}: {crop_local} में स्प्रे के लिए मौसम अनुकूल है। हवा {wind} km/h है। कृपया स्प्रे करें।',
        'mr': f'{district}: {crop_local} मध्ये फवारणीसाठी हवामान अनुकूल आहे. वारा {wind} km/h आहे. कृपया फवारणी करा.',
        'te': f'{district}: {crop_local} లో స్ప్రే చేయడానికి వాతావరణం అనుకూలంగా ఉంది. గాలి {wind} km/h. దయచేసి స్ప్రే చేయండి.',
        'en': f'{district}: Weather is favorable for spraying {crop_local}. Wind: {wind} km/h. Please spray.',
    }
    
    return generic_messages.get(dialect, generic_messages['en'])

def build_reminder_message(
    dialect: str, reminder_type: str, district: str, crop: str
) -> str:
    """Entry point used by reminder lambda."""
    return get_reminder_message(dialect, reminder_type, district, crop)


def get_reminder_message(dialect: str, reminder_type: str, district: str, crop: str) -> str:
    """
    Generate reminder message (T+24h or T+48h).
    
    Production version includes escalation logic and context-aware phrasing.
    """
    # Crop name translations
    crop_names = {
        'Cotton': {'hi': 'कपास', 'mr': 'कापूस', 'te': 'పత్తి', 'en': 'Cotton'},
        'Wheat': {'hi': 'गेहूं', 'mr': 'गहू', 'te': 'గోధుమ', 'en': 'Wheat'},
        'Soybean': {'hi': 'सोयाबीन', 'mr': 'सोयाबीन', 'te': 'సోయాబీన్', 'en': 'Soybean'},
        'Maize': {'hi': 'मक्का', 'mr': 'मका', 'te': 'మొక్కజొన్న', 'en': 'Maize'},
        'Rice': {'hi': 'धान', 'mr': 'भात', 'te': 'వరి', 'en': 'Rice'},
    }
    
    crop_local = crop_names.get(crop, {}).get(dialect, crop)
    
    if reminder_type == 'T+24h':
        generic_reminders = {
            'hi': f'{district}: {crop_local} में अभी तक स्प्रे नहीं किया? मौसम अनुकूल है। कृपया आज स्प्रे करें।',
            'mr': f'{district}: {crop_local} मध्ये अजून फवारणी केली नाही का? हवामान अनुकूल आहे. कृपया आज फवारणी करा.',
            'te': f'{district}: {crop_local} లో ఇంకా స్ప్రే చేయలేదా? వాతావరణం అనుకూలంగా ఉంది. దయచేసి ఈరోజు స్ప్రే చేయండి.',
            'en': f'{district}: Haven\'t sprayed {crop_local} yet? Weather is favorable. Please spray today.',
        }
    else:  # T+48h
        generic_reminders = {
            'hi': f'{district}: {crop_local} में स्प्रे करने की अंतिम याद दिलाना। कृपया जल्द करें।',
            'mr': f'{district}: {crop_local} मध्ये फवारणी करण्याची शेवटची आठवण. कृपया लवकर करा.',
            'te': f'{district}: {crop_local} లో స్ప్రే చేయడానికి చివరి రిమైండర్. దయచేసి త్వరగా చేయండి.',
            'en': f'{district}: Final reminder to spray {crop_local}. Please do it soon.',
        }
    
    return generic_reminders.get(dialect, generic_reminders['en'])

# Note: Full implementation available under commercial license
# Contact: prasad@prasadtilloo.com
