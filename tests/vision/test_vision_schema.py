# tests/vision/test_vision_schema.py
import pytest
import json
from src.vision.analyzer import validate_vision_schema


def test_valid_schema_passes():
    """Valid vision response passes validation"""
    vision = {
        'is_real_crop_photo': True,
        'inferred_crop': 'Cotton',
        'crop_confidence': 'high',
        'visible_problem': True,
        'severity': 'medium',
        'recommendations': 'Bollworm detected.'
    }

    # Should not raise
    validate_vision_schema(vision)


def test_missing_required_field_fails():
    """Missing required field raises ValueError"""
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'high',
        # Missing: inferred_crop, visible_problem, severity, recommendations
    }

    with pytest.raises(ValueError, match="Missing required fields"):
        validate_vision_schema(vision)


def test_invalid_crop_confidence_fails():
    """Invalid crop_confidence enum raises ValueError"""
    vision = {
        'is_real_crop_photo': True,
        'inferred_crop': 'Cotton',
        'crop_confidence': 'maybe',  # Invalid
        'visible_problem': True,
        'severity': 'medium',
        'recommendations': 'Test'
    }

    with pytest.raises(ValueError, match="Invalid crop_confidence"):
        validate_vision_schema(vision)


def test_fence_stripping_works():
    """Model returning fenced JSON should be parsed correctly"""
    # Simulate what analyze_crop_image does with fenced JSON
    fenced_json = '''```json
{
    "is_real_crop_photo": true,
    "inferred_crop": "Cotton",
    "crop_confidence": "high",
    "visible_problem": true,
    "severity": "medium",
    "recommendations": "Test message"
}
```'''

    # Simulate fence stripping logic from analyzer.py
    raw_text = fenced_json.strip()
    if raw_text.startswith('```'):
        raw_text = '\n'.join(raw_text.split('\n')[1:-1])

    vision = json.loads(raw_text)

    # Should not raise
    validate_vision_schema(vision)
    assert vision['inferred_crop'] == 'Cotton'
