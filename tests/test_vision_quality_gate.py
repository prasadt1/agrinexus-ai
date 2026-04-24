import io
import os

import pytest


def _make_jpeg_bytes(w: int, h: int) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (w, h), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=25)
    return buf.getvalue()

def _make_white_dominant_ui_like_jpeg() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1280, 900), color=(250, 250, 250))
    d = ImageDraw.Draw(img)
    # Simulate a web page: a sidebar + header + text lines (edges), very little green.
    d.rectangle([0, 0, 260, 900], fill=(235, 235, 235))
    d.rectangle([260, 0, 1280, 120], fill=(245, 245, 245))
    for y in range(160, 820, 22):
        d.line([300, y, 1180, y], fill=(120, 120, 120), width=2)
    # A small photo placeholder
    d.rectangle([300, 140, 720, 420], outline=(80, 80, 80), width=3)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=35)
    return buf.getvalue()


def test_quality_gate_blocks_tiny_images_before_model(monkeypatch):
    os.environ["VISION_QUALITY_GATE_ENABLED"] = "true"

    from src.processor import analyzer
    # Analyzer reads TEMP_AUDIO_BUCKET at import time; force bucket for this test.
    monkeypatch.setattr(analyzer, "TEMP_BUCKET", "bucket", raising=False)

    # If we ever try to invoke analyze_crop_image, the gate failed.
    monkeypatch.setattr(analyzer, "analyze_crop_image", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("should_not_call_model")))

    # Avoid real S3 calls
    class _FakeS3:
        def put_object(self, **kwargs):
            return {"ETag": "x"}

    monkeypatch.setattr(analyzer, "s3", _FakeS3())

    message = {"image": {"id": "img1"}, "from": "123"}
    profile = {"dialect": "en", "crop": "Wheat", "phone_number": "123"}

    # Tiny thumbnail-like image
    monkeypatch.setattr(analyzer, "download_whatsapp_image", lambda _image_id: _make_jpeg_bytes(218, 153))

    out = analyzer.process_image_message(message, profile)
    assert isinstance(out, dict)
    assert out.get("quality_gate_failed") is True
    assert "too small" in (out.get("text") or "").lower() or "small/unclear" in (out.get("text") or "").lower()
    assert out.get("s3", {}).get("bucket") == "bucket"
    assert out.get("s3", {}).get("key", "").startswith("images/")


def test_ui_screenshot_is_rejected_before_model(monkeypatch):
    # This is a real WhatsApp UI screenshot from the repo assets.
    p = "/Users/prasadt1/.cursor/projects/Users-prasadt1-projects-AgriNexus-ai-push/assets/image-ec057046-890e-4dfd-a00b-3af1ebc7e182.png"
    img_bytes = open(p, "rb").read()

    from src.processor import analyzer

    monkeypatch.setattr(analyzer, "bedrock", object(), raising=False)
    # If bedrock invocation happens, something went wrong (it should reject earlier).
    def _boom(*args, **kwargs):
        raise RuntimeError("should_not_call_model")
    monkeypatch.setattr(analyzer, "_looks_like_logo_or_illustration", lambda b: False, raising=False)
    monkeypatch.setattr(analyzer, "bedrock", type("B", (), {"invoke_model": _boom})(), raising=False)

    out = analyzer.analyze_crop_image(img_bytes, "hi", "Wheat", district="Latur")
    assert isinstance(out, dict)
    assert out.get("diagnosis") == "non_photo"


def test_white_dominant_ui_like_image_is_rejected(monkeypatch):
    from src.processor import analyzer

    img_bytes = _make_white_dominant_ui_like_jpeg()
    out = analyzer.analyze_crop_image(img_bytes, "en", "Wheat", district="Latur")
    assert out.get("diagnosis") == "non_photo"

