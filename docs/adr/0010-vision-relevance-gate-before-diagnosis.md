# ADR 0010 — Vision relevance gate (generic non‑agri filter) + crop name localization

### Status
Accepted (2026-04-25)

### Context
The WhatsApp vision pipeline already uses a “3-layer defense” pattern (see ADR 0009):

- **Layer 1 (deterministic)**: screenshot/logo heuristics + basic quality gate before any model call.
- **Layer 2 (model)**: Claude Vision returns strict JSON schema.
- **Layer 3 (handler)**: last-mile enforcement prevents unsafe/low-confidence leakage into farmer-facing messages.

Despite deterministic heuristics, real-world inputs still include **non-agriculture images** that are not UI screenshots (e.g., mobile home screens with photo wallpaper, underwater photos, random objects). These can bypass pixel-statistics rules and accidentally flow into “crop confirmation” or diagnosis paths, causing confusing UX.

Additionally, farmer-facing prompts sometimes echoed the **profile crop in English** (e.g., “Wheat”) even when the farmer’s dialect is Hindi/Marathi/Telugu.

### Decision
Add a **generic AI relevance gate** between deterministic heuristics and the full diagnosis call:

1. **Layer 1 (deterministic, pre-model) — unchanged**
   - UI/screenshot/logo heuristics
   - Quality gate for tiny/low-byte images

2. **Layer 1.5 (AI, pre-diagnosis) — new**
   - Call a cheap/faster model to classify the image as:
     - `agri_photo` (safe to proceed to diagnosis),
     - `not_agri` (block with a generic farmer message),
     - `unclear` (fail-open to existing behavior; do not block).
   - If `not_agri` with `confidence in {high, medium}`, return a **generic “please send crop/leaf photo”** message (dialect-specific) and do **not** ask “which crop?”.
   - Fail-open on any relevance-gate error.

3. **Layer 2 (Claude Vision diagnosis) — unchanged**
   - Only invoked when Layer 1 passes and Layer 1.5 does not block.

4. **Layer 3 (last-mile enforcement) — unchanged**
   - Structured output and confidence-driven message enforcement.

Also add **profile crop name localization** for farmer-facing prompts:
- When the system asks “which crop is this?”, the “profile crop” string is localized (e.g., `Wheat → गेहूँ` for Hindi).

### Why this model
Use **Claude 3 Haiku** for the relevance gate because it is:
- Lower cost and lower latency than the full diagnosis model
- Well-suited for short, strict-JSON classification tasks

Model ID (configurable):
- Default: `us.anthropic.claude-haiku-4-5-20251001-v1:0` (stack parameter `RelevanceModelId`, passed as `VISION_RELEVANCE_MODEL_ID`)
- Override via `VISION_RELEVANCE_MODEL_ID`

**Update (2026-10-02).** Claude 3 Haiku reached end of life, so every check failed and returned `unclear`; the gate had silently stopped working. It now uses the Claude Haiku 4.5 inference profile. With the original prompt, Haiku 4.5 labelled the pink bollworm sample photo `not_agri`/`animal` with high confidence in 3 of 3 runs, which would hard-block a real crop-pest photo. The prompt now names insects, larvae, caterpillars and mites on crops as `agri_photo`, and excludes crop pests from "animals". Probed live on 8 crop and pest photos and 4 non-photos, 3 runs each: every crop and pest photo `agri_photo`/high; the logo, diagram and app screenshot `not_agri`/high; a WhatsApp screenshot containing a leaf photo `agri_photo` (the diagnosis model's own non-photo check still applies).

The relevance call carries the content guardrail. When the model answers `not_agri`, the guardrail's non-farming topic often intervenes on that output, and an intervention is read as `unclear`. In practice the gate therefore confirms farm photos and rarely hard-blocks; the diagnosis model remains the check for non-farm images.

### Architecture (relevant slice)

```
WhatsApp → Webhook → SQS → MessageProcessor
                         ├─ download media bytes
                         ├─ UI/logo reject (deterministic)
                         ├─ relevance gate (Haiku, strict JSON)   ← NEW
                         ├─ quality gate (deterministic)
                         ├─ save to S3 (audit + re-run)
                         └─ Claude Vision diagnosis (strict JSON)
                               └─ last-mile enforcement → WhatsApp reply
```

### Consequences
- **Pros**
  - Generic non-agri filtering without continuously adding bespoke heuristic rules (“home-screen-like”, “underwater-like”, etc.).
  - Reduces confusing “which crop?” prompts for clearly non-agri images.
  - Reduces wasted diagnosis calls on irrelevant images (cost + latency).
  - Improves localization quality by avoiding English crop names in non-English farmer prompts.

- **Cons / Caveats**
  - Adds an extra model call for images that pass deterministic heuristics.
  - Relevance model can still be wrong; policy is conservative:
    - Only block when `not_agri` and confidence is `high/medium`.
    - Fail-open on errors and `unclear`.

### Implementation
- Relevance gate + config:
  - `src/processor/analyzer.py`
  - env: `VISION_RELEVANCE_GATE_ENABLED` (default true), `VISION_RELEVANCE_MODEL_ID`
- Dialect-specific non-agri message + crop localization:
  - `src/processor/messages.py`
- Tests:
  - `tests/test_image_relevance_gate.py`
  - `tests/test_photo_relevance_model.py` (model ID, prompt wording, template IAM)

### Alternatives considered
1. **Add more deterministic heuristic rules** (rejected)  
   Becomes brittle and never complete; new non-agri categories will keep appearing.

2. **Use the diagnosis model for relevance** (not chosen)  
   Works but is more expensive; Haiku is sufficient for classification.

