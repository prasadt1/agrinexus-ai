"""
Image heuristics for screenshot/logo detection.
Pillow-only implementation (no OpenCV/NumPy).
"""
from PIL import Image, ImageFilter
import io
from typing import Dict, Any


def run_heuristics(image_bytes: bytes) -> Dict[str, Any]:
    """
    Detect screenshots/logos using deterministic heuristics.
    Matches existing _looks_like_screenshot_or_ui() implementation.
    """
    try:
        metrics = _calculate_image_metrics(image_bytes)
        m = metrics  # shorthand

        # Check unusable first
        if m['width'] < 64 or m['height'] < 64:
            return {'decision': 'block', 'reason': 'too_small', 'metrics': metrics}

        # Screenshot/UI detection (9 rules - OR logic)

        # Rule 1: Light mode UI/docs
        if m['edge_frac'] > 0.16 and m['white_frac'] > 0.18 and m['black_frac'] > 0.008:
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Rule 2: Very white screenshots
        if m['edge_frac'] > 0.22 and m['white_frac'] > 0.28:
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Rule 3: White-dominant articles (low green)
        if m['edge_frac'] > 0.14 and m['white_frac'] > 0.55 and m['green_frac'] < 0.03:
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Rule 4: Dark-mode chat/app
        if m['black_frac'] > 0.22 and m['edge_frac'] > 0.085:
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Rule 5: Dark-mode IDE (GitHub, VS Code compressed)
        if m['dark_frac'] > 0.30 and m['edge_frac'] > 0.052 and m['green_frac'] < 0.12:
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Rule 6: GitHub dark repo tree
        if (m['dark_frac'] > 0.24 and m['edge_frac'] > 0.068 and
            m['green_frac'] < 0.085 and m['palette_size'] <= 140):
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Rule 7: Heavily compressed dark UI
        if (m['dark_frac'] > 0.72 and m['edge_frac'] > 0.034 and
            m['green_frac'] < 0.05 and m['palette_size'] <= 110):
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Rule 8: Small UI thumbnails
        if (min(m['width'], m['height']) <= 320 and m['green_frac'] < 0.12 and
            (m['white_frac'] > 0.60 or m['black_frac'] > 0.18)):
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Rule 9: Flat UI (limited palette, low green)
        if m['green_frac'] < 0.06 and m['edge_frac'] > 0.09 and m['palette_size'] <= 90:
            return {'decision': 'block', 'reason': 'screenshot_ui', 'metrics': metrics}

        # Logo/illustration detection
        if m['white_frac'] >= 0.70 and m['palette_size'] <= 180:
            return {'decision': 'block', 'reason': 'logo', 'metrics': metrics}

        # Default: pass to vision model
        return {'decision': 'pass', 'reason': None, 'metrics': metrics}

    except Exception as e:
        # Fail-open: if heuristics error, pass to vision model
        return {'decision': 'pass', 'reason': None, 'metrics': {'error': str(e)}}


def _calculate_image_metrics(image_bytes: bytes) -> Dict[str, Any]:
    """
    Pillow-only metrics matching existing _looks_like_screenshot_or_ui().
    No OpenCV/NumPy to keep Lambda cold starts fast.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size
    file_size_kb = len(image_bytes) / 1024.0
    aspect_ratio = width / height if height > 0 else 1.0

    # Normalize size for stable thresholds
    target_w = 256
    target_h = max(128, int(height * (target_w / float(width))))
    small = img.resize((target_w, target_h))
    gray = small.convert("L")

    # Histogram-based metrics
    hist = gray.histogram()  # 256 bins
    total = float(sum(hist) or 1.0)

    black_frac = sum(hist[0:20]) / total
    dark_frac = sum(hist[0:56]) / total  # Dark grey UI (GitHub/VS Code dark)
    white_frac = sum(hist[235:256]) / total

    # Edge detection using Pillow's FIND_EDGES filter
    edges = gray.filter(ImageFilter.FIND_EDGES)
    ehist = edges.histogram()
    edge_total = float(sum(ehist) or 1.0)
    edge_frac = sum(ehist[40:256]) / edge_total  # Pixels with noticeable edge strength

    # Green dominance: real crop photos have significant green pixels
    s2 = img.resize((128, 128))
    gp = list(s2.getdata())
    green = 0
    qcolors16 = set()

    for r, g, b in gp:
        if g > r + 18 and g > b + 18 and g > 60:
            green += 1
        qcolors16.add((r // 16, g // 16, b // 16))

    green_frac = green / float(len(gp) or 1.0)
    palette_size = len(qcolors16)

    return {
        'black_frac': black_frac,
        'dark_frac': dark_frac,
        'white_frac': white_frac,
        'edge_frac': edge_frac,
        'green_frac': green_frac,
        'palette_size': palette_size,
        'aspect_ratio': aspect_ratio,
        'width': width,
        'height': height,
        'file_size_kb': file_size_kb
    }
