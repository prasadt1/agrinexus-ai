"""The processor answers spray-timing questions from weather, and keeps the pesticide policy for product questions."""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from tests import test_crop_override_confirmation_flow as flow

REPO = Path(__file__).resolve().parents[1]
PHONE = "1555123000000"
KB_ANSWER = "Check the undersides of leaves twice a week and hang yellow sticky traps."
KB_REFUSAL = "I don't have information about this in my knowledge base. Please contact your local KVK."


@pytest.fixture(autouse=True)
def _restore_modules():
    """_install_common_stubs() replaces common.* in sys.modules; put the real ones back afterwards."""
    saved_modules, saved_path = dict(sys.modules), list(sys.path)
    yield
    for name in list(sys.modules):
        if name not in saved_modules:
            del sys.modules[name]
    sys.modules.update(saved_modules)
    sys.path[:] = saved_path


def _load(monkeypatch, profile):
    for k, v in {"TABLE_NAME": "tbl", "TEMP_AUDIO_BUCKET": "tmp-bucket", "KNOWLEDGE_BASE_ID": "kb",
                 "GUARDRAIL_ID": "", "GUARDRAIL_VERSION": "1"}.items():
        monkeypatch.setenv(k, v)
    sent = []
    flow._install_common_stubs(sent)
    analyzer = types.ModuleType("analyzer")
    analyzer.process_image_message = lambda *_a, **_k: "x"
    analyzer.analyze_crop_image = lambda *_a, **_k: {"recommendations": "x"}
    analyzer.diagnose_with_confirmed_crop = lambda *_a, **_k: "x"
    sys.modules["analyzer"] = analyzer
    spec = importlib.util.spec_from_file_location("processor_handler_spray_timing", REPO / "src" / "processor" / "handler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.table = flow._FakeDynamoTable(profile)
    mod.s3 = flow._FakeS3(b"img")
    mod._send_whatsapp_buttons = lambda *_a, **_k: True
    calls = []

    def rag(**kw):
        calls.append(kw)
        text = KB_REFUSAL if "pesticide" in kw["input"]["text"].lower() or "कौन" in kw["input"]["text"] else KB_ANSWER
        return {"output": {"text": text}, "citations": [], "sessionId": "s"}

    mod.bedrock_agent = types.SimpleNamespace(
        exceptions=types.SimpleNamespace(ValidationException=Exception), retrieve_and_generate=rag)
    mod._sent, mod._calls = sent, calls
    # weather is stubbed: calm and dry now, windy tomorrow
    mod.spray_timing.current_conditions = lambda district, **_k: {"wind_kmh": 4.0, "rain_mm": 0, "favorable": True}
    mod.spray_timing.tomorrow_conditions = lambda district, **_k: {"wind_kmh": 13.0, "rain_mm": 0, "rain_probability": 0.0, "favorable": False}
    return mod


@pytest.fixture
def farmer(monkeypatch):
    return _load(monkeypatch, {"onboarding_complete": True, "dialect": "hi", "district": "Latur",
                               "location": "Latur", "crop": "Cotton", "demo_tier": "full"})


@pytest.fixture
def english_farmer(monkeypatch):
    return _load(monkeypatch, {"onboarding_complete": True, "dialect": "en", "district": "Latur",
                               "location": "Latur", "crop": "Cotton", "demo_tier": "full"})


@pytest.fixture
def unknown_district(monkeypatch):
    return _load(monkeypatch, {"onboarding_complete": True, "dialect": "en", "district": "Pune",
                               "location": "Pune", "crop": "Cotton", "demo_tier": "full"})


def _ask(mod, text, source=None):
    body = {"wamid": "wamid.x", "from": PHONE, "type": "text", "message": {"text": {"body": text}}}
    if source:
        body["message"]["_source"] = source
    mod.lambda_handler({"Records": [{"body": json.dumps(body)}]}, None)
    return [m["text"] for m in mod._sent if m["text"]][-1]


def test_the_live_question_of_4_october_is_answered_from_weather(farmer):
    reply = _ask(farmer, "क्या कल लाटूर में स्प्रे करने का सही समय है?")
    assert reply.startswith("Latur: कल सुबह हवा तेज़ रहने की संभावना है (लगभग 13.0 km/h)")
    assert "कीटनाशक के नाम या मात्रा नहीं बता सकता" not in reply   # no pesticide-policy reply
    assert "KVK" in reply                                           # standard footer
    assert farmer._calls == []                                      # no Bedrock call


def test_today_question_uses_current_conditions(english_farmer):
    reply = _ask(english_farmer, "Can I spray today?")
    assert reply.startswith("Latur: the weather is favorable for spraying now. Wind 4.0 km/h")
    assert english_farmer._calls == []
    saved = [i for i in english_farmer.table.put_items if i.get("SK", "").startswith("MSG#")]
    assert saved and saved[-1]["source_citation"] == "spray_timing_weather"   # marked, not a KB citation


def test_product_question_still_gets_the_pesticide_policy_on_a_refusal(english_farmer):
    reply = _ask(english_farmer, "Which pesticide should I spray tomorrow for whitefly?")
    assert reply.startswith("I can't give pesticide names or quantities.")
    assert len(english_farmer._calls) == 1


def test_general_when_question_goes_to_the_knowledge_base(english_farmer):
    reply = _ask(english_farmer, "When is it safe to spray after rain?")
    assert reply.startswith(KB_ANSWER)
    assert len(english_farmer._calls) == 1


def test_unknown_district_falls_back_to_the_knowledge_base(unknown_district):
    reply = _ask(unknown_district, "Can I spray today?")
    assert reply.startswith(KB_ANSWER)
    assert len(unknown_district._calls) == 1


def test_weather_failure_says_so_and_states_the_rule(english_farmer):
    english_farmer.spray_timing.current_conditions = lambda district, **_k: None
    reply = _ask(english_farmer, "Can I spray today?")
    assert "not available right now" in reply and "under 10 km/h" in reply
    assert english_farmer._calls == []


def test_voice_question_gets_text_and_audio(english_farmer, monkeypatch):
    monkeypatch.setattr(english_farmer, "text_to_speech", lambda *_a, **_k: "https://audio.test/a.mp3")
    _ask(english_farmer, "Can I spray today?", source="voice")
    audio = [m for m in english_farmer._sent if m.get("audio_url")]
    assert audio and audio[-1]["audio_url"] == "https://audio.test/a.mp3"
