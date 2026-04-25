# Architecture Diagrams

Mermaid diagrams for AgriNexus AI. Rendered on GitHub. These stay **accuracy-first** (and may look plain compared to slide decks).

For slide-ready / article figures (PNG / GIF / MP4), see:
- [`../docs/diagrams/`](../docs/diagrams/)
- [`./polished/`](./polished/)

## Contents

- [System architecture (competition-style, accurate)](#system-architecture-competition-style-accurate)
- [High-level system](#high-level-system)
- [Webhook and routing](#webhook-and-routing)
- [Text message flow](#text-message-flow)
- [Voice message flow](#voice-message-flow)
- [Vision (image) flow](#vision-image-flow)
- [Nudge flow](#nudge-flow)
- [WhatsApp integration (secrets and webhook)](#whatsapp-integration-secrets-and-webhook)

## System architecture (competition-style, accurate)

Use this for slides or a single “system architecture” image. It matches the actual code: **Webhook Lambda → SQS → Processor Lambdas** for messages; **Step Functions only for nudges**; **Lambdas call WhatsApp API directly** for outbound.

```mermaid
flowchart TB
    subgraph User["User interaction"]
        Farmer[Farmer]
        WA[WhatsApp]
    end
    Farmer -->|1| WA

    subgraph AWS["AWS Cloud"]
        API[API Gateway\n/webhook]
        WH[Webhook Lambda]
        MQ[SQS Message Queue]
        VQ[SQS Voice Queue]
        Proc[Message Processor Lambda]
        VoiceProc[Voice Processor Lambda]
        DDB[(DynamoDB)]
        subgraph AI["AI services"]
            Bedrock[Bedrock\nClaude + RAG]
            KB[Knowledge Base\nS3 Vectors]
            Transcribe[Transcribe]
            Polly[Polly]
            Vision[Claude Vision]
        end
        NudgeSend[Nudge Sender Lambda]
        RemindSend[Reminder Sender Lambda]
    end

    WA -->|2 POST| API --> WH
    WH -->|3a text/image| MQ --> Proc
    WH -->|3b audio: ACK then| VQ --> VoiceProc
    VoiceProc --> Transcribe
    VoiceProc -->|transcript| MQ
    Proc --> DDB
    Proc --> Bedrock
    Proc --> KB
    Proc --> Vision
    Proc --> Polly
    WH -.->|voice ACK text| WA
    Proc -->|4 reply| WA
    NudgeSend -->|4 nudge| WA
    RemindSend -->|4 reminder| WA

    subgraph Event["Event-driven"]
        EB[EventBridge\nschedule]
        Poll[Weather Poller Lambda]
        SF[Step Functions\nnudge workflow]
        EBS[EventBridge Scheduler\nT+24h, T+48h, T+72h]
    end
    EB --> Poll --> SF --> NudgeSend
    NudgeSend -.->|create| EBS --> RemindSend
```

**Flow summary:** (1) Farmer → WhatsApp. (2) WhatsApp → API Gateway → Webhook Lambda. (3) Webhook → SQS (message or voice queue) → Message Processor or Voice Processor. For **audio**, webhook sends a short **voice-received** text (after dedup, before queue) using Secrets Manager + Graph API. **Transcribe** runs only in **Voice Processor**; Message Processor uses Bedrock RAG, Polly, Vision. (4) Processors and nudge/reminder Lambdas send replies **directly to WhatsApp Cloud API** (HTTP). Nudges: EventBridge → Weather Poller → Step Functions → Nudge Sender → WhatsApp; reminders via EventBridge Scheduler → Reminder Sender → WhatsApp.

**Demo vs full nudge loop:** New **`PROFILE`** items default to **`demo_tier: public`** — users get **one** nudge per favorable weather run, **without** T+24h/T+48h reminders. Override in DynamoDB for full scheduling.

---

## High-level system

This is the simplified “big picture” view: WhatsApp → webhook → queues → processors → Bedrock/Vision/Polly + DynamoDB; plus a separate weather→nudge workflow.

```mermaid
flowchart TB
    subgraph Farmer
        WA[WhatsApp App]
    end
    subgraph AWS
        API[API Gateway\n/webhook]
        WH[Webhook\nLambda]
        VQ[SQS Voice Queue]
        MQ[SQS Message Queue]
        Proc[Message\nProcessor]
        VoiceProc[Voice\nProcessor]
        Bedrock[Bedrock RAG]
        Vision[Claude Vision]
        Polly[Polly]
        DDB[(DynamoDB)]
        Weather[Weather Poller]
        SF[Step Functions]
        Nudge[Nudge Sender]
    end
    WA -->|POST| API --> WH
    WH -->|audio| VQ --> VoiceProc --> Proc
    WH -->|text/image| MQ --> Proc
    Proc --> Bedrock
    Proc --> Vision
    Proc --> Polly
    Proc --> DDB
    Weather --> SF --> Nudge --> WA
    Proc --> WA
```

## Webhook and routing

This diagram shows webhook validation (signature + dedup) and the routing split between audio vs text/image into separate SQS queues.

```mermaid
flowchart LR
    WA[WhatsApp] -->|POST body| API[API Gateway]
    API --> WH[Webhook Lambda]
    WH -->|Verify\nX-Hub-Signature-256| Verify{Valid?}
    Verify -->|No| 403[403 Forbidden]
    Verify -->|Yes| Dedup{Dedup\nWAMID?}
    Dedup -->|Duplicate| Skip[Skip]
    Dedup -->|New| AudioQ{Audio?}
    AudioQ -->|yes| Ack[Voice received ACK\nWhatsApp Graph API]
    Ack --> Store[Store MSG\nin DynamoDB]
    AudioQ -->|no| Store
    Store --> Type{Message\nType?}
    Type -->|audio| VQ[Voice Queue]
    Type -->|text/image| MQ[Message Queue]
    Type -->|DONE/NOT YET| Skip
```

## Text message flow

This is the text-only path: webhook → SQS → processor → Bedrock RAG → WhatsApp reply (with citations when available).

```mermaid
sequenceDiagram
    participant U as User
    participant WA as WhatsApp
    participant WH as Webhook
    participant SQS as Message Queue
    participant Proc as Processor
    participant Bedrock as Bedrock RAG
    participant DDB as DynamoDB

    U->>WA: Text message
    WA->>WH: POST /webhook
    WH->>DDB: Store (dedup)
    WH->>SQS: Send message
    WH->>WA: 200 OK
    SQS->>Proc: Invoke
    Proc->>DDB: Get profile
    Proc->>Bedrock: Retrieve + generate
    Bedrock->>Proc: Answer + citations
    Proc->>WA: Send reply
    WA->>U: Bot reply
```

## Voice message flow

This is the voice-note path: webhook ACK → voice queue → Transcribe → message queue → processor → optional Polly audio reply.

```mermaid
sequenceDiagram
    participant U as User
    participant WA as WhatsApp
    participant WH as Webhook
    participant VQ as Voice Queue
    participant VP as Voice Processor
    participant S3 as S3
    participant Transcribe as Transcribe
    participant MQ as Message Queue
    participant Proc as Processor
    participant Polly as Polly

    U->>WA: Voice note
    WA->>WH: POST (audio ref)
    WH->>WA: Voice received ACK (after dedup)
    WH->>VQ: Send to Voice Queue
    VP->>WA: Download media (Graph)
    VP->>S3: Upload audio
    VP->>Transcribe: Start job
    Transcribe->>VP: Transcript
    VP->>MQ: Text + _source: voice
    MQ->>Proc: Process (RAG)
    Proc->>Polly: Text-to-speech (optional)
    Proc->>WA: Text + optional audio
    WA->>U: Reply
```

## Vision (image) flow

This is the **image path** through the production pipeline: WhatsApp image → webhook → SQS → processor → **Pillow heuristics** → **optional Bedrock Haiku relevance gate** → optional quality gate → **S3 audit save** → **Claude Sonnet Vision (JSON)** → optional **crop confirm** (only if relevance was confident agri) or **`enforce_message_safety()`** → WhatsApp. Toggle: `VISION_RELEVANCE_GATE_ENABLED` (default on). See [ADR 0010](../docs/adr/0010-vision-relevance-gate-before-diagnosis.md).

```mermaid
sequenceDiagram
    participant U as User
    participant WA as WhatsApp
    participant WH as Webhook
    participant SQS as MessageQueue
    participant Proc as MessageProcessor
    participant Heur as Heuristics<br/>(Pillow)
    participant Rel as Relevance<br/>(Haiku JSON)
    participant QG as QualityGate
    participant S3 as S3 temp images
    participant V as Claude Vision<br/>(Sonnet JSON)
    participant Enf as Enforcement
    participant DDB as DynamoDB

    U->>WA: Send crop/pest photo
    WA->>WH: POST /webhook (image)
    WH->>DDB: Store MSG#* (detector + audit)
    WH->>SQS: Enqueue message
    WH->>WA: 200 OK

    SQS->>Proc: Invoke
    Proc->>WA: Download media (Graph API)
    Proc->>Heur: run_heuristics(image_bytes)
    alt Heuristics block (screenshot/logo/etc.)
        Heur-->>Proc: decision=block
        Proc->>WA: Block message (localized)
    else Heuristics pass
        Note over Proc,Rel: If VISION_RELEVANCE_GATE_ENABLED
        Proc->>Rel: classify_image_relevance()
        alt Confident not_agri
            Rel-->>Proc: not_agri (high/medium)
            Proc->>WA: Generic non-agri message
        else Unclear + not photo-like (heuristic tie-break)
            Rel-->>Proc: unclear + low greens/palette
            Proc->>WA: Retake / clearer photo
        else Proceed toward diagnosis
            Proc->>QG: optional quality gate (dims/bytes)
            alt Quality gate fails
                QG-->>Proc: unacceptable
                Proc->>S3: Save image (audit)
                Proc->>WA: Retake / too small
            else Quality OK or gate off
                Proc->>S3: Save image (audit)
                Proc->>V: analyze_crop_image() JSON
                V-->>Proc: vision_result
                alt Ambiguous crop + relevance was agri_photo (high/medium)
                    Proc->>WA: Crop confirm + pending_crop_confirm
                else Normal reply
                    Proc->>Enf: enforce_message_safety()
                    Enf-->>Proc: safe final message
                    Proc->>WA: Structured diagnosis / template
                end
            end
        end
    end
```

**Notes:** (1) **Relevance gate off** (`VISION_RELEVANCE_GATE_ENABLED=false`): skip `Rel` — flow is heuristics → QG → S3 → Vision → enforcement/crop confirm rules without the agri-photo prerequisite for crop confirm. (2) **Crop reconfirm** after user reply is handled in `handler.py` (S3 re-fetch + `analyze_crop_image` with chosen crop); not shown above. (3) **Handler** also parses Hindi/English yes-phrases so “हाँ वही है” retriggers vision instead of RAG.

## Nudge flow

This is the closed-loop nudge path: weather poll (rate: 6 hours) → Step Functions → nudge send → Scheduler reminders (T+24h/T+48h/T+72h) → DONE/NOT YET detection via DynamoDB Streams.

```mermaid
flowchart TB
    EventBridge["EventBridge\nSchedule (rate: 6 hours)"] --> Poll[Weather Poller\nLambda]
    Poll --> Check{Weather OK\nfor district?}
    Check -->|No| End1[End]
    Check -->|Yes| SF[Step Functions\nNudge Workflow]
    SF --> Send[Nudge Sender]
    Send --> WA[WhatsApp\nTemplate/Text]
    Send --> Sched[EventBridge Scheduler\nT+24h, T+48h, T+72h]
    Sched --> Remind[Reminder Sender]
    Remind --> WA
    Stream[DynamoDB Streams] --> Detector[Response Detector]
    Detector -->|DONE| UpdateDone[Status: DONE\nCancel schedules]
    Detector -->|NOT YET after T+48h| UpdateExpired[Status: EXPIRED\nCancel schedules]
    Detector -->|NOT YET before T+48h| Ack[Acknowledge\nKeep schedules]
    Sched -->|T+72h no response| AutoExpire[Auto-expire\nStatus: EXPIRED]
```

## WhatsApp integration (secrets and webhook)

This diagram shows where WhatsApp secrets live (Secrets Manager) and how the webhook/processor use them to verify signatures and send outbound messages via Meta’s Cloud API.

```mermaid
flowchart LR
    subgraph Meta
        MetaAPI[Meta WhatsApp API]
    end
    subgraph AWS
        Secrets[Secrets Manager]
        WH[Webhook Lambda]
        API[API Gateway]
    end
    MetaAPI -->|POST events| API
    API --> WH
    WH -->|verify_token| Secrets
    WH -->|app_secret\nX-Hub-Signature-256| Secrets
    WH -->|access_token\nphone_number_id| Secrets
    WH -->|Send messages| MetaAPI
```

**Secrets (Secrets Manager):**

| Secret name | Purpose |
|-------------|---------|
| `agrinexus/whatsapp/verify-token` | GET webhook verification (hub.verify_token) |
| `agrinexus/whatsapp/app-secret` | HMAC signature verification (X-Hub-Signature-256) |
| `agrinexus/whatsapp/access-token` | Send messages via WhatsApp Cloud API (processor, nudge, **webhook** voice ACK) |
| `agrinexus/whatsapp/phone-number-id` | Sender phone number ID |

The **webhook** Lambda uses the Common layer and these two secrets to send the **voice-received** text for inbound audio (after dedup; see `src/webhook/handler.py`).

**Webhook:** `https://<api-id>.execute-api.<region>.amazonaws.com/dev/webhook`  
- **GET:** `hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>` → return `hub.challenge`.  
- **POST:** Incoming messages; validate signature, then queue for processing.
