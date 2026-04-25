"""
Tests for structured 4-section output format.
Verifies both high-confidence and low-confidence cases return professional format.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/processor'))

from enforcement import enforce_message_safety, _format_structured_output
from messages import get_safe_structured_template


def test_high_confidence_formats_4_sections():
    """High confidence case should format model's diagnosis/severity/recommendations/confidence into 4 sections"""
    vision_result = {
        'is_real_crop_photo': True,
        'crop_confidence': 'high',
        'visible_problem': True,
        'diagnosis': 'कपास की फली पर इल्ली दिखाई दे रही है',
        'severity': 'high',
        'recommendations': 'नीम का तेल स्प्रे करें',
        'confidence_text': 'उच्च - कपास की फली स्पष्ट दिखाई दे रही है'
    }

    result = enforce_message_safety(vision_result, 'Cotton', 'hi')

    # Check all 4 sections present
    assert '**निदान (Diagnosis):**' in result
    assert '**गंभीरता (Severity):**' in result
    assert '**सिफ़ारिशें (Recommendations):**' in result
    assert '**विश्वास (Confidence):**' in result

    # Check content
    assert 'कपास की फली पर इल्ली दिखाई दे रही है' in result
    assert 'high' in result
    assert 'नीम का तेल स्प्रे करें' in result
    assert 'उच्च - कपास की फली स्पष्ट दिखाई दे रही है' in result


def test_low_confidence_uses_structured_template():
    """Low confidence should use structured safe template with same 4 sections"""
    vision_result = {
        'is_real_crop_photo': True,
        'crop_confidence': 'low',
        'visible_problem': False,
        'diagnosis': 'unclear',
        'severity': 'unknown',
        'recommendations': 'unclear',
        'confidence_text': 'low'
    }

    result = enforce_message_safety(vision_result, 'Cotton', 'hi')

    # Check all 4 sections present
    assert '**निदान (Diagnosis):**' in result
    assert '**गंभीरता (Severity):**' in result
    assert '**सिफ़ारिशें (Recommendations):**' in result
    assert '**विश्वास (Confidence):**' in result

    # Check safe template content
    assert 'पौधे की पहचान स्पष्ट नहीं है' in result
    assert 'अज्ञात' in result
    assert 'स्पष्ट फोटो भेजें' in result
    assert 'कम - फोटो की गुणवत्ता' in result


def test_medium_confidence_also_uses_structured_template():
    """Medium confidence should also use structured safe template"""
    vision_result = {
        'is_real_crop_photo': True,
        'crop_confidence': 'medium',
        'visible_problem': False,
        'diagnosis': 'unclear',
        'severity': 'unknown',
        'recommendations': 'unclear',
        'confidence_text': 'medium'
    }

    result = enforce_message_safety(vision_result, 'Wheat', 'hi')

    # Should get structured template (not model output)
    assert '**निदान (Diagnosis):**' in result
    assert 'पौधे की पहचान स्पष्ट नहीं है' in result


def test_high_confidence_no_problem_adds_hedge():
    """High confidence + no visible problem should add hedge language"""
    vision_result = {
        'is_real_crop_photo': True,
        'crop_confidence': 'high',
        'visible_problem': False,
        'diagnosis': 'पौधा स्वस्थ दिखाई दे रहा है',
        'severity': 'none',
        'recommendations': 'कोई कार्रवाई आवश्यक नहीं',
        'confidence_text': 'उच्च - पौधा स्पष्ट दिखाई दे रहा है'
    }

    result = enforce_message_safety(vision_result, 'Cotton', 'hi')

    # Should have base recommendations + hedge
    assert 'कोई कार्रवाई आवश्यक नहीं' in result
    assert 'कीट की जांच के लिए नियमित निगरानी करते रहें' in result


def test_format_helper_english():
    """Test the formatting helper with English"""
    result = _format_structured_output(
        diagnosis='Cotton bollworm visible on boll',
        severity='high',
        recommendations='Apply neem oil spray',
        confidence_text='High - clear image of cotton boll',
        dialect='en'
    )

    assert '**Diagnosis:** Cotton bollworm visible on boll' in result
    assert '**Severity:** high' in result
    assert '**Recommendations:** Apply neem oil spray' in result
    assert '**Confidence:** High - clear image of cotton boll' in result


def test_template_all_dialects():
    """Verify structured template exists for all supported dialects"""
    for dialect in ['hi', 'mr', 'te', 'en']:
        template = get_safe_structured_template(dialect)

        # All should have 4 sections (check for 4 occurrences of **)
        assert template.count('**') >= 8  # 4 sections × 2 markers each

        # All should mention diagnosis/severity/recommendations/confidence concepts
        assert len(template) > 100  # Non-empty template
