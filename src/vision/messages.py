"""
Localized message templates for vision analysis responses.
Supports: Hindi (hi), Marathi (mr), Telugu (te), English (en).
"""
from typing import Dict


def get_safe_retake_message(dialect: str) -> str:
    """
    Safe template for unknown/low-confidence cases.
    Asks for clearer photo without naming crops.
    """
    templates = {
        'hi': 'पौधे की पहचान स्पष्ट नहीं है। कृपया प्रभावित पत्ती या हिस्से का करीब से स्पष्ट फोटो भेजें।',
        'mr': 'रोपाची ओळख स्पष्ट नाही. कृपया प्रभावित पानाचा किंवा भागाचा जवळून स्पष्ट फोटो पाठवा.',
        'te': 'మొక్క గుర్తింపు స్పష్టంగా లేదు. దయచేసి ప్రభావిత ఆకు లేదా భాగం యొక్క దగ్గరి స్పష్ట ఫోటో పంపండి.',
        'en': 'Cannot identify the plant clearly. Please send a closer, clearer photo of the affected leaf or part.'
    }
    return templates.get(dialect, templates['en'])


def get_block_message(reason: str, dialect: str) -> str:
    """Hard block messages for non-crop inputs (short, 1-2 lines)"""
    messages = {
        'screenshot_ui': {
            'hi': 'यह स्क्रीनशॉट लगती है। कृपया फसल/पत्ती की असली फोटो भेजें।',
            'mr': 'ही स्क्रीनशॉट दिसते. कृपया पिक/पानाची खरी फोटो पाठवा.',
            'te': 'ఇది స్క్రీన్‌షాట్ లా కనిపిస్తోంది. దయచేసి పంట/ఆకు యొక్క నిజమైన ఫోటో పంపండి.',
            'en': 'This looks like a screenshot. Please send a real photo of the crop/leaf.'
        },
        'logo': {
            'hi': 'यह लोगो/ग्राफिक लगती है। कृपया पत्ती का क्लोज-अप भेजें।',
            'mr': 'ही लोगो/ग्राफिक दिसते. कृपया पानाचा क्लोज-अप पाठवा.',
            'te': 'ఇది లోగో/గ్రాఫిక్ లా కనిపిస్తోంది. దయచేసి ఆకు క్లోజ్-అప్ పంపండి.',
            'en': 'This looks like a logo/graphic. Please send a close-up of a leaf.'
        },
        'too_small': {
            'hi': 'फोटो बहुत छोटी है। कृपया बड़ी फोटो भेजें।',
            'mr': 'फोटो खूप लहान आहे. कृपया मोठा फोटो पाठवा.',
            'te': 'ఫోటో చాలా చిన్నది. దయచేసి పెద్ద ఫోటో పంపండి.',
            'en': 'Photo is too small. Please send a larger photo.'
        }
    }

    reason_templates = messages.get(reason, messages['screenshot_ui'])
    return reason_templates.get(dialect, reason_templates['en'])


def get_error_message(error_type: str, dialect: str) -> str:
    """User-friendly error messages (short, 1-2 lines)"""
    messages = {
        'download_failed': {
            'hi': 'फोटो डाउनलोड नहीं हुई। कृपया दोबारा भेजें।',
            'mr': 'फोटो डाउनलोड झाला नाही. कृपया पुन्हा पाठवा.',
            'te': 'ఫోటో డౌన్‌లోడ్ కాలేదు. దయచేసి మళ్లీ పంపండి.',
            'en': 'Photo download failed. Please resend.'
        },
        'model_error': {
            'hi': 'विश्लेषण में समस्या। कृपया दोबारा भेजें।',
            'mr': 'विश्लेषणात समस्या. कृपया पुन्हा पाठवा.',
            'te': 'విశ్లేషణలో సమస్య. దయచేసి మళ్లీ పంపండి.',
            'en': 'Analysis problem. Please resend.'
        },
        'model_invalid_json': {
            'hi': 'तकनीकी समस्या। कृपया दोबारा भेजें।',
            'mr': 'तांत्रिक समस्या. कृपया पुन्हा पाठवा.',
            'te': 'సాంకేతిక సమస్య. దయచేసి మళ్లీ పంపండి.',
            'en': 'Technical problem. Please resend.'
        },
        'unknown': {
            'hi': 'कुछ गड़बड़ हुई। कृपया दोबारा कोशिश करें।',
            'mr': 'काहीतरी चूक. कृपया पुन्हा प्रयत्न करा.',
            'te': 'ఏదో తప్పు. దయచేసి మళ్లీ ప్రయత్నించండి.',
            'en': 'Something went wrong. Please try again.'
        }
    }

    return messages.get(error_type, messages['unknown']).get(dialect, messages['unknown']['en'])
