# Architecture

Diagrams and high-level design for AgriNexus AI.

## Contents

- **[Diagrams](diagrams.md)** – Mermaid diagrams: high-level system, message flows (text / voice / image), webhook, and nudge flow.
- **Root [architecture.md](../architecture.md)** – Full architecture document (components, data model, security, cost).

## Quick reference

| Flow        | Path |
|------------|------|
| Text query | WhatsApp → Webhook → SQS → Processor → Bedrock RAG → WhatsApp |
| Voice      | WhatsApp → Webhook → Voice Queue → Transcribe → SQS → Processor → RAG → Polly → WhatsApp |
| Image      | WhatsApp → Webhook → SQS → Processor → Claude Vision → WhatsApp |
| Nudge      | Weather Poller → Step Functions → Nudge Sender → WhatsApp; reminders via EventBridge Scheduler |
