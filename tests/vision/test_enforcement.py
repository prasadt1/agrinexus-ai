import pytest
import sys
import os

# Single source of truth: the deployed crop-diagnosis code in src/processor/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/processor'))
from enforcement import enforce_message_safety


def test_high_confidence_preserves_model_content():
    """High confidence → model's content is preserved (inside the structured 4-section output)."""
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'high',
        'recommendations': 'Cotton bollworm detected on leaves.'
    }

    result = enforce_message_safety(vision, 'cotton', 'en')

    # High confidence keeps the model's diagnosis (wrapped in the 4-section format),
    # rather than replacing it with the safe template.
    assert 'Cotton bollworm detected on leaves.' in result
    assert '*Recommendations:*' in result
    assert 'Cannot identify' not in result


def test_low_confidence_blocks_crop_name():
    """Low confidence → safe template (no crop names)"""
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'low',
        'recommendations': 'This looks like wheat with aphids.'  # Model leaked crop name
    }

    result = enforce_message_safety(vision, 'wheat', 'en')

    # Should return safe template, NOT model message
    assert 'wheat' not in result.lower()
    assert 'Cannot identify' in result


def test_non_crop_hard_block():
    """Non-crop image → hard block message"""
    vision = {
        'is_real_crop_photo': False,
        'non_photo_reason': 'screenshot',
        'crop_confidence': 'low',
        'recommendations': 'Some analysis...'
    }

    result = enforce_message_safety(vision, 'cotton', 'en')

    assert 'screenshot' in result.lower()


def test_medium_confidence_also_gets_template():
    """Medium confidence also gets safe template (Option A)"""
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'medium',
        'recommendations': 'Appears to be cotton with some leaf damage.'
    }

    result = enforce_message_safety(vision, 'cotton', 'en')

    # Should return safe template, not model message
    assert 'Cannot identify' in result
    assert 'cotton' not in result.lower()
