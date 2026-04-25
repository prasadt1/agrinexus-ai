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
            "needs_crop_confirm": False,
        },
    )

    msg = {"image": {"id": "mid-1"}, "from": "1555"}
    profile = {"dialect": "en", "crop": "Wheat", "district": "Latur", "phone_number": "1555"}

    out = a.process_image_message(msg, profile)

    assert isinstance(out, dict)
    assert "pending_crop_confirm" in out
    assert "which crop" in out["text"].lower() or "profile crop" in out["text"].lower()


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
            "needs_crop_confirm": False,
        },
    )

    msg = {"image": {"id": "mid-3"}, "from": "1555"}
    profile = {"dialect": "en", "crop": "Wheat", "district": "Latur", "phone_number": "1555"}

    out = a.process_image_message(msg, profile)
    assert isinstance(out, dict)
    assert "pending_crop_confirm" in out

