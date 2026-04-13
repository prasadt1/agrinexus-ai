# Architecture

Diagrams and high-level design for AgriNexus AI.

## Contents

- **[Diagrams](diagrams.md)** – Mermaid diagrams: high-level system, message flows (text / voice / image), webhook, and nudge flow.
- **[Polished article diagrams](../docs/diagrams/ARTICLE-POLISHED-DIAGRAM.md)** – Keynote/PowerPoint + AWS icons, optional MP4/GIF; repo Mermaid/D2 stay canonical for truth.
- **[Diagrams + Builder + Ilograph](../docs/diagrams/README.md)** – Mermaid exports as PNG; **`docs/diagrams/agrinexus.ilograph.yaml`** for Ilograph perspectives. Publish steps: [`docs/diagrams/PUBLISH-ILOGRAPH.md`](../docs/diagrams/PUBLISH-ILOGRAPH.md). Builder embed tests: [`docs/diagrams/BUILDER-EMBED.md`](../docs/diagrams/BUILDER-EMBED.md).
- **Scroll walkthrough** – [`docs/architecture-walkthrough.html`](../docs/architecture-walkthrough.html) (highlight-on-scroll paths); serve via GitHub Pages from `/docs` for HTTPS.
- **Root [architecture.md](../architecture.md)** – Full architecture document (components, data model, security, cost).

## Quick reference

| Flow        | Path |
|------------|------|
| Text query | WhatsApp → Webhook → SQS → Processor → Bedrock RAG → WhatsApp |
| Voice      | WhatsApp → Webhook → **voice ACK text** → Voice Queue → Voice Processor (Transcribe) → message queue → Processor → RAG → Polly → WhatsApp |
| Image      | WhatsApp → Webhook → SQS → Processor → Claude Vision → WhatsApp |
| Nudge      | Weather Poller → Step Functions → Nudge Sender → WhatsApp; reminders via EventBridge Scheduler (reminders **off** when `PROFILE.demo_tier == public`) |

**Onboarding districts** (code): **Latur**, **Jalna**, **Nagpur** (`src/processor/handler.py`).

**Profiles:** **`demo_tier: public`** (default) = single nudge for public demos; change in Dynamo for full reminder loop.
