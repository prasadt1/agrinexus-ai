# Vision Confidence & Image Classification Design

**Date:** 2026-04-25
**Author:** Claude Sonnet 4.5
**Status:** Draft (pending review)
**Implementation:** Approach 1 - Minimal, Non-Overengineered

---

## Executive Summary

**Problem:** The WhatsApp vision advisory system makes confident wrong assumptions about images, leading to farmer confusion and potential incorrect advice:
- Screenshots/UI images analyzed as crop photos
- Logos/illustrations treated as real plants
- Generic vegetation mis-labeled as specific crops (especially "wheat")
- Profile crop used as evidence instead of visual features

**Solution:** 3-layer defense system with deterministic heuristics, structured JSON schema, and handler-level enforcement to prevent hallucinations and crop name leakage.

**Key Principle:** **Fail-safe over fail-graceful.** When in doubt, ask for a clearer photo rather than guessing.

---

## Architecture Overview

### 3-Layer Defense

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: PRE-FLIGHT HEURISTICS (Deterministic)              │
│  - Dark/white pixel ratio (light & dark mode UI detection)  │
│  - Edge density patterns (sharp rectangles vs organic)      │
│  - Palette size (flat graphics vs rich photos)              │
│  → Decision: PASS (run model) | BLOCK (screenshot/logo)     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: VISION MODEL (Claude 3 Sonnet)                     │
│  - Input: image_bytes + structured JSON prompt              │
│  - Output: Validated JSON with classification + diagnosis   │
│  - Schema: English enums + localized final_message          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: HANDLER ENFORCEMENT (Business Logic)               │
│  - Parse JSON strictly (fail fast on violations)            │
│  - Route: BLOCK non-crop | TEMPLATE if not high confidence  │
│  - Override: Block crop names when confidence != "high"     │
│  → Output: Safe, validated WhatsApp message                 │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
WhatsApp image
  → download_whatsapp_image()
  → run_heuristics()
      → BLOCK? return template immediately
      → PASS? continue ↓
  → analyze_crop_image() (Vision Model)
      → JSON response with classification
  → enforce_message_safety() (Handler)
      → Validate & route based on confidence
  → return localized message to farmer
```

### Key Architectural Decisions

1. **No preflight model call** – Heuristics are deterministic (fast, cheap, predictable)
2. **Single vision model call** – All classification + diagnosis in one invocation
3. **Strict validation** – Handler enforces rules even if model deviates
4. **Fail-safe defaults** – When in doubt, hard block or ask for clearer photo (never guess)
5. **Observability-first** – Log every decision for tuning and debugging

---

## Component Designs

### 1. Pre-Flight Heuristics

**Purpose:** Catch obvious non-crop inputs (screenshots, logos, documents) before calling expensive vision model.

**Design Principle:** Multi-signal, conservative blocking. Only block when 2+ signals agree. Prefer false-pass over false-block (vision model + handler catch ambiguous cases).

#### Function Signature

```python
def run_heuristics(image_bytes: bytes) -> Dict[str, Any]:
    """
    Conservative multi-signal detector based on real-world failure patterns.
    Consolidates existing _looks_like_screenshot_or_ui() and
    _looks_like_logo_or_illustration() into unified logic.

    Returns:
        {
            'decision': 'pass' | 'block',
            'reason': 'screenshot_ui' | 'logo' | 'document' | 'too_small' | None,
            'metrics': {
                'white_frac': float,   # % pixels with luminance > 240
                'dark_frac': float,            # fraction in grayscale bins 0-55
                'edge_frac': float,         # % pixels that are edges
                'palette_size': int,           # distinct colors (quantized)
                'aspect_ratio': float,         # width / height
                'width': int,
                'height': int,
                'file_size_kb': float
            }
        }
    """
```

#### Detection Rules

**Screenshot/UI Detection** (matches existing `_looks_like_screenshot_or_ui()`):

Multiple rule combinations (OR logic - any match triggers block):

1. **Light mode UI/docs**: `edge_frac > 0.16 AND white_frac > 0.18 AND black_frac > 0.008`
2. **Very white screenshots**: `edge_frac > 0.22 AND white_frac > 0.28`
3. **White-dominant articles**: `edge_frac > 0.14 AND white_frac > 0.55 AND green_frac < 0.03`
4. **Dark-mode chat/app**: `black_frac > 0.22 AND edge_frac > 0.085`
5. **Dark-mode IDE (compressed)**: `dark_frac > 0.30 AND edge_frac > 0.052 AND green_frac < 0.12`
6. **GitHub dark repo tree**: `dark_frac > 0.24 AND edge_frac > 0.068 AND green_frac < 0.085 AND palette_size <= 140`
7. **Heavily compressed dark UI**: `dark_frac > 0.72 AND edge_frac > 0.034 AND green_frac < 0.05 AND palette_size <= 110`
8. **Small UI thumbnails**: `min(width, height) <= 320 AND green_frac < 0.12 AND (white_frac > 0.60 OR black_frac > 0.18)`
9. **Flat UI (limited palette)**: `green_frac < 0.06 AND edge_frac > 0.09 AND palette_size <= 90`

**Logo/Illustration Detection** (matches existing `_looks_like_logo_or_illustration()`):

- `white_frac >= 0.70 AND palette_size <= 180` → Logo/icon on white background

**Unusable image:**
- `width < 64` OR `height < 64` → too small
- `file_size_kb < 3` → likely corrupt (optional check)

**Pass criteria (default):**
- None of the above block rules triggered → PASS to vision model
- Aspect ratio NOT used as primary blocker (real photos vary widely)
- When in doubt, pass (fail-open)

#### Implementation Notes

```python
def run_heuristics(image_bytes: bytes) -> Dict[str, Any]:
    """
    Consolidates existing _looks_like_screenshot_or_ui() and
    _looks_like_logo_or_illustration() into unified detector.
    """

    # Calculate all metrics once
    metrics = _calculate_image_metrics(image_bytes)
    m = metrics  # shorthand

    # Check unusable first
    if m['width'] < 64 or m['height'] < 64:
        return {'decision': 'block', 'reason': 'too_small', 'metrics': metrics}

    # Screenshot/UI detection (9 rules - matches existing implementation)

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


def _calculate_image_metrics(image_bytes: bytes) -> Dict[str, Any]:
    """
    Pillow-only metrics matching existing _looks_like_screenshot_or_ui() implementation.
    No OpenCV/NumPy to keep Lambda cold starts fast.

    Returns metrics dict with all required fields for heuristic detection.
    """
    from PIL import Image, ImageFilter
    import io

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size
    file_size_kb = len(image_bytes) / 1024.0
    aspect_ratio = width / height if height > 0 else 1.0

    # Normalize size for stable thresholds (matches existing implementation)
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
    approx_unique_colors16 = len(qcolors16)

    return {
        'black_frac': black_frac,
        'dark_frac': dark_frac,
        'white_frac': white_frac,
        'edge_frac': edge_frac,
        'green_frac': green_frac,
        'palette_size': approx_unique_colors16,  # Approximate unique colors (quantized to 16-level)
        'aspect_ratio': aspect_ratio,
        'width': width,
        'height': height,
        'file_size_kb': file_size_kb
    }
```

**Dependencies:** Pillow only (already in Lambda layer). No OpenCV/NumPy.

**Performance:** ~30-40ms on Lambda for typical WhatsApp images after cold start.

#### Example Decisions

**Dark mode GitHub screenshot (real failure case):**
```python
{
    'decision': 'block',
    'reason': 'screenshot_ui',
    'metrics': {
        'white_frac': 0.08,   # Dark mode
        'dark_frac': 0.52,            # ✓ signal 1
        'edge_frac': 0.22,         # ✓ signal 2
        'palette_size': 38,           # ✓ signal 3
        'aspect_ratio': 1.6,
        'width': 1920,
        'height': 1200
    }
}
```

**Real cotton boll photo (bright white fiber, organic):**
```python
{
    'decision': 'pass',
    'reason': None,
    'metrics': {
        'white_frac': 0.48,   # White cotton (below 0.5)
        'dark_frac': 0.12,            # Some dark stems
        'edge_frac': 0.11,         # Organic edges (below 0.18)
        'palette_size': 342,          # Rich variation
        'aspect_ratio': 0.75,
        'width': 1024,
        'height': 1365
    }
}
```

**Wheat field at dusk (dark soil, low light - passes):**
```python
{
    'decision': 'pass',
    'reason': None,
    'metrics': {
        'white_frac': 0.02,
        'dark_frac': 0.38,            # Dark soil (below 0.4)
        'edge_frac': 0.09,         # Organic
        'palette_size': 876,          # ✓ Rich palette saves it
        'aspect_ratio': 1.33,
        'width': 1280,
        'height': 960
    }
}
```

#### Tuning Strategy

- Start with these thresholds (based on existing implementation)
- Log every heuristic decision + vision outcome to CloudWatch
- After 100+ real images, analyze false-block rate (target: <2%)
- Adjust individual thresholds based on failure patterns
- **Prefer false-pass over false-block** (vision model + handler catch ambiguous cases)

---

### 2. Vision Prompt & JSON Schema

**Purpose:** Force vision model to output structured, validated responses with clear confidence levels and crop identification.

**Design Principle:** Schema-first. English enums for control fields, localized prose only in final message. Temperature=0 for deterministic JSON.

#### Helper Functions

**WhatsApp Image Download:**

```python
def download_whatsapp_image(media_id: str) -> bytes:
    """
    Download image from WhatsApp Media API.

    Args:
        media_id: WhatsApp media ID from webhook message

    Returns:
        Image bytes

    Raises:
        urllib.error.HTTPError: If WhatsApp API returns error (401, 404, 500)
        urllib.error.URLError: If network connection fails
        KeyError: If media URL not in response
    """
    import urllib.request
    import json

    # Get WhatsApp credentials from Secrets Manager
    access_token_secret = os.environ.get('ACCESS_TOKEN_SECRET', 'agrinexus/whatsapp/access-token')
    response = secrets.get_secret_value(SecretId=access_token_secret)
    access_token = response['SecretString']

    # Get media URL from WhatsApp
    url = f"https://graph.facebook.com/v22.0/{media_id}"
    headers = {"Authorization": f"Bearer {access_token}"}

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        media_url = data['url']

    # Download actual image bytes
    req = urllib.request.Request(media_url, headers=headers)
    with urllib.request.urlopen(req) as response:
        return response.read()
```

**Supported Dialects:**

```python
SUPPORTED_DIALECTS = {
    'hi': 'Hindi (Devanagari script)',
    'mr': 'Marathi (Devanagari script)',
    'te': 'Telugu script',
    'en': 'English'
}

# Dialect fallback: If user_profile has unsupported dialect (e.g., 'ta', 'kn'),
# default to 'en' for prompt construction and 'en' for error messages.
# This is handled by: language_map.get(dialect, "English")
```

**Schema Field Name Clarification:**

The vision model MUST return a field named `recommendations` (not `text`). This is the localized user-facing message in the appropriate dialect. The field name is consistent throughout the codebase and all error paths.

Handler enforcement references `vision_result['recommendations']` - validated by schema check, no fallback needed.

**Supported Crops (Extensible List):**

Initial supported crops: Cotton, Wheat, Soybean, Rice, Sugarcane, Maize. The vision model can identify other crops if distinctive features are visible, but these 6 are the primary focus for Indian smallholder farmers. To add new crops: update the vision prompt examples and ensure RAG knowledge base has relevant content.

#### JSON Response Schema

```python
VISION_RESPONSE_SCHEMA = {
    "is_real_crop_photo": bool,  # True | False
    "non_photo_reason": str | None,  # "screenshot" | "logo" | "document" | "too_blurry" | None
    "inferred_crop": str,  # "Cotton" | "Wheat" | "Soybean" | "Rice" | ... | "unknown"
    "crop_confidence": str,  # "high" | "medium" | "low"
    "visible_problem": bool,  # True | False
    "severity": str,  # "high" | "medium" | "low" | "none" | "unknown"
    "recommendations": str  # Localized diagnosis + recommendations (hi/mr/te/en)
}
```

**Note:** `recommendations` is the actual field name used in current implementation. This is the localized user-facing message.

#### Vision Prompt Structure

```python
def analyze_crop_image(
    image_bytes: bytes,
    dialect: str,
    profile_crop: str = "cotton",
    district: Optional[str] = None,
) -> Dict[str, Any]:

    language_map = {
        'hi': 'Hindi (Devanagari script)',
        'mr': 'Marathi (Devanagari script)',
        'te': 'Telugu script',
        'en': 'English'
    }
    language = language_map.get(dialect, "English")
    area = (district or "").strip() or "not specified"
    profile_crop_title = profile_crop.title()  # Match schema: "Cotton" not "cotton"

    prompt = f"""You are an agricultural extension agent helping smallholder farmers in India.

**CRITICAL: Return ONLY valid JSON. No markdown code fences, no extra text. Raw JSON only.**

PROFILE CONTEXT (farmer's registered crop, NOT visual evidence):
- Registered crop: {profile_crop_title}
- District: {area}

JSON OUTPUT (all fields required):
{% raw %}{{
    "is_real_crop_photo": true | false,
    "non_photo_reason": "screenshot" | "logo" | "document" | "too_blurry" | null,
    "inferred_crop": "Cotton" | "Wheat" | "Soybean" | "Rice" | "Sugarcane" | "Maize" | "unknown",
    "crop_confidence": "high" | "medium" | "low",
    "visible_problem": true | false,
    "severity": "high" | "medium" | "low" | "none" | "unknown",
    "recommendations": "<2-4 sentences in {language}>"
}}{% endraw %}

3-TIER CROP IDENTIFICATION (CRITICAL):

1. **Visual overrides profile**: If distinctive crop organs clearly visible (cotton bolls, wheat grain heads, specific leaf morphology) → set inferred_crop to what you SEE with crop_confidence="high", EVEN if different from {profile_crop_title}.

2. **Ambiguous → unknown**: If vegetation visible but NO distinctive features (generic leaves, far view, blur, early stage) → MUST set:
   - inferred_crop="unknown"
   - crop_confidence="low"
   - In recommendations: use "this plant"/"this leaf" (NO crop name)
   - Suggest clearer/closer photo

3. **Never anchor on profile**: Do NOT use {profile_crop_title} as evidence. Only name crops when visual features confirm it.

IMAGE TYPE RULES:
- "real_crop": Real photograph of plant/crop (field, hand-held, close-up)
- "screenshot": UI, terminal, app, file explorer, chat
- "logo": Graphic, icon, illustration, stylized image
- "document": PDF, scanned text, document photo
- "too_blurry": Too dark/blurry/corrupted to classify

If is_real_crop_photo=false:
- Set: inferred_crop="unknown", crop_confidence="low", visible_problem=false, severity="none"
- recommendations: one sentence asking for real crop photo in {language}

CONFIDENCE LEVELS:
- "high": Distinctive organs clearly visible
- "medium": Crop features present but not definitive
- "low": No distinguishing features

SEVERITY:
- "high" | "medium" | "low": when visible_problem=true and you can assess severity
- "none": when visible_problem=false (no problem visible)
- "unknown": when is_real_crop_photo=false or image too unclear to assess

RECOMMENDATIONS ({language}):
- Non-crop: "यह असली फसल की फोटो नहीं लगती। कृपया पत्ती/पौधे का क्लोज-अप भेजें।"
- Unknown crop: "पौधे की पहचान स्पष्ट नहीं है। कृपया करीब से फोटो भेजें।" (NO crop name)
- High confidence: Name crop, describe problem, give specific advice
- No problem: "कोई स्पष्ट समस्या दिखाई नहीं दे रही।" + monitoring/retake advice

REMEMBER:
- Return raw JSON only (no ``` fences)
- Title Case crops: "Cotton", "Wheat"
- Never name crop unless visual evidence supports it
"""

    # Detect image format from magic bytes
    if image_bytes[:2] == b'\xff\xd8':
        media_type = "image/jpeg"
    elif image_bytes[:4] == b'\x89PNG':
        media_type = "image/png"
    elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"  # Default fallback

    # Encode image to base64
    import base64
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

    # Call Bedrock with structured prompt
    response = bedrock.invoke_model(
        modelId='anthropic.claude-3-sonnet-20240229-v1:0',
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "temperature": 0,  # Deterministic for JSON
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                    {"type": "text", "text": prompt}
                ]
            }]
        })
    )

    response_body = json.loads(response['body'].read())
    raw_text = response_body['content'][0]['text'].strip()

    # Defensive fallback: strip fences if present (should be rare)
    if raw_text.startswith('```'):
        raw_text = '\n'.join(raw_text.split('\n')[1:-1])

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Vision model returned invalid JSON: {e}")
```

#### Key Design Decisions

1. **Schema-first**: Model must return structured JSON, not natural language
2. **English enums**: `is_real_crop_photo`, `inferred_crop`, etc. are English for reliable parsing
3. **Only `recommendations` localized**: Separates control signals from user-facing content
4. **3-tier rule in prompt**: Explicit instructions for each confidence level
5. **Temperature=0**: Deterministic output for consistent JSON structure
6. **Defensive parsing**: Strip markdown fences if model adds them despite instructions
7. **Title Case crops**: "Cotton" not "cotton" (matches existing code conventions)

---

### 3. Handler Logic & Last-Mile Enforcement

**Purpose:** Final safety layer that validates structured fields and **overrides or blocks** user-facing messages when they violate confidence rules.

**Design Principle:** Handler is source of truth, not model prose. Structured fields control display logic; prose is untrusted input that must be validated.

#### Integration with Existing Code

**Current implementation** (`src/processor/analyzer.py`) already has:
- `_normalize_vision_metadata(photo_kind, inferred_crop, crop_confidence)` - enforces `crop_confidence != "high" → inferred_crop="unknown"`
- This handles **metadata normalization** but doesn't control the user-facing **message text**

**New requirement** (this spec):
- `enforce_message_safety(vision_result, profile_crop, dialect)` - enforces message-level safety
- Returns the **actual text sent to WhatsApp**, blocking crop names when confidence != "high"

**Integration path:**
```python
# In process_image_message() after vision model call:
vision = analyze_crop_image(...)  # Returns JSON with 'recommendations' field

# NEW: Validate schema (already added to spec)
validate_vision_schema(vision)

# EXISTING: Normalize metadata fields
normalized = _normalize_vision_metadata(
    vision.get('photo_kind', 'unknown'),
    vision['inferred_crop'],
    vision['crop_confidence']
)

# NEW: Enforce message-level safety (Option A - bulletproof)
final_message = enforce_message_safety(vision, profile_crop, dialect)

# Return final_message to WhatsApp (not vision['recommendations'] directly)
return final_message
```

**Note:** `enforce_message_safety()` is **additive** - it doesn't replace `_normalize_vision_metadata()`, it adds message-level enforcement on top of metadata normalization.

#### Handler Flow

```python
def process_image_message(message: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
    """
    3-layer defense with diagnostic logging.
    NEVER raise exceptions to webhook (breaks WhatsApp flow).
    """
    try:
        image_id = message['image']['id']
        dialect = user_profile.get('dialect', 'hi')
        profile_crop = user_profile.get('crop', 'cotton')
        district = user_profile.get('district')
        phone = user_profile.get('phone_number', 'unknown')

        # Download image (can fail: network, WhatsApp auth)
        try:
            image_bytes = download_whatsapp_image(image_id)
        except (urllib.error.HTTPError, urllib.error.URLError, KeyError) as e:
            logger.error(f"Image download failed: {e}", exc_info=True)
            return get_error_message('download_failed', dialect)

        # LAYER 1: Heuristics gate
        heuristics_error = False
        try:
            heuristics = run_heuristics(image_bytes)
        except Exception as e:
            logger.error(f"Heuristics failed (PIL/corrupt): {e}", exc_info=True)
            heuristics_error = True  # Flag for monitoring
            heuristics = {'decision': 'pass', 'reason': None, 'metrics': {}}

        if heuristics['decision'] == 'block':
            blocked_msg = get_block_message(heuristics['reason'], dialect)

            logger.info({
                'phone_suffix': phone[-4:] if phone and len(phone) >= 4 else 'unknown',
                'layer': 'heuristics_block',
                'reason': heuristics['reason'],
                'metrics': heuristics['metrics']
            })

            return blocked_msg

        # LAYER 2: Vision model
        vision = analyze_crop_image(image_bytes, dialect, profile_crop, district)

        # Validate schema immediately after vision call
        try:
            validate_vision_schema(vision)
        except ValueError as e:
            logger.error(f"Vision response missing required fields: {e}")
            return get_error_message('model_invalid_json', dialect)

        # LAYER 3: Handler enforcement (CRITICAL)
        final_msg = enforce_message_safety(vision, profile_crop, dialect)

        # Diagnostic logging (full decision path)
        logger.info({
            'phone_suffix': phone[-4:] if phone and len(phone) >= 4 else 'unknown',
            'heuristics_error': heuristics_error,
            'heuristics_decision': 'pass',
            'is_real_crop_photo': vision['is_real_crop_photo'],
            'non_photo_reason': vision.get('non_photo_reason'),
            'inferred_crop': vision['inferred_crop'],
            'crop_confidence': vision['crop_confidence'],
            'visible_problem': vision['visible_problem'],
            'severity': vision['severity'],
            'raw_message_preview': vision.get('recommendations', '')[:120],
            'final_message_preview': final_msg[:120],
            'was_overridden': (vision.get('recommendations', '') != final_msg)
        })

        return final_msg

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return get_error_message('unknown', user_profile.get('dialect', 'hi'))
```

#### Enforcement Function (Option A - Bulletproof)

**Chosen approach:** Simplest possible enforcement. If `crop_confidence != "high"` → safe template. No exceptions.

```python
def enforce_message_safety(
    vision_result: Dict[str, Any],
    profile_crop: str,
    dialect: str
) -> str:
    """
    Bulletproof enforcement: trust structured fields only.
    If confidence != high → safe template. Zero leakage risk.
    """

    is_real_crop = vision_result['is_real_crop_photo']
    non_photo_reason = vision_result.get('non_photo_reason')
    crop_confidence = vision_result['crop_confidence']
    model_message = vision_result['recommendations']  # Validated by schema check

    # Gate 1: Non-crop → hard block
    if not is_real_crop:
        return get_block_message(non_photo_reason or 'screenshot', dialect)

    # Gate 2: High confidence → allow model message (earned the right)
    if crop_confidence == "high":
        return model_message

    # Gate 3: Anything else → safe template (no trust, no scan)
    return get_safe_retake_message(dialect)
```

**Rationale:** For production with real farmers, fail-safe wins until we have data proving fail-graceful doesn't leak. Can upgrade to Option B (scan + preserve compliant messages) later if templates feel too repetitive after logging 100+ real images.

#### Message Templates

```python
def get_safe_retake_message(dialect: str) -> str:
    """
    Short, consistent safe template for unknown/low-confidence.
    Asks for clearer photo without excessive detail.
    """
    templates = {
        'hi': 'पौधे की पहचान स्पष्ट नहीं है। कृपया प्रभावित पत्ती या हिस्से का करीब से स्पष्ट फोटो भेजें।',
        'mr': 'रोपाची ओळख स्पष्ट नाही. कृपया प्रभावित पानाचा किंवा भागाचा जवळून स्पष्ट फोटो पाठवा.',
        'te': 'మొక్క గుర్తింపు స్పష్టంగా లేదు. దయచేసి ప్రభావిత ఆకు లేదా భాగం యొక్క దగ్గరి స్పష్ట ఫోటో పంపండి.',
        'en': 'Cannot identify the plant clearly. Please send a closer, clearer photo of the affected leaf or part.'
    }
    return templates.get(dialect, templates['en'])


def get_block_message(reason: str, dialect: str) -> str:
    """Hard block messages for non-crop inputs (short, 1-2 lines)"""
    messages = {
        'screenshot': {
            'hi': 'यह स्क्रीनशॉट लगती है। कृपया फसल/पत्ती की असली फोटो भेजें।',
            'mr': 'ही स्क्रीनशॉट दिसते. कृपया पिक/पानाची खरी फोटो पाठवा.',
            'te': 'ఇది స్క్రీన్‌షాట్ లా కనిపిస్తోంది. దయచేసి పంట/ఆకు యొక్క నిజమైన ఫోటో పంపండి.',
            'en': 'This looks like a screenshot. Please send a real photo of the crop/leaf.'
        },
        'logo': {
            'hi': 'यह लोगो/ग्राफिक लगती है। कृपया पत्ती का क्लोज-अप भेजें।',
            'mr': 'ही लोगो/ग्राफिक दिसते. कृपया पानाचा क्लोज-अप पाठवा.',
            'te': 'ఇది లోగో/గ్రాఫిక్ లా కనిపిస్తోంది. దయచేసి ఆకు క్లోజ్-అప్ పంపండి.',
            'en': 'This looks like a logo/graphic. Please send a close-up of a leaf.'
        },
        'document': {
            'hi': 'यह डॉक्यूमेंट लगती है। कृपया फसल की फोटो भेजें।',
            'mr': 'हे दस्तऐवज दिसते. कृपया पिकाचा फोटो पाठवा.',
            'te': 'ఇది డాక్యుమెంట్ లా కనిపిస్తోంది. దయచేసి పంట ఫోటో పంపండి.',
            'en': 'This looks like a document. Please send a crop photo.'
        },
        'too_blurry': {
            'hi': 'फोटो धुंधली है। कृपया स्पष्ट फोटो भेजें।',
            'mr': 'फोटो अस्पष्ट आहे. कृपया स्पष्ट फोटो पाठवा.',
            'te': 'ఫోటో అస్పష్టంగా ఉంది. దయచేసి స్పష్ట ఫోటో పంపండి.',
            'en': 'Photo is blurry. Please send a clearer photo.'
        },
        'too_small': {
            'hi': 'फोटो बहुत छोटी है। कृपया बड़ी फोटो भेजें।',
            'mr': 'फोटो खूप लहान आहे. कृपया मोठा फोटो पाठवा.',
            'te': 'ఫోటో చాలా చిన్నది. దయచేసి పెద్ద ఫోటో పంపండి.',
            'en': 'Photo is too small. Please send a larger photo.'
        }
    }

    return messages.get(reason, {}).get(dialect, messages['screenshot']['en'])
```

#### Enforcement Guarantees

1. ✅ **Heuristics block** → never calls vision model, returns template immediately
2. ✅ **Non-crop image** → handler returns hard block (ignores model prose)
3. ✅ **Low/medium confidence** → handler returns safe template (zero crop name leakage)
4. ✅ **High confidence** → handler trusts model's message (earned the right to name crops)
5. ✅ **Logging** → captures full decision path for debugging deployment mismatches

---

### 4. Error Handling

**Purpose:** Graceful degradation for all failure modes. Never break WhatsApp message flow.

**Design Principle:** Fail-safe. Every error returns actionable farmer message + logs for debugging.

#### Error Categories

- **Download failure**: WhatsApp API auth, network issues
- **Heuristics failure**: PIL errors, corrupt images → graceful degradation (skip to vision)
- **Vision model failure**: Bedrock timeout, rate limits, invalid JSON
- **Schema validation failure**: Missing required fields
- **Handler failure**: Enforcement logic errors → ultimate fallback

#### Schema Validation

```python
def validate_vision_schema(vision: Dict[str, Any]) -> None:
    """
    Validate required fields including the display message field.
    Raises ValueError if invalid.
    """
    required_fields = [
        'is_real_crop_photo',
        'inferred_crop',
        'crop_confidence',
        'visible_problem',
        'severity',
        'recommendations'  # Required display field
    ]

    missing = [f for f in required_fields if f not in vision or vision[f] is None]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    # Validate enums
    if vision['crop_confidence'] not in ['high', 'medium', 'low']:
        raise ValueError(f"Invalid crop_confidence: {vision['crop_confidence']}")

    if vision['severity'] not in ['high', 'medium', 'low', 'none', 'unknown']:
        raise ValueError(f"Invalid severity: {vision['severity']}")
```

#### Error Messages (Short, 1-2 lines)

```python
def get_error_message(error_type: str, dialect: str) -> str:
    """User-friendly error messages. Always suggest alternative."""
    messages = {
        'download_failed': {
            'hi': 'फोटो डाउनलोड नहीं हुई। कृपया दोबारा भेजें।',
            'mr': 'फोटो डाउनलोड झाला नाही. कृपया पुन्हा पाठवा.',
            'te': 'ఫోటో డౌన్‌లోడ్ కాలేదు. దయచేసి మళ్లీ పంపండి.',
            'en': 'Photo download failed. Please resend.'
        },
        'model_error': {
            'hi': 'विश्लेषण में समस्या। कृपया दोबारा भेजें।',
            'mr': 'विश्लेषणात समस्या. कृपया पुन्हा पाठवा.',
            'te': 'విశ్లేషణలో సమస్య. దయచేసి మళ్లీ పంపండి.',
            'en': 'Analysis problem. Please resend.'
        },
        'rate_limit': {
            # Reuse existing rate-limit message
            'hi': 'अभी बहुत व्यस्त हैं। 1 मिनट बाद कोशिश करें।',
            'mr': 'आत्ता खूप व्यस्त. 1 मिनिटानंतर प्रयत्न करा.',
            'te': 'ఇప్పుడు చాలా బిజీ. 1 నిమిషం తర్వాత ప్రయత్నించండి.',
            'en': 'Very busy now. Try after 1 minute.'
        },
        'model_invalid_json': {
            'hi': 'तकनीकी समस्या। कृपया दोबारा भेजें।',
            'mr': 'तांत्रिक समस्या. कृपया पुन्हा पाठवा.',
            'te': 'సాంకేతిక సమస్య. దయచేసి మళ్లీ పంపండి.',
            'en': 'Technical problem. Please resend.'
        },
        'unknown': {
            'hi': 'कुछ गड़बड़ हुई। कृपया दोबारा कोशिश करें।',
            'mr': 'काहीतरी चूक. कृपया पुन्हा प्रयत्न करा.',
            'te': 'ఏదో తప్పు. దయచేసి మళ్లీ ప్రయత్నించండి.',
            'en': 'Something went wrong. Please try again.'
        }
    }

    return messages.get(error_type, messages['unknown']).get(dialect, messages['unknown']['en'])
```

#### Error Handling Principles

1. ✅ **Never raise to webhook** - All exceptions caught, farmer always gets response
2. ✅ **Graceful degradation** - Heuristics fail → skip to vision (don't block farmer)
3. ✅ **Clear messages** - Tell farmer what to do (resend, try text, wait)
4. ✅ **Distinguish transient vs permanent** - Rate limits get different message
5. ✅ **Log with context** - Phone suffix, error type, stack trace
6. ✅ **heuristics_error flag** - Track PIL/corrupt image failures for monitoring

---

### 5. Testing Strategy

**Purpose:** Prevent regressions and validate the fix catches all known failure modes.

**Design Principle:** Test at each layer. Use existing synthetic generators. Minimal regression suite (3-5 cases), grow from real incidents.

#### Test Categories

**1. Heuristics Unit Tests (using existing generators)**

```python
def test_heuristics_dark_mode_ui():
    """Dark mode UI → blocked (uses dark_frac bins 0-55)"""
    image_bytes = generate_github_dark_screenshot()  # Existing helper
    result = run_heuristics(image_bytes)

    assert result['decision'] == 'block'
    assert result['reason'] == 'screenshot_ui'
    assert result['metrics']['dark_frac'] > 0.4
    assert result['metrics']['edge_frac'] > 0.18

def test_heuristics_cotton_boll_white():
    """Real cotton boll (white fiber) → passes"""
    image_bytes = generate_cotton_boll()  # Existing helper
    result = run_heuristics(image_bytes)

    assert result['decision'] == 'pass'
    assert result['metrics']['white_frac'] < 0.5
    assert result['metrics']['edge_frac'] < 0.18

def test_heuristics_light_mode_ui():
    """Light mode UI → blocked"""
    image_bytes = generate_slack_screenshot()
    result = run_heuristics(image_bytes)

    assert result['decision'] == 'block'
    assert result['reason'] == 'screenshot_ui'
    assert result['metrics']['white_frac'] > 0.5

def test_heuristics_logo():
    """Logo/icon → blocked"""
    image_bytes = generate_leaf_logo()
    result = run_heuristics(image_bytes)

    assert result['decision'] == 'block'
    assert result['reason'] == 'logo'
    assert result['metrics']['palette_size'] < 30
```

**2. Vision Model Integration Tests**

```python
def test_vision_screenshot_classification():
    """Vision model classifies screenshot correctly"""
    image_bytes = generate_github_dark_screenshot()
    result = analyze_crop_image(image_bytes, 'en', 'cotton')

    assert result['is_real_crop_photo'] == False
    assert result['non_photo_reason'] == 'screenshot'
    assert result['inferred_crop'] == 'unknown'

def test_vision_high_confidence_crop():
    """Distinctive crop organs → high confidence, visual overrides profile"""
    image_bytes = generate_cotton_boll_clear()
    result = analyze_crop_image(image_bytes, 'en', 'wheat')  # Wrong profile

    assert result['is_real_crop_photo'] == True
    assert result['inferred_crop'] == 'Cotton'  # Visual overrides
    assert result['crop_confidence'] == 'high'

def test_vision_generic_vegetation():
    """Generic leaves → unknown crop, low confidence"""
    image_bytes = generate_generic_green_leaves()
    result = analyze_crop_image(image_bytes, 'en', 'wheat')

    assert result['is_real_crop_photo'] == True
    assert result['inferred_crop'] == 'unknown'
    assert result['crop_confidence'] == 'low'
```

**3. Handler Enforcement Tests (Option A - Bulletproof)**

**Critical tests** - these validate the fix for crop name leakage:

```python
def test_enforcement_high_confidence_allows():
    """High confidence → model message allowed"""
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'high',
        'recommendations': 'Cotton bollworm detected.'
    }

    result = enforce_message_safety(vision, 'cotton', 'en')
    assert result == 'Cotton bollworm detected.'

def test_enforcement_not_high_template():
    """crop_confidence != "high" → safe template (Option A)"""
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'low',
        'recommendations': 'This looks like wheat with aphids.'  # Doesn't matter
    }

    result = enforce_message_safety(vision, 'wheat', 'en')
    # Always safe template when not high
    assert 'Cannot identify' in result
    assert 'wheat' not in result.lower()

def test_enforcement_medium_confidence_template():
    """Medium confidence also gets template (Option A)"""
    vision = {
        'is_real_crop_photo': True,
        'crop_confidence': 'medium',
        'recommendations': 'Appears to be cotton with some damage.'
    }

    result = enforce_message_safety(vision, 'cotton', 'en')
    assert 'Cannot identify' in result

def test_enforcement_non_crop_hard_block():
    """Non-crop image → hard block"""
    vision = {
        'is_real_crop_photo': False,
        'non_photo_reason': 'screenshot',
        'crop_confidence': 'low',
        'recommendations': 'Some text'
    }

    result = enforce_message_safety(vision, 'cotton', 'en')
    assert 'screenshot' in result.lower()
```

**4. Minimal Regression Suite (3-5 critical cases)**

```python
REGRESSION_SUITE = [
    {
        'name': 'dark_github_screenshot',
        'generator': generate_github_dark_screenshot,
        'expect_heuristics_block': 'screenshot_ui'
    },
    {
        'name': 'generic_leaves_no_organs',
        'generator': generate_generic_green_leaves,
        'expect_inferred_crop': 'unknown',
        'expect_confidence': 'low'
    },
    {
        'name': 'leaf_logo_icon',
        'generator': generate_leaf_logo,
        'expect_heuristics_block': 'logo'
    }
]

@pytest.mark.parametrize('case', REGRESSION_SUITE)
def test_regression(case):
    """Ensure known failures stay fixed"""
    image_bytes = case['generator']()
    heuristics = run_heuristics(image_bytes)

    if 'expect_heuristics_block' in case:
        assert heuristics['decision'] == 'block'
        assert heuristics['reason'] == case['expect_heuristics_block']
    else:
        vision = analyze_crop_image(image_bytes, 'en', 'wheat')
        assert vision['inferred_crop'] == case.get('expect_inferred_crop', 'unknown')
        assert vision['crop_confidence'] == case.get('expect_confidence', 'low')
```

**5. Manual Validation Checklist (before deployment)**

```
[ ] Dark mode screenshot (GitHub, VS Code, Slack) → blocked
[ ] Light mode screenshot (docs, chat, file explorer) → blocked
[ ] Logo/icon (stylized leaf, flat graphic) → blocked
[ ] Document/PDF → blocked
[ ] Cotton boll close-up (white fiber) → passes heuristics, high confidence
[ ] Wheat grain heads → high confidence "Wheat"
[ ] Generic green leaves (no organs) → "unknown", low confidence
[ ] Blurry vegetation → "unknown", low confidence
[ ] Far field view → "unknown", low confidence
[ ] Error: corrupt image → graceful error message
[ ] Error: Bedrock timeout → graceful error message
[ ] Enforcement: low confidence + crop name in message → safe template returned
[ ] Enforcement: high confidence → model message allowed
```

---

## Implementation Notes

### Deployment Sequence

1. **Add heuristics function** (`run_heuristics()`) - consolidate existing screenshot/logo detection
2. **Update vision prompt** - add 3-tier crop logic + JSON schema requirements
3. **Add schema validation** - `validate_vision_schema()` with required fields
4. **Add enforcement function** - `enforce_message_safety()` with Option A (bulletproof)
5. **Update handler** - integrate 3 layers + diagnostic logging
6. **Add error handling** - graceful degradation for all failure modes
7. **Deploy to dev/staging** - validate with manual checklist
8. **Monitor logs** - check `heuristics_decision`, `crop_confidence`, `was_overridden` fields
9. **Deploy to production** - gradual rollout, monitor farmer feedback
10. **Iterate on thresholds** - after 100+ images, tune heuristics if needed

### Configuration

No new environment variables required. Uses existing:
- `TEMP_AUDIO_BUCKET` (for image storage)
- `ACCESS_TOKEN_SECRET` (for WhatsApp image download)
- Bedrock model ID: `anthropic.claude-3-sonnet-20240229-v1:0`

### Monitoring & Tuning

**Key CloudWatch metrics to track:**
- `heuristics_block_rate` - % of images blocked pre-flight (target: 5-15%)
- `heuristics_error_rate` - % of PIL/corrupt failures (target: <1%)
- `crop_confidence_distribution` - % high/medium/low (expect: high ~30%, medium ~20%, low ~50%)
- `message_override_rate` - % where handler changed model message (expect: 40-60% initially with Option A)
- `is_real_crop_photo_false_rate` - % vision model classified as non-crop after heuristics passed

**Tuning thresholds after 100+ images:**
- If `heuristics_block_rate` too high (>20%) → relax multi-signal thresholds
- If `heuristics_error_rate` high → investigate PIL/WhatsApp compression issues
- If `crop_confidence=high` too low (<20%) → vision prompt may be too conservative
- If farmer complaints about templates → consider Option B (preserve compliant messages)

### Rollback Plan

If issues arise:
1. **Quick rollback**: Disable enforcement layer (return model message directly) - falls back to current behavior
2. **Partial rollback**: Disable heuristics (always pass to vision) - keeps schema + enforcement
3. **Full rollback**: Revert to previous `analyzer.py` version

Old behavior preserved in `src/vision/analyzer.py` git history.

---

## Success Criteria

**Primary (zero tolerance):**
- ✅ No "wheat" mentions when `crop_confidence != "high"`
- ✅ Screenshots/logos never analyzed as crops
- ✅ Non-crop images return hard block, not diagnosis

**Secondary (monitor for 2 weeks):**
- 🎯 False-block rate from heuristics <2% (check manual complaints)
- 🎯 Error rate <0.5% (graceful degradation working)
- 🎯 Farmer satisfaction maintained or improved (WhatsApp feedback)

**Iteration goals (after Option A stable):**
- Consider Option B (preserve compliant low-confidence messages) if templates feel repetitive
- Tune heuristic thresholds based on real failure patterns
- Add conditional fallback ("If this is your {crop}...") selectively where it adds value

---

## Open Questions / Future Enhancements

1. **OCR-lite for text detection?** - Not in initial implementation (multi-signal sufficient), but could add if screenshots still leak
2. **EXIF metadata checks?** - Not implemented (WhatsApp strips most EXIF), revisit if needed
3. **Confidence scoring from model?** - Currently binary (high vs not high), could add numeric scores later
4. **Multi-crop support?** - Current schema supports one `inferred_crop`, could extend to list if farmers send intercrop photos
5. **Crop-specific organ detection?** - Could add explicit checks ("cotton boll detected: true/false") but increases prompt complexity

---

## Related Documents

- `HALLUCINATION-FIX-APR13.md` - Previous RAG hallucination fix (similar prompt hardening)
- `src/vision/analyzer.py` - Current vision implementation
- `src/processor/handler.py` - RAG handler with anti-hallucination rules

---

**Document Status:** Ready for review
**Next Steps:** User review → Spec document review loop → Implementation planning
