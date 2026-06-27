import pytest
import sys
import os

# Single source of truth: the deployed crop-diagnosis code in src/processor/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/processor'))
from messages import get_safe_retake_message, get_block_message, get_error_message


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
    assert 'स्क्रीनशॉट' in get_block_message('screenshot', 'hi')
    assert 'स्क्रीनशॉट' in get_block_message('screenshot', 'mr')
    assert 'స్క్రీన్‌షాట్' in get_block_message('screenshot', 'te')
    assert 'screenshot' in get_block_message('screenshot', 'en')


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


@pytest.mark.parametrize('dialect', ['hi', 'mr', 'te', 'en'])
def test_safe_retake_all_dialects(dialect):
    """All dialects should have safe retake messages"""
    msg = get_safe_retake_message(dialect)
    assert len(msg) > 0
    assert len(msg) < 150  # WhatsApp-friendly


@pytest.mark.parametrize('dialect', ['hi', 'mr', 'te', 'en'])
def test_error_messages_all_dialects(dialect):
    """All dialects should have error messages"""
    for error_type in ['download_failed', 'model_error', 'model_invalid_json', 'unknown', 'rate_limit']:
        msg = get_error_message(error_type, dialect)
        assert len(msg) > 0
        assert len(msg) < 150


def test_all_messages_whatsapp_friendly():
    """All messages should be under 150 characters for mobile display"""
    for dialect in ['hi', 'mr', 'te', 'en']:
        assert len(get_safe_retake_message(dialect)) < 150

        for reason in ['screenshot', 'logo', 'too_small', 'document', 'too_blurry']:
            assert len(get_block_message(reason, dialect)) < 150

        for error in ['download_failed', 'model_error', 'model_invalid_json', 'unknown', 'rate_limit']:
            assert len(get_error_message(error, dialect)) < 150
