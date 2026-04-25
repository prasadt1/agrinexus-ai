"""
Message-level safety enforcement (Option A - Bulletproof).
Prevents crop name leakage when confidence != "high".
"""
from typing import Dict, Any
from messages import get_safe_retake_message, get_block_message


def enforce_message_safety(
    vision_result: Dict[str, Any],
    profile_crop: str,
    dialect: str
) -> str:
    """
    Bulletproof enforcement: trust structured fields only.
    If confidence != "high" → safe template. Zero leakage risk.

    Args:
        vision_result: Vision model JSON output (validated by schema)
        profile_crop: User's registered crop from profile
        dialect: User's dialect (hi/mr/te/en)

    Returns:
        Safe message text for WhatsApp
    """
    is_real_crop = vision_result['is_real_crop_photo']
    non_photo_reason = vision_result.get('non_photo_reason')
    crop_confidence = vision_result['crop_confidence']
    model_message = vision_result['recommendations']  # Validated by schema check

    # Gate 1: Non-crop → hard block
    if not is_real_crop:
        return get_block_message(non_photo_reason or 'screenshot', dialect)

    # Gate 2: High confidence → allow model message (earned the right)
    if crop_confidence == "high":
        return model_message

    # Gate 3: Anything else → safe template (no trust, no scan)
    return get_safe_retake_message(dialect)
