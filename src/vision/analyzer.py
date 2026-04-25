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
from typing import Any, Dict, Optional

from src.vision.heuristics import run_heuristics
from src.vision.messages import get_block_message

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
secrets = boto3.client('secretsmanager', region_name='us-east-1')

TEMP_BUCKET = os.environ.get('TEMP_AUDIO_BUCKET')

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
            'diagnosis': str,  # What's wrong with the crop
            'severity': str,   # low, medium, high
            'recommendations': str,  # What to do
            'confidence': str  # high, medium, low
        }
    """
    # If this looks like a UI/screenshot, reject (cropping embedded content creates false positives).
    if _looks_like_screenshot_or_ui(image_bytes):
        msg = _non_photo_message(dialect)
        return {
            "diagnosis": "non_photo",
            "severity": "unknown",
            "recommendations": msg,
            "confidence": "low",
            "photo_kind": "unknown",
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "raw_analysis": msg,
        }

    image_bytes = _extract_primary_frame(image_bytes)
    if _looks_like_screenshot_or_ui(image_bytes):
        msg = _non_photo_message(dialect)
        return {
            "diagnosis": "non_photo",
            "severity": "unknown",
            "recommendations": msg,
            "confidence": "low",
            "photo_kind": "unknown",
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "raw_analysis": msg,
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
            "diagnosis": "non_photo",
            "severity": "unknown",
            "recommendations": msg,
            "confidence": "low",
            "raw_analysis": msg,
        }

    prompt = f"""You are an agricultural extension agent helping smallholder farmers in India.

CONTEXT (profile crop is background context, NOT proof of what is in the image):
- Registered crop in the farmer's app profile: **{crop}**
- Registered district / area: **{area}**

TASK: Look at the photo for pests, diseases, nutrient stress, or other visible problems. First identify what the visible plant/crop part actually is; then use the profile crop only if the image itself is ambiguous.

RULES:
VISUAL CROP EVIDENCE WINS:
- Distinctive crop organs override profile context. If you clearly see **cotton boll/fiber** on a plant, set `inferred_crop="Cotton"` and `crop_confidence="high"` even if the registered crop is Wheat or another crop.
- Do not call cotton lint/fiber, white boll lobes, flowers, pods, fruit, or bracts “insects” unless actual insects are clearly visible.
- Only describe the crop as Wheat/cereal if you clearly see cereal plant structure (narrow blade leaves, cereal ear/head, stem/tillers). A cotton boll/fiber photo is never wheat.
NO CROP GUESSING:
- If you are not strongly confident about the crop from the visible plant structure, set `inferred_crop="unknown"` and `crop_confidence="low"`.
- In `final_message`, do not name a specific crop unless `crop_confidence="high"`. Use generic wording (e.g., “plant/leaf”) when uncertain.
NO VISIBLE PROBLEM IS A VALID DIAGNOSIS:
- If you can identify the crop/plant part but do **not** clearly see pests, disease spots, wilting, rot, nutrient stress, chewing, holes, or other damage, say that no clear pest/disease symptom is visible in this photo.
- Do not recommend pesticides, fungicides, insecticides, or spray schedules unless an actual pest/disease/damage symptom is clearly visible.
- Normal crop structures are not symptoms: cotton lint/fiber, brown dry bracts, boll seams, stems, shadows, and dried plant parts should not be labeled as pests or disease by themselves.
0. **Non-photo guardrail (be conservative)**: If the image is a logo, illustration, screenshot/UI, document, meme, diagram, or you are not clearly seeing a real plant/leaf captured by a camera, set `is_real_crop_photo=false`. Examples: a stylized leaf icon with clean lines on a white background; app/file browser screenshots; **GitHub/repo/code listings, IDE panels, or folder trees** (thin colored text on dark backgrounds); graphics with flat colors. Do not invent pests/diseases. **Never** call something a wheat/cotton/soy field from these UI images.
   But a real close-up photo of a crop part is still a crop photo: cotton boll/fiber on the plant, flower, fruit/pod, leaf, stem, pest on plant tissue, or field canopy. Do **not** reject a cotton boll or white cotton fiber as "logo/illustration" just because it is white-dominant.
1. **Profile fallback only**: If the picture is partly blurry, backlit, or just "green vegetation" with no distinctive crop part, do **not** relabel it as sugarcane, rice, etc. Say visibility is limited and give guidance for **{crop}**.
2. **Foreground first**: Base the diagnosis on the **sharp, main subject** (e.g. hand-held leaf, insects on that leaf). Out-of-focus yellow flowers or other plants in the **background** are often weeds or intercrop—mention in **at most one short phrase**, not as the headline. **Do not** use background color alone to reject **{crop}**.
3. **Visual fidelity**: Describe what you can actually see (including insect color if visible). Do not contradict obvious colors (e.g., don't call black insects “white”). If color is unclear, say “color not clear in this photo”.
4. **Wheat / cereals (apply ONLY when conditions match)**: Only use this rule if you **clearly** see a **cereal leaf blade** (narrow leaf with parallel veins) AND **clusters of tiny soft-bodied insects** (aphid-like colonies). **Do not apply** this rule to photos of **large larvae/caterpillars**, **buds/flowers/bolls**, or macro insect shots with no cereal leaf visible. If you see a **caterpillar/larva chewing**, describe it as a chewing pest (e.g., bollworm/armyworm-type) with appropriate scouting/IPM steps, even if the profile crop is different.
5. **Uncertainty**: If species ID or symptoms are unclear, state that briefly in **Confidence** and give conservative next steps (monitor, send a closer symptom/pest photo, check nearby plants). Do not invent a treatment.
6. **Tone**: Support the farmer. Avoid harsh denials unless the in-focus plant structure **clearly** rules out **{crop}**.
7. **Consistency**: Use the same four numbered headings below every time so answers feel stable across retries.

OUTPUT:
Return ONLY one JSON object (no prose, no markdown) with keys:
- is_real_crop_photo: boolean
- non_photo_reason: string
- photo_kind: one of ["leaf_symptom","pest_macro","field_view","unknown"]
- inferred_crop: one of ["Cotton","Wheat","Soybean","Maize","unknown"]
- crop_confidence: one of ["low","medium","high"]
- visible_problem: boolean
- insect_color: one of ["black","white","green","brown","mixed","unknown"]
- severity: one of ["low","medium","high","unknown"]
- confidence: one of ["low","medium","high"]
- final_message: string in **{language}** with exactly these 4 sections:
  1. **Diagnosis**
  2. **Severity**
  3. **Recommendations**
  4. **Confidence**

If is_real_crop_photo is false:
- final_message must ask for a real crop/leaf close-up photo and must NOT mention pests/diseases.
If visible_problem is false:
- final_message must say no clear pest/disease/damage symptom is visible in this photo.
- Recommendations should be monitoring / sending a clearer close-up if symptoms appear; no pesticide or spray advice.
"""
    
    # Call Claude 3 Sonnet Vision
    print(f"Analyzing image with Claude 3 Sonnet Vision (dialect: {dialect}, crop: {crop})")
    
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
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
        analysis = response_body['content'][0]['text']

        print(f"Vision analysis complete: {len(analysis)} characters")

        obj = _extract_json_object(analysis)
        if obj and isinstance(obj.get("final_message"), str):
            if obj.get("is_real_crop_photo") is False:
                msg = _non_photo_message(dialect)
                return {
                    "diagnosis": "non_photo",
                    "severity": "unknown",
                    "recommendations": msg,
                    "confidence": "low",
                    "photo_kind": "unknown",
                    "inferred_crop": "unknown",
                    "crop_confidence": "low",
                    "raw_analysis": analysis,
                }
            photo_kind = str(obj.get("photo_kind") or "unknown")
            inferred_crop = str(obj.get("inferred_crop") or "unknown")
            crop_confidence = str(obj.get("crop_confidence") or "low")
            norm = _normalize_vision_metadata(photo_kind, inferred_crop, crop_confidence)
            photo_kind = norm["photo_kind"]
            inferred_crop = norm["inferred_crop"]
            crop_confidence = norm["crop_confidence"]
            visible_problem = bool(obj.get("visible_problem", True))
            severity = str(obj.get("severity") or "unknown")
            confidence = str(obj.get("confidence") or "medium")
            needs_confirm = False
            return {
                "diagnosis": "Unknown",
                "severity": severity,
                "recommendations": obj["final_message"],
                "confidence": confidence,
                "photo_kind": photo_kind,
                "inferred_crop": inferred_crop,
                "crop_confidence": crop_confidence,
                "visible_problem": visible_problem,
                "needs_crop_confirm": needs_confirm,
                "raw_analysis": analysis,
            }

        msg = _non_photo_message(dialect)
        return {
            "diagnosis": "unknown",
            "severity": "unknown",
            "recommendations": msg,
            "confidence": "low",
            "photo_kind": "unknown",
            "inferred_crop": "unknown",
            "crop_confidence": "low",
            "raw_analysis": analysis,
        }
        
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
            'diagnosis': 'Error',
            'severity': 'unknown',
            'recommendations': error_messages.get(dialect, error_messages['en']),
            'confidence': 'low',
            'error': str(e)
        }


def process_image_message(message: Dict[str, Any], user_profile: Dict[str, Any]) -> Any:
    """
    Process WhatsApp image message
    
    Args:
        message: WhatsApp message with image
        user_profile: User profile from DynamoDB
    
    Returns:
        Analysis text to send back to user
    """
    try:
        image_id = message['image']['id']
        dialect = user_profile.get('dialect', 'hi')
        crop = user_profile.get('crop', 'cotton')
        
        print(f"Processing image message: image_id={image_id}, dialect={dialect}, crop={crop}")
        
        # Download image from WhatsApp
        print("Downloading image from WhatsApp...")
        image_bytes = download_whatsapp_image(image_id)
        print(f"Downloaded {len(image_bytes)} bytes")

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
            return blocked_msg

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
        phone = user_profile.get('phone_number', 'unknown')
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
        
        # Analyze image
        district = user_profile.get("district") or user_profile.get("location")
        result = analyze_crop_image(image_bytes, dialect, crop, district=district)

        photo_kind = str(result.get("photo_kind") or "unknown")
        crop_conf = str(result.get("crop_confidence") or "low")
        if photo_kind in ("pest_macro", "leaf_symptom", "unknown") and crop_conf != "high":
            profile_crop = str(crop or "").strip() or "unknown"
            prompt_msgs = {
                "hi": "यह *क्लोज़‑अप/आंशिक फसल फोटो* लग रहा है। सही सलाह के लिए बताइए यह फोटो किस फसल पर है?",
                "mr": "हा *जवळून/अंशतः घेतलेला पीक फोटो* दिसतो. योग्य सल्ल्यासाठी हा फोटो कोणत्या पिकावर आहे?",
                "te": "ఇది *దగ్గరగా/భాగంగా తీసిన పంట ఫోటోలా* ఉంది. సరైన సలహా కోసం ఇది ఏ పంటపై ఉందో చెప్పండి.",
                "en": "This looks like a *close-up/partial crop photo*. To give the right recommendation, which crop is this?",
            }
            return {
                "text": prompt_msgs.get(dialect, prompt_msgs["en"]),
                "pending_crop_confirm": {
                    "bucket": TEMP_BUCKET,
                    "key": s3_key,
                    "profile_crop": profile_crop,
                    "inferred_crop": "",
                },
            }

        return {"text": result["recommendations"], "s3": {"bucket": TEMP_BUCKET, "key": s3_key}}
        
    except Exception as e:
        print(f"Error processing image message: {e}")
        
        # Return error message in user's dialect
        dialect = user_profile.get('dialect', 'hi')
        error_messages = {
            'hi': 'माफ़ करें, छवि प्रोसेस करने में समस्या हुई। कृपया फिर से कोशिश करें या टेक्स्ट में समस्या बताएं।',
            'mr': 'माफ करा, प्रतिमा प्रक्रियेत समस्या आली. कृपया पुन्हा प्रयत्न करा किंवा मजकूरात समस्या सांगा.',
            'te': 'క్షమించండి, చిత్రం ప్రాసెస్ చేయడంలో సమస్య. దయచేసి మళ్లీ ప్రయత్నించండి లేదా టెక్స్ట్‌లో సమస్య చెప్పండి.',
            'en': 'Sorry, there was a problem processing the image. Please try again or describe the problem in text.'
        }
        
        return error_messages.get(dialect, error_messages['en'])
