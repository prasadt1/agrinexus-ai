"""
Vision Analyzer
Uses Claude 3 Sonnet Vision for pest/disease identification from images
"""
import boto3
import json
import base64
import os
import io
from typing import Any, Dict, Optional

_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
bedrock = boto3.client("bedrock-runtime", region_name=_region)
s3 = boto3.client("s3", region_name=_region)
secrets = boto3.client("secretsmanager", region_name=_region)

TEMP_BUCKET = os.environ.get("TEMP_AUDIO_BUCKET")
IMAGE_MAX_BYTES = int(os.environ.get("IMAGE_MAX_BYTES", str(5 * 1024 * 1024)))

def _looks_like_logo_or_illustration(image_bytes: bytes) -> bool:
    """
    Best-effort heuristic to reject obvious non-photo images (logos, icons, UI screenshots).
    We keep it lightweight and fail-open if Pillow isn't available.
    """
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return False

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        w, h = img.size
        if w < 64 or h < 64:
            return True

        # Downsample for fast stats.
        small = img.resize((96, 96))
        pixels = list(small.getdata())
        total = len(pixels)
        if total == 0:
            return True

        # Count near-white pixels (common for logos on white background).
        whiteish = 0
        colors = set()
        step = 2  # reduce unique-color set size a bit
        for i, (r, g, b) in enumerate(pixels):
            if r > 245 and g > 245 and b > 245:
                whiteish += 1
            if i % step == 0:
                colors.add((r // 8, g // 8, b // 8))

        white_ratio = whiteish / total
        approx_unique_colors = len(colors)

        # Heuristic: lots of white + low color variety → likely logo/illustration/screenshot.
        if white_ratio >= 0.70 and approx_unique_colors <= 180:
            return True
        return False
    except Exception:
        return False


def _non_photo_message(dialect: str) -> str:
    msgs = {
        "hi": "यह तस्वीर फसल/पत्ते की वास्तविक फोटो नहीं लग रही (logo/illustration). कृपया प्रभावित पत्ता/फसल की साफ़, पास से ली हुई फोटो भेजें।",
        "mr": "ही प्रतिमा फसल/पानाची वास्तविक फोटो वाटत नाही (logo/illustration). कृपया प्रभावित पान/पीक याचा स्पष्ट जवळून घेतलेला फोटो पाठवा.",
        "te": "ఇది పంట/ఆకు యొక్క నిజమైన ఫోటోలా లేదు (logo/illustration). దయచేసి ప్రభావిత ఆకు/పంట యొక్క స్పష్టమైన దగ్గరి ఫోటో పంపండి.",
        "en": "This doesn’t look like a real crop/leaf photo (logo/illustration). Please send a clear close-up photo of the affected leaf/plant.",
    }
    return msgs.get(dialect, msgs["en"])


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
        body = response.read()
    if len(body) > IMAGE_MAX_BYTES:
        raise ValueError(f"image too large ({len(body)} bytes > {IMAGE_MAX_BYTES})")
    return body


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
        district: District / location from PROFILE (optional, for regional advice)
    
    Returns:
        {
            'diagnosis': str,  # What's wrong with the crop
            'severity': str,   # low, medium, high
            'recommendations': str,  # What to do
            'confidence': str  # high, medium, low
        }
    """
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

    # Reject obvious non-photo inputs early (prevents confident hallucinations on logos/icons).
    if _looks_like_logo_or_illustration(image_bytes):
        msg = _non_photo_message(dialect)
        return {
            "diagnosis": "non_photo",
            "severity": "unknown",
            "recommendations": msg,
            "confidence": "low",
            "raw_analysis": msg,
        }

    # Profile-first prompt: avoids false "not your crop" / "not infected" denials on noisy field photos.
    prompt = f"""You are an agricultural extension agent helping smallholder farmers in India.

CONTEXT (use unless the image gives *unmistakable* proof this is a different crop type, e.g. banana plantation vs wheat):
- Registered crop in the farmer's app profile: **{crop}**
- Registered district / area: **{area}**

TASK: Look at the photo for pests, diseases, nutrient stress, or other visible problems — assuming this is their **{crop}** field unless proven otherwise.

RULES:
0. **Non-photo guardrail**: If the image is a logo, illustration, screenshot, document, or not a real crop/leaf photo, say so and ask for a clear close-up photo. Do not invent pests/diseases.
1. **Profile-first**: If the picture is partly blurry, backlit, or just "green vegetation", do **not** relabel it as sugarcane, rice, etc. Say visibility is limited and give guidance for **{crop}**.
2. **Foreground first**: Base the diagnosis on the **sharp, main subject** (e.g. hand-held leaf, insects on that leaf). Out-of-focus yellow flowers or other plants in the **background** are often weeds or intercrop—mention in **at most one short phrase**, not as the headline. **Do not** use background color alone to reject **{crop}**.
3. **Visual fidelity**: Describe what you can actually see (including insect color if visible). Do not contradict obvious colors (e.g., don't call black insects “white”). If color is unclear, say “color not clear in this photo”.
4. **Wheat / cereals**: If **{crop}** is wheat (गेहूं) or similar small grains and you see **clusters of tiny soft-bodied insects** on a **narrow leaf with parallel veins** (typical grass/cereal blade), treat this as a **working diagnosis of cereal aphid / sucking-pest infestation consistent with {crop}** with **medium confidence**—not only "might be aphids". Give concrete scouting (count patches per meter, check flag leaf, look for honeydew/sooty mold) and IPM-style next steps (beneficials, thresholds, consult KVK/local officer for **authorized** products). Do **not** say "not infected" when obvious colonies are visible.
5. **Uncertainty**: If species ID is unclear, state that in **one sentence** in **Confidence** only—still give **full actionable** Recommendations for **{crop}** in the same reply (do not repeat "more photos needed" in every section).
6. **Tone**: Support the farmer. Avoid harsh denials unless the in-focus plant structure **clearly** rules out **{crop}**.
7. **Consistency**: Use the same four numbered headings below every time so answers feel stable across retries.

OUTPUT in **{language}**, simple practical wording, with sections:
1. **Diagnosis** (framed for their **{crop}**)
2. **Severity** (low / medium / high, or "cannot assess from this photo alone")
3. **Recommendations** (immediate actions, timing, cultural practices; mention consulting local agri officer for product choice where rules vary)
4. **Confidence** (how sure you are)
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
        
        # Extract structured data (simple parsing)
        diagnosis = "Unknown"
        severity = "medium"
        recommendations = analysis
        confidence = "medium"
        
        # Try to extract severity
        if 'high' in analysis.lower() or 'गंभीर' in analysis or 'severe' in analysis.lower():
            severity = 'high'
        elif 'low' in analysis.lower() or 'कम' in analysis or 'mild' in analysis.lower():
            severity = 'low'
        
        # Try to extract confidence
        if 'high confidence' in analysis.lower() or 'निश्चित' in analysis:
            confidence = 'high'
        elif 'low confidence' in analysis.lower() or 'अनिश्चित' in analysis:
            confidence = 'low'
        
        return {
            'diagnosis': diagnosis,
            'severity': severity,
            'recommendations': analysis,  # Full response
            'confidence': confidence,
            'raw_analysis': analysis
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


def process_image_message(message: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
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
        phone = user_profile.get('phone_number') or message.get('from', 'unknown')
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
        
        return result['recommendations']
        
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
