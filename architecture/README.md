# Architecture

Diagrams and high-level design for AgriNexus AI.

## Contents

- **[Diagrams](diagrams.md)** – Mermaid diagrams: high-level system, message flows (text / voice / image), webhook, and nudge flow.
- **Polished article diagrams (PNG)** – Higher-fidelity, slide-ready diagrams:
  - **Overall stack**: [`docs/diagrams/builder-full-architecture.png`](../docs/diagrams/builder-full-architecture.png)
  - **Nudge loop**: [`docs/diagrams/builder-nudge-flow.png`](../docs/diagrams/builder-nudge-flow.png) 
  - **Text / Voice / Vision flows**: [`architecture/polished/`](./polished/)
- **Full architecture doc**: [`docs/architecture.md`](../docs/architecture.md) (components, data model, security, cost).

## Quick reference

| Flow        | Path |
|------------|------|
| Text query | WhatsApp → Webhook → SQS → Processor → Bedrock RAG → WhatsApp |
| Voice      | WhatsApp → Webhook → **voice ACK text** → Voice Queue → Voice Processor (Transcribe) → message queue → Processor → RAG → Polly → WhatsApp |
| Image      | WhatsApp → Webhook → SQS → Processor → Claude Vision → WhatsApp |
| Nudge      | Weather Poller → Step Functions → Nudge Sender → WhatsApp; reminders via EventBridge Scheduler (reminders **off** when `PROFILE.demo_tier == public`) |

**Onboarding districts** (code): **Latur**, **Jalna**, **Nagpur** (`src/processor/handler.py`).

**Profiles:** **`demo_tier: public`** (default) = single nudge for public demos; change in Dynamo for full reminder loop.
