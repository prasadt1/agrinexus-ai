# Architecture Diagrams

Mermaid diagrams for AgriNexus AI. Rendered on GitHub.

## High-level system

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

```mermaid
flowchart LR
    WA[WhatsApp] -->|POST body| API[API Gateway]
    API --> WH[Webhook Lambda]
    WH -->|Verify\nX-Hub-Signature-256| Verify{Valid?}
    Verify -->|No| 403[403 Forbidden]
    Verify -->|Yes| Dedup{Dedup\nWAMID?}
    Dedup -->|Duplicate| Skip[Skip]
    Dedup -->|New| Store[Store MSG\nin DynamoDB]
    Store --> Type{Message\nType?}
    Type -->|audio| VQ[Voice Queue]
    Type -->|text/image| MQ[Message Queue]
    Type -->|DONE/NOT YET| Skip
```

## Text message flow

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
    WH->>VQ: Send to Voice Queue
    VP->>WA: Download media
    VP->>S3: Upload audio
    VP->>Transcribe: Start job
    Transcribe->>VP: Transcript
    VP->>MQ: Text + _source: voice
    MQ->>Proc: Process (RAG)
    Proc->>Polly: Text-to-speech (optional)
    Proc->>WA: Text + optional audio
    WA->>U: Reply
```

## Nudge flow

```mermaid
flowchart TB
    EventBridge[EventBridge\nScheduler] --> Poll[Weather Poller\nLambda]
    Poll --> Check{Weather OK\nfor district?}
    Check -->|No| End1[End]
    Check -->|Yes| SF[Step Functions\nNudge Workflow]
    SF --> Send[Nudge Sender]
    Send --> WA[WhatsApp\nTemplate/Text]
    Send --> Sched[EventBridge\nT+24h, T+48h]
    Sched --> Remind[Reminder Sender]
    Remind --> WA
    Stream[DynamoDB Streams] --> Detector[Response Detector]
    Detector -->|DONE/NOT YET| Update[Update nudge state]
    Update --> Cancel[Cancel reminders\nif DONE]
```

## WhatsApp integration (secrets and webhook)

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
| `agrinexus/whatsapp/access-token` | Send messages via WhatsApp Cloud API |
| `agrinexus/whatsapp/phone-number-id` | Sender phone number ID |

**Webhook:** `https://<api-id>.execute-api.<region>.amazonaws.com/dev/webhook`  
- **GET:** `hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>` → return `hub.challenge`.  
- **POST:** Incoming messages; validate signature, then queue for processing.
