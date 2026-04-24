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

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
secrets = boto3.client('secretsmanager', region_name='us-east-1')

TEMP_BUCKET = os.environ.get('TEMP_AUDIO_BUCKET')

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
        if black_frac > 0.22 and edge_frac > 0.085:
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
    maybe_ui = _looks_like_screenshot_or_ui(image_bytes)
    if maybe_ui:
        cropped = _extract_primary_frame(image_bytes)
        if cropped != image_bytes:
            image_bytes = cropped
        if _looks_like_screenshot_or_ui(image_bytes):
            msg = _non_photo_message(dialect)
            return {
                "diagnosis": "non_photo",
                "severity": "unknown",
                "recommendations": msg,
                "confidence": "low",
                "raw_analysis": msg,
            }
    else:
        image_bytes = _extract_primary_frame(image_bytes)

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

CONTEXT (use unless the image gives *unmistakable* proof this is a different crop type, e.g. banana plantation vs wheat):
- Registered crop in the farmer's app profile: **{crop}**
- Registered district / area: **{area}**

TASK: Look at the photo for pests, diseases, nutrient stress, or other visible problems — assuming this is their **{crop}** field unless proven otherwise.

RULES:
0. **Non-photo guardrail (be conservative)**: If the image is a logo, illustration, screenshot/UI, document, meme, diagram, or you are not clearly seeing a real plant/leaf captured by a camera, set `is_real_crop_photo=false`. Examples: a stylized leaf icon with clean lines on a white background; app/file browser screenshots; graphics with flat colors. Do not invent pests/diseases.
1. **Profile-first**: If the picture is partly blurry, backlit, or just "green vegetation", do **not** relabel it as sugarcane, rice, etc. Say visibility is limited and give guidance for **{crop}**.
2. **Foreground first**: Base the diagnosis on the **sharp, main subject** (e.g. hand-held leaf, insects on that leaf). Out-of-focus yellow flowers or other plants in the **background** are often weeds or intercrop—mention in **at most one short phrase**, not as the headline. **Do not** use background color alone to reject **{crop}**.
3. **Visual fidelity**: Describe what you can actually see (including insect color if visible). Do not contradict obvious colors (e.g., don't call black insects “white”). If color is unclear, say “color not clear in this photo”.
4. **Wheat / cereals (apply ONLY when conditions match)**: Only use this rule if you **clearly** see a **cereal leaf blade** (narrow leaf with parallel veins) AND **clusters of tiny soft-bodied insects** (aphid-like colonies). **Do not apply** this rule to photos of **large larvae/caterpillars**, **buds/flowers/bolls**, or macro insect shots with no cereal leaf visible. If you see a **caterpillar/larva chewing**, describe it as a chewing pest (e.g., bollworm/armyworm-type) with appropriate scouting/IPM steps, even if the profile crop is different.
5. **Uncertainty**: If species ID is unclear, state that in **one sentence** in **Confidence** only—still give **full actionable** Recommendations for **{crop}** in the same reply (do not repeat "more photos needed" in every section).
6. **Tone**: Support the farmer. Avoid harsh denials unless the in-focus plant structure **clearly** rules out **{crop}**.
7. **Consistency**: Use the same four numbered headings below every time so answers feel stable across retries.

OUTPUT:
Return ONLY one JSON object (no prose, no markdown) with keys:
- is_real_crop_photo: boolean
- non_photo_reason: string
- photo_kind: one of ["leaf_symptom","pest_macro","field_view","unknown"]
- inferred_crop: one of ["Cotton","Wheat","Soybean","Maize","unknown"]
- crop_confidence: one of ["low","medium","high"]
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
"""
    
    # Call Claude 3 Sonnet Vision
    print(f"Analyzing image with Claude 3 Sonnet Vision (dialect: {dialect}, crop: {crop})")
    
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "temperature": 0.2,
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
            severity = str(obj.get("severity") or "unknown")
            confidence = str(obj.get("confidence") or "medium")
            needs_confirm = (crop_confidence == "high" and inferred_crop in ("Cotton", "Wheat", "Soybean", "Maize") and inferred_crop != crop)
            return {
                "diagnosis": "Unknown",
                "severity": severity,
                "recommendations": obj["final_message"],
                "confidence": confidence,
                "photo_kind": photo_kind,
                "inferred_crop": inferred_crop,
                "crop_confidence": crop_confidence,
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
                "hi": f"यह एक *कीट का क्लोज़‑अप* फोटो लग रहा है। सही सलाह देने के लिए बताइए यह फोटो किस फसल पर है?\n\nCotton / Wheat / Soybean / Maize में से लिखें (या प्रोफ़ाइल वाली फसल: **{profile_crop}**).",
                "mr": f"हा *किडीचा क्लोज‑अप* फोटो दिसतो. योग्य सल्ल्यासाठी हा फोटो कोणत्या पिकाचा आहे?\n\nCotton / Wheat / Soybean / Maize पैकी लिहा (किंवा प्रोफाईल पीक: **{profile_crop}**).",
                "te": f"ఇది *పురుగు క్లోస్‑అప్* ఫోటోలా ఉంది. సరైన సలహా కోసం ఇది ఏ పంటపై ఉందో చెప్పండి.\n\nCotton / Wheat / Soybean / Maize లో ఒకటి పంపండి (లేదా ప్రొఫైల్ పంట: **{profile_crop}**).",
                "en": f"This looks like a *close-up pest photo*. To give the right recommendation, which crop is this on?\n\nReply with one: Cotton / Wheat / Soybean / Maize (or your profile crop: **{profile_crop}**).",
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

        if result.get("needs_crop_confirm") and isinstance(result.get("inferred_crop"), str):
            inferred = str(result.get("inferred_crop") or "").strip()
            profile_crop = str(crop or "").strip() or "unknown"
            if inferred and inferred != profile_crop:
                confirm_msgs = {
                    "hi": f"आपके प्रोफ़ाइल में फसल **{profile_crop}** है, लेकिन यह फोटो **{inferred}** जैसी लग रही है।\n\n{inferred} के रूप में विश्लेषण करने के लिए `YES` भेजें, या प्रोफ़ाइल वाली फसल के लिए `{profile_crop.upper()}` भेजें।",
                    "mr": f"तुमच्या प्रोफाईलमध्ये पीक **{profile_crop}** आहे, पण हा फोटो **{inferred}** सारखा दिसतो.\n\n{inferred} म्हणून विश्लेषणासाठी `YES` पाठवा, किंवा प्रोफाईल पिकासाठी `{profile_crop.upper()}` पाठवा.",
                    "te": f"మీ ప్రొఫైల్‌లో పంట **{profile_crop}** ఉంది, కానీ ఈ ఫోటో **{inferred}** లాగా కనిపిస్తోంది.\n\n{inferred} గా విశ్లేషించడానికి `YES` పంపండి, లేదా ప్రొఫైల్ పంట కోసం `{profile_crop.upper()}` పంపండి.",
                    "en": f"Your profile crop is **{profile_crop}**, but this photo looks like **{inferred}**.\n\nReply `YES` to analyze as {inferred}, or reply `{profile_crop.upper()}` to analyze using your profile crop.",
                }
                return {
                    "text": confirm_msgs.get(dialect, confirm_msgs["en"]),
                    "pending_crop_confirm": {
                        "bucket": TEMP_BUCKET,
                        "key": s3_key,
                        "profile_crop": profile_crop,
                        "inferred_crop": inferred,
                    },
                }

        return result["recommendations"]
        
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
