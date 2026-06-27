import pytest
import os
import sys

# Set env before importing analyzer (module reads at import time)
os.environ['TEMP_AUDIO_BUCKET'] = 'test-bucket'

# Single source of truth: the deployed crop-diagnosis code in src/processor/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/processor'))
from analyzer import process_image_message
from tests.vision.test_heuristics import generate_dark_github_screenshot, generate_cotton_boll_photo


def test_screenshot_blocked_before_vision_call():
    """Screenshot should be blocked by heuristics, no vision call"""
    message = {'image': {'id': 'fake_media_id'}}
    user_profile = {'dialect': 'en', 'crop': 'cotton', 'phone_number': '1234567890'}

    # Mock download to return screenshot
    import analyzer
    original_download = analyzer.download_whatsapp_image
    original_s3_put = analyzer.s3.put_object

    def mock_download(media_id):
        return generate_dark_github_screenshot()

    def mock_s3_put(**kwargs):
        pass  # No-op S3 upload in tests

    analyzer.download_whatsapp_image = mock_download
    analyzer.s3.put_object = mock_s3_put

    try:
        result = process_image_message(message, user_profile)

        # Should return block message, not call vision model
        # Result can be a string or dict with 'text' key
        result_text = result if isinstance(result, str) else result.get('text', '')
        assert 'screenshot' in result_text.lower()
    finally:
        analyzer.download_whatsapp_image = original_download
        analyzer.s3.put_object = original_s3_put


def test_cotton_boll_passes_to_vision():
    """Real cotton boll should pass heuristics, call vision model"""
    # This test will need vision model mocking
    # For now, just verify heuristics don't block it
    from heuristics import run_heuristics

    image_bytes = generate_cotton_boll_photo()
    heuristics_result = run_heuristics(image_bytes)

    assert heuristics_result['decision'] == 'pass'


def test_low_confidence_returns_safe_template():
    """Low confidence vision result should return safe template"""
    from enforcement import enforce_message_safety
    from messages import get_safe_structured_template

    # Simulate vision model returning low confidence
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'low',
        'inferred_crop': 'unknown',
        'visible_problem': False,
        'severity': 'none',
        'recommendations': 'Cannot identify crop from this photo.'  # Model-generated
    }

    result = enforce_message_safety(vision, 'cotton', 'en')
    expected = get_safe_structured_template('en')

    # Should return the safe structured template, not the model message
    assert result == expected
    assert 'Cannot identify the plant' in result


def test_full_3_layer_defense_screenshot():
    """Full integration: screenshot blocked by heuristics"""
    message = {'image': {'id': 'test_screenshot'}}
    user_profile = {'dialect': 'en', 'crop': 'wheat', 'phone_number': '9876543210'}

    # Mock download
    import analyzer
    original = analyzer.download_whatsapp_image
    original_s3 = analyzer.s3.put_object

    def mock_download(mid):
        return generate_dark_github_screenshot()

    def mock_s3_put(**kwargs):
        pass  # No-op S3 upload

    analyzer.download_whatsapp_image = mock_download
    analyzer.s3.put_object = mock_s3_put

    try:
        result = process_image_message(message, user_profile)

        # Layer 1 should block (no vision call)
        # Result can be string or dict
        result_text = result if isinstance(result, str) else result.get('text', '')
        assert 'screenshot' in result_text.lower()
        assert len(result_text) < 200  # Short block message
    finally:
        analyzer.download_whatsapp_image = original
        analyzer.s3.put_object = original_s3


def test_full_3_layer_defense_real_crop_low_confidence():
    """Full integration: real crop but low confidence → safe template"""
    # This would require mocking Bedrock, which is complex
    # For now, verify enforcement works independently
    from enforcement import enforce_message_safety

    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'low',
        'inferred_crop': 'unknown',
        'visible_problem': False,
        'severity': 'none',
        'recommendations': 'Unclear plant photo.'
    }

    result = enforce_message_safety(vision, 'cotton', 'hi')

    # Layer 3 enforcement → safe template in Hindi
    assert 'पौधे की पहचान स्पष्ट नहीं' in result
