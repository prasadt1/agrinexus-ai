import pytest
import os

# Set env before importing analyzer (module reads at import time)
os.environ['TEMP_AUDIO_BUCKET'] = 'test-bucket'

from src.vision.analyzer import process_image_message
from tests.vision.test_heuristics import generate_dark_github_screenshot, generate_cotton_boll_photo


def test_screenshot_blocked_before_vision_call():
    """Screenshot should be blocked by heuristics, no vision call"""
    message = {'image': {'id': 'fake_media_id'}}
    user_profile = {'dialect': 'en', 'crop': 'cotton', 'phone_number': '1234567890'}

    # Mock download to return screenshot
    import src.vision.analyzer as analyzer
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
    from src.vision.heuristics import run_heuristics

    image_bytes = generate_cotton_boll_photo()
    heuristics_result = run_heuristics(image_bytes)

    assert heuristics_result['decision'] == 'pass'
