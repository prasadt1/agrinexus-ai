"""
Message-level safety enforcement (Option A - Structured 4-Section Output Always).
Prevents crop name leakage when confidence != "high".
Returns professional 4-section format for ALL responses.
"""
from typing import Dict, Any
from messages import get_safe_retake_message, get_block_message, get_safe_structured_template


def _format_structured_output(
    diagnosis: str,
    severity: str,
    recommendations: str,
    confidence_text: str,
    dialect: str
) -> str:
    """
    Format the 4-section structured output.

    Returns professional format:
    **निदान (Diagnosis):** [what you see]
    **गंभीरता (Severity):** [high/medium/low/none]
    **सिफ़ारिशें (Recommendations):** [what to do]
    **विश्वास (Confidence):** [confidence level + why]
    """
    section_labels = {
        'hi': {
            'diagnosis': '**निदान (Diagnosis):**',
            'severity': '**गंभीरता (Severity):**',
            'recommendations': '**सिफ़ारिशें (Recommendations):**',
            'confidence': '**विश्वास (Confidence):**'
        },
        'mr': {
            'diagnosis': '**निदान (Diagnosis):**',
            'severity': '**गंभीरता (Severity):**',
            'recommendations': '**सिफ़ारिशें (Recommendations):**',
            'confidence': '**विश्वास (Confidence):**'
        },
        'te': {
            'diagnosis': '**నిర్ధారణ (Diagnosis):**',
            'severity': '**తీవ్రత (Severity):**',
            'recommendations': '**సిఫార్సులు (Recommendations):**',
            'confidence': '**విశ్వాసం (Confidence):**'
        },
        'en': {
            'diagnosis': '**Diagnosis:**',
            'severity': '**Severity:**',
            'recommendations': '**Recommendations:**',
            'confidence': '**Confidence:**'
        }
    }

    labels = section_labels.get(dialect, section_labels['en'])

    return f"""{labels['diagnosis']} {diagnosis}
{labels['severity']} {severity}
{labels['recommendations']} {recommendations}
{labels['confidence']} {confidence_text}"""


def enforce_message_safety(
    vision_result: Dict[str, Any],
    profile_crop: str,
    dialect: str
) -> str:
    """
    Structured 4-section output enforcement.

    - If confidence != "high" → structured safe template (zero leakage risk)
    - If confidence == "high" → format model's structured output into 4 sections
    - Add hedge language if model says "healthy" but we're uncertain

    Args:
        vision_result: Vision model JSON output (validated by schema)
        profile_crop: User's registered crop from profile
        dialect: User's dialect (hi/mr/te/en)

    Returns:
        Structured 4-section message for WhatsApp
    """
    is_real_crop = vision_result['is_real_crop_photo']
    non_photo_reason = vision_result.get('non_photo_reason')
    crop_confidence = vision_result['crop_confidence']
    visible_problem = vision_result.get('visible_problem', False)

    # Gate 1: Non-crop → hard block
    if not is_real_crop:
        return get_block_message(non_photo_reason or 'screenshot', dialect)

    # Gate 2: Low/medium confidence → structured safe template
    if crop_confidence != "high":
        return get_safe_structured_template(dialect)

    # Gate 3: High confidence → format model's structured output
    diagnosis = vision_result['diagnosis']
    severity = vision_result['severity']
    recommendations = vision_result['recommendations']
    confidence_text = vision_result['confidence_text']

    # Add hedge language if no visible problem (uncertainty about small pests)
    if not visible_problem:
        hedge_additions = {
            'hi': ' कीट की जांच के लिए नियमित निगरानी करते रहें।',
            'mr': ' कीटकांचे परीक्षण करण्यासाठी नियमित देखरेख करा.',
            'te': ' చీడలు ఉన్నాయో లేదో తనిఖీ చేయడానికి క్రమంగా పర్యవేక్షించండి.',
            'en': ' Keep monitoring regularly to check for pests.'
        }
        recommendations += hedge_additions.get(dialect, hedge_additions['en'])

    return _format_structured_output(
        diagnosis, severity, recommendations, confidence_text, dialect
    )
