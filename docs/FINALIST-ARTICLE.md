# AIdeas Finalist: AgriNexus AI

**Category:** Social Impact

---

## My Vision

More than 100 million smallholder farmers in India face the same structural gap: agronomic knowledge exists in ICAR bulletins and FAO manuals, but it rarely reaches a farmer like Ramesh—in Marathi or Telugu, at the moment he is standing in the field, with a decision window measured in days, not weeks.

**AgriNexus AI** is a fully serverless **WhatsApp** assistant that closes that last mile. There is no new app to install. A farmer can send **text**, a **voice note**, or a **photo of a sick leaf** and receive cited, actionable guidance powered by **Amazon Bedrock** (RAG, Claude, vision). On top of Q&A, AgriNexus runs a **closed-loop nudge engine**: when spray weather is suitable, it sends a crop-specific reminder, waits for a **“done”** confirmation, and follows up at T+24h and T+48h until the loop closes or the farmer opts out.

This finalist build is not a rewrite of the idea—it is the same architecture judges responded to in round one, with **deliberate improvements** driven by judge feedback (real weather data, faster voice turnaround, and a cost model that can survive a pilot).

The design assumption throughout is **low literacy–friendly UX**: WhatsApp **list messages** and **reply buttons** for onboarding, so even a farmer uncomfortable typing in Devanagari can complete profiling in under two minutes. That accessibility choice is inseparable from the AI stack—if the channel were a web form, the same farmer would never arrive at the model.

---

## Why This Matters

### Scale and stakes

- **100M+** smallholder farmers in India; **1:1,000+** extension ratio in many districts  
- **30–40%** crop loss to pests and diseases; **$15–20B** annual economic impact  
- **10,000+** farmer suicides a year—crop failure and debt remain intertwined with rural distress  

**WhatsApp** is already on the phone. Voice is how many farmers already communicate with family and traders. Meeting them there removes adoption friction that sinks standalone apps.

### The behavior gap (why “information” is not enough)

Most advisory systems optimize for **correct answers**. Smallholders optimize for **timely action** under cash and labor constraints. A spray recommendation that arrives **after** the wind picks up, or **in English** when the farmer thinks in Marathi, behaves like “no advice” in practice. AgriNexus therefore pairs **retrieval-grounded answers** with **stateful nudges**: the system does not only say *what* to do—it creates a **time-bounded window** (weather consent, duplicate suppression, T+24h/T+48h follow-ups) aligned with how decisions are actually made in the field.

### How I see the competitive landscape

There are credible agricultural AI products—**Farmer.Chat**, **iSDA Virtual Agronomist**, **AgriChat.AI**, **WeatherInbox**, and others. Most excel at **information delivery**. Few close the loop on **whether the farmer actually acted**, and fewer still combine **multimodal** access (voice + vision + text) with **weather-timed** nudges and **verified** confirmation on WhatsApp.

| Capability | Typical ag-AI chat | AgriNexus AI |
|------------|-------------------|--------------|
| WhatsApp-first | Often | Yes |
| Voice in + Polly voice out | Rare | Yes (hi / mr / te / en-IN dialects) |
| Vision (pest / leaf) | Sometimes | Yes (Claude multimodal) |
| Behavioral nudge engine | Rare | Yes |
| Closed-loop “done” + reminders | **No** | **Yes** |
| Weather-aware spray window | Partial | Yes (current conditions + consent) |

The differentiation is not “another LLM.” It is **outcomes-oriented design**: advice **plus** accountability—implemented with **SQS FIFO**, **Step Functions**, **EventBridge Scheduler**, and **DynamoDB Streams** so the system scales like software, not like a call center.

---

## How I Built This

### Serverless architecture (high level)

- **Ingress:** API Gateway → **WebhookHandler** (HMAC, idempotency) → **SQS FIFO** / voice queue  
- **Core:** **MessageProcessor** — onboarding state machine (language → district → crop → nudge consent), Bedrock **retrieve_and_generate** for RAG, Polly for voice replies, Claude **vision** for images  
- **Voice:** **VoiceProcessor** — media to S3 → **Amazon Transcribe** (batch) → transcript re-queued into the same RAG path  
- **Nudges:** **WeatherPoller** (scheduled) → **Step Functions** → **NudgeSender** → WhatsApp; **ResponseDetector** on **DynamoDB Streams** cancels **EventBridge Scheduler** reminders when “done” keywords appear  

**Ordering and scale:** **SQS FIFO** gives per-phone message ordering—critical when a farmer sends voice then text. **DynamoDB** uses a **single-table** design: profiles, idempotency keys (`MSG#…`), and nudge state live in one place with GSIs for location-based weather targeting. That keeps Lambda functions small and avoids scatter-gun SQL or multi-table transactions for what is fundamentally an **event-driven** workload.

**Why not long Step Functions waits?** Holding a state machine open for 48 hours would be expensive at scale. The nudge workflow **schedules** delayed work with **EventBridge Scheduler** and tears those schedules down when the farmer taps **done**—so AWS bills reflect **short** executions, not **days-long** ones.

### Knowledge and vectors

Round-one documentation referenced **OpenSearch Serverless** as the vector store. For sustainable economics—and after fixed OpenSearch cost dominated early bills—I moved the Bedrock Knowledge Base to **Amazon S3 Vectors** as the backing store. Retrieval remains real **RAG** (same `retrieve_and_generate` integration); query latency on the vector leg is on the order of **100–300ms**, which is negligible compared to LLM generation in an **async** WhatsApp interaction.

At **10,000 active farmers**, modeled monthly cost lands near **~$450** (Bedrock + S3 Vectors + Transcribe + Polly + minor Lambda/S3/Dynamo) — about **$0.54 per farmer per year** at that scale—better than the **~$0.70** figure tied to the older OpenSearch-heavy stack.

### Weather (judge feedback #1)

The **WeatherPoller** now calls **OpenWeatherMap** for **current** conditions at district coordinates (Latur, Jalna, Nagpur). A spray window is **favorable** when **wind &lt; 10 km/h** and **no recent rain** in the API payload. If the API key is missing or the call fails, the code **logs the reason** and falls back to mock data so demos stay reliable—production deployments should always pass a valid key.

### Voice latency (judge feedback #2)

Voice remains **batch Transcribe** (the right trade for an MVP), but the poller now **checks job status immediately** once after `StartTranscriptionJob`, then uses **adaptive sleeps** (1s, then 2s). That reduces **time-to-reply** versus a naive fixed 3s poll—without claiming “streaming” latency the stack does not provide.

### Methodology

Requirements were captured in **EARS**; implementation was accelerated with **Kiro**-assisted spec-to-code. The discipline of explicit requirements kept the architecture stable while iterating on nudge copy and multimodal paths.

### Security and operations

Outbound WhatsApp traffic uses **Secrets Manager**–backed credentials with short-lived caching in Lambda. The webhook path validates **Meta HMAC** signatures (configurable for dev). None of this is glamorous in a demo video, but it is what makes the same codebase safe to **expose on the public internet**—a prerequisite for any real pilot with NGOs or government partners.

---

## Demo

Embed your **under-three-minute** YouTube video here in AWS Builder Center (**Insert YouTube embed**).

**Suggested flow:** onboarding → text RAG question → short voice note → pest image → nudge + DONE (use labeled demo weather if live nudges are rare).

**Recording checklist:** [docs/DEMO-RECORDING.md](../DEMO-RECORDING.md)

**Placeholder link (replace with your video):** `https://www.youtube.com/watch?v=YOUR_VIDEO_ID`

---

## What I Learned

### Which judge feedback mattered most

1. **“Weather API is mock data.”**  
   I integrated **OpenWeatherMap** with explicit **logging** when the system falls back to mock data, and documented deployment so **production** uses a real key. I also aligned messaging with the implementation: **current** weather and a **&lt; 10 km/h** wind gate—not a vague “forecast” claim the MVP does not yet implement.

2. **“Batch transcription — 20–34s latency.”**  
   I did not pretend WhatsApp delivers **streaming STT** overnight. I **optimized polling** (immediate first status check + adaptive intervals) to shorten the **observed** wait for typical 5–15s voice notes, and I treat **Transcribe Streaming** as a **Phase 2** research item if pilots justify the architecture.

### Cost and research

**OpenSearch Serverless** taught me a lesson about **fixed** infrastructure on a **variable** pilot: the bill stayed high even when usage was low. Moving vectors to **S3 Vectors** restored **real RAG** at a **pay-per-use** curve that matches social-impact budgets.

I am transparent about numbers: modeled costs depend on **embedding refresh**, **query volume**, and **Bedrock token** usage. The right takeaway for readers is directional: **eliminate always-on search OCUs** before you scale users, or the economics stop being “social impact” and start being “venture burn.”

### Research literacy (not medical claims)

Vision outputs include **pest names, confidence, severity, and safety caveats** grounded in prompts that cite institutional sources where possible. The product is positioned as **decision support**, not a replacement for local extension officers or regulated pesticide guidance—another lesson from building in a **high-stakes** domain.

### Product insights

- **Voice is the interface**, not a checkbox—especially for Devanagari typing on low-end phones.  
- **Closed-loop nudges** are what people remember: follow-up until confirmation differentiates “chatbot” from “extension agent behavior.”  
- **Honesty in the write-up matters**: judges and voters reward **specific** improvements over buzzwords.

---

### Resources

- **GitHub:** https://github.com/prasadt1/agrinexus-ai  
- **KB sources (examples):** FAO cotton/IPM materials, ICAR-CICR pest advisories, NIPHM cotton advisory, PAU package of practices  
- **KB rebuild (S3 Vectors):** [REBUILD-KB-WITH-S3-VECTORS.md](../REBUILD-KB-WITH-S3-VECTORS.md) · `scripts/rebuild-kb-s3-vectors.sh`

---

**Tags:** `#aideas-2025` `#aideas-2025-finalist` `#social-impact` `#APJC`

*Amazon Bedrock (Knowledge Bases, Claude), Amazon Transcribe, Amazon Polly, AWS Lambda, DynamoDB, SQS, Step Functions, EventBridge Scheduler, WhatsApp Business API. Built with EARS requirements and Kiro-assisted development.*
