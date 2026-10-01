import os
import types


def test_pest_macro_low_confidence_prompts_for_crop(monkeypatch):
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "false")

    # Avoid real WhatsApp download and S3 writes
    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())

    # Force vision result: pest macro + can't infer crop confidently
    monkeypatch.setattr(
        a,
        "analyze_crop_image",
        lambda *_args, **_kwargs: {
            "recommendations": "WHEAT_BIASED_TEXT_SHOULD_NOT_BE_RETURNED",
            "diagnosis": "Unknown",
            "severity": "unknown",
            "confidence": "low",
            "photo_kind": "pest_macro",
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "is_real_crop_photo": True,
            "visible_problem": True,
            "needs_crop_confirm": False,
        },
    )

    msg = {"image": {"id": "mid-1"}, "from": "1555"}
    profile = {"dialect": "en", "crop": "Wheat", "district": "Latur", "phone_number": "1555"}

    out = a.process_image_message(msg, profile)

    # Image does not contradict the registered crop: answer now under a stated
    # assumption instead of spending a round trip on a question.
    assert isinstance(out, dict)
    assert "buttons" not in out
    assert out["pending_crop_confirm"]["assumed"] is True
    assert out["pending_crop_confirm"]["profile_crop"] == "Wheat"
    assert "Wheat" in out["text"]
    assert "profile" in out["text"].lower()


def test_visible_problem_low_confidence_prompts_even_when_inferred_crop_set(monkeypatch):
    """Widened trigger: visible problem + non-high confidence → confirm, even if inferred_crop is set."""
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "false")

    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())

    monkeypatch.setattr(
        a,
        "analyze_crop_image",
        lambda *_args, **_kwargs: {
            "recommendations": "SHOULD_NOT_LEAK",
            "diagnosis": "pest visible",
            "severity": "high",
            "is_real_crop_photo": True,
            "visible_problem": True,
            "photo_kind": "other_kind",
            "inferred_crop": "Cotton",
            "crop_confidence": "low",
        },
    )

    msg = {"image": {"id": "mid-wide"}, "from": "1555"}
    profile = {"dialect": "en", "crop": "Cotton", "district": "Latur", "phone_number": "1555"}

    out = a.process_image_message(msg, profile)
    # inferred_crop agrees with the profile, so there is nothing to ask about.
    assert "buttons" not in out
    assert out["pending_crop_confirm"]["assumed"] is True
    assert out["pending_crop_confirm"]["model_crop"] == "Cotton"


def test_crop_confirm_still_offered_when_relevance_unclear_low(monkeypatch):
    """Haiku relevance unclear/low must not suppress crop-confirm after Claude vision agrees."""
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "true")

    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")
    monkeypatch.setattr(
        a,
        "run_heuristics",
        lambda _b: {"decision": "pass", "reason": None, "metrics": {"green_frac": 0.2, "palette_size": 200}},
    )
    monkeypatch.setattr(
        a,
        "classify_image_relevance",
        lambda *_a, **_k: {"relevance": "unclear", "confidence": "low", "reason": "other"},
    )

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())
    monkeypatch.setattr(
        a,
        "analyze_crop_image",
        lambda *_args, **_kwargs: {
            "recommendations": "SHOULD_NOT_LEAK",
            "diagnosis": "pink bollworm",
            "severity": "high",
            "is_real_crop_photo": True,
            "visible_problem": True,
            "photo_kind": "pest_macro",
            "inferred_crop": "unknown",
            "crop_confidence": "low",
        },
    )

    msg = {"image": {"id": "mid-relev"}, "from": "1555"}
    profile = {"dialect": "mr", "crop": "Cotton", "district": "Latur", "phone_number": "1555"}

    out = a.process_image_message(msg, profile)
    assert "buttons" not in out
    assert out["pending_crop_confirm"]["assumed"] is True
    assert "कापूस" in out["text"]


def test_leaf_symptom_low_confidence_prompts_for_crop(monkeypatch):
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "false")

    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())

    monkeypatch.setattr(
        a,
        "analyze_crop_image",
        lambda *_args, **_kwargs: {
            "recommendations": "WHEAT_BIASED_TEXT_SHOULD_NOT_BE_RETURNED",
            "diagnosis": "Unknown",
            "severity": "unknown",
            "confidence": "low",
            "photo_kind": "leaf_symptom",
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "is_real_crop_photo": True,
            "visible_problem": True,
            "needs_crop_confirm": False,
        },
    )

    msg = {"image": {"id": "mid-2"}, "from": "1555"}
    profile = {"dialect": "en", "crop": "Wheat", "district": "Latur", "phone_number": "1555"}

    out = a.process_image_message(msg, profile)
    assert isinstance(out, dict)
    assert "pending_crop_confirm" in out


def test_unknown_kind_low_confidence_prompts_for_crop(monkeypatch):
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "false")

    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())

    monkeypatch.setattr(
        a,
        "analyze_crop_image",
        lambda *_args, **_kwargs: {
            "recommendations": "WHEAT_BIASED_TEXT_SHOULD_NOT_BE_RETURNED",
            "diagnosis": "Unknown",
            "severity": "unknown",
            "confidence": "low",
            "photo_kind": "unknown",
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "is_real_crop_photo": True,
            "visible_problem": True,
            "needs_crop_confirm": False,
        },
    )

    msg = {"image": {"id": "mid-3"}, "from": "1555"}
    profile = {"dialect": "en", "crop": "Wheat", "district": "Latur", "phone_number": "1555"}

    out = a.process_image_message(msg, profile)
    assert isinstance(out, dict)
    assert "pending_crop_confirm" in out

