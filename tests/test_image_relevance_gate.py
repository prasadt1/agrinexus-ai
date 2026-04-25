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

