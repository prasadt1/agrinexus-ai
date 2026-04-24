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

def _make_darkmode_chat_screenshot_like_bytes():
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont  # type: ignore

    img = Image.new("RGB", (900, 600), (18, 18, 18))
    draw = ImageDraw.Draw(img)

    # Dark header + lighter content blocks (mimics chat UI on dark mode).
    draw.rectangle([0, 0, 900, 90], fill=(10, 10, 10))
    draw.rectangle([40, 120, 860, 540], fill=(35, 35, 35))
    # Add multiple light "cards" with crisp borders to create edges.
    for i in range(5):
        top = 150 + i * 75
        draw.rectangle([70, top, 830, top + 55], fill=(235, 235, 235), outline=(255, 255, 255), width=2)

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    # Dense text lines (high-frequency edges) inside the dark area.
    y = 110
    for _ in range(18):
        draw.text((60, y), "UI SCREENSHOT TEXT 12345 | not a crop photo", fill=(230, 230, 230), font=font)
        y += 18

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()

def _make_small_blurry_ui_thumbnail_bytes():
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFilter  # type: ignore

    img = Image.new("RGB", (240, 240), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 20, 230, 70], fill=(235, 235, 235))
    draw.rectangle([10, 90, 230, 140], fill=(245, 245, 245))
    draw.rectangle([10, 160, 230, 210], fill=(240, 240, 240))
    # blur to simulate heavy compression where edges smear
    img = img.filter(ImageFilter.GaussianBlur(radius=1.6))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=35)
    return buf.getvalue()

def _make_github_dark_repo_tree_like_bytes():
    """Dark IDE / GitHub file tree: lots of dark grey (not pure black) + thin UI edges, little foliage green."""
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont  # type: ignore

    bg = (13, 17, 23)  # near GitHub dark canvas
    img = Image.new("RGB", (720, 900), bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    # Fake folder rows + file names (high edge density, low green).
    y = 40
    for i in range(28):
        indent = 24 + (i % 4) * 16
        draw.text((indent, y), f"src  scripts  README.md  allowlist-user.py  {i}", fill=(201, 209, 217), font=font)
        y += 28
    # Occasional accent (orange "folder" dot) — still low foliage green overall.
    for j in range(0, 720, 120):
        draw.ellipse([j + 8, 200, j + 18, 210], fill=(218, 138, 76))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


def _make_limited_palette_ui_bytes():
    PIL = pytest.importorskip("PIL")
    from PIL import Image, ImageDraw  # type: ignore

    # Flat fills + text-like bars (limited palette), not predominantly white/black.
    img = Image.new("RGB", (800, 500), (30, 35, 45))
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 60, 760, 430], fill=(210, 210, 215))
    for i in range(10):
        y = 90 + i * 28
        draw.rectangle([70, y, 720, y + 10], fill=(60, 60, 60))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
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


def test_processor_darkmode_screenshot_heuristic_blocks_before_model(monkeypatch):
    from src.processor import analyzer as proc_analyzer

    called = {"bedrock": False}

    class _DummyBedrock:
        def invoke_model(self, *args, **kwargs):
            called["bedrock"] = True
            raise AssertionError("bedrock.invoke_model should not be called for dark UI screenshot-like inputs")

    monkeypatch.setattr(proc_analyzer, "bedrock", _DummyBedrock())
    # Make this test independent of the screenshot-cropper.
    monkeypatch.setattr(proc_analyzer, "_extract_primary_frame", lambda b: b)

    image_bytes = _make_darkmode_chat_screenshot_like_bytes()
    assert proc_analyzer._looks_like_screenshot_or_ui(image_bytes) is True
    result = proc_analyzer.analyze_crop_image(image_bytes=image_bytes, dialect="en", crop="wheat")
    assert result["diagnosis"] == "non_photo"
    assert called["bedrock"] is False


def test_processor_small_blurry_ui_thumbnail_blocks(monkeypatch):
    from src.processor import analyzer as proc_analyzer

    called = {"bedrock": False}

    class _DummyBedrock:
        def invoke_model(self, *args, **kwargs):
            called["bedrock"] = True
            raise AssertionError("bedrock.invoke_model should not be called for small blurry UI thumbnails")

    monkeypatch.setattr(proc_analyzer, "bedrock", _DummyBedrock())
    monkeypatch.setattr(proc_analyzer, "_extract_primary_frame", lambda b: b)

    image_bytes = _make_small_blurry_ui_thumbnail_bytes()
    assert proc_analyzer._looks_like_screenshot_or_ui(image_bytes) is True
    result = proc_analyzer.analyze_crop_image(image_bytes=image_bytes, dialect="en", crop="wheat")
    assert result["diagnosis"] == "non_photo"
    assert called["bedrock"] is False


def test_processor_github_dark_repo_tree_blocks_before_model(monkeypatch):
    from src.processor import analyzer as proc_analyzer

    called = {"bedrock": False}

    class _DummyBedrock:
        def invoke_model(self, *args, **kwargs):
            called["bedrock"] = True
            raise AssertionError("bedrock.invoke_model should not run for GitHub/IDE-style repo screenshots")

    monkeypatch.setattr(proc_analyzer, "bedrock", _DummyBedrock())
    monkeypatch.setattr(proc_analyzer, "_extract_primary_frame", lambda b: b)

    image_bytes = _make_github_dark_repo_tree_like_bytes()
    assert proc_analyzer._looks_like_screenshot_or_ui(image_bytes) is True
    result = proc_analyzer.analyze_crop_image(image_bytes=image_bytes, dialect="hi", crop="wheat")
    assert result["diagnosis"] == "non_photo"
    assert called["bedrock"] is False


def test_processor_limited_palette_ui_blocks(monkeypatch):
    from src.processor import analyzer as proc_analyzer

    called = {"bedrock": False}

    class _DummyBedrock:
        def invoke_model(self, *args, **kwargs):
            called["bedrock"] = True
            raise AssertionError("bedrock.invoke_model should not be called for limited-palette UI inputs")

    monkeypatch.setattr(proc_analyzer, "bedrock", _DummyBedrock())
    monkeypatch.setattr(proc_analyzer, "_extract_primary_frame", lambda b: b)

    image_bytes = _make_limited_palette_ui_bytes()
    assert proc_analyzer._looks_like_screenshot_or_ui(image_bytes) is True
    result = proc_analyzer.analyze_crop_image(image_bytes=image_bytes, dialect="en", crop="wheat")
    assert result["diagnosis"] == "non_photo"
    assert called["bedrock"] is False
