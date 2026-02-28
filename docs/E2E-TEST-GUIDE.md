# End-to-End Test Guide

This guide covers testing **all** AgriNexus AI functionality: onboarding, Q&A chat, voice, vision, and behavioral nudges.

## What This App Does

AgriNexus AI is a **WhatsApp agricultural advisory chatbot** for smallholder farmers:

- **Onboarding**: User picks language (Hindi, Marathi, Telugu, English), district, crop, and consents to weather-based nudges.
- **Q&A (RAG)**: Text questions are answered using a Bedrock Knowledge Base (FAO + Indian ag research). Supports 4 languages.
- **Voice**: Voice notes are transcribed (Transcribe), answered via RAG, and can get audio replies (Polly) in Hindi/Marathi/English.
- **Vision**: Crop photos are analyzed with Claude Vision for pest/disease/nutrient issues; recommendations are sent as text.
- **Nudges**: When weather is favorable, the bot sends spray reminders. User can reply **DONE** (हो गया / झाला / అయ్యింది / DONE) or **NOT YET**; reminders continue until DONE.

All compute is serverless (Lambda, DynamoDB, SQS, Step Functions, EventBridge). There is no local server; tests hit the deployed webhook and AWS services.

---

## Prerequisites

1. **Deployed stack** (e.g. `agrinexus-week2` in `dev`)  
   - API Gateway webhook URL, Lambda functions, DynamoDB table, SQS queues, Bedrock KB.

2. **Environment for scripts**
   - `WEBHOOK_URL` – Your webhook URL, e.g.  
     `https://xxxxxxxx.execute-api.us-east-1.amazonaws.com/dev/webhook`
   - `APP_SECRET` – WhatsApp app secret (for `X-Hub-Signature-256`). If verification is disabled in dev, you can omit it.
   - A **test phone number** in E.164 (e.g. `919876543210` or `4917647009148`). For voice and image tests, use a number that can send media (real WhatsApp Business numbers; test numbers often don’t support media).

3. **Recommended (no typing URL each time):** Copy the example env file and edit with your values:
   ```bash
   cp scripts/demo.env.example scripts/demo.env
   # Edit scripts/demo.env: set WEBHOOK_URL, APP_SECRET, PHONE_NUMBER
   ```
   All automated test scripts (`e2e-test.sh`, `reset-onboard-and-demo.sh`, `reset-profile.sh`, `demo-nudge-flow.sh`, etc.) **auto-load** `scripts/demo.env` when present. You can then run tests without passing env vars every time, e.g.:
   ```bash
   ./scripts/e2e-test.sh --phone +4917647009148
   # or, if PHONE_NUMBER is set in demo.env:
   ./scripts/e2e-test.sh
   ```
   `demo.env` is gitignored so secrets are not committed.

4. **AWS CLI** configured (for Lambda invoke, DynamoDB reset, and integration tests).

### Single-number testing (one WhatsApp number)

If you only have **one** test number (e.g. your own: `+4917647009148`), each onboarding creates a **user profile** in DynamoDB. To test onboarding in a **different language**, you must delete that profile first; otherwise the bot may treat you as already onboarded.

**Before each new language onboarding:**

```bash
./scripts/reset-profile.sh +4917647009148
```

If you have `PHONE_NUMBER` in `scripts/demo.env`, you can run: `./scripts/reset-profile.sh` (script uses `PHONE_NUMBER` when no argument is given—see below). For `reset-profile.sh`, the phone can also be passed as the first argument.

Then in WhatsApp send the new language keyword (हिंदी / मराठी / తెలుగు / English) and complete the four onboarding steps again. No webhook or `APP_SECRET` needed for the reset—only AWS CLI and `TABLE_NAME` (default `agrinexus-data`).

---

## 1. Onboarding

User must complete onboarding before Q&A/nudges work correctly (language and profile are stored in DynamoDB).

**Steps (by language):**

| Step   | Hindi    | Marathi  | Telugu   | English  |
|--------|----------|----------|----------|----------|
| Language | `हिंदी`  | `मराठी`  | `తెలుగు` | `English` |
| District | e.g. `Aurangabad` | same | same | same |
| Crop   | e.g. `Cotton` | same | same | same |
| Nudge consent | `Yes` / `No` | same | same | same |

**Automated:** The script `scripts/e2e-test.sh` sends these four messages for you (see below).

**Manual:** In WhatsApp, send the four messages in order; you should get a short confirmation.

---

## 2. Q&A (RAG) Chat

After onboarding, any text question (in the chosen language) is answered using the Knowledge Base.

**Examples:**
- English: `How to control cotton pests?`
- Hindi: `कपास में कीट कैसे नियंत्रित करें?`
- Help in any language: `HELP` or `मदद` / `मदत` / `సహాయం`

**Automated:** `e2e-test.sh` sends **HELP** and one sample question (e.g. cotton pest control).

**Manual:** Send any farming-related question; you should get a text reply with citations.

---

## 3. Voice

- User sends a **voice note** in WhatsApp.
- Webhook routes it to the **Voice** queue → **VoiceProcessor** (Transcribe) → text is sent to the main **Processor** (RAG) → optional **Polly** reply.
- Voice output is supported for Hindi, Marathi, and English (Telugu is text-only).

**WhatsApp limitation:** Test numbers do **not** support media. If you send a voice note from a test number, WhatsApp returns *"Media download error" (code 131052)*. Voice and image E2E over WhatsApp require a **real WhatsApp Business number**. The pipeline itself works; the restriction is on the test-number infrastructure.

### How to test voice without WhatsApp (local integration tests)

From the **repo root**, with **AWS credentials** and the **deployed stack** (S3 temp bucket, Transcribe, Bedrock):

**Option A – Transcribe only (fast)**  
Proves Amazon Transcribe works with your audio:

```bash
cd "/path/to/Agri-Nexus AI Project"
python tests/test_voice_simple.py path/to/your_audio.mp3 hi-IN
```

- Replace `path/to/your_audio.mp3` with an MP3 (or M4A converted to MP3).
- Language: `hi-IN` (Hindi), `mr-IN` (Marathi), `te-IN` (Telugu), `en-IN` (English).
- The script uploads to the dev S3 bucket, runs Transcribe, prints the transcript and confidence, then cleans up.

**Option B – Full voice pipeline (Transcribe → RAG → Polly)**  
Proves voice-in → text → Knowledge Base answer → optional audio-out:

```bash
cd "/path/to/Agri-Nexus AI Project"
python tests/test_voice_end_to_end.py path/to/your_audio.mp3 hi
```

- Args: **audio file path**, **dialect** (`hi`, `mr`, `te`, `en`).
- Runs: Transcribe → Bedrock RAG query → (optional) Polly audio; prints a URL to listen to the response. No WhatsApp involved.

**Getting a test audio file**

- Record a short question (e.g. “How to control cotton pests?” or “कपास में कीट कैसे नियंत्रित करें”) on your phone or laptop.
- Save as MP3, or convert: `ffmpeg -i recording.m4a recording.mp3`.

**Manual E2E on WhatsApp (real Business number only)**  
1. Complete onboarding (e.g. Hindi or English).  
2. Send a **voice note** asking a farming question.  
3. Expect: transcription is answered; if your language has Polly, you may get an **audio** reply.

---

## 4. Vision

- User sends a **crop image** in WhatsApp.
- Webhook sends message to Processor → **Claude Vision** analyzes image → text recommendation is sent back.

**Automated (integration only):** No WhatsApp media in scripts. Use:
- `python tests/test_vision.py path/to/crop-image.jpg en cotton`  
  This calls the vision analyzer directly (no webhook).

**Manual E2E:**  
1. Complete onboarding.  
2. Send a **photo** of a crop (e.g. cotton leaf with pest/disease).  
3. Expect: “✓ Photo received. Analyzing…” then a text diagnosis and recommendations.

---

## 5. Nudges

- **Weather poller** Lambda runs on a schedule (or is invoked manually). If weather is favorable for the user’s district, a **nudge** (spray reminder) is sent via WhatsApp.
- User replies **DONE** (or language equivalent) → completion recorded, reminders cancelled, confirmation sent.
- User replies **NOT YET** → acknowledgement; T+24h / T+48h reminders continue until DONE.

**Automated:**  
1. Run onboarding with consent `Yes`.  
2. Invoke weather poller:  
   `aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/response.json`  
3. Send **DONE** (or `हो गया` / `झाला` / `అయ్యింది`) so the loop closes.

The script `scripts/e2e-test.sh` can do onboarding + one Q&A + trigger weather + send DONE for you.

**Manual:** After triggering the poller, check WhatsApp for the nudge message; reply DONE or NOT YET and confirm the bot’s response.

---

## Running the E2E Script (Automated Part)

One script drives the **automated** E2E flow: onboarding, HELP, one text question, nudge trigger, and DONE.

```bash
# From repo root. Load demo.env if present.
WEBHOOK_URL="https://YOUR_API.execute-api.us-east-1.amazonaws.com/dev/webhook" \
APP_SECRET="YOUR_APP_SECRET" \
./scripts/e2e-test.sh --phone 919876543210
```

Optional:

- `--lang hi|mr|te|en` – onboarding language (default: `en`).
- `--no-reset` – skip DynamoDB profile reset (use existing profile).
- `--no-nudge` – skip weather poller and DONE (onboarding + Q&A only).

Examples:

```bash
# Full E2E (reset, onboard, HELP, question, nudge, DONE)
./scripts/e2e-test.sh --phone 919876543210 --lang en

# Onboarding + Q&A only (no nudge)
./scripts/e2e-test.sh --phone 919876543210 --no-nudge --no-reset
```

After the script, do **manual** checks for **voice** (send voice note) and **vision** (send image) in WhatsApp.

---

## Running Integration Tests (RAG, Voice, Vision)

These hit AWS (Bedrock, Transcribe, Polly, S3) and do **not** use WhatsApp.

```bash
# RAG (Knowledge Base)
pytest tests/test_golden_questions.py -v

# Voice (Transcribe + optional Polly)
python tests/test_voice_simple.py path/to/audio.mp3 hi-IN
# or
python tests/test_voice_end_to_end.py

# Vision (Claude Vision)
python tests/test_vision.py path/to/crop-image.jpg en cotton
```

See `AGENTS.md` for env vars (e.g. `TABLE_NAME`, `KNOWLEDGE_BASE_ID`) and expected failures (e.g. some golden-question assertions may fail due to RAG wording).

---

## E2E Checklist (All Functionality)

| Area        | Automated (script/tests)        | Manual (WhatsApp)                    |
|------------|----------------------------------|--------------------------------------|
| Onboarding | ✅ `e2e-test.sh`                 | Optional: verify in WhatsApp         |
| Q&A chat   | ✅ `e2e-test.sh` + HELP + 1 Q   | Optional: send more questions        |
| Voice      | ✅ `test_voice_*.py` (integration) | ✅ Send voice note, check reply    |
| Vision     | ✅ `test_vision.py` (integration)  | ✅ Send crop image, check reply     |
| Nudges     | ✅ `e2e-test.sh` (trigger + DONE)  | Optional: trigger poller, reply DONE/NOT YET |

Use this guide for a full end-to-end test of onboarding, nudges, vision, voice, and question/answer chat.
