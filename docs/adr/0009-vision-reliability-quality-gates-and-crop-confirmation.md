# ADR 0009 — Vision reliability: deterministic gates + crop confirmation (WhatsApp)

### Status
Accepted (2026-04-24)

### Context
AgriNexus AI supports WhatsApp photo advisory via Claude Vision. In judge-style and real-world testing, two issues repeatedly reduced trust:

- **Non-photo inputs** (logos, UI screenshots, article/web screenshots) sometimes triggered confident pest/disease outputs.
- **Profile-crop bias**: when the onboarding crop was Wheat, ambiguous images—especially **pest macro** close-ups—could be framed as wheat issues even when the photo was on a different crop (e.g., cotton bollworm).

WhatsApp media delivery also varies significantly (compression/resizing), producing very small or low-information images that are not diagnosable.

### Decision
Adopt a “deterministic safety first” design for vision:

1. **Deterministic non-photo rejection (pre-LLM)**  
   Reject screenshots/UI and obvious logo/illustration images using pixel-statistics heuristics (Pillow).

2. **Deterministic quality gate (pre-LLM)**  
   If the image is clearly unusable (`min_dimension < 320` OR `file_size < 3000 bytes`), do not call Vision; ask the user to resend a clearer photo.

3. **Strict JSON schema + hard gate (LLM output)**  
   Require Vision to return a single JSON object including `is_real_crop_photo`. If parsing fails or `is_real_crop_photo == false`, return a non-photo safe message.

4. **Crop selection / confirmation loop for low-context cases**  
   For pest macro photos and other low-confidence cases, do not trust model crop inference. Ask the user which crop the photo is on using **localized WhatsApp buttons**; accept button taps or typed crop words.

5. **Last-image pointer (10-min TTL)**  
   Store a short-lived pointer to the most recent saved image so a user can reply with a crop name and trigger a re-run with that crop.

### Architecture (relevant slice)

```
WhatsApp → Webhook → SQS → MessageProcessor
                         ├─ download media bytes
                         ├─ UI/logo reject (deterministic)
                         ├─ quality gate (deterministic)
                         ├─ save to S3 (audit + re-run)
                         └─ Claude Vision (strict JSON) → normalize → respond
                               ├─ non-photo → safe reject
                               ├─ pest_macro/low crop confidence → ask crop (buttons)
                               └─ confident case → recommendations
```

### Consequences
- **Pros**
  - Reduces judge-visible hallucinations on screenshots/logos.
  - Prevents profile-crop bias for pest macros by forcing crop selection.
  - Better UX for low-literacy users via localized buttons.
  - Clear “fail safe” behavior for low-quality images.
  - Deterministic behavior is testable and regression-resistant.

- **Cons / Caveats**
  - Some true crop photos embedded inside screenshots will be rejected (intentional conservative stance).
  - Adds a step (“which crop?”) for many macro shots (but improves correctness).
  - Requires maintaining localized crop labels as supported crops expand.

### Implementation
- Heuristics + quality gate + normalization:
  - `src/processor/analyzer.py`
  - `src/vision/analyzer.py`
- Pending state + last-image pointer (DynamoDB TTL) + interactive button parsing:
  - `src/processor/handler.py`
- Tests:
  - `tests/test_vision_quality_gate.py`
  - `tests/test_pest_macro_crop_prompt.py`
  - `tests/test_crop_button_localization.py`

### Alternatives considered
1. **Prompt-only hardening (rejected)**  
   Insufficient. LLMs can still hallucinate; judge evaluation demands deterministic safety for non-photos.

2. **Always ask crop before running Vision (rejected)**  
   Increases friction for normal leaf symptom photos where crop context is clear.

3. **Attempt to crop embedded photos from screenshots (rejected)**  
   Produced false positives and inconsistent behavior due to screenshot variability.

