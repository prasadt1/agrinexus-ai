"""The sample photo is sent as an image message, and the photo prompt matches advice to what is visible."""
import io
import json

import pytest

from src.processor import analyzer

PHONE = "4915112345678"


class _Ok:
    status_code = 200
    text = "{}"

    def json(self):
        return {"messages": [{"id": "wamid.x"}]}


def test_image_payload_sends_the_link_and_caption(monkeypatch):
    import common.whatsapp as wa

    posted = []
    monkeypatch.setattr(wa, "get_whatsapp_credentials", lambda: ("tok", "pnid"))
    monkeypatch.setattr(wa.requests, "post", lambda url, **k: posted.append((url, k["json"])) or _Ok())
    assert wa.send_whatsapp_image(PHONE, "https://b.s3.test/k.jpg?sig", "Sample crop photo.") is True
    url, payload = posted[0]
    assert url.endswith("/pnid/messages")
    assert payload == {
        "messaging_product": "whatsapp",
        "to": PHONE,
        "type": "image",
        "image": {"link": "https://b.s3.test/k.jpg?sig", "caption": "Sample crop photo."},
    }


def test_image_without_caption_omits_it(monkeypatch):
    import common.whatsapp as wa

    posted = []
    monkeypatch.setattr(wa, "get_whatsapp_credentials", lambda: ("tok", "pnid"))
    monkeypatch.setattr(wa.requests, "post", lambda url, **k: posted.append(k["json"]) or _Ok())
    wa.send_whatsapp_image(PHONE, "https://b.s3.test/k.jpg")
    assert posted[0]["image"] == {"link": "https://b.s3.test/k.jpg"}


class _Bedrock:
    def __init__(self):
        self.calls = []

    def invoke_model(self, **kwargs):
        self.calls.append(kwargs)
        body = {"content": [{"type": "text", "text": json.dumps({
            "is_real_crop_photo": True, "non_photo_reason": None, "insects_visible": [],
            "inferred_crop": "Cotton", "crop_confidence": "high", "diagnosis": "Holes in leaves.",
            "visible_problem": True, "severity": "medium",
            "recommendations": "Check leaf undersides.", "confidence_text": "Medium - no insect visible.",
        })}]}
        return {"body": io.BytesIO(json.dumps(body).encode())}


@pytest.fixture
def prompt(monkeypatch):
    monkeypatch.setenv("GUARDRAIL_ID", "")
    monkeypatch.setattr(analyzer, "_looks_like_screenshot_or_ui", lambda b: False)
    monkeypatch.setattr(analyzer, "_looks_like_logo_or_illustration", lambda b: False, raising=False)
    monkeypatch.setattr(analyzer, "_extract_primary_frame", lambda b: b, raising=False)
    fake = _Bedrock()
    monkeypatch.setattr(analyzer, "bedrock", fake)
    analyzer.diagnose_with_confirmed_crop(b"\xff\xd8\xff\xe0" + b"0" * 64, "en", "Cotton")
    texts = [part["text"] for call in fake.calls
             for msg in json.loads(call["body"])["messages"]
             for part in msg["content"] if part.get("type") == "text"]
    return next(t for t in texts if "confidence_text" in t)


def test_traps_only_when_their_target_is_visible(prompt):
    assert "Yellow sticky traps only when small flying insects" in prompt
    assert "Pheromone traps only when moths or bollworm larvae" in prompt
    assert "chewing damage with no insect visible" in prompt and "do not suggest traps" in prompt


def test_confidence_is_capped_when_the_cause_is_not_visible(prompt):
    assert "Confidence in the DIAGNOSIS" in prompt
    assert "the level is at most Medium" in prompt
