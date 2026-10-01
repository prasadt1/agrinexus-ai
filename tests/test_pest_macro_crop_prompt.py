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

    assert isinstance(out, dict)
    assert "pending_crop_confirm" in out
    assert "buttons" in out and len(out["buttons"]) == 3
    text_l = out["text"].lower()
    assert "crop" in text_l or "पीक" in out["text"] or "फसल" in out["text"] or "పంట" in out["text"]
    assert out["buttons"][0] in ("Wheat", "गहू", "गेहूँ", "गेहूं", "గోధుమ")  # profile crop first


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
    assert "pending_crop_confirm" in out
    assert out["buttons"][0] == "Cotton"


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

