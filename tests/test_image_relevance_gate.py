import os


def test_relevance_gate_blocks_non_agri_before_vision(monkeypatch):
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "true")

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"

    # Avoid real WhatsApp download and S3 writes
    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())

    # If we ever try to invoke full analysis, the gate failed.
    monkeypatch.setattr(a, "analyze_crop_image", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("should_not_call_vision")))

    monkeypatch.setattr(
        a,
        "classify_image_relevance",
        lambda *_args, **_kwargs: {"relevance": "not_agri", "reason": "screenshot", "confidence": "high"},
    )

    out = a.process_image_message({"image": {"id": "mid-1"}, "from": "1555"}, {"dialect": "en", "crop": "Wheat", "phone_number": "1555"})
    assert isinstance(out, dict)
    assert out.get("non_photo") is True
    assert "crop/leaf" in (out.get("text") or "")


def test_relevance_gate_blocks_unclear_with_medium_confidence(monkeypatch):
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "true")

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"

    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())
    monkeypatch.setattr(a, "analyze_crop_image", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("should_not_call_vision")))
    monkeypatch.setattr(
        a,
        "classify_image_relevance",
        lambda *_args, **_kwargs: {"relevance": "unclear", "reason": "other", "confidence": "medium"},
    )

    out = a.process_image_message({"image": {"id": "mid-2"}, "from": "1555"}, {"dialect": "en", "crop": "Wheat", "phone_number": "1555"})
    assert isinstance(out, dict)
    assert out.get("non_photo") is True
    assert "closer, clearer" in (out.get("text") or "").lower()


def test_relevance_gate_only_allows_agri_photo_medium_or_high(monkeypatch):
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "true")

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"

    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())

    called = {"vision": False}

    def _fake_vision(*_args, **_kwargs):
        called["vision"] = True
        return {
            "is_real_crop_photo": True,
            "non_photo_reason": None,
            "insects_visible": [],
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "diagnosis": "ok",
            "visible_problem": False,
            "severity": "none",
            "recommendations": "ok",
            "confidence_text": "ok",
        }

    monkeypatch.setattr(a, "analyze_crop_image", _fake_vision)
    monkeypatch.setattr(
        a,
        "classify_image_relevance",
        lambda *_args, **_kwargs: {"relevance": "agri_photo", "reason": "other", "confidence": "medium"},
    )

    out = a.process_image_message({"image": {"id": "mid-3"}, "from": "1555"}, {"dialect": "en", "crop": "Wheat", "phone_number": "1555"})
    assert isinstance(out, dict)
    assert called["vision"] is True


def test_relevance_unclear_medium_but_photo_likely_proceeds(monkeypatch):
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"
    monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "true")

    from src.processor import analyzer as a
    a.TEMP_BUCKET = "tmp-bucket"

    # Make heuristics return "pass" with photo-likely metrics.
    monkeypatch.setattr(
        a,
        "run_heuristics",
        lambda _b: {"decision": "pass", "reason": None, "metrics": {"green_frac": 0.10, "palette_size": 200}},
    )
    monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")

    class _FakeS3:
        def put_object(self, **_kwargs):
            return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    monkeypatch.setattr(a, "s3", _FakeS3())
    monkeypatch.setattr(
        a,
        "classify_image_relevance",
        lambda *_args, **_kwargs: {"relevance": "unclear", "reason": "other", "confidence": "medium"},
    )

    called = {"vision": False}

    def _fake_vision(*_args, **_kwargs):
        called["vision"] = True
        return {
            "is_real_crop_photo": True,
            "non_photo_reason": None,
            "insects_visible": [],
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "diagnosis": "ok",
            "visible_problem": False,
            "severity": "none",
            "recommendations": "ok",
            "confidence_text": "ok",
        }

    monkeypatch.setattr(a, "analyze_crop_image", _fake_vision)

    out = a.process_image_message({"image": {"id": "mid-4"}, "from": "1555"}, {"dialect": "en", "crop": "Wheat", "phone_number": "1555"})
    assert isinstance(out, dict)
    assert called["vision"] is True

