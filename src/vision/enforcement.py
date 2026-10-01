"""
Message-level safety enforcement (Option A - Bulletproof).
Prevents crop name leakage when confidence != "high".
"""
from typing import Dict, Any
from src.vision.messages import get_safe_structured_template, get_block_message


def enforce_message_safety(
    vision_result: Dict[str, Any],
    profile_crop: str,
    dialect: str
) -> str:
    """
    Bulletproof enforcement: trust structured fields only.
    If confidence != "high" → safe template. Zero leakage risk.
    Gate 2 behavior unchanged; only the template copy is richer.
    """
    is_real_crop = vision_result.get('is_real_crop_photo', True)
    non_photo_reason = vision_result.get('non_photo_reason')
    crop_confidence = vision_result.get('crop_confidence') or vision_result.get('confidence') or "low"
    visible_problem = vision_result.get('visible_problem', False)

    # Gate 1: Non-crop → hard block
    if not is_real_crop:
        return get_block_message(non_photo_reason or 'screenshot', dialect)

    # Gate 2: Low/medium confidence → structured safe template (unchanged gate)
    if crop_confidence != "high":
        return get_safe_structured_template(
            dialect,
            visible_problem=bool(visible_problem),
            quality_flagged=bool(vision_result.get("quality_flagged", False)),
        )

    # Gate 3: High confidence → allow model message
    return vision_result.get('recommendations') or vision_result.get('final_message') or ""
