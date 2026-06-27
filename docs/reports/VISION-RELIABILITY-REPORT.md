# Vision Reliability Report (WhatsApp photo pipeline)

**Date:** 2026-04-24  
**Audience:** judges / reviewers / contributors  
**Scope:** WhatsApp image handling + Claude Vision reliability hardening (non-photo rejection, quality gating, crop confirmation, and safe fallbacks)

---

## 1) Problem summary

AgriNexus AI’s WhatsApp channel supports photos for pest/disease advisory using Claude Vision. In judge-style testing, two classes of failures were repeatedly observed:

1. **Non-agri / non-photo inputs triggered confident “diagnosis”**  
   Examples: logos, app screenshots, web/article screenshots. These often produced hallucinated pests/diseases, which breaks user trust.

2. **Profile-crop bias on ambiguous images**  
   When the user’s onboarding crop was **Wheat**, some pest macro photos (e.g., cotton bollworm/larva) were mis-framed as wheat pests (e.g., “aphids”)—especially when crop context was missing or the photo was low quality.

Additionally, the WhatsApp platform frequently delivers:

- **Heavily compressed thumbnails** (small dimensions / few KB) that are objectively not diagnosable.
- **Screenshots** that contain UI chrome and text (high edges, low green), which are not suitable for agronomy advice.

The goal was to make the system **deterministically safe**: if the input is not a real crop photo (or not clear enough), we must not “guess”.

---

## 2) Constraints (why this was tricky)

- **WhatsApp media variability**: WhatsApp can change the delivered bytes dramatically vs. the original (compression, resizing, color/contrast shifts).
- **LLM non-determinism**: prompt instructions alone cannot guarantee “no hallucinations”.
- **Crop context is often absent** in pest macro shots (close-ups of larvae/insects rarely show the plant).
- **Judge timeline**: changes had to be safe, testable, and deployable without breaking the live demo.

---

## 3) High-level architecture (before & after)

### Baseline message flow

```
WhatsApp → API Gateway → Webhook Lambda → SQS (FIFO) → MessageProcessor → WhatsApp reply
                                      ↘ DynamoDB (dedup / rate limit)
```

### Vision sub-flow (hardened)

```
Incoming image
  ├─ Deterministic rejects (UI/screenshot, logo/illustration)
  ├─ Deterministic quality gate (too small / too few bytes)
  ├─ Persist to S3 (audit + re-run capability)
  └─ Claude Vision (strict JSON) → safe normalization → output
        ├─ If non-photo: reject message
        ├─ If low crop confidence / pest macro: ask crop (buttons)
        └─ Else: return advice
```

Key code locations:

- `src/processor/analyzer.py`: image download, S3 save, deterministic gates, Vision call, crop prompt trigger
- `src/processor/handler.py`: orchestrates WhatsApp message types, stores pending crop confirmation + last-image pointer
- `tests/vision/` + `tests/test_vision.py`: unit tests for the analyzer modules, importing directly from `src/processor/` (single source of truth; the former `src/vision/` mirror was removed)

---

## 4) Approach (iterative hardening)

This was solved via a sequence of “guardrails” moving left in the pipeline—**before** the LLM:

### A) Strict JSON output + hard gate (LLM-level)

Claude Vision is instructed to return a single JSON object containing:

- `is_real_crop_photo` (boolean)
- `photo_kind` (`leaf_symptom` / `pest_macro` / `field_view` / `unknown`)
- `inferred_crop` + `crop_confidence`
- `final_message` (four fixed sections)

Hard rule: if JSON parsing fails or `is_real_crop_photo == false`, **do not diagnose**; return a non-photo rejection message.

Why: prompt-only “don’t hallucinate” is unreliable; JSON enables deterministic gating.

### B) Deterministic non-photo rejection (pre-LLM)

Two fast heuristics reject non-agri inputs without calling the model:

1. **UI / screenshot detector** (`_looks_like_screenshot_or_ui`)  
   Uses Pillow stats (luminance histogram + edge density + green dominance + palette cues).  
   Extended to handle:
   - dark-mode screenshots (high near-black + edges)
   - small UI thumbnails (size gate + low green)
   - white-dominant article/web screenshots (high white + edges + near-zero green)

2. **Logo / illustration detector** (`_looks_like_logo_or_illustration`)  
   High white background + low color diversity patterns; used as a conservative pre-check.

Outcome: screenshots/logos are rejected deterministically with a helpful message, preventing judge-visible hallucinations.

### C) Deterministic quality gate (pre-LLM)

If an image is obviously not diagnosable:

- `min_dimension < 320` **or**
- `file_size < 3000 bytes`

…then we do **not** call Vision. Instead we return a “photo too small/unclear” message with simple re-capture tips (move closer, tap to focus, good light). The image is still saved to S3 for audit/debugging and possible override flows.

Why: This is the most common cause of “confident but wrong” answers—there simply isn’t enough information in the pixels.

### D) Crop selection / confirmation loop (user-in-the-loop)

We use the user’s onboarding crop as a default for agronomy context, but we do **not** trust crop inference for:

- `photo_kind == pest_macro` (most macros lack crop context)
- cases where the model returns low/medium `crop_confidence`

In those situations the system asks the user which crop the photo is on. This is now optimized for low-literacy UX:

- Uses **WhatsApp buttons** localized to the user’s dialect (Hindi/Marathi/Telugu/English)
- Accepts either **button taps** or typed crop words (localized variants)

### E) “Last-image” override (10-minute pointer)

After any image message, the system stores a short-lived pointer (`bucket`, `key`) to the most recently saved image (TTL ~10 minutes). If the user then replies with just a crop name (or taps a crop button), we can re-run analysis on the last image using that crop.

Why: Farmers often send a photo first, then clarify “this is cotton” after seeing the prompt.

---

## 5) Design decisions (why these choices)

- **Deterministic gates first**: If we can reject safely using pixel statistics, we should—this prevents judge-visible hallucinations.
- **Never infer crop on pest macros**: Even “high confidence” crop inference is frequently wrong when there is no plant context. We force `pest_macro` crop inference to `unknown/low` to trigger the crop prompt.
- **Buttons over English text**: WhatsApp is a constrained UI; buttons reduce typing and avoid English literacy assumptions.
- **Fail-safe defaults**: If parsing fails, or if the model is uncertain, we choose a “safe ask” rather than a diagnosis.

---

## 6) Implementation notes (high level)

### Key mechanics

- **Strict JSON + hard gate**: Vision must return JSON; otherwise we send the non-photo safe message.
- **UI/screenshot detection**: `_looks_like_screenshot_or_ui` uses:
  - luminance histogram (black/white fractions)
  - edge density (text/UI lines)
  - green dominance (typical for real plant photos)
  - palette hints (limited-color UI)
- **Quality gate**: `_check_image_quality` blocks images below thresholds.
- **State management** (DynamoDB, TTL):
  - `PENDING#CROP_CONFIRM` stores confirmation state for re-run
  - `PENDING#LAST_IMAGE` stores last-image pointer for override

---

## 7) Testing strategy

We added unit tests to prevent regressions in the two “trust-breaking” areas:

- **Screenshot/UI rejection**: ensures we do not call Vision on UI screenshots (including WhatsApp-compressed variants).
- **Thumbnail quality gate**: ensures tiny images are blocked deterministically.
- **Crop selection parsing**: ensures localized crop words map correctly, and button replies work.

See:

- `tests/test_vision_quality_gate.py`
- `tests/test_pest_macro_crop_prompt.py`
- `tests/test_crop_button_localization.py`

---

## 8) Results (observable behavior)

After hardening:

- **Logos, screenshots, article/web UI images** are deterministically rejected with a non-photo message (no diagnosis).
- **Very small / heavily compressed images** are blocked with a “resend clearer photo” message.
- **Pest macro photos** reliably trigger a crop selection prompt (buttons in the user’s language), preventing profile-crop bias.
- Users can **confirm crop** via button or text and get a re-run using the chosen crop.

---

## 9) What’s next (optional)

- Add more crops (localized labels) if onboarding expands.
- Add a small “why we ask crop” line to the crop prompt (kept short for WhatsApp).
- Consider storing the last N images (instead of last 1) if users often send multiple photos before replying.


