import io

import pytest


def _make_screenshot_like_bytes():
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont  # type: ignore

    img = Image.new("RGB", (900, 500), (250, 250, 250))
    draw = ImageDraw.Draw(img)

    # Simulate a UI header + blocks of black text on light background.
    draw.rectangle([0, 0, 900, 70], fill=(30, 30, 30))
    draw.rectangle([40, 110, 860, 440], fill=(255, 255, 255))

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    y = 130
    for _ in range(14):
        draw.text((60, y), "Welcome! Choose an alias. Country: Germany. Get started.", fill=(0, 0, 0), font=font)
        y += 20

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_processor_screenshot_heuristic_blocks_before_model(monkeypatch):
    from src.processor import analyzer as proc_analyzer

    called = {"bedrock": False}

    class _DummyBedrock:
        def invoke_model(self, *args, **kwargs):
            called["bedrock"] = True
            raise AssertionError("bedrock.invoke_model should not be called for screenshot-like inputs")

    monkeypatch.setattr(proc_analyzer, "bedrock", _DummyBedrock())

    image_bytes = _make_screenshot_like_bytes()

    result = proc_analyzer.analyze_crop_image(image_bytes=image_bytes, dialect="en", crop="wheat")
    assert result["diagnosis"] == "non_photo"
    assert called["bedrock"] is False

