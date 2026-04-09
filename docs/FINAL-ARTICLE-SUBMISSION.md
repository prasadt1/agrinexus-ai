# AIdeas Finalist: AgriNexus AI

**Category:** Social Impact · **Status:** Top 50 Finalist (selected from 300 semi-finalists)

> **Vote April 17–23, 2026** — Community voting on AWS Builder Center. If this project resonates, [**vote here**](https://builder.aws.com/content/39qTnLaOki9b8RyT8MXOrg7Fns6) and help it reach the finish line.

---

*Before publish: replace the cover image, embed your real YouTube link, and add a thumbnail.*

![Cover image — replace before publish](cover-image.png)

---

## Demo Video

**Watch AgriNexus AI in action — text, voice, vision, and closed-loop nudges on WhatsApp:**

[![AgriNexus AI Demo — replace thumbnail](video-thumbnail.png)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)

*Under 3 minutes — portrait is fine. Replace `YOUR_VIDEO_ID` with your real upload.*

---

Growing up in India, I saw smallholders lose cotton to pests they couldn’t name in time — and neighbors with no one to ask between field and market, watching leaves yellow while the spray window closed.

The knowledge to save those crops exists: India’s [Indian Council of Agricultural Research](https://icar.org.in/) (ICAR) bulletins cover pink bollworm; [Food and Agriculture Organization](https://www.fao.org/) (FAO) manuals cover spray timing and wind. Too much of it stays in offices and universities — not with the farmer in the field.

**AgriNexus AI** closes that last-mile gap.

---

## My Vision

**App Category:** Social Impact

Meet Ramesh. He grows cotton in Latur, Maharashtra. Three days ago, he noticed something wrong with his leaves. He asked the village agronomist, who visits once a month. He searched online, but results came back in English. Meanwhile, pink bollworm is spreading. The spray window is closing.

This is the daily reality for **100+ million smallholder farmers** across India. The ratio of extension agents to farmers can exceed 1:5,000 in some districts. The information exists — the failure is the *last mile*.

**AgriNexus AI** is a fully serverless WhatsApp assistant that bridges that gap:

- **No app to download** — WhatsApp is already on hundreds of millions of phones in India
- **No English required** — Hindi, Marathi, Telugu, with natural Hinglish support
- **Three input modes** — text, voice note, or photo of a sick leaf
- **Text and voice Q&A** — retrieval-grounded answers from ingested extension-style documents, with **visible citations** when the pipeline returns them
- **Photo analysis** — Claude Vision returns a **structured** diagnosis (severity, safety, recommendations in the farmer’s language). That path is **not** the same as KB retrieval; **document citations** are the story for **typed** RAG

But here's what makes AgriNexus different from every other agricultural AI chatbot: **the closed-loop nudge engine**.

When weather conditions are optimal for spraying (wind under 10 km/h, no rain), AgriNexus sends a crop-specific reminder at 7 AM. It doesn't just deliver advice — it waits for Ramesh's "हो गया" (*done*) confirmation, and follows up at T+24h and T+48h until the loop closes or he opts out.

**Most advisory systems optimize for correct answers. Farmers optimize for timely action.** AgriNexus is not a chatbot — it's a behavior-change engine.

---

## Why This Matters

### The Stakes

The scale of this problem is staggering:
- **Roughly 30–40%** crop losses to pests and diseases appear in **global** plant-health summaries ([Food and Agriculture Organization](https://www.fao.org/) / [International Plant Protection Convention](https://www.ippc.int/)–style aggregate figures) — **directional**, not the same for every crop or season
- **Extension staffing** in rainfed areas is often far **wider** than government **norms** (commentary and literature cite **1:5,000+** farmers per worker in places; norms are often nearer **1:750–1,100** — terrain and reporting vary)
- **Cotton:** press and **Cotton Advisory Board–style** figures show **severe stress** in the belt (pink bollworm, production swings) — treat headline percentages as **source-dependent**

### The Know-Do Gap

Behavioral economics research (Thaler & Sunstein, 2008) shows that information alone doesn't change behavior — the gap between *knowing* what to do and *actually doing it* is where crop losses happen.

A spray recommendation that arrives **after** the wind picks up, or **in English** when the farmer thinks in Marathi, behaves like "no advice" in practice. The timing matters as much as the content.

AgriNexus addresses this fundamental gap with:
- **Weather-aware timing** — nudges fire when conditions are actually favorable for spraying
- **Native language delivery** — advice in the farmer's dialect, not translated corporate Hindi
- **Closed-loop accountability** — follow-up until confirmed action, not just message delivery

### Competitive Landscape

Peers vs AgriNexus. **Vendor pages:** [Farmer.Chat](https://farmer.chat/), [iSDA Virtual Agronomist](https://www.isda-africa.com/virtual-agronomist), [AgriChat.AI](https://www.agrichat.ai/), [Weather Impact](https://www.weatherimpact.com/chatbot/) (Uliza-WI). *(Standard markdown links in paragraphs usually work; the same syntax inside table headers often does not.)* Table columns 2–5 follow the same order.

Cost @ 10K: last row.

| Capability | Farmer.Chat | iSDA Virtual Agronomist | AgriChat.AI | Weather Impact (Uliza-WI) | AgriNexus AI |
|------------|---------------|-------------------------|---------------|-----------------------------|----------------|
| Multi-lingual text | Yes | No | No | Partial | Yes |
| **Voice in + out** | No | No | No | No | **Yes** (4 dialects) |
| **Photo → structured advice** | Yes | Yes | Yes | Partial | **Yes** (Claude Vision) |
| **Behavioral nudge engine** (crop + timing) | No | No | No | No | **Yes** |
| **Closed-loop DONE + T+24h/T+48h** | No | No | No | No | **Yes** |
| **Weather-linked farm alerts** | Partial | Partial | Yes | Yes | **Yes** (spray-window nudges) |
| **Cost / farmer @ 10K (modeled)** | Not public | Not public | Not public | Not public | **~$0.54/year** |

**Bold** = main gaps vs peers. Infra: SQS FIFO, Step Functions, EventBridge Scheduler, DynamoDB Streams. *Directional.*

---

## How I Built This

### Architecture Overview

AgriNexus is 100% serverless on AWS, designed with EARS requirements methodology (100+ traceable requirements) and built using Kiro AI.

**[Architecture diagram — add your diagram or link before publish]**
*Full serverless architecture: API Gateway → Lambda → Bedrock → WhatsApp*

**Core Stack:**
- **Messaging:** WhatsApp Business API + API Gateway
- **Intelligence:** Amazon Bedrock (Claude 3 Sonnet RAG + Vision)
- **Knowledge Base:** Bedrock Knowledge Bases with **S3 Vectors**
- **Voice:** Amazon Transcribe (hi-IN, mr-IN, te-IN, en-IN) + Amazon Polly
- **Nudge Engine:** EventBridge Scheduler + Step Functions + DynamoDB Streams
- **Storage:** DynamoDB single-table design + S3

### Four Flows, One Pipeline

**1. Text RAG:** Farmer sends Hindi question → WebhookHandler validates HMAC → SQS FIFO → MessageProcessor retrieves profile → Bedrock **retrieve_and_generate** with citations → WhatsApp reply (typically on the order of **a few seconds** end-to-end).

**2. Voice:** OGG audio → S3 → Amazon Transcribe (batch with adaptive polling) → transcript re-queued → **same RAG pipeline** → Polly TTS + text reply.

**3. Vision:** Crop photo → Claude Vision → **structured** diagnosis (what it might be, confidence, severity, safety, recommendations in dialect). **No** Knowledge Base citation line in the current vision UI — that’s the **text RAG** path.

**4. Nudge Loop:** WeatherPoller checks OpenWeatherMap → if wind < 10 km/h, no rain → Step Functions starts → NudgeSender delivers crop-specific message with buttons → EventBridge Scheduler creates T+24h/T+48h reminders → ResponseDetector on DynamoDB Streams cancels reminders when "done" detected. Nudge copy points farmers to **local [Krishi Vigyan Kendra](https://icar.org.in/en/krishi-vigyan-kendras) (KVK) / dealer** for scouting and products; **district helpline** snippets can also append on certain **RAG** replies (e.g. purchase-style questions).

**[WhatsApp screenshots — add before publish]**
*Example: onboarding (language/district/crop) · nudge with Done / Not now buttons*

### Key Architecture Decision

**Why EventBridge Scheduler, not Step Functions Wait States?**

Keeping a state machine open for 48 hours would be expensive at scale. Instead, the nudge workflow completes in seconds, creating EventBridge Scheduler targets for delayed reminders. When Ramesh responds, ResponseDetector deletes those schedules. AWS bills reflect short executions, not days-long ones.

### Security

All WhatsApp credentials are stored in **AWS Secrets Manager** with IAM role-based access per Lambda. The webhook validates **Meta HMAC-SHA256 signatures** on every incoming message. No secrets in environment variables, no secrets in code — the same codebase is safe to expose on the public internet, a prerequisite for any real pilot with NGOs or government partners.

### Cost at Scale

Moving from OpenSearch Serverless to **S3 Vectors** was a critical optimization. OpenSearch's always-on OCU costs dominated early bills regardless of query volume. S3 Vectors provides true pay-per-use economics.

At **10,000 active farmers**, modeled cost is **~$450/month** — approximately **$0.54 per farmer per year**. That's an economic model NGOs and government agricultural departments can sustain at scale.

---

## What I Learned

### Addressing Judge Feedback

**1. "Weather API is mock data"**

Integrated **OpenWeatherMap** for real-time current conditions at district coordinates (Latur, Jalna, Nagpur). The API key is stored in **AWS Secrets Manager** — never in code or environment variables. The system logs explicitly when falling back to mock data for demos.

**2. "Batch transcription latency (20-34s)"**

I did not pretend WhatsApp delivers streaming STT overnight. **Adaptive polling** after `StartTranscriptionJob` (immediate check, then 1s → 2s) cuts wait for typical 5–15s notes. Transcribe Streaming stays Phase 2 if pilots justify it.

**3. "Cost model sustainability"**

The **S3 Vectors** migration eliminated always-on OpenSearch OCU costs. At 10K farmers, per-farmer cost dropped from ~$0.70/year (OpenSearch) to **~$0.54/year** — better economics for social impact deployment.

### New Capabilities Since Semi-Finals

- **Production WhatsApp Business number** — real number working end-to-end, not just test sandbox
- **Voice messaging E2E** — full pipeline operational with production number
- **Contextual nudges** — copy references **[KVK](https://icar.org.in/en/krishi-vigyan-kendras) (Krishi Vigyan Kendra) / dealer** for scouting and compliant purchases; district **helpline** footers on relevant **RAG** answers when the question is purchase-style
- **Optional Haiku nudge liner** — when `NUDGE_BEDROCK_LINER` is enabled, a **single** Bedrock **scouting** sentence can augment the first nudge line (still **not** KB RAG)

### Development Insights

**Voice is the interface, not a feature.** Devanagari typing on basic phones is painful; voice notes match how farmers already talk to traders and family. WhatsApp’s India footprint removes “install another app” friction.

**Closed-loop nudges are what people remember.** Every competitor stops at information delivery. The T+24h/T+48h follow-up chain with "done" confirmation is what differentiates a chatbot from an extension agent's behavior. It's also what judges noticed as genuinely novel.

**Code-switching just works.** Farmers naturally mix scripts: "Mere cotton mein pests hain." Rather than over-engineer language detection, I let Claude handle what it's trained for. Hinglish flows through without special handling.

**Behavior > Intelligence.** The AI quality matters, but the nudge architecture — when to send, how to follow up, when to stop — is what converts advice into action. That's the real innovation. Any team can deploy Claude; few have built the behavioral scaffolding around it.

**WhatsApp interactive buttons increase accessibility.** List messages and reply buttons let farmers finish onboarding in under two minutes without comfortable Devanagari typing — the channel is part of the product, not a wrapper.

### Beyond Agriculture

The nudge stack (trigger → **done** → follow-up) is **not crop-specific** — health, finance, or anywhere **timing + accountability** matter. RAG/vision are vertical; roadmap = **triggers** + partner copy.

---

## Try It Yourself

Want to test AgriNexus AI on WhatsApp?

📩 **Request demo access:** [Open a GitHub issue](https://github.com/prasadt1/agrinexus-ai/issues/new?template=demo-request.md) — the template asks for **WhatsApp number** (for allowlisting), **email** (recommended), and context. I’ll add you within ~24 hours. *(Public issues are visible; see template note if you prefer a private channel.)*

**What you can try:**
- Send "Namaste" to start onboarding (Hindi, Marathi, Telugu, English)
- Ask a farming question — get cited RAG response
- Send a crop photo — get structured diagnosis
- Send a voice note — hear the answer spoken back

**Demo limits:** Text-only for public demo tier. Voice/vision enabled for pilot partners and serious evaluators.

*Your number is used only for this demo. No data shared or retained beyond 7 days.*

---

## Vote for AgriNexus AI

**Community voting runs April 17–23, 2026.**

If you believe in closing the last mile for smallholder farmers — advice **plus** accountability, in their language, on the phone they already have — please vote:

1. Visit the [AgriNexus AI article on AWS Builder Center](https://builder.aws.com/content/39qTnLaOki9b8RyT8MXOrg7Fns6)
2. Click the **Vote** button
3. Share with others who care about agricultural impact

The technology to help 100M+ farmers already exists. AgriNexus is proof the last mile problem is solvable today.

---

**GitHub:** https://github.com/prasadt1/agrinexus-ai

---

**Tags:** `#aideas-2025` `#aideas-2025-finalist` `#social-impact` `#APJC`

*Built with Amazon Bedrock (Knowledge Bases with S3 Vectors, Claude), Amazon Transcribe, Amazon Polly, AWS Lambda, DynamoDB, SQS FIFO, Step Functions, EventBridge Scheduler, DynamoDB Streams, WhatsApp Business API. Developed using EARS requirements methodology and Kiro AI.*
