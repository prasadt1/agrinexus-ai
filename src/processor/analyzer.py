"""
Vision Analyzer
Uses Claude 3 Sonnet Vision for pest/disease identification from images
"""
import boto3
import json
import base64
import os
import io
import struct
import zlib
import urllib.error
from typing import Any, Dict, Optional

from heuristics import run_heuristics
from messages import get_block_message, get_not_agri_message, get_safe_retake_message, localize_crop_name
from enforcement import enforce_message_safety

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
secrets = boto3.client('secretsmanager', region_name='us-east-1')

TEMP_BUCKET = os.environ.get('TEMP_AUDIO_BUCKET')

RELEVANCE_MODEL_ID = os.environ.get("VISION_RELEVANCE_MODEL_ID") or "anthropic.claude-3-haiku-20240307-v1:0"


def _relevance_gate_enabled() -> bool:
    # Default ON; disable explicitly for debugging.
    v = (os.environ.get("VISION_RELEVANCE_GATE_ENABLED") or "true").strip().lower()
    return v in ("1", "true", "yes", "on")


def classify_image_relevance(image_bytes: bytes, dialect: str) -> Dict[str, Any]:
    """
    Cheap relevance check to avoid running full diagnosis on non-agri images.
    Returns strict JSON:
      {"relevance":"agri_photo"|"not_agri"|"unclear","reason":str,"confidence":"high"|"medium"|"low"}
    Fail-open on any error (treat as unclear).
    """
    try:
        # Detect image format from magic bytes
        media_type = "image/jpeg"
        if image_bytes[:2] == b'\xff\xd8':
            media_type = "image/jpeg"
        elif image_bytes[:4] == b'\x89PNG':
            media_type = "image/png"
        elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
            media_type = "image/webp"

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "Return ONLY valid JSON (no markdown). Task: classify whether this image is a real agriculture-related "
            "photo suitable for crop/leaf diagnosis.\n\n"
            "JSON schema:\n"
            "{\n"
            '  "relevance": "agri_photo" | "not_agri" | "unclear",\n'
            '  "reason": "screenshot" | "document" | "logo" | "person" | "animal" | "food" | "landscape" | "underwater" | "other",\n'
            '  "confidence": "high" | "medium" | "low"\n'
            "}\n\n"
            "Guidelines:\n"
            "- agri_photo: real photo of plant/leaf/crop/field/plant damage/pest on plant.\n"
            "- not_agri: UI/screenshot, logo/graphic, document, selfie/person, animals, food, underwater, random objects.\n"
            "- unclear: too blurry/dark/cropped to be sure.\n"
        )

        resp = bedrock.invoke_model(
            modelId=RELEVANCE_MODEL_ID,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 200,
                    "temperature": 0,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                }
            ),
        )

        response_body = json.loads(resp["body"].read())
        raw_text = response_body["content"][0]["text"].strip()
        if raw_text.startswith("```"):
            raw_text = "\n".join(raw_text.split("\n")[1:-1])
        out = json.loads(raw_text)

        relevance = (out.get("relevance") or "unclear").strip().lower()
        confidence = (out.get("confidence") or "low").strip().lower()
        reason = (out.get("reason") or "other").strip().lower()
        if relevance not in ("agri_photo", "not_agri", "unclear"):
            relevance = "unclear"
        if confidence not in ("high", "medium", "low"):
            confidence = "low"
        if reason not in ("screenshot", "document", "logo", "person", "animal", "food", "landscape", "underwater", "other"):
            reason = "other"
        return {"relevance": relevance, "confidence": confidence, "reason": reason}
    except Exception:
        _ = dialect
        return {"relevance": "unclear", "confidence": "low", "reason": "other"}


def validate_vision_schema(vision: Dict[str, Any]) -> None:
    """
    Validate required fields in vision model response.
    Raises ValueError if invalid.
    """
    required_fields = [
        'is_real_crop_photo',
        'inferred_crop',
        'crop_confidence',
        'insects_visible',
        'visible_problem',
        'severity',
        'recommendations'
    ]

    missing = [f for f in required_fields if f not in vision or vision[f] is None]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    # Validate insects_visible is a list
    if not isinstance(vision['insects_visible'], list):
        raise ValueError(f"insects_visible must be a list, got: {type(vision['insects_visible'])}")

    # Validate enums
    if vision['crop_confidence'] not in ['high', 'medium', 'low']:
        raise ValueError(f"Invalid crop_confidence: {vision['crop_confidence']}")

    if vision['severity'] not in ['high', 'medium', 'low', 'none', 'unknown']:
        raise ValueError(f"Invalid severity: {vision['severity']}")

    # Validate non_photo_reason enum (if present)
    if vision.get('non_photo_reason') and vision['non_photo_reason'] not in ['screenshot', 'logo', 'document', 'too_blurry']:
        raise ValueError(f"Invalid non_photo_reason: {vision['non_photo_reason']}")

    # Validate inferred_crop enum
    if vision['inferred_crop'] not in ['Cotton', 'Wheat', 'Soybean', 'Rice', 'Sugarcane', 'Maize', 'unknown']:
        raise ValueError(f"Invalid inferred_crop: {vision['inferred_crop']}")


def _normalize_vision_metadata(photo_kind: str, inferred_crop: str, crop_confidence: str) -> Dict[str, str]:
    pk = (photo_kind or "unknown").strip() or "unknown"
    ic = (inferred_crop or "unknown").strip() or "unknown"
    cc = (crop_confidence or "low").strip() or "low"
    if pk == "pest_macro":
        return {"photo_kind": pk, "inferred_crop": "unknown", "crop_confidence": "low"}

    # Be conservative: only keep a specific crop label when confidence is truly high.
    if cc != "high":
        return {"photo_kind": pk, "inferred_crop": "unknown", "crop_confidence": cc}

    return {"photo_kind": pk, "inferred_crop": ic, "crop_confidence": cc}

def _quality_gate_enabled() -> bool:
    return (os.environ.get("VISION_QUALITY_GATE_ENABLED") or "").strip().lower() in ("1", "true", "yes", "on")


def _check_image_quality(image_bytes: bytes) -> Dict[str, Any]:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return {"is_acceptable": True, "reason": None, "metrics": {}}
    try:
        import io as _io
        img = Image.open(_io.BytesIO(image_bytes))
        w, h = img.size
        file_size = len(image_bytes)
        min_dim = min(w, h)
        if min_dim < int(os.environ.get("VISION_MIN_DIMENSION", "320")):
            return {"is_acceptable": False, "reason": "too_small", "metrics": {"width": w, "height": h, "file_size": file_size, "min_dimension": min_dim}}
        if file_size < int(os.environ.get("VISION_MIN_FILE_BYTES", "3000")):
            return {"is_acceptable": False, "reason": "file_too_small", "metrics": {"width": w, "height": h, "file_size": file_size, "min_dimension": min_dim}}
        return {"is_acceptable": True, "reason": None, "metrics": {"width": w, "height": h, "file_size": file_size, "min_dimension": min_dim}}
    except Exception as e:
        return {"is_acceptable": False, "reason": f"error:{type(e).__name__}", "metrics": {}}


def _insufficient_quality_message(dialect: str, reason: str) -> str:
    msgs = {
        "hi": "फोटो बहुत छोटा/धुंधला लग रहा है, इसलिए पक्का निदान करना सुरक्षित नहीं है।\n\nकृपया:\n- पत्ते/कीट के पास जाकर फोटो लें (लगभग 30cm)\n- फोकस के लिए स्क्रीन पर टैप करें\n- अच्छी रोशनी में फोटो लें\n\nफिर दोबारा फोटो भेजें।",
        "mr": "फोटो खूप छोटा/अस्पष्ट दिसतो, त्यामुळे खात्रीशीर निदान सुरक्षित नाही.\n\nकृपया:\n- पान/किडीजवळ जाऊन फोटो घ्या (सुमारे 30cm)\n- फोकससाठी टॅप करा\n- चांगल्या प्रकाशात फोटो घ्या\n\nमग फोटो पुन्हा पाठवा.",
        "te": "ఫోటో చాలా చిన్నగా/అస్పష్టంగా ఉంది, కాబట్టి ఖచ్చితమైన నిర్ధారణ చేయడం సురక్షితం కాదు.\n\nదయచేసి:\n- ఆకుకు/పురుగుకు దగ్గరగా (సుమారు 30cm) ఫోటో తీసండి\n- ఫోకస్ కోసం ట్యాప్ చేయండి\n- మంచి వెలుతురులో ఫోటో తీసండి\n\nతర్వాత మళ్లీ ఫోటో పంపండి.",
        "en": "The photo is too small/unclear to diagnose reliably.\n\nPlease:\n- Move closer (~30cm)\n- Tap to focus\n- Take in good light\n\nThen resend the photo.",
    }
    _ = reason
    return msgs.get(dialect, msgs["en"])

def _looks_like_screenshot_or_ui(image_bytes: bytes) -> bool:
    try:
        from PIL import Image, ImageFilter  # type: ignore
    except Exception:
        return False
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if w < 96 or h < 96:
            return False
        target_w = 256
        target_h = max(128, int(h * (target_w / float(w))))
        small = img.resize((target_w, target_h))
        gray = small.convert("L")
        hist = gray.histogram()
        total = float(sum(hist) or 1.0)
        black_frac = sum(hist[0:20]) / total
        dark_frac = sum(hist[0:56]) / total
        white_frac = sum(hist[235:256]) / total
        edges = gray.filter(ImageFilter.FIND_EDGES)
        ehist = edges.histogram()
        edge_total = float(sum(ehist) or 1.0)
        edge_frac = sum(ehist[40:256]) / edge_total
        s2 = img.resize((128, 128))
        gp = list(s2.getdata())
        green = 0
        qcolors16 = set()
        for r, g, b in gp:
            if g > r + 18 and g > b + 18 and g > 60:
                green += 1
            qcolors16.add((r // 16, g // 16, b // 16))
        green_frac = green / float(len(gp) or 1.0)
        approx_unique_colors16 = len(qcolors16)
        if edge_frac > 0.16 and white_frac > 0.18 and black_frac > 0.008:
            return True
        if edge_frac > 0.22 and white_frac > 0.28:
            return True
        # White-dominant web/article screenshots (WhatsApp compression can reduce near-black pixels).
        if edge_frac > 0.14 and white_frac > 0.55 and green_frac < 0.03:
            return True
        if black_frac > 0.22 and edge_frac > 0.085:
            return True
        if dark_frac > 0.30 and edge_frac > 0.052 and green_frac < 0.12:
            return True
        if dark_frac > 0.24 and edge_frac > 0.068 and green_frac < 0.085 and approx_unique_colors16 <= 140:
            return True
        if dark_frac > 0.72 and edge_frac > 0.034 and green_frac < 0.05 and approx_unique_colors16 <= 110:
            return True
        if (min(w, h) <= 320) and (green_frac < 0.12) and (white_frac > 0.60 or black_frac > 0.18):
            return True
        if (green_frac < 0.06) and (edge_frac > 0.09) and (approx_unique_colors16 <= 90):
            return True
        return False
    except Exception:
        return False

def _looks_like_logo_or_illustration(image_bytes: bytes) -> bool:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        try:
            if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
                return _png_looks_like_logo(image_bytes)
        except Exception:
            return False
        return False
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if w < 64 or h < 64:
            return True
        small = img.resize((96, 96))
        pixels = list(small.getdata())
        total = len(pixels)
        if total == 0:
            return True
        whiteish = 0
        colors = set()
        step = 2
        for i, (r, g, b) in enumerate(pixels):
            if r > 245 and g > 245 and b > 245:
                whiteish += 1
            if i % step == 0:
                colors.add((r // 8, g // 8, b // 8))
        if (whiteish / total) >= 0.70 and len(colors) <= 180:
            return True
        return False
    except Exception:
        return False


def _png_looks_like_logo(png_bytes: bytes) -> bool:
    # PNG signature already checked by caller.
    pos = 8
    width = height = None
    bit_depth = color_type = None
    idat = bytearray()
    while pos + 8 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        ctype = png_bytes[pos + 4 : pos + 8]
        pos += 8
        if pos + length + 4 > len(png_bytes):
            break
        data = png_bytes[pos : pos + length]
        pos += length + 4
        if ctype == b"IHDR":
            if length < 13:
                return False
            width = struct.unpack(">I", data[0:4])[0]
            height = struct.unpack(">I", data[4:8])[0]
            bit_depth = data[8]
            color_type = data[9]
        elif ctype == b"IDAT":
            idat.extend(data)
        elif ctype == b"IEND":
            break

    if not width or not height or bit_depth != 8 or color_type not in (2, 6):
        return False
    raw = zlib.decompress(bytes(idat))
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp
    expected = height * (1 + stride)
    if len(raw) < expected:
        return False

    def paeth(a: int, b: int, c: int) -> int:
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

    pixels_sampled = 0
    whiteish = 0
    colors = set()
    step = max(1, (width * height) // 5000)

    prev = bytearray(stride)
    idx = 0
    px_index = 0
    for _y in range(height):
        f = raw[idx]
        idx += 1
        line = bytearray(raw[idx : idx + stride])
        idx += stride

        if f == 1:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + left) & 0xFF
        elif f == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif f == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up = prev[i]
                line[i] = (line[i] + ((left + up) // 2)) & 0xFF
        elif f == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up = prev[i]
                up_left = prev[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + paeth(left, up, up_left)) & 0xFF

        for x in range(0, stride, bpp):
            if (px_index % step) == 0:
                r = line[x]
                g = line[x + 1]
                b = line[x + 2]
                pixels_sampled += 1
                if r > 245 and g > 245 and b > 245:
                    whiteish += 1
                colors.add((r // 8, g // 8, b // 8))
            px_index += 1

        prev = line

    if pixels_sampled <= 0:
        return True
    white_ratio = whiteish / pixels_sampled
    approx_unique_colors = len(colors)
    return white_ratio >= 0.70 and approx_unique_colors <= 180


def _non_photo_message(dialect: str) -> str:
    msgs = {
        "hi": "यह तस्वीर फसल/पत्ते की वास्तविक फोटो नहीं लग रही (logo/illustration). कृपया प्रभावित पत्ता/फसल की साफ़, पास से ली हुई फोटो भेजें।",
        "mr": "ही प्रतिमा फसल/पानाची वास्तविक फोटो वाटत नाही (logo/illustration). कृपया प्रभावित पान/पीक याचा स्पष्ट जवळून घेतलेला फोटो पाठवा.",
        "te": "ఇది పంట/ఆకు యొక్క నిజమైన ఫోటోలా లేదు (logo/illustration). దయచేసి ప్రభావిత ఆకు/పంట యొక్క స్పష్టమైన దగ్గరి ఫోటో పంపండి.",
        "en": "This doesn’t look like a real crop/leaf photo (logo/illustration). Please send a clear close-up photo of the affected leaf/plant.",
    }
    return msgs.get(dialect, msgs["en"])

def _extract_primary_frame(image_bytes: bytes) -> bytes:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return image_bytes
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if w < 200 or h < 200:
            return image_bytes

        small_w = 220
        small_h = max(220, int(h * (small_w / w)))
        small = img.resize((small_w, small_h))
        px = small.load()

        min_x, min_y = small_w, small_h
        max_x, max_y = -1, -1
        for y in range(small_h):
            for x in range(small_w):
                r, g, b = px[x, y]
                if r > 220 and g > 220 and b > 220:
                    if x < min_x: min_x = x
                    if y < min_y: min_y = y
                    if x > max_x: max_x = x
                    if y > max_y: max_y = y

        if max_x < 0:
            return image_bytes

        bbox_w = (max_x - min_x + 1)
        bbox_h = (max_y - min_y + 1)
        area_ratio = (bbox_w * bbox_h) / float(small_w * small_h)
        if area_ratio < 0.18:
            return image_bytes

        scale_x = w / float(small_w)
        scale_y = h / float(small_h)
        pad = 12
        left = max(0, int(min_x * scale_x) - pad)
        upper = max(0, int(min_y * scale_y) - pad)
        right = min(w, int((max_x + 1) * scale_x) + pad)
        lower = min(h, int((max_y + 1) * scale_y) + pad)
        crop = img.crop((left, upper, right, lower))
        cw, ch = crop.size
        if (cw * ch) / float(w * h) > 0.92:
            return image_bytes

        out = io.BytesIO()
        crop.save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue()
    except Exception:
        return image_bytes

def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                snippet = text[start : i + 1]
                try:
                    obj = json.loads(snippet)
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    return None
    return None


def download_whatsapp_image(media_id: str) -> bytes:
    """Download image from WhatsApp"""
    import urllib.request
    
    # Get WhatsApp credentials
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    response = secrets.get_secret_value(SecretId=access_token_secret)
    access_token = response['SecretString']
    
    # Get media URL
    url = f"https://graph.facebook.com/v22.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        media_url = data['url']
    
    # Download image
    req = urllib.request.Request(media_url, headers=headers)
    with urllib.request.urlopen(req) as response:
        return response.read()


def analyze_crop_image(
    image_bytes: bytes,
    dialect: str,
    crop: str = "cotton",
    district: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze crop image for pests, diseases, or nutrient deficiencies

    Args:
        image_bytes: Image data
        dialect: User's dialect (hi, mr, te, en)
        crop: Crop type from PROFILE (default: cotton)
        district: District / location from PROFILE (optional)

    Returns:
        {
            'is_real_crop_photo': bool,
            'non_photo_reason': str | None,
            'inferred_crop': str,  # Cotton, Wheat, Soybean, Rice, Sugarcane, Maize, unknown
            'crop_confidence': str,  # high, medium, low
            'visible_problem': bool,
            'severity': str,  # high, medium, low, none, unknown
            'recommendations': str  # Advice in user's language
        }
    """
    # If this looks like a UI/screenshot, reject (cropping embedded content creates false positives).
    if _looks_like_screenshot_or_ui(image_bytes):
        msg = _non_photo_message(dialect)
        return {
            "is_real_crop_photo": False,
            "non_photo_reason": "screenshot",
            "insects_visible": [],
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "diagnosis": "non_photo",
            "visible_problem": False,
            "severity": "none",
            "recommendations": msg,
            "confidence_text": msg
        }

    image_bytes = _extract_primary_frame(image_bytes)
    if _looks_like_screenshot_or_ui(image_bytes):
        msg = _non_photo_message(dialect)
        return {
            "is_real_crop_photo": False,
            "non_photo_reason": "screenshot",
            "insects_visible": [],
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "diagnosis": "non_photo",
            "visible_problem": False,
            "severity": "none",
            "recommendations": msg,
            "confidence_text": msg
        }

    # Detect image format from magic bytes
    media_type = "image/jpeg"  # default
    if image_bytes[:2] == b'\xff\xd8':
        media_type = "image/jpeg"
    elif image_bytes[:4] == b'\x89PNG':
        media_type = "image/png"
    elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        media_type = "image/webp"
    
    # Encode image to base64
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    # Map dialect to language
    language_map = {
        'hi': 'Hindi (Devanagari script)',
        'mr': 'Marathi (Devanagari script)',
        'te': 'Telugu script',
        'en': 'English'
    }
    language = language_map.get(dialect, "English")
    area = (district or "").strip() or "not specified"

    if _looks_like_logo_or_illustration(image_bytes):
        msg = _non_photo_message(dialect)
        return {
            "is_real_crop_photo": False,
            "non_photo_reason": "logo",
            "insects_visible": [],
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "diagnosis": "non_photo",
            "visible_problem": False,
            "severity": "none",
            "recommendations": msg,
            "confidence_text": msg
        }

    prompt = f"""You are an agricultural extension agent helping smallholder farmers in India.

**CRITICAL: Return ONLY valid JSON. No markdown code fences, no extra text. Raw JSON only.**

JSON OUTPUT (all fields required):
{{
    "is_real_crop_photo": true | false,
    "non_photo_reason": "screenshot" | "logo" | "document" | "too_blurry" | null,
    "insects_visible": ["beetle", "grasshopper", "caterpillar", "aphid", "moth"] | [],
    "inferred_crop": "Cotton" | "Wheat" | "Soybean" | "Rice" | "Sugarcane" | "Maize" | "unknown",
    "crop_confidence": "high" | "medium" | "low",
    "diagnosis": "<1-2 sentences describing what you see in {language}>",
    "visible_problem": true | false,
    "severity": "high" | "medium" | "low" | "none" | "unknown",
    "recommendations": "<specific actions to take in {language}>",
    "confidence_text": "<why you are/aren't confident in {language}>"
}}

**STRUCTURED OUTPUT RULES:**
- "diagnosis": What's wrong OR what you see (e.g., "कपास की फली पर इल्ली दिखाई दे रही है" or "पौधे की पहचान स्पष्ट नहीं")
- "severity": How serious the problem is (or "none" if healthy, "unknown" if can't tell)
- "recommendations": Specific actions (spray neem, use pesticide, send better photo, etc.)
- "confidence_text": Explain your confidence level (e.g., "उच्च - कपास की फली स्पष्ट दिखाई दे रही है" or "कम - फोटो धुंधली है")
- NO VISIBLE PROBLEM IS A VALID DIAGNOSIS (healthy photos are allowed): use severity="none", visible_problem=false, and give preventive monitoring guidance.
- Do not recommend pesticides unless there is clear visible pest/disease evidence.

**insects_visible RULES:**
- List EVERY insect/creature you see (beetles, grasshoppers, caterpillars, moths, aphids, worms, etc.)
- Even if tiny/small, LIST IT
- If you see a beetle → add "beetle" to the list
- If you see a grasshopper → add "grasshopper" to the list
- If you see NOTHING → empty list []
- **If insects_visible is NOT empty, you MUST set visible_problem=true**

3-TIER CROP IDENTIFICATION (CRITICAL):

VISUAL CROP EVIDENCE WINS (DO NOT ANCHOR ON PROFILE):
- Only name a crop when distinctive organs are visible, e.g. cotton boll/fiber, wheat ear/grain head.
- If unclear, set inferred_crop="unknown" and crop_confidence="low".

1. **Visual overrides profile**: If distinctive crop organs clearly visible (cotton bolls, wheat grain heads, specific leaf morphology) → set inferred_crop to what you SEE with crop_confidence="high", EVEN if different from {crop.title()}.

2. **Ambiguous → unknown**: If vegetation visible but NO distinctive features (generic leaves, far view, blur, early stage) → MUST set:
   - inferred_crop="unknown"
   - crop_confidence="low"
   - In recommendations: use "this plant"/"this leaf" (NO crop name)
   - Suggest clearer/closer photo

3. **Never anchor on profile**: Do NOT use {crop.title()} as evidence. Only name crops when visual features confirm it.

IMAGE TYPE RULES:
**is_real_crop_photo=true** (BE INCLUSIVE):
- Field photos, hand-held leaves, close-ups of plant parts
- **Pest macro shots** (close-up of caterpillar/insect ON crop) = REAL CROP PHOTO ✓
- **Boll/fruit/grain with pest** = REAL CROP PHOTO ✓
- ANY photo showing actual vegetation/plant tissue (even if very zoomed in)
- As long as it's NOT screenshot/UI/logo/document, mark as true

**is_real_crop_photo=false** (ONLY for):
- "screenshot": UI, terminal, app, file explorer, chat interface
- "logo": Graphic, icon, illustration, stylized drawing
- "document": PDF, scanned text, printed document
- "too_blurry": Completely dark/corrupted/unidentifiable

**Default to true**: If it's a photograph of vegetation/plant, even extreme close-up of pest/damage, mark as true.

If is_real_crop_photo=false:
- Set: inferred_crop="unknown", crop_confidence="low", visible_problem=false, severity="none"
- recommendations: one sentence asking for real crop photo in {language}

⚠️ MANDATORY FIRST STEP - PEST SCAN (DO THIS BEFORE ANYTHING ELSE):
**BEFORE analyzing crop type or health, you MUST scan the ENTIRE image for insects/pests.**

Look for:
- Beetles, grasshoppers, locusts, moths, butterflies ON the plant
- Caterpillars, worms, larvae ON leaves/stems/grain
- Aphids (tiny white/green bugs in clusters)
- ANY creature sitting on or near plant parts

**If you see ANY insect/creature → IMMEDIATELY set:**
- visible_problem=true
- severity="high" (if actively feeding) or "medium" (if just present)
- In recommendations: describe the pest (e.g., "beetle on wheat ear", "grasshopper on grain head")

PEST DETECTION RULES (CRITICAL):
1. **Scan foreground AND background**: Insects can be anywhere in frame - on leaves, stems, grain heads, flowers

2. **Size doesn't matter**: Even small insects (beetles, aphids) = visible_problem=true

3. **Disease symptoms**: Spots, lesions, yellowing, wilting, rot → visible_problem=true

4. **ONLY mark healthy if**: NO insects visible ANYWHERE + NO disease symptoms + plant looks completely healthy

**Your mental checklist before responding:**
□ "Did I scan the ENTIRE frame for insects?" (Yes/No)
□ "Are there ANY creatures ON the plant?" (Yes/No)
□ "If YES → did I set visible_problem=true?" (Yes/No)

If you marked visible_problem=false, ask yourself: "Am I 100% certain there are NO insects anywhere in this image?"

CROP CONFIDENCE LEVELS:
- "high": Distinctive organs clearly visible (bolls, grain heads, specific leaf shape) AND you are 95%+ certain
- "medium": Crop features present but not definitive OR you are 60-94% certain
- "low": No distinguishing features OR you are <60% certain

**Conservative crop ID**: When in doubt, use inferred_crop="unknown" and crop_confidence="low". Never guess.

REMEMBER:
- Return raw JSON only (no ``` fences)
- Title Case crops: "Cotton", "Wheat"
- Never name crop unless visual evidence strongly supports it (95%+ certainty for "high")
- ALWAYS check for insects/pests - they are often the main issue farmers send photos about
"""
    
    # Call Claude 3 Sonnet Vision
    print(f"Analyzing image with Claude 3 Sonnet Vision (dialect: {dialect}, crop: {crop})")
    
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',  # Stable legacy model (best cost/performance)
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            })
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        raw_text = response_body['content'][0]['text'].strip()

        # Defensive fallback: strip fences if present (should be rare with temp=0)
        if raw_text.startswith('```'):
            raw_text = '\n'.join(raw_text.split('\n')[1:-1])

        try:
            vision_result = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Vision model returned invalid JSON: {e}")

        # Backward-compat normalization for older/minimal schemas (incl. some unit-test stubs).
        if "recommendations" not in vision_result or vision_result.get("recommendations") is None:
            if vision_result.get("final_message"):
                vision_result["recommendations"] = vision_result.get("final_message")
            elif vision_result.get("diagnosis"):
                vision_result["recommendations"] = vision_result.get("diagnosis")
            else:
                vision_result["recommendations"] = ""
        vision_result.setdefault("insects_visible", [])
        vision_result.setdefault("visible_problem", False)
        vision_result.setdefault("severity", "unknown")
        vision_result.setdefault("crop_confidence", vision_result.get("confidence", "low"))
        vision_result.setdefault("inferred_crop", "unknown")
        vision_result.setdefault("is_real_crop_photo", True)
        vision_result.setdefault("confidence_text", str(vision_result.get("confidence") or ""))

        # Validate schema immediately
        validate_vision_schema(vision_result)

        print(f"Vision analysis complete: {len(raw_text)} characters")

        # Return validated structured result
        return vision_result

    except Exception as e:
        print(f"Error analyzing image: {e}")
        
        # Fallback error message in user's dialect
        error_messages = {
            'hi': 'माफ़ करें, छवि का विश्लेषण करने में समस्या हुई। कृपया स्पष्ट फोटो भेजें या टेक्स्ट में समस्या बताएं।',
            'mr': 'माफ करा, प्रतिमा विश्लेषणात समस्या आली. कृपया स्पष्ट फोटो पाठवा किंवा मजकूरात समस्या सांगा.',
            'te': 'క్షమించండి, చిత్రం విశ్లేషణలో సమస్య. దయచేసి స్పష్టమైన ఫోటో పంపండి లేదా టెక్స్ట్‌లో సమస్య చెప్పండి.',
            'en': 'Sorry, there was a problem analyzing the image. Please send a clear photo or describe the problem in text.'
        }
        
        return {
            'is_real_crop_photo': False,
            'non_photo_reason': 'too_blurry',
            'inferred_crop': 'unknown',
            'crop_confidence': 'low',
            'visible_problem': False,
            'severity': 'unknown',
            'recommendations': error_messages.get(dialect, error_messages['en'])
        }


def process_image_message(message: Dict[str, Any], user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    3-layer defense with diagnostic logging.
    NEVER raise exceptions to webhook (breaks WhatsApp flow).

    Args:
        message: WhatsApp message with image
        user_profile: User profile from DynamoDB

    Returns:
        Dict with 'text' key (message for user) and optional metadata (s3, heuristics_error, etc.)
    """
    try:
        image_id = message['image']['id']
        dialect = user_profile.get('dialect', 'hi')
        crop = user_profile.get('crop', 'cotton')
        phone = user_profile.get('phone_number', 'unknown')

        print(f"Processing image message: image_id={image_id}, dialect={dialect}, crop={crop}")

        # Download image from WhatsApp (can fail: network, WhatsApp auth)
        print("Downloading image from WhatsApp...")
        try:
            image_bytes = download_whatsapp_image(image_id)
            print(f"Downloaded {len(image_bytes)} bytes")
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            print(f"Image download failed: {e}")
            from messages import get_error_message
            return {"text": get_error_message('download_failed', dialect)}

        # LAYER 1: Heuristics gate (pre-flight check)
        heuristics_error = False
        try:
            heuristics = run_heuristics(image_bytes)
            print(f"Heuristics result: {heuristics['decision']}, reason: {heuristics.get('reason')}")
        except Exception as e:
            print(f"Heuristics failed (PIL error): {e}")
            heuristics_error = True
            heuristics = {'decision': 'pass', 'reason': None, 'metrics': {}}

        if heuristics['decision'] == 'block':
            blocked_msg = get_block_message(heuristics['reason'], dialect)
            print(f"Blocked by heuristics: {heuristics['reason']}")
            return {"text": blocked_msg, "non_photo": True, "diagnosis": "non_photo", "non_photo_reason": heuristics.get("reason")}

        # LAYER 1.5: AI relevance gate (generic non-agri detection)
        if _relevance_gate_enabled():
            rel = classify_image_relevance(image_bytes, dialect)
            print(f"Relevance gate: relevance={rel.get('relevance')} confidence={rel.get('confidence')} reason={rel.get('reason')}")
            relevance = rel.get("relevance")
            conf = rel.get("confidence")
            reason = rel.get("reason")

            # Hard-block only when model is confidently non-agri.
            if relevance == "not_agri" and conf in ("high", "medium"):
                msg = get_not_agri_message(dialect)
                return {"text": msg, "non_photo": True, "diagnosis": "non_photo", "non_photo_reason": reason}

            # If model is unsure but reasonably confident, use heuristics metrics as a tie-breaker.
            if relevance == "unclear" and conf in ("high", "medium"):
                m = (heuristics or {}).get("metrics") or {}
                green_frac = float(m.get("green_frac") or 0.0)
                palette_size = int(m.get("palette_size") or 0)
                # If this looks like a real photo (more colors/greens), proceed; else ask retake.
                photo_likely = (green_frac >= 0.06) or (palette_size >= 140)
                if not photo_likely:
                    msg = get_safe_retake_message(dialect)
                    return {"text": msg, "non_photo": True, "diagnosis": "non_photo", "non_photo_reason": (reason or "unclear")}

        if _quality_gate_enabled():
            q = _check_image_quality(image_bytes)
            if not q.get("is_acceptable", True):
                txt = _insufficient_quality_message(dialect, str(q.get("reason") or "unclear"))
                import time
                timestamp = int(time.time())
                phone = user_profile.get('phone_number') or message.get('from', 'unknown')
                s3_key = f"images/{phone}/{timestamp}.jpg"
                if not TEMP_BUCKET:
                    raise RuntimeError('TEMP_AUDIO_BUCKET is required for the WhatsApp image pipeline')
                s3.put_object(Bucket=TEMP_BUCKET, Key=s3_key, Body=image_bytes, ContentType='image/jpeg')
                return {"text": txt, "quality_gate_failed": True, "quality": q, "s3": {"bucket": TEMP_BUCKET, "key": s3_key}}

        # Optional: Save to S3 for record-keeping
        import time
        timestamp = int(time.time())
        s3_key = f"images/{phone}/{timestamp}.jpg"

        if not TEMP_BUCKET:
            raise RuntimeError('TEMP_AUDIO_BUCKET is required for the WhatsApp image pipeline')
        s3.put_object(
            Bucket=TEMP_BUCKET,
            Key=s3_key,
            Body=image_bytes,
            ContentType='image/jpeg'
        )
        print(f"Saved to S3: s3://{TEMP_BUCKET}/{s3_key}")

        # LAYER 2: Vision model
        district = user_profile.get("district") or user_profile.get("location")
        try:
            vision = analyze_crop_image(image_bytes, dialect, crop, district=district)
        except ValueError as e:
            # Schema validation failed or invalid JSON
            print(f"Vision model validation error: {e}")
            from messages import get_error_message
            return {"text": get_error_message('model_invalid_json', dialect)}
        except Exception as e:
            # Other model errors (timeout, rate limit, etc.)
            print(f"Vision model error: {e}")
            from messages import get_error_message
            return {"text": get_error_message('model_error', dialect)}

        # Schema already validated inside analyze_crop_image()

        # EXISTING: _normalize_vision_metadata() already enforces metadata-level safety
        # (crop_confidence != "high" → inferred_crop="unknown")
        # This is preserved for metadata fields.

        # NEW: enforce_message_safety() adds MESSAGE-level safety
        # (crop_confidence != "high" → safe template text, not model prose)
        # This prevents crop names from leaking into user-facing messages.

        # LAYER 3: Handler enforcement
        # If crop is unclear (non-high confidence) and we couldn't infer a crop,
        # ask the user to confirm which crop this is. This preserves the existing
        # crop-confirmation UX used by `handler.py` and associated tests.
        allow_crop_confirm = True
        if _relevance_gate_enabled():
            # Only allow crop confirmation when relevance gate is confidently agri.
            allow_crop_confirm = bool(relevance == "agri_photo" and conf in ("high", "medium"))
        pk = (vision.get("photo_kind") or "unknown").strip() or "unknown"
        cc = (vision.get("crop_confidence") or vision.get("confidence") or "low").strip().lower()
        inferred = (vision.get("inferred_crop") or "unknown").strip() or "unknown"
        if allow_crop_confirm and cc in ("low", "medium") and inferred == "unknown" and pk in ("pest_macro", "leaf_symptom", "unknown"):
            crop_local = localize_crop_name(crop, dialect)
            prompts = {
                "hi": f"यह तस्वीर किस फसल की है? आपकी प्रोफ़ाइल में फसल: {crop_local}. क्या यह वही है?",
                "mr": f"हा फोटो कोणत्या पिकाचा आहे? तुमच्या प्रोफाइलमधील पीक: {crop_local}. हेच आहे का?",
                "te": f"ఇది ఏ పంట ఫోటో? మీ ప్రొఫైల్‌లో పంట: {crop_local}. ఇదేనా?",
                "en": f"Which crop is this photo of? Your profile crop is {crop_local}. Is it the same?",
            }
            return {
                "text": prompts.get(dialect, prompts["en"]),
                "pending_crop_confirm": {
                    "bucket": TEMP_BUCKET,
                    "key": s3_key,
                    "profile_crop": crop,
                    "inferred_crop": crop,
                },
                "s3": {"bucket": TEMP_BUCKET, "key": s3_key},
                "heuristics_error": heuristics_error,
            }

        final_msg = enforce_message_safety(vision, crop, dialect)

        print(f"Final message (enforced): {final_msg[:100]}...")

        # Diagnostic logging (full decision path)
        phone_suffix = phone[-4:] if phone and len(phone) >= 4 else 'unknown'

        log_data = {
            'phone_suffix': phone_suffix,
            'heuristics_decision': heuristics.get('decision', 'pass'),
            'heuristics_error': heuristics_error,
            'is_real_crop_photo': vision.get('is_real_crop_photo'),
            'inferred_crop': vision.get('inferred_crop'),
            'crop_confidence': vision.get('crop_confidence'),
            'visible_problem': vision.get('visible_problem'),
            'severity': vision.get('severity'),
            'raw_message_preview': vision.get('recommendations', '')[:120],
            'final_message_preview': final_msg[:120],
            'was_overridden': (vision.get('recommendations', '') != final_msg)
        }

        print(f"Vision analysis complete: {log_data}")

        return {
            "text": final_msg,
            "s3": {"bucket": TEMP_BUCKET, "key": s3_key},
            "heuristics_error": heuristics_error
        }

    except Exception as e:
        # Ultimate fallback: log and return generic error
        print(f"Unexpected error in image processing: {e}")
        import traceback
        traceback.print_exc()

        dialect = user_profile.get('dialect', 'hi')
        from messages import get_error_message
        return {"text": get_error_message('unknown', dialect)}
