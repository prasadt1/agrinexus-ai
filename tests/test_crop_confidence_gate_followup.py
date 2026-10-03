"""
Crop-confidence gate follow-up: safe template copy, widened confirm, visitor confirmed crop.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parents[1]
PROC = str(REPO / "src" / "processor")
if PROC not in sys.path:
    sys.path.insert(0, PROC)

from enforcement import enforce_message_safety  # noqa: E402
from messages import get_safe_structured_template  # noqa: E402


def test_safe_template_visible_problem_mentions_buttons_not_photo_quality():
    for dialect in ("hi", "mr", "te", "en"):
        text = get_safe_structured_template(dialect, visible_problem=True)
        assert "button" in text.lower() or "बटन" in text or "बटण" in text or "బటన్" in text
        assert "quality" not in text.lower() and "गुणवत्ता" not in text and "నాణ్యత" not in text


def test_safe_template_quality_flagged_mentions_quality():
    text = get_safe_structured_template("en", visible_problem=False, quality_flagged=True)
    assert "quality" in text.lower()


def test_gate2_uses_visible_problem_copy_without_changing_gate():
    vision = {
        "is_real_crop_photo": True,
        "crop_confidence": "low",
        "visible_problem": True,
        "diagnosis": "should not appear",
        "recommendations": "LEAK",
        "severity": "high",
        "confidence_text": "x",
    }
    out = enforce_message_safety(vision, "Cotton", "en")
    assert "LEAK" not in out
    assert "buttons" in out.lower()
    assert "quality" not in out.lower()


def test_non_crop_still_hard_blocked():
    vision = {
        "is_real_crop_photo": False,
        "non_photo_reason": "screenshot",
        "crop_confidence": "low",
        "visible_problem": False,
        "recommendations": "x",
    }
    out = enforce_message_safety(vision, "Cotton", "en")
    assert "screenshot" in out.lower()


def test_high_confidence_unchanged_structured():
    vision = {
        "is_real_crop_photo": True,
        "crop_confidence": "high",
        "visible_problem": True,
        "diagnosis": "Pink bollworm on cotton boll",
        "severity": "high",
        "recommendations": "Remove larvae and spray spinosad",
        "confidence_text": "High - boll and larvae clear",
    }
    out = enforce_message_safety(vision, "Cotton", "en")
    assert "Pink bollworm" in out
    assert "spinosad" in out


def test_visitor_sample_and_farmer_confirm_share_helper(monkeypatch):
    """Byte-identical: both paths call _diagnose_image_with_confirmed_crop."""
    monkeypatch.setenv("TABLE_NAME", "t")
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "kb")
    monkeypatch.setenv("GUARDRAIL_ID", "")
    monkeypatch.setenv("GUARDRAIL_VERSION", "1")
    monkeypatch.setenv("TEMP_AUDIO_BUCKET", "bucket")
    monkeypatch.setenv("VISITOR_SAMPLE_IMAGE_CROP", "Cotton")

    calls = []

    output_mod = types.ModuleType("output")
    output_mod.text_to_speech = lambda *a, **k: None
    output_mod.truncate_for_voice = lambda t, *a, **k: t
    output_mod.voice_truncation_prefix = lambda *a, **k: ""
    monkeypatch.setitem(sys.modules, "output", output_mod)
    analyzer_mod = types.ModuleType("analyzer")

    def _analyze(image_bytes, dialect, crop, district=None):
        calls.append((image_bytes, dialect, crop, district))
        return {"recommendations": f"ADVICE|{dialect}|{crop}|{district}"}

    def _diagnose(image_bytes, dialect, crop, district=None):
        calls.append((image_bytes, dialect, crop, district))
        return f"ADVICE|{dialect}|{crop}|{district}"

    analyzer_mod.analyze_crop_image = _analyze
    analyzer_mod.diagnose_with_confirmed_crop = _diagnose
    analyzer_mod.process_image_message = lambda *a, **k: {}
    monkeypatch.setitem(sys.modules, "analyzer", analyzer_mod)

    wa = types.ModuleType("common.whatsapp")
    wa.send_whatsapp_message = MagicMock(return_value=True)
    wa.send_whatsapp_list = MagicMock(return_value=True)
    wa.send_whatsapp_image = MagicMock(return_value=True)
    wa.send_whatsapp_buttons = MagicMock(return_value=True)
    monkeypatch.setitem(sys.modules, "common.whatsapp", wa)

    layer = str(REPO / "src" / "common-layer" / "python")
    if layer not in sys.path:
        sys.path.insert(0, layer)

    original = list(sys.path)
    try:
        sys.path.insert(0, PROC)
        sys.path.insert(0, layer)
        spec = importlib.util.spec_from_file_location(
            "processor_handler_confirmed_crop",
            REPO / "src" / "processor" / "handler.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = original

    img = b"FAKE_IMAGE_BYTES"
    visitor_reply = mod._diagnose_image_with_confirmed_crop(img, "en", "Cotton", district="Latur")
    farmer_reply = mod._diagnose_image_with_confirmed_crop(img, "en", "Cotton", district="Latur")
    assert visitor_reply == farmer_reply
    assert visitor_reply.startswith("ADVICE|en|Cotton|Latur")
    assert "contact your nearest KVK" in visitor_reply
    assert calls[0] == calls[1]
