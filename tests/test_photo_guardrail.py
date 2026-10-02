"""Every Bedrock call on the photo path carries the content guardrail, and a block fails closed."""
import io
import json

import pytest

from src.processor import analyzer
from common.guardrail_reply import localized_guardrail_refusal


VISION_OK = {
    "is_real_crop_photo": True,
    "non_photo_reason": None,
    "inferred_crop": "Cotton",
    "crop_confidence": "high",
    "visible_problem": True,
    "severity": "medium",
    "diagnosis": "Pink bollworm damage on the boll.",
    "recommendations": "Remove and destroy damaged bolls.",
    "insects_visible": [],
    "confidence_text": "high",
}


class _Bedrock:
    def __init__(self, text, intervened=False):
        self.calls = []
        self._text = text
        self._intervened = intervened

    def invoke_model(self, **kwargs):
        self.calls.append(kwargs)
        body = {"content": [{"type": "text", "text": self._text}]}
        if self._intervened:
            body["amazon-bedrock-guardrailAction"] = "INTERVENED"
        return {"body": io.BytesIO(json.dumps(body).encode())}


@pytest.fixture(autouse=True)
def _guardrail_env(monkeypatch):
    monkeypatch.setenv("GUARDRAIL_ID", "gr-test")
    monkeypatch.setenv("GUARDRAIL_VERSION", "7")
    monkeypatch.setattr(analyzer, "_looks_like_screenshot_or_ui", lambda b: False)
    monkeypatch.setattr(analyzer, "_looks_like_logo_or_illustration", lambda b: False, raising=False)
    monkeypatch.setattr(analyzer, "_extract_primary_frame", lambda b: b, raising=False)


IMG = b"\xff\xd8\xff\xe0" + b"0" * 64


def test_relevance_call_carries_guardrail(monkeypatch):
    fake = _Bedrock('{"relevance":"agri_photo","reason":"other","confidence":"high"}')
    monkeypatch.setattr(analyzer, "bedrock", fake)
    analyzer.classify_image_relevance(IMG, "en")
    assert fake.calls[0]["guardrailIdentifier"] == "gr-test"
    assert fake.calls[0]["guardrailVersion"] == "7"


def test_diagnosis_call_carries_guardrail(monkeypatch):
    fake = _Bedrock(json.dumps(VISION_OK))
    monkeypatch.setattr(analyzer, "bedrock", fake)
    analyzer.analyze_crop_image(IMG, "en", "cotton")
    assert fake.calls[0]["guardrailIdentifier"] == "gr-test"
    assert fake.calls[0]["guardrailVersion"] == "7"


def test_confirmed_crop_call_carries_guardrail(monkeypatch):
    fake = _Bedrock(json.dumps(VISION_OK))
    monkeypatch.setattr(analyzer, "bedrock", fake)
    analyzer.diagnose_with_confirmed_crop(IMG, "en", "Cotton")
    assert fake.calls and all(c.get("guardrailIdentifier") == "gr-test" for c in fake.calls)


@pytest.mark.parametrize("dialect", ["en", "hi", "mr", "te"])
def test_blocked_diagnosis_returns_localized_refusal(monkeypatch, dialect):
    fake = _Bedrock("I can only help with farming questions", intervened=True)
    monkeypatch.setattr(analyzer, "bedrock", fake)
    out = analyzer.analyze_crop_image(IMG, dialect, "cotton")
    assert out["guardrail_blocked"] is True
    assert out["recommendations"] == localized_guardrail_refusal(dialect)
    assert out["visible_problem"] is False


def test_blocked_confirmed_crop_returns_refusal_only(monkeypatch):
    fake = _Bedrock("I can only help with farming questions", intervened=True)
    monkeypatch.setattr(analyzer, "bedrock", fake)
    assert analyzer.diagnose_with_confirmed_crop(IMG, "mr", "Cotton") == localized_guardrail_refusal("mr")


def _run_process_image(monkeypatch, analyze):
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "false")
    monkeypatch.setenv("VISION_QUALITY_GATE_ENABLED", "false")
    monkeypatch.setattr(analyzer, "TEMP_BUCKET", "bucket", raising=False)
    monkeypatch.setattr(analyzer, "download_whatsapp_image", lambda _id: IMG)
    monkeypatch.setattr(analyzer, "run_heuristics", lambda b: {"decision": "pass", "reason": None, "metrics": {}})
    monkeypatch.setattr(analyzer, "s3", type("S", (), {"put_object": lambda self, **k: None})())
    monkeypatch.setattr(analyzer, "analyze_crop_image", analyze)
    return analyzer.process_image_message(
        {"image": {"id": "m1"}, "from": "15550001111"},
        {"dialect": "hi", "crop": "Cotton", "phone_number": "15550001111"},
    )


def test_process_image_returns_refusal_when_blocked(monkeypatch):
    blocked = {
        "is_real_crop_photo": False, "inferred_crop": "unknown", "crop_confidence": "low",
        "visible_problem": False, "severity": "unknown", "guardrail_blocked": True,
        "recommendations": localized_guardrail_refusal("hi"),
    }
    out = _run_process_image(monkeypatch, lambda *a, **k: dict(blocked))
    assert out["text"] == localized_guardrail_refusal("hi")
    assert out.get("guardrail_blocked") is True
    assert "pending_crop_confirm" not in out


def test_process_image_refuses_when_second_pass_blocked(monkeypatch):
    first = dict(VISION_OK, crop_confidence="medium", inferred_crop="unknown")
    blocked = {
        "is_real_crop_photo": False, "inferred_crop": "unknown", "crop_confidence": "low",
        "visible_problem": False, "severity": "unknown", "guardrail_blocked": True,
        "recommendations": localized_guardrail_refusal("hi"),
    }

    def analyze(*a, confirmed_crop=False, **k):
        return dict(blocked) if confirmed_crop else dict(first)

    out = _run_process_image(monkeypatch, analyze)
    assert out["text"] == localized_guardrail_refusal("hi")
    assert "pending_crop_confirm" not in out
