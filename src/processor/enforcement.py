"""
Message-level safety enforcement (Option A - Structured 4-Section Output Always).
Prevents crop name leakage when confidence != "high".
Returns professional 4-section format for ALL responses.
"""
from typing import Dict, Any
from messages import get_safe_retake_message, get_block_message, get_safe_structured_template
from messages import (
    get_assumed_confidence_note,
    get_assumed_crop_line,
    get_crop_correction_hint,
    localize_crop_name,
)


def _localize_severity(severity: str, dialect: str) -> str:
    """
    Convert model enum severity (high/medium/low/none/unknown) into user-facing localized text.
    Keep enums out of farmer-facing text to avoid language mixing.
    """
    sev = (severity or "unknown").strip().lower() or "unknown"
    if sev not in ("high", "medium", "low", "none", "unknown"):
        sev = "unknown"

    mapping = {
        "hi": {"high": "उच्च", "medium": "मध्यम", "low": "कम", "none": "कोई नहीं", "unknown": "अज्ञात"},
        "mr": {"high": "उच्च", "medium": "मध्यम", "low": "कमी", "none": "नाही", "unknown": "अज्ञात"},
        "te": {"high": "ఎక్కువ", "medium": "మధ్యమ", "low": "తక్కువ", "none": "లేదు", "unknown": "తెలియదు"},
        "en": {"high": "High", "medium": "Medium", "low": "Low", "none": "None", "unknown": "Unknown"},
    }
    lang = (dialect or "en").strip().lower() or "en"
    if lang not in mapping:
        lang = "en"
    return mapping[lang][sev]


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
    # WhatsApp uses single-asterisk for bold: *text*.
    # Avoid markdown "**" which can show up as stray "*" in WhatsApp clients.
    section_labels = {
        'hi': {
            'diagnosis': '*निदान (Diagnosis):*',
            'severity': '*गंभीरता (Severity):*',
            'recommendations': '*सिफ़ारिशें (Recommendations):*',
            'confidence': '*विश्वास (Confidence):*'
        },
        'mr': {
            'diagnosis': '*निदान (Diagnosis):*',
            'severity': '*तीव्रता (Severity):*',
            'recommendations': '*शिफारशी (Recommendations):*',
            'confidence': '*विश्वास (Confidence):*'
        },
        'te': {
            'diagnosis': '*నిర్ధారణ (Diagnosis):*',
            'severity': '*తీవ్రత (Severity):*',
            'recommendations': '*సిఫార్సులు (Recommendations):*',
            'confidence': '*విశ్వాసం (Confidence):*'
        },
        'en': {
            'diagnosis': '*Diagnosis:*',
            'severity': '*Severity:*',
            'recommendations': '*Recommendations:*',
            'confidence': '*Confidence:*'
        }
    }

    labels = section_labels.get(dialect, section_labels['en'])
    localized_severity = _localize_severity(severity, dialect)

    return f"""{labels['diagnosis']} {diagnosis}
{labels['severity']} {localized_severity}
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
    # Backward-compat: some unit tests and legacy paths stub minimal fields.
    is_real_crop = vision_result.get('is_real_crop_photo', True)
    non_photo_reason = vision_result.get('non_photo_reason')
    crop_confidence = (vision_result.get('crop_confidence') or vision_result.get('confidence') or "low")
    visible_problem = vision_result.get('visible_problem', False)

    # Gate 1: Non-crop → hard block
    if not is_real_crop:
        return get_block_message(non_photo_reason or 'screenshot', dialect)

    # Gate 2: Low/medium confidence → structured safe template
    if crop_confidence != "high":
        return get_safe_structured_template(
            dialect,
            visible_problem=bool(visible_problem),
            quality_flagged=bool(vision_result.get("quality_flagged", False)),
        )

    # Gate 3: High confidence → format model's structured output
    diagnosis = vision_result.get('diagnosis') or ""
    severity = vision_result.get('severity') or "unknown"
    recommendations = vision_result.get('recommendations') or vision_result.get('final_message') or ""
    confidence_text = vision_result.get('confidence_text') or str(vision_result.get('confidence') or "")

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


def format_crop_message(
    vision_result: Dict[str, Any],
    crop: str,
    dialect: str,
    assumed: bool = False,
) -> str:
    """
    Four-section output for a crop that is an input rather than a model guess:
    either the farmer confirmed it, or it came from the profile and the image did
    not contradict it.

    Gate 2 is deliberately not applied here. It guards against leaking a crop name
    the model guessed; on this path the crop is supplied, so that risk is absent.
    Gate 1 (non-crop photo) still applies.
    """
    if not vision_result.get("is_real_crop_photo", True):
        return get_block_message(vision_result.get("non_photo_reason") or "screenshot", dialect)

    diagnosis = vision_result.get("diagnosis") or ""
    severity = vision_result.get("severity") or "unknown"
    recommendations = vision_result.get("recommendations") or vision_result.get("final_message") or ""
    confidence_text = vision_result.get("confidence_text") or ""

    crop_local = localize_crop_name(crop, dialect)
    if assumed:
        # The diagnosing call was told the crop, so its confidence wording justifies
        # that crop ("cotton boll clearly visible") rather than reporting what the
        # first pass saw. Show only the note that separates pest from crop.
        confidence_text = get_assumed_confidence_note(crop_local, dialect)

    body = _format_structured_output(diagnosis, severity, recommendations, confidence_text, dialect)
    if not assumed:
        return body

    return "\n".join(
        [
            get_assumed_crop_line(crop_local, dialect),
            "",
            body,
            "",
            get_crop_correction_hint(crop_local, dialect),
        ]
    )
