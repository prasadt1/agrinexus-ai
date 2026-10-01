"""
Crop identity is asked about only when it is genuinely in doubt.

Design under test:
- Problem visible, crop confidence not high, image agrees with the registered
  crop  -> answer now, state the assumption, allow a one-reply correction.
- Image suggests a different crop, or there is no registered crop
  -> show what was seen, then ask.
- A tapped crop that disagrees with the image is questioned once before any
  crop-specific chemical advice is given.
"""
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for _p in (_REPO / "src" / "processor", _REPO / "src" / "common-layer" / "python"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _vision(**over):
    base = {
        "recommendations": "Remove the larvae and spray as per label.",
        "diagnosis": "Two pink-striped caterpillars feeding inside a boll.",
        "severity": "high",
        "confidence_text": "medium - pest clear, crop organs partly hidden",
        "photo_kind": "pest_macro",
        "inferred_crop": "unknown",
        "crop_confidence": "low",
        "is_real_crop_photo": True,
        "visible_problem": True,
    }
    base.update(over)
    return base


def _analyzer(monkeypatch, vision):
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"
    from src.processor import analyzer as a

    a.TEMP_BUCKET = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "false")
    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())
    monkeypatch.setattr(a, "analyze_crop_image", lambda *_a, **_k: vision)
    return a


def test_assumed_crop_answers_without_asking(monkeypatch):
    a = _analyzer(monkeypatch, _vision())
    out = a.process_image_message(
        {"image": {"id": "m"}, "from": "1555"},
        {"dialect": "en", "crop": "Cotton", "district": "Latur", "phone_number": "1555"},
    )

    assert "buttons" not in out
    # The diagnosis the model produced survives instead of being replaced.
    assert "caterpillars" in out["text"]
    assert "High" in out["text"]
    assert "Taking your crop as Cotton" in out["text"]
    assert "Not Cotton?" in out["text"]
    pending = out["pending_crop_confirm"]
    assert pending["assumed"] is True
    assert pending["profile_crop"] == "Cotton"


def test_contradicting_image_asks_and_leads_with_the_observation(monkeypatch):
    a = _analyzer(monkeypatch, _vision(inferred_crop="Wheat", crop_confidence="medium"))
    out = a.process_image_message(
        {"image": {"id": "m"}, "from": "1555"},
        {"dialect": "en", "crop": "Cotton", "district": "Latur", "phone_number": "1555"},
    )

    assert out["text"].startswith("Two pink-striped caterpillars")
    assert "looks like Wheat" in out["text"]
    assert out["buttons"][0] == "Wheat"
    assert "Cotton" in out["buttons"]
    assert out["pending_crop_confirm"]["contradiction"] is True


def test_no_registered_crop_asks(monkeypatch):
    a = _analyzer(monkeypatch, _vision())
    out = a.process_image_message(
        {"image": {"id": "m"}, "from": "1555"},
        {"dialect": "en", "district": "Latur", "phone_number": "1555"},
    )

    assert len(out["buttons"]) == 3
    assert "Which crop is this?" in out["text"]
    assert out["pending_crop_confirm"].get("assumed") is not True


def test_high_confidence_is_unchanged(monkeypatch):
    a = _analyzer(monkeypatch, _vision(inferred_crop="Cotton", crop_confidence="high"))
    out = a.process_image_message(
        {"image": {"id": "m"}, "from": "1555"},
        {"dialect": "en", "crop": "Cotton", "district": "Latur", "phone_number": "1555"},
    )

    assert "buttons" not in out
    assert "pending_crop_confirm" not in out


def test_non_crop_photo_is_still_blocked(monkeypatch):
    a = _analyzer(
        monkeypatch,
        _vision(is_real_crop_photo=False, non_photo_reason="screenshot", visible_problem=False),
    )
    out = a.process_image_message(
        {"image": {"id": "m"}, "from": "1555"},
        {"dialect": "en", "crop": "Cotton", "district": "Latur", "phone_number": "1555"},
    )

    assert "buttons" not in out
    assert "pending_crop_confirm" not in out


def test_confirmed_crop_prompt_tells_the_model_not_to_ask(monkeypatch):
    from src.processor import analyzer as a

    seen = {}

    def _fake_invoke(**kwargs):
        import json as _json

        body = _json.loads(kwargs["body"])
        seen["prompt"] = body["messages"][0]["content"][1]["text"]
        raise RuntimeError("stop after prompt capture")

    monkeypatch.setattr(a, "_looks_like_screenshot_or_ui", lambda _b: False)
    monkeypatch.setattr(a, "_looks_like_logo_or_graphic", lambda _b: False, raising=False)
    monkeypatch.setattr(a.bedrock, "invoke_model", _fake_invoke)

    try:
        a.analyze_crop_image(b"\xff\xd8fake", "en", "Cotton", confirmed_crop=True)
    except Exception:
        pass

    prompt = seen.get("prompt", "")
    assert "CONFIRMED CROP OVERRIDE" in prompt
    assert "Do NOT ask for another photo to identify the crop" in prompt


def test_first_pass_prompt_keeps_crop_inference_but_drops_crop_photo_request(monkeypatch):
    """The first call must still let the model name a different crop (the contradiction
    question depends on it), but must not ask the farmer for a crop-identification photo."""
    from src.processor import analyzer as a

    seen = {}

    def _fake_invoke(**kwargs):
        import json as _json

        body = _json.loads(kwargs["body"])
        seen["prompt"] = body["messages"][0]["content"][1]["text"]
        raise RuntimeError("stop after prompt capture")

    monkeypatch.setattr(a, "_looks_like_screenshot_or_ui", lambda _b: False)
    monkeypatch.setattr(a, "_looks_like_logo_or_graphic", lambda _b: False, raising=False)
    monkeypatch.setattr(a.bedrock, "invoke_model", _fake_invoke)

    try:
        a.analyze_crop_image(b"\xff\xd8fake", "en", "Cotton")
    except Exception:
        pass

    prompt = seen.get("prompt", "")
    assert "CONFIRMED CROP OVERRIDE" not in prompt
    assert "Visual overrides profile" in prompt
    assert "Do NOT ask for another photo to identify the crop" in prompt
    assert "Never ask in \"recommendations\" for a photo of the whole plant" in prompt
    assert "Suggest clearer/closer photo" not in prompt
    assert "send better photo" not in prompt


def test_prompt_separates_whitefly_from_aphid(monkeypatch):
    """Whiteflies were being named aphids, and the pest name selects the pesticide."""
    from src.processor import analyzer as a

    seen = {}

    def _fake_invoke(**kwargs):
        import json as _json

        body = _json.loads(kwargs["body"])
        seen["prompt"] = body["messages"][0]["content"][1]["text"]
        raise RuntimeError("stop after prompt capture")

    monkeypatch.setattr(a, "_looks_like_screenshot_or_ui", lambda _b: False)
    monkeypatch.setattr(a, "_looks_like_logo_or_graphic", lambda _b: False, raising=False)
    monkeypatch.setattr(a.bedrock, "invoke_model", _fake_invoke)

    for confirmed in (False, True):
        seen.clear()
        try:
            a.analyze_crop_image(b"\xff\xd8fake", "en", "Cotton", confirmed_crop=confirmed)
        except Exception:
            pass
        prompt = seen.get("prompt", "")
        assert "Whiteflies:" in prompt
        assert "Aphids:" in prompt
        assert "tiny white/green bugs in clusters" not in prompt
        assert "advise confirming the pest" in prompt


def test_mismatched_tap_is_questioned_once(monkeypatch):
    from src.processor import analyzer as a

    text, buttons = a.crop_mismatch_prompt("en", "Cotton", "Wheat")
    assert "looks like Cotton, not Wheat" in text
    assert buttons == ["Cotton", "Wheat"]


def _load_handler(monkeypatch):
    """Load handler.py with the module-level clients stubbed out."""
    import importlib.util
    import types

    monkeypatch.setenv("TABLE_NAME", "tbl")
    monkeypatch.setenv("TEMP_AUDIO_BUCKET", "tmp-bucket")
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "kb")
    monkeypatch.setenv("GUARDRAIL_ID", "")
    monkeypatch.setenv("GUARDRAIL_VERSION", "1")

    output = types.ModuleType("output")
    output.text_to_speech = lambda *_a, **_k: None
    output.truncate_for_voice = lambda s, *_a, **_k: s
    output.voice_truncation_prefix = ""
    monkeypatch.setitem(sys.modules, "output", output)

    spec = importlib.util.spec_from_file_location(
        "processor_handler_crop_rules", _REPO / "src" / "processor" / "handler.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_short_crop_name_corrects_an_assumed_answer(monkeypatch):
    h = _load_handler(monkeypatch)
    pending = {"assumed": True, "profile_crop": "Cotton"}
    assert h._is_crop_correction("Wheat", "Wheat", pending) is True


def test_ordinary_question_does_not_rerun_the_image(monkeypatch):
    h = _load_handler(monkeypatch)
    pending = {"assumed": True, "profile_crop": "Cotton"}
    # Names a crop, but it is a question, not a correction.
    assert h._is_crop_correction("how much water for wheat in summer", "Wheat", pending) is False
    # Repeating the crop we already assumed is not a correction either.
    assert h._is_crop_correction("Cotton", "Cotton", pending) is False


def test_pending_from_an_explicit_question_is_unaffected(monkeypatch):
    h = _load_handler(monkeypatch)
    pending = {"profile_crop": "Cotton"}
    assert h._is_crop_correction("Wheat", "Wheat", pending) is True


def test_tap_against_the_image_is_questioned_once(monkeypatch):
    h = _load_handler(monkeypatch)
    pending = {"model_crop": "Cotton"}
    assert h._crop_tap_conflicts_with_image("Wheat", pending) is True
    # Already asked once: the farmer's second answer stands.
    assert h._crop_tap_conflicts_with_image("Wheat", {**pending, "rechecked": True}) is False
    # The contradiction was already shown in the first question.
    assert h._crop_tap_conflicts_with_image("Wheat", {**pending, "contradiction": True}) is False
    # Agreement, and the unknown case, pass straight through.
    assert h._crop_tap_conflicts_with_image("Cotton", pending) is False
    assert h._crop_tap_conflicts_with_image("Wheat", {"model_crop": "unknown"}) is False


def test_confident_wrong_crop_is_questioned_not_obeyed(monkeypatch):
    """
    Live case: a cotton boll macro came back as Sugarcane with crop_confidence
    high, and the farmer was given sugarcane borer advice. A confident crop the
    farmer did not register is the dangerous case, so it is asked about rather
    than acted on.
    """
    a = _analyzer(monkeypatch, _vision(inferred_crop="Sugarcane", crop_confidence="high"))
    out = a.process_image_message(
        {"image": {"id": "m"}, "from": "1555"},
        {"dialect": "en", "crop": "Cotton", "district": "Latur", "phone_number": "1555"},
    )

    assert out["text"].startswith("Two pink-striped caterpillars")
    assert "looks like Sugarcane" in out["text"]
    assert out["buttons"][0] == "Sugarcane"
    assert "Cotton" in out["buttons"]
    assert out["pending_crop_confirm"]["contradiction"] is True


def test_confident_agreeing_crop_is_still_answered_directly(monkeypatch):
    a = _analyzer(monkeypatch, _vision(inferred_crop="Cotton", crop_confidence="high"))
    out = a.process_image_message(
        {"image": {"id": "m"}, "from": "1555"},
        {"dialect": "en", "crop": "Cotton", "district": "Latur", "phone_number": "1555"},
    )

    assert "buttons" not in out
    assert "pending_crop_confirm" not in out


def test_marathi_labels_are_marathi_not_hindi(monkeypatch):
    from src.processor import enforcement as e

    out = e.format_crop_message(_vision(crop_confidence="high"), "Cotton", "mr", assumed=False)
    assert "शिफारशी" in out  # Marathi
    assert "सिफ़ारिशें" not in out  # Hindi
    assert "तीव्रता" in out
    assert "गंभीरता" not in out


def test_assumed_answer_does_not_claim_confidence_in_the_crop(monkeypatch):
    from src.processor import enforcement as e

    vision = _vision(confidence_text="high - pest clearly visible")
    out = e.format_crop_message(vision, "Cotton", "mr", assumed=True)
    # The crop half is named as an assumption inside the confidence section itself.
    assert "गृहीत धरले आहे" in out.split("विश्वास")[1]
    # The model's own wording is kept rather than discarded.
    assert "high - pest clearly visible" in out


def test_confirmed_answer_keeps_the_model_confidence_wording(monkeypatch):
    from src.processor import enforcement as e

    vision = _vision(confidence_text="high - boll and fibre visible", crop_confidence="high")
    out = e.format_crop_message(vision, "Cotton", "en", assumed=False)
    assert "high - boll and fibre visible" in out
    assert "taken from your profile" not in out
