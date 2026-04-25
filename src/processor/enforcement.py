"""
Message-level safety enforcement (Option A - Bulletproof + Hedge Language).
Prevents crop name leakage when confidence != "high".
Adds uncertainty expressions when model says "healthy" but might miss small pests.
"""
from typing import Dict, Any
from messages import get_safe_retake_message, get_block_message


def enforce_message_safety(
    vision_result: Dict[str, Any],
    profile_crop: str,
    dialect: str
) -> str:
    """
    Bulletproof enforcement with hedge language for uncertainty.

    - If confidence != "high" → safe template (zero leakage risk)
    - If confidence == "high" but no visible_problem → add "keep monitoring" hedge

    This addresses model blindness to small insects (beetles/grasshoppers on wheat ears).
    Instead of falsely claiming "healthy", we add "keep monitoring for pests".

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
    visible_problem = vision_result.get('visible_problem', False)
    model_message = vision_result['recommendations']  # Validated by schema check

    # Gate 1: Non-crop → hard block
    if not is_real_crop:
        return get_block_message(non_photo_reason or 'screenshot', dialect)

    # Gate 2: High confidence + no visible problem → add hedge language
    # (Model says "healthy" but we're not 100% certain - express uncertainty)
    if crop_confidence == "high" and not visible_problem:
        hedge_additions = {
            'hi': ' कीट की जांच के लिए नियमित निगरानी करते रहें।',
            'mr': ' कीटकांचे परीक्षण करण्यासाठी नियमित देखरेख करा.',
            'te': ' చీడలు ఉన్నాయో లేదో తనిఖీ చేయడానికి క్రమంగా పర్యవేక్షించండి.',
            'en': ' Keep monitoring regularly to check for pests.'
        }
        model_message += hedge_additions.get(dialect, hedge_additions['en'])

    # Gate 3: High confidence → allow model message (with hedge if added)
    if crop_confidence == "high":
        return model_message

    # Gate 4: Anything else → safe template (no trust, no leakage)
    return get_safe_retake_message(dialect)
