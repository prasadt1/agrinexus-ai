# Architecture Diagram Corrections

This doc clarifies how the **AgriNexus AI** system actually works so you can fix or redraw the "AgriNexus AI System Architecture" diagram to match the codebase.

---

## What the current diagram gets wrong

| Diagram element | Current (wrong) | Actual behavior |
|----------------|-----------------|------------------|
| **Inbound path** | WhatsApp → API Gateway → **Step Functions** | WhatsApp → API Gateway → **Webhook Lambda** → **SQS** (message queue or voice queue) → **Message Processor Lambda** or **Voice Processor Lambda**. Step Functions is **not** in the path for incoming messages. |
| **Orchestrator** | Step Functions as central orchestrator for every message | Step Functions is used **only for the nudge flow**. Message handling is: Webhook Lambda → SQS → Processor Lambdas. |
| **RAG / AI** | "Flow 5. RAG Query" from **Step Functions** to AI layer | RAG (Bedrock Knowledge Base + Claude) is called by the **Message Processor Lambda** and **Voice Processor Lambda**, not by Step Functions. |
| **Outbound to WhatsApp** | "Flow 8. Send Notification" via **SQS/API Gateway** | Processor Lambdas, Nudge Sender, Reminder Sender, and Response Detector call the **WhatsApp Cloud API directly** (HTTP to `graph.facebook.com`) from inside Lambda. There is no SQS or API Gateway for outbound messages. |
| **Event-driven layer** | "Schedule Nudge" from Business Logic to EventBridge Scheduler | **Weather Poller Lambda** (triggered by EventBridge schedule) → **Step Functions** (nudge workflow) → **Nudge Sender Lambda** → WhatsApp. Separately, **EventBridge Scheduler** (one-time T+24h/T+48h) → **Reminder Sender Lambda** → WhatsApp. |

---

## Correct high-level flow

### Inbound (farmer sends a message)

1. **Farmer** → **WhatsApp**
2. **WhatsApp** → **API Gateway** (webhook POST)
3. **API Gateway** → **Webhook Lambda** (signature check, dedup in DynamoDB, store MSG for response detector)
4. **Webhook Lambda** → **SQS**  
   - **Audio** → Voice Queue → **Voice Processor Lambda** (Transcribe → S3 → then enqueue text to Message Queue → Message Processor does RAG/Polly)  
   - **Text/Image** (and not DONE/NOT YET) → Message Queue → **Message Processor Lambda**
5. **Message Processor** / **Voice Processor**: read DynamoDB (profile), call **Bedrock** (RAG + Claude), **Transcribe** (voice in), **Polly** (voice out), **Claude Vision** (images), **S3** (KB + temp audio)
6. **Message Processor** / **Voice Processor** → **WhatsApp Cloud API** (direct HTTP) → **WhatsApp** → Farmer

### Nudge path (no farmer message)

1. **EventBridge** (scheduled rule, e.g. every 6h) → **Weather Poller Lambda**
2. **Weather Poller** → **Step Functions** (nudge workflow)
3. **Step Functions** → **Nudge Sender Lambda** → **WhatsApp Cloud API** → Farmer
4. Nudge Sender also creates **EventBridge Scheduler** one-time schedules for T+24h, T+48h
5. **EventBridge Scheduler** (at T+24h/T+48h) → **Reminder Sender Lambda** → **WhatsApp Cloud API** → Farmer

### DONE/NOT YET (no SQS for these)

- Webhook does **not** enqueue DONE/NOT YET messages. It writes the message to **DynamoDB**.
- **DynamoDB Streams** → **Response Detector Lambda** → updates nudge state, sends acknowledgment, cancels reminders if DONE → **WhatsApp Cloud API** (direct).

---

## Suggested diagram changes

1. **Replace "API Gateway → Step Functions"** with **API Gateway → Webhook Lambda → SQS** (two queues: Message Queue, Voice Queue).
2. **Show two consumer Lambdas:** Message Processor (text/image), Voice Processor (audio); both use Bedrock, DynamoDB, and (for voice) Transcribe/Polly.
3. **Draw RAG/AI flows from the Processor Lambdas** to the AI layer (Bedrock, Knowledge Base, Transcribe, Polly, Vision), not from Step Functions.
4. **Outbound:** Label as **Processor / Nudge / Reminder Lambdas → WhatsApp Cloud API (HTTP)**, not "SQS/API Gateway."
5. **Event-driven:** Show **EventBridge (schedule) → Weather Poller → Step Functions → Nudge Sender → WhatsApp**; optionally **EventBridge Scheduler → Reminder Sender → WhatsApp**.

An accurate Mermaid version of the system architecture is in [architecture/diagrams.md](../architecture/diagrams.md) under **"System architecture (competition-style)"**. You can use that to redraw the diagram or export an image from a Mermaid renderer.
