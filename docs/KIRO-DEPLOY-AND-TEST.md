# Handoff: deploy and test recent AgriNexus changes (AWS)

Give this document to Kiro (or any operator) to **build, deploy, and verify** the codebase changes on AWS. Active SAM template: **`template-week2.yaml`**. Config: **`samconfig-week2.toml`**. Region: **`us-east-1`** (unless you changed it).

---

## 1. What changed (summary)

| Area | Change |
|------|--------|
| **Weather** | OpenWeatherMap integration; `MOCK_WEATHER` / `WEATHER_API_KEY`; logging on fallback; **districts: Latur, Jalna, Nagpur** (Aurangabad removed). |
| **Voice** | Adaptive polling + immediate first `GetTranscriptionJob`; **WhatsApp ack** after job starts (“message received, preparing reply…” in hi/mr/te/en). |
| **Processor** | Onboarding districts **Latur / Jalna / Nagpur**; coords for Latur. |
| **Secrets / WhatsApp** | Still `agrinexus/whatsapp/*` — **new business number** = update **`phone-number-id`** + **`access-token`** in Secrets Manager (see `docs/WHATSAPP-PRODUCTION-NUMBER-CUTOVER.md`). |
| **Bedrock RAG** | Knowledge Base ID in `samconfig-week2.toml` (example: `ARZ4XQEBCU`) — **confirm** yours in Bedrock console. |
| **Docs** | Cutover, voice Phase 2 plan, finalist article draft, weather testing, etc. |

---

## 2. Prerequisites

- [ ] AWS CLI configured (`aws sts get-caller-identity` works).
- [ ] **SAM CLI** installed (`sam --version`).
- [ ] Python 3.11 (matches Lambda runtime) for local `sam build` / `pytest`.
- [ ] Repo at latest `main` (or your release branch) with all merges.

---

## 3. Configure deploy parameters

Edit **`samconfig-week2.toml`** (or pass overrides on the CLI):

| Parameter | Purpose |
|-----------|---------|
| `Environment` | e.g. `dev` → Lambda names `agrinexus-*-dev`. |
| `TableName` | DynamoDB table (e.g. `agrinexus-data`). |
| `KnowledgeBaseId` | Bedrock KB ID from console (must match S3 Vectors KB you ingested). |
| `WeatherApiKey` | OpenWeatherMap API key for **real** weather (use `""` only if you will set key via Console after deploy). |
| `TableStreamArn` | Required by template for Response Detector — must match your table’s stream ARN. |
| Other params | As in `template-week2.yaml` / existing `samconfig`. |

**Important:** If `WeatherApiKey` is empty, the weather Lambda **falls back to mock** data (see `src/weather/handler.py`). For **production demos**, set a real key at deploy or in Lambda env after deploy.

---

## 4. Build and deploy

From the **repository root**:

```bash
cd /path/to/Agri-Nexus\ AI\ Project

# Clean build (recommended after many file changes)
sam build --template template-week2.yaml

# Deploy using saved config
sam deploy --config-file samconfig-week2.toml
```

If **`sam deploy`** fails on parameters, compare **`template-week2.yaml`** `Parameters` section with **`samconfig-week2.toml`** `parameter_overrides` and add any missing required values (e.g. `TableStreamArn`, `WeatherApiKey`).

**Functions this stack updates** (names use `Environment`, e.g. `dev`):

- `agrinexus-webhook-<env>`
- `agrinexus-processor-<env>`
- `agrinexus-voice-<env>`
- `agrinexus-weather-<env>`
- `agrinexus-nudge-sender-<env>`, `agrinexus-reminder-<env>`, `agrinexus-response-detector-<env>`, `agrinexus-dlq-<env>`, etc.

**Common layer:** `agrinexus-common-<env>` — must rebuild when `src/common-layer/` changes.

---

## 5. Secrets (after Meta / WhatsApp ready)

In **AWS Secrets Manager** (same names as in template):

- `agrinexus/whatsapp/access-token`
- `agrinexus/whatsapp/phone-number-id`
- `agrinexus/whatsapp/app-secret`
- `agrinexus/whatsapp/verify-token`

Update when switching to the **new** WhatsApp Business number. Full checklist: **`docs/WHATSAPP-PRODUCTION-NUMBER-CUTOVER.md`**.

Wait **~5 minutes** after secret updates (or force new invocations) so Lambda credential cache refreshes — see `CACHE_TTL_SECONDS` in `src/common-layer/python/common/whatsapp.py`.

---

## 6. Automated tests (local, against AWS where needed)

From repo root:

```bash
# Nudge unit tests (no AWS required for mocked paths)
pytest tests/test_nudge_flow.py -v

# RAG integration — requires network + AWS credentials + valid KB ID
export KNOWLEDGE_BASE_ID="<your-kb-id-same-as-samconfig>"
pytest tests/test_golden_questions.py -v -k "GQ-01"   # optional: one question first
```

Quick **RAG smoke** (replace KB ID):

```bash
export KNOWLEDGE_BASE_ID=ARZ4XQEBCU   # or your ID
python3 -c "
from tests.test_golden_questions import query_knowledge_base
r = query_knowledge_base('How to control cotton bollworm?', __import__('os').environ['KNOWLEDGE_BASE_ID'])
assert r['success'], r
print('OK', len(r.get('citations') or []), 'citations')
"
```

---

## 7. AWS smoke tests

### 7.1 Weather Lambda

```bash
aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/weather-out.json --cli-binary-format raw-in-base64-out --region us-east-1
cat /tmp/weather-out.json | python3 -m json.tool
```

Expect: **`mock_mode`** reflects `MOCK_WEATHER`; with real key and `MOCK_WEATHER=false`, **`details`** entries should show **`mock": false`** when OWM succeeds.

Tail logs:

```bash
aws logs tail /aws/lambda/agrinexus-weather-dev --since 10m --region us-east-1
```

### 7.2 Voice + processor (manual via WhatsApp)

1. Message the **business number** from a test phone.
2. Complete onboarding → choose **Latur** (or Jalna / Nagpur).
3. Send a **short voice note** → you should get **two** bot messages: **ack** (“received / preparing reply…”) then **RAG answer** (after Transcribe + processor).

Tail:

```bash
aws logs tail /aws/lambda/agrinexus-voice-dev --since 15m --region us-east-1
aws logs tail /aws/lambda/agrinexus-processor-dev --since 15m --region us-east-1
```

### 7.3 Webhook

Send a test **text** message; confirm **200** in API Gateway / Lambda and no HMAC errors if signature verification is on.

---

## 8. Data migration note (district rename)

**Aurangabad** was removed; districts are **Latur, Jalna, Nagpur**.

Existing DynamoDB users with `location` = **Aurangabad** will **not** match weather GSI / poller until profile is **updated** or user **re-onboards**. Optional: one-off script or manual `UpdateItem` to **`Latur`** if you need continuity.

---

## 9. Rollback

- Revert Git to previous tag/commit and **`sam build && sam deploy`** again, **or**
- Redeploy previous **SAM template** / parameters from backup.

Keep **Secrets Manager** backups of WhatsApp tokens **outside** git.

---

## 10. Reference files in repo

| Doc | Purpose |
|-----|---------|
| `CLAUDE.md` | Stack overview, test commands |
| `docs/WHATSAPP-PRODUCTION-NUMBER-CUTOVER.md` | New WhatsApp number |
| `WEATHER-API-SETUP.md` | OpenWeatherMap + testing |
| `docs/VOICE-LATENCY-PHASE2-PLAN.md` | Future streaming/async voice |
| `REBUILD-KB-WITH-S3-VECTORS.md` | KB / S3 Vectors |

---

## 10. One-line summary for Kiro

**“Run `sam build --template template-week2.yaml` then `sam deploy --config-file samconfig-week2.toml` with valid `KnowledgeBaseId`, `TableStreamArn`, and `WeatherApiKey`; confirm Secrets Manager WhatsApp secrets; run pytest `test_nudge_flow`, RAG smoke test with `KNOWLEDGE_BASE_ID`, then `lambda invoke` weather and manual WhatsApp voice + text; note Latur/Jalna/Nagpur only and optional user profile migration from Aurangabad.”**

---

## 11. Instructions for Kiro (after new WABA / `+49` production number)

**Context (already done by owner):** AgriNexus AI WABA; **`agrinexus/whatsapp/access-token`** = long-lived **System User** token; **`agrinexus/whatsapp/phone-number-id`** = **Phone number ID** for the German business line; **`agrinexus/whatsapp/app-secret`** matches Meta app; **`weather_nudge_spray`** templates migrated to this WABA via Graph **`migrate_message_templates`**.

**Kiro should:**

1. **Confirm deploy is current** — From repo root: `sam build --template template-week2.yaml` and `sam deploy --config-file samconfig-week2.toml` if any code or parameters changed; verify **`samconfig-week2.toml`** has **`KnowledgeBaseId`**, **`TableStreamArn`**, **`WeatherApiKey`** (or document mock-weather for demos).

2. **Secrets (read-only check)** — Do not print secrets. Confirm these **exist** in Secrets Manager **`us-east-1`**: `agrinexus/whatsapp/access-token`, `agrinexus/whatsapp/phone-number-id`, `agrinexus/whatsapp/app-secret`, `agrinexus/whatsapp/verify-token`. Owner already aligned token + phone ID with **`+49`** sender.

3. **Meta webhook** — In **developers.facebook.com** → app → **WhatsApp** → **Configuration**: Callback URL matches API Gateway **`…/dev/webhook`** (or prod path); **Verify** succeeds; **`messages`** (and any required fields) subscribed.

4. **Automated tests** — `pytest tests/test_nudge_flow.py -v`; optional RAG smoke with **`KNOWLEDGE_BASE_ID`** per §6.

5. **Lambda smoke** — `aws lambda invoke --function-name agrinexus-weather-dev --payload '{}' /tmp/weather-out.json` (see §7.1).

6. **End-to-end WhatsApp** — From a **personal/test phone**, message the **business `+49` number** (not the old `+555` test line). Complete onboarding with **Latur / Jalna / Nagpur**; test **text**, **voice note**, optional **image**. Tail **`agrinexus-webhook-dev`**, **`agrinexus-processor-dev`**, **`agrinexus-voice-dev`** (§7.2–7.3).

7. **Nudge (optional)** — If **`USE_NUDGE_TEMPLATE`** is true, trigger weather path or **`scripts/trigger-test-nudge.sh`** with **`scripts/demo.env`**; confirm template send uses **`weather_nudge_spray`** on **AgriNexus AI** WABA.

8. **DynamoDB** — If any test user still has **`Aurangabad`** as district, migrate to **Latur** or re-onboard (§8).

9. **Do not commit** **`scripts/demo.env`** (gitignored); use **`scripts/demo.env.example`** as the template.
