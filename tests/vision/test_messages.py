import pytest
from src.vision.messages import get_safe_retake_message, get_block_message, get_error_message


def test_safe_retake_message_hindi():
    """Safe retake message in Hindi"""
    msg = get_safe_retake_message('hi')

    assert 'पौधे की पहचान स्पष्ट नहीं' in msg
    assert 'फोटो भेजें' in msg


def test_safe_retake_message_english():
    """Safe retake message in English"""
    msg = get_safe_retake_message('en')

    assert 'Cannot identify the plant' in msg
    assert 'clearer photo' in msg


def test_safe_retake_message_unsupported_dialect():
    """Unsupported dialect should fallback to English"""
    msg = get_safe_retake_message('ta')  # Tamil not supported

    assert 'Cannot identify the plant' in msg


def test_block_message_screenshot():
    """Screenshot block message in all dialects"""
    assert 'स्क्रीनशॉट' in get_block_message('screenshot_ui', 'hi')
    assert 'स्क्रीनशॉट' in get_block_message('screenshot_ui', 'mr')
    assert 'స్క్రీన్‌షాట్' in get_block_message('screenshot_ui', 'te')
    assert 'screenshot' in get_block_message('screenshot_ui', 'en')


def test_block_message_logo():
    """Logo block message"""
    msg = get_block_message('logo', 'en')
    assert 'logo' in msg.lower() or 'graphic' in msg.lower()


def test_error_message_download():
    """Download error message"""
    msg = get_error_message('download_failed', 'en')
    assert 'download' in msg.lower() or 'resend' in msg.lower()


def test_error_message_unknown_fallback():
    """Unknown error type should return generic error"""
    msg = get_error_message('nonexistent_error', 'en')
    assert 'wrong' in msg.lower() or 'try again' in msg.lower()
