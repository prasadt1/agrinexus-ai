"""
Vision Analyzer
Uses Claude 3 Sonnet Vision for pest/disease identification from images
"""
import boto3
import json
import base64
import os
from typing import Dict, Any, Optional

# Import WhatsApp credentials with caching from common layer
from common.whatsapp import get_whatsapp_credentials

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

TEMP_BUCKET = os.environ.get('TEMP_AUDIO_BUCKET')
if not TEMP_BUCKET:
    raise RuntimeError('TEMP_AUDIO_BUCKET is required but not set')

# WhatsApp images are typically small; cap to avoid abuse / Lambda memory spikes
IMAGE_MAX_BYTES = int(os.environ.get('IMAGE_MAX_BYTES', str(5 * 1024 * 1024)))


def download_whatsapp_image(media_id: str) -> bytes:
    """Download image from WhatsApp"""
    import urllib.request

    # Get WhatsApp credentials (cached - saves Secrets Manager calls)
    access_token, _ = get_whatsapp_credentials()
    
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
    crop: str = 'cotton',
    caption: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze crop image for pests, diseases, or nutrient deficiencies
    
    Args:
        image_bytes: Image data
        dialect: User's dialect (hi, mr, te, en)
        crop: Crop type (default: cotton)
        caption: Optional WhatsApp image caption (farmer's question)
    
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
    language = language_map.get(dialect, 'English')
    
    caption_block = ""
    if caption and str(caption).strip():
        caption_block = (
            "\nThe farmer added this caption with the photo (treat as their question):\n"
            f"{repr(str(caption).strip())}\n"
        )

    # Build prompt — ground in visible evidence; avoid invented Hindi terms
    prompt = f"""You are a careful agricultural assistant for Indian farmers. You only see this image — do not invent facts.

{caption_block}
Crop context from the farmer's profile: **{crop}** (the photo may show leaves, stem, or field — identify what you actually see).

RULES (must follow):
1. **Visible evidence only**: Describe ONLY symptoms you can see (e.g. insect shape/color, clustering, chewing, holes, yellowing, mold). If you do NOT see holes, tears, or spots, do NOT claim them. If the leaf looks mostly intact, say so.
2. **Hindi terminology**: If responding in Hindi, use **standard** terms farmers and extension use — e.g. small sap-sucking insects in dense groups on cereals are often **माहू** (aphids). Do NOT invent compound words or nonsense phrases. If unsure of the Hindi name, write a short plain description, then the English name in parentheses (e.g. "माहू (aphids)").
3. **Uncertainty**: If identification is not certain, say clearly and set confidence to low or medium — do not fake certainty.
4. **Treatment advice**: Give short, practical steps: scouting, cultural/IPM (water, avoid overcrowding, natural enemies), and tell the farmer to **confirm with local agriculture department / authorized dealer** for approved products in their state. Avoid long lists of chemical names and dosages unless you are highly confident they match the visible problem; never invent product rates.
5. **Format** (use these section headings in {language}):
   - Diagnosis (2–5 short sentences)
   - Severity (one line: low / medium / high + why)
   - Recommendations (numbered, at most 4 points, each brief)
   - Confidence (one line: low / medium / high)

Keep the entire answer concise (roughly under 350 words). Respond in {language}.
"""
    
    # Call Claude 3 Sonnet Vision
    print(f"Analyzing image with Claude 3 Sonnet Vision (dialect: {dialect}, crop: {crop})")
    
    try:
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-sonnet-20240229-v1:0',
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 900,
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
        caption = message.get('image', {}).get('caption')
        
        print(f"Processing image message: image_id={image_id}, dialect={dialect}, crop={crop}")
        
        # Download image from WhatsApp
        print("Downloading image from WhatsApp...")
        image_bytes = download_whatsapp_image(image_id)
        print(f"Downloaded {len(image_bytes)} bytes")
        if len(image_bytes) > IMAGE_MAX_BYTES:
            too_big = {
                'hi': f'यह फ़ोटो बहुत बड़ी है ({len(image_bytes)//1024} KB)। कृपया छोटी या कम रिज़ॉल्यूशन वाली फोटो भेजें।',
                'mr': 'ही फोटो खूप मोठी आहे. कृपया लहान किंवा कमी रिझोल्यूशन फोटो पाठवा.',
                'te': 'ఈ ఫోటో చాలా పెద్దది. దయచేసి చిన్న లేదా తక్కువ రిజల్యూషన్ ఫోటో పంపండి.',
                'en': 'This photo file is too large. Please send a smaller or lower-resolution image.',
            }
            return too_big.get(dialect, too_big['en'])
        
        # Optional: Save to S3 for record-keeping
        import time
        timestamp = int(time.time())
        phone = user_profile.get('phone_number', 'unknown')
        s3_key = f"images/{phone}/{timestamp}.jpg"
        
        s3.put_object(
            Bucket=TEMP_BUCKET,
            Key=s3_key,
            Body=image_bytes,
            ContentType='image/jpeg'
        )
        print(f"Saved to S3: s3://{TEMP_BUCKET}/{s3_key}")
        
        # Analyze image
        result = analyze_crop_image(image_bytes, dialect, crop, caption=caption)
        
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
