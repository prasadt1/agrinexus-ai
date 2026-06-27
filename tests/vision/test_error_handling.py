"""
Tests for error handling in vision pipeline.
Ensures all error paths return user-friendly messages.
"""
import pytest
import sys
import os

# Single source of truth: the deployed crop-diagnosis code in src/processor/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/processor'))
from analyzer import process_image_message, validate_vision_schema
from messages import get_error_message


def test_download_failure_returns_error_message():
    """Download failure should return user-friendly error"""
    import analyzer
    import urllib.error

    original = analyzer.download_whatsapp_image

    def mock_download_fail(media_id):
        raise urllib.error.HTTPError(None, 404, "Not found", None, None)

    analyzer.download_whatsapp_image = mock_download_fail

    message = {'image': {'id': 'invalid_id'}}
    user_profile = {'dialect': 'en', 'phone_number': '1234'}

    try:
        result = process_image_message(message, user_profile)

        # Should return error message, not crash
        # Check if it's a dict (with text key) or string
        if isinstance(result, dict):
            result_text = result.get('text', result)
        else:
            result_text = result

        assert 'download' in result_text.lower() or 'resend' in result_text.lower()
    finally:
        analyzer.download_whatsapp_image = original


def test_schema_validation_failure_raises_error():
    """Invalid vision JSON should raise ValueError"""
    # Test validate_vision_schema directly
    with pytest.raises(ValueError):
        validate_vision_schema({'incomplete': 'data'})


def test_schema_validation_missing_fields():
    """Missing required fields should raise ValueError"""
    incomplete_schemas = [
        {},  # Empty
        {'is_real_crop_photo': True},  # Missing other fields
        {'is_real_crop_photo': True, 'inferred_crop': 'cotton'},  # Missing confidence
        {'is_real_crop_photo': True, 'inferred_crop': 'cotton', 'crop_confidence': 'high'},  # Missing visible_problem
    ]

    for schema in incomplete_schemas:
        with pytest.raises(ValueError):
            validate_vision_schema(schema)


def test_schema_validation_valid_schema():
    """Valid schema should not raise"""
    valid_schema = {
        'is_real_crop_photo': True,
        'inferred_crop': 'Cotton',
        'crop_confidence': 'high',
        'insects_visible': [],
        'visible_problem': 'pest',
        'severity': 'medium',
        'recommendations': 'Test recommendations'
    }

    # Should not raise
    validate_vision_schema(valid_schema)


def test_error_messages_exist():
    """All error message types should exist in all dialects"""
    error_types = ['download_failed', 'model_error', 'model_invalid_json', 'unknown', 'rate_limit']
    dialects = ['hi', 'mr', 'te', 'en']

    for error_type in error_types:
        for dialect in dialects:
            msg = get_error_message(error_type, dialect)
            assert msg, f"Missing message for {error_type} in {dialect}"
            assert len(msg) > 0, f"Empty message for {error_type} in {dialect}"


def test_unknown_error_type_returns_unknown_message():
    """Unknown error type should return 'unknown' message"""
    msg = get_error_message('some_random_error', 'en')
    # Should fall back to 'unknown' message
    assert 'wrong' in msg.lower() or 'try again' in msg.lower()
