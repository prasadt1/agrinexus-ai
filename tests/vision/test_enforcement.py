import pytest
from src.vision.enforcement import enforce_message_safety


def test_high_confidence_allows_model_message():
    """High confidence → allow model's message"""
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'high',
        'recommendations': 'Cotton bollworm detected on leaves.'
    }

    result = enforce_message_safety(vision, 'cotton', 'en')

    assert result == 'Cotton bollworm detected on leaves.'


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
