import pytest
import sys
import os

# Single source of truth: the deployed crop-diagnosis code in src/processor/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/processor'))
from heuristics import run_heuristics, _calculate_image_metrics


def generate_dark_github_screenshot():
    """Generate synthetic dark mode UI image"""
    from PIL import Image, ImageDraw
    import io

    # Create 1920x1200 dark grey image with text-like edges
    img = Image.new('RGB', (1920, 1200), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    # Add white text-like boxes and lines (UI elements with strong edges)
    for y in range(100, 1100, 100):
        draw.rectangle([50, y, 1870, y+40], outline=(240, 240, 240), width=2)
        # Add some horizontal divider lines
        draw.line([50, y+50, 1870, y+50], fill=(80, 80, 80), width=1)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def test_dark_mode_screenshot_blocked():
    """Dark mode GitHub/IDE screenshot should be blocked"""
    image_bytes = generate_dark_github_screenshot()
    result = run_heuristics(image_bytes)

    assert result['decision'] == 'block'
    assert result['reason'] == 'screenshot_ui'
    assert result['metrics']['dark_frac'] > 0.30
    assert result['metrics']['edge_frac'] > 0.05


def generate_cotton_boll_photo():
    """Generate synthetic cotton boll (white fiber, organic edges)"""
    from PIL import Image, ImageDraw
    import io

    # Create 1024x1365 image with organic white cotton + dark stems
    img = Image.new('RGB', (1024, 1365), color=(60, 80, 50))  # Dark green background
    draw = ImageDraw.Draw(img)

    # Add white cotton boll (circular, organic)
    for i in range(20):
        x = 400 + i * 10
        y = 600 + (i % 5) * 15
        draw.ellipse([x, y, x+80, y+80], fill=(245, 245, 240))

    # Add some green leaves (mid-tone green)
    for i in range(10):
        draw.rectangle([200+i*30, 800, 220+i*30, 900], fill=(80, 140, 70))

    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return buf.getvalue()


def generate_leaf_logo():
    """Generate synthetic logo (limited palette, white background)"""
    from PIL import Image, ImageDraw
    import io

    # Create 400x400 white background with simple green leaf icon
    img = Image.new('RGB', (400, 400), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Simple green leaf shape (very limited colors)
    draw.ellipse([100, 100, 300, 300], fill=(60, 180, 80))
    draw.line([200, 100, 200, 300], fill=(40, 120, 50), width=10)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def test_cotton_boll_passes():
    """Real cotton boll (white fiber) should pass heuristics"""
    image_bytes = generate_cotton_boll_photo()
    result = run_heuristics(image_bytes)

    assert result['decision'] == 'pass'
    assert result['metrics']['white_frac'] < 0.5  # Below threshold
    assert result['metrics']['edge_frac'] < 0.18  # Organic edges


def test_logo_blocked():
    """Logo/icon on white background should be blocked"""
    image_bytes = generate_leaf_logo()
    result = run_heuristics(image_bytes)

    assert result['decision'] == 'block'
    assert result['reason'] == 'logo'
    assert result['metrics']['white_frac'] >= 0.70
    assert result['metrics']['palette_size'] <= 180


def test_tiny_image_blocked():
    """Images smaller than 64x64 should be blocked"""
    from PIL import Image
    import io

    img = Image.new('RGB', (50, 50), color=(100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format='PNG')

    result = run_heuristics(buf.getvalue())

    assert result['decision'] == 'block'
    assert result['reason'] == 'too_small'
