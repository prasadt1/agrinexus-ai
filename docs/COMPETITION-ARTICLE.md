# AgriNexus AI: Closing the Last Mile in Agricultural Extension

**Author:** Prasad T
**Category:** Agriculture & Food Security
**GitHub:** https://github.com/prasadt1/agrinexus-ai
**Competition:** AWS Builder 10,000 AIdeas
**Reading Time:** ~10 minutes

---

## My Vision

Every year, Indian cotton farmers lose 30-40% of their crops to pests and diseases. Not because they don't know what to do — but because they don't know *when* to do it, or in which language to ask.

Meet Ramesh. He grows cotton in Aurangabad, Maharashtra. Three days ago, he noticed something wrong with his leaves — a pattern he's never seen before. He asked the village agronomist, who visits once a month. He searched online, but results came back in English. Meanwhile, his crop is getting worse. The 3-day window for bollworm treatment is closing.

This is the daily reality for **over 100 million smallholder farmers across India**. The information exists — ICAR (Indian Council of Agricultural Research) produces world-class research, FAO (Food and Agriculture Organization) manuals are comprehensive. The failure is the *last mile*: that knowledge rarely reaches Ramesh in Aurangabad, in Marathi, in time to make a difference.

**AgriNexus AI bridges that gap using WhatsApp, Amazon Bedrock, and a fully serverless AWS stack.**

No app to download. No English required. No IVR menus to navigate. Ramesh sends a voice note, a photo of a sick leaf, or a Hindi text — and gets cited, actionable advice back within seconds. When weather conditions are optimal for spraying, AgriNexus sends him a nudge at 7 AM, waits for his "हो गया" (done) confirmation, then cancels the reminder. If he doesn't respond, a follow-up arrives 24 hours later. The loop closes only when Ramesh acts.

This isn't just an app. It's a digital extension agent in every farmer's pocket — 24/7, in their language, timed to the weather.

![AgriNexus AI — bridging the last mile: from trapped research to Ramesh's WhatsApp in seconds](vision-bridging-last-mile.png)

### Why Current Solutions Fail

There are already agricultural AI tools in the market. Farmer.Chat (Digital Green), iSDA Virtual Agronomist, AgriChat.AI, WeatherInbox — all real, funded, deployed. They all share the same fundamental limitation: **they stop at information delivery.**

They tell Ramesh what to do. None of them know whether he did it.

- **Agricultural AI chatbots**: Answer questions well. No behavioral follow-up, no closed-loop confirmation, no verified action.
- **Generic apps**: One-size-fits-all advice ignores local weather, specific crops, and timing windows
- **SMS alerts**: Text-only, passive, no conversation, no follow-up
- **Call centers**: IVR (Interactive Voice Response) menus in Hindi that don't serve Marathi or Telugu speakers; limited hours; chronically under-resourced
- **YouTube videos**: Passive learning, no accountability, no personalization

The gap isn't information. It's the distance between *knowing what to do* and *actually doing it* — and every existing system leaves that gap open.

**AgriNexus closes it.**

![Closing the behavior gap — competing tools stop at information delivery; AgriNexus closes the loop only when Ramesh confirms action](behavior-gap-closed-loop.png)

WhatsApp has 500+ million users in India — it's already on every farmer's phone. No new habit to form. Ramesh already sends voice notes to family. He can use AgriNexus the same way from day one.

---

## How AgriNexus Works: A Continuous Advisory Cycle

AgriNexus operates across three interconnected stages: **Onboarding**, **Conversational Advisory**, and **Behavioral Nudges**. Together they form a closed loop — from first contact to crop protected.

### Stage 1: Onboarding & Profiling

Ramesh sends "Namaste" to the AgriNexus WhatsApp number — his first message, any greeting. No profile exists yet in DynamoDB, so the system replies with a multilingual welcome and a scrollable language **list** (WhatsApp's list message type is used here because it supports 4 options — one more than the 3-button cap on reply buttons):

```
Welcome to AgriNexus AI! 🌾

नमस्ते! AgriNexus AI में आपका स्वागत है।
नमस्कार! AgriNexus AI मध्ये आपले स्वागत आहे.
నమస్కారం! AgriNexus AI కి స్వాగతం.

Please choose your language / कृपया अपनी भाषा चुनें:
[Select Language ▼]  →  English / हिंदी / मराठी / తెలుగు
```
From there, every step uses WhatsApp **reply buttons** rendered in the farmer's chosen language and script:

| Step | AgriNexus asks (Hindi) | Farmer sees |
|---|---|---|
| Language | Multilingual welcome — all 4 languages | English / हिंदी (Hindi) / मराठी (Marathi) / తెలుగు (Telugu) |
| District | बढ़िया! आप किस जिले में हैं? *(Great! Which district are you in?)* | [औरंगाबाद] [जालना] [नागपुर] *(Aurangabad / Jalna / Nagpur)* |
| Crop | धन्यवाद! कौन सी फसल उगाते हैं? *(Thank you! Which crop do you grow?)* | [कपास] [गेहूं] [सोयाबीन] *(Cotton / Wheat / Soybean)* |
| Consent | मौसम सलाह चाहते हैं? *(Want weather-based advice?)* | [हाँ ✅] [नहीं ❌] *(Yes / No)* |
| Complete | बधाई हो! प्रोफाइल तैयार है। *(Congratulations! Profile ready. Ask any question.)* | — |

The entire state machine (`language → location → crop → consent → complete`) runs inside the **MessageProcessor** Lambda, with each state stored in DynamoDB as `onboarding_state`. No typing required at any step — a farmer who can't read can tap through buttons and be fully onboarded in under two minutes.

![AgriNexus onboarding — Ramesh's complete journey from "Namaste" to profiled user in under 2 minutes, entirely via WhatsApp taps](1.onboarding.png)

Smart shortcut: if the very first message is already a language keyword ("Hindi", "हिंदी", "mr", etc.), the system skips the welcome screen and jumps straight to district selection. Both paths handled gracefully.

Once `onboarding_complete: true` is written to DynamoDB, Ramesh is profiled: Hindi dialect, Aurangabad district, Cotton crop, nudge consent active. Every subsequent interaction — advice, nudges, reminders — is personalized against that profile.

---

### Stage 2: Conversational Advisory

Four ways to get help — all through the WhatsApp number Ramesh already has on his phone.

#### Flow 1: Text Chat

Ramesh types a question in Hindi, Hinglish, or Marathi. Within 3-5 seconds, AgriNexus responds in his language with a specific, cited answer drawn from FAO and ICAR research manuals. Not a generic tip — a response that knows he grows cotton in Aurangabad and answers accordingly.

![AgriNexus text chat — farmer sends Hindi question, gets cited advice in seconds](image-1.png)

#### Flow 2: Voice

Typing in Devanagari on a basic Android is slow. Ramesh sends a 30-second voice note instead — describing his crop symptoms in natural spoken Hindi. AgriNexus transcribes it, runs the same AI analysis as a text message, and replies with both a voice note and text. He hears the answer while walking his field.

![AgriNexus voice pipeline — voice note in, cited advice and audio reply out](image-2.png)

#### Flow 3: Vision / Image Analysis

Ramesh photographs a yellowing leaf and sends the photo. In seconds, AgriNexus returns a structured diagnosis — not a generic tip, but a specific prescription for his crop:

> **🔍 कपास बॉलवर्म (Cotton Bollworm — Helicoverpa armigera)**
> विश्वास: 87% | गंभीरता: अधिक *(Confidence: 87% | Severity: High)*
>
> **उपचार:** Chlorpyrifos 50% + Cypermethrin 5% EC *(Treatment)*
> **मात्रा:** 2ml प्रति लीटर पानी *(Dosage: 2ml per litre of water)*
> **समय:** सुबह या शाम को छिड़काव करें *(Spray in early morning or evening)*
> ⚠️ **सुरक्षा:** दस्ताने और मास्क पहनें। 48 घंटे बच्चों को दूर रखें।
> *(Wear gloves and mask. Keep children away for 48 hours.)*
>
> *Source: ICAR-CICR Pest Advisory 2024, NIPHM Cotton Advisory 2022*

No agronomist visit. No guessing from a YouTube thumbnail.

![AgriNexus vision — crop photo in, pest diagnosis and treatment plan out](image-3.png)

#### Flow 4: Nudge Loop (The Behavior-Change Engine)

AgriNexus doesn't send nudges blindly. Before any message fires, four conditions must pass: wind below 15 km/h, no rain forecast, no duplicate nudge already sent today, and confirmed farmer consent. The nudge is crop-specific — a wheat farmer gets a fungicide alert, not a generic spray reminder.

When conditions are right, at 7 AM, Ramesh receives:

> *"आज गेहूं में फफूंदनाशक स्प्रे के लिए अच्छा मौसम है। हवा 8 km/h।"*
> *(Today is good weather for fungicide spray on wheat. Wind: 8 km/h.)*
>
> **[हो गया ✓]** *(Done)* &nbsp;&nbsp; **[अभी नहीं]** *(Not now)*

He taps "हो गया" *(done)* — the system knows instantly, all pending follow-ups cancelled, loop closed. If he doesn't respond, a follow-up arrives at 24 hours, then 48 hours.

![AgriNexus nudge loop — weather-triggered nudge, T+24h follow-up, closed on confirmation](image-4.png)

**Every other agricultural advisory system in this space ends at message delivery.** AgriNexus doesn't. It follows up until Ramesh confirms. That is the structural difference between an advice bot and a behavior-change engine.

### Beyond Weather: The Nudge Engine's Future Potential

The current MVP focuses on weather-triggered spray nudges — the highest-impact, lowest-complexity starting point. But the same closed-loop architecture unlocks a much broader range of behavioral interventions:

**Market timing nudges:**
- *"मंडी में कपास का भाव आज ₹6,200/क्विंटल है। पिछले हफ्ते से 8% ऊपर। बेचने का अच्छा समय।"*  
  *(Cotton price at mandi is ₹6,200/quintal today. Up 8% from last week. Good time to sell.)*
- Trigger: Real-time mandi price API + historical price trends
- Confirmation: "बेच दिया" *(Sold)* → tracks market timing adoption

**Crop stage reminders:**
- *"आपकी गेहूं की फसल 45 दिन की हो गई। दूसरी सिंचाई का समय।"*  
  *(Your wheat crop is 45 days old. Time for second irrigation.)*
- Trigger: Planting date + crop calendar
- Confirmation: "सिंचाई हो गई" *(Irrigated)* → tracks practice adherence

**Pest outbreak alerts (area-wide):**
- *"आपके जिले में पिछले 3 दिनों में 12 किसानों ने बॉलवर्म की रिपोर्ट की। अपनी फसल जांचें।"*  
  *(12 farmers in your district reported bollworm in the last 3 days. Check your crop.)*
- Trigger: Vision analysis aggregation across region
- Confirmation: "जांच ली" *(Checked)* → early detection network effect

**Subsidy/scheme deadlines:**
- *"PM-KISAN की अगली किस्त के लिए आवेदन 15 मार्च तक। क्या आपने किया?"*  
  *(PM-KISAN next installment application deadline is March 15. Have you applied?)*
- Trigger: Government scheme calendar
- Confirmation: "आवेदन किया" *(Applied)* → increases benefit uptake

**Soil health reminders:**
- *"पिछली बार मिट्टी परीक्षण 18 महीने पहले हुआ था। हर 2 साल में जांच जरूरी।"*
  *(Last soil test was 18 months ago. Testing every 2 years is essential.)*
- Trigger: Profile history + best practice intervals
- Confirmation: "टेस्ट बुक किया" *(Test booked)* → long-term soil management

**Gamification — rewards for responsiveness:**
- *"🏆 रामेश जी, आपने लगातार 5 सलाहों पर काम किया! आप 'AgriNexus Champion' हैं। अगले महीने मंडी भाव अलर्ट सबसे पहले मिलेगा।"*
  *(Ramesh, you acted on 5 consecutive advisories! You are an AgriNexus Champion. Next month's mandi price alerts will reach you first.)*
- Trigger: Consecutive "हो गया" confirmations tracked in DynamoDB — 3, 5, 10 streak milestones
- Confirmation: Intrinsic — the reward IS the next nudge arriving earlier / priority access to scheme alerts
- Why it works: Behavioral economics shows that variable reward schedules (not fixed) drive the strongest habit formation. Ramesh isn't earning points — he's earning faster, more relevant information. The incentive is perfectly aligned with the outcome.

The architecture is already built for this. Each nudge type needs:
1. A trigger condition (weather API, price API, crop calendar, aggregated data)
2. A message template in the farmer's language
3. A confirmation keyword for closed-loop tracking

The MVP proves the pattern works. The roadmap is about expanding the trigger library — not rebuilding the engine.

---

## Why This Matters

### The Numbers

- **100+ million** smallholder farmers in India
- **1:1,000+** extension agent-to-farmer ratio in many districts
- **30-40%** annual crop loss to pests and diseases
- **$15-20 billion** economic impact per year
- **10,000+** farmer suicides annually — debt from crop loss is a leading driver

### What Changes for Ramesh

| Scenario | Before AgriNexus | With AgriNexus |
|---|---|---|
| Pest advice | Wait for monthly agronomist visit | Instant RAG response with cited sources |
| Spray timing | Fixed calendar, regardless of weather | Nudge fires when wind < 15 km/h |
| Language | English/Hindi IVR | Native Hindi, Marathi, or Telugu |
| Accountability | None | Closed-loop DONE confirmation |
| **Crop loss** | **35%** | **~15%** |
| **Season income** | Baseline | **+Rs. 30,000 (~$360)** |


![Practice adoption impact — farmer outcomes before and after AgriNexus](image-7.png)


Scale that to 1,000 farmers: **Rs. 30 million ($360,000) additional income per season.**

### How AgriNexus Compares to Existing Solutions

There are well-funded, deployed agricultural AI systems in India and globally. Here is an honest comparison:

| Capability | Farmer.Chat | iSDA Agronomist | AgriChat.AI | AgriNexus AI |
|---|---|---|---|---|
| AI-powered Q&A | Yes | Yes | Yes | Yes |
| WhatsApp delivery | Partial | Yes | Yes | Yes |
| Multi-lingual text | Yes | No | No | Yes |
| **Voice input + output** | No | No | No | **Yes** |
| **Behavioral nudge engine** | No | No | No | **Yes** |
| **Closed-loop DONE confirmation** | No | No | No | **Yes** |
| **Weather-triggered proactive alerts** | No | Partial | Yes | **Yes** |
| **Verified practice adoption** | No | No | No | **Yes** |
| **Cost per farmer at scale** | Not public | Not public | Not public | **<$0.70/year** |

The top row is roughly even. Everything below it is unique to AgriNexus. The compound advantage — voice-first accessibility, weather-triggered nudges, and closed-loop behavioral tracking together — is not replicable by adding a single feature to a competitor. It requires a fundamentally different architecture and a different philosophy: **outcomes, not information.**

### Why Behavioral Nudges Work

Thaler and Sunstein's nudge theory (Nobel Prize 2017) is clear: timing matters. The right advice at the wrong time produces no action. AgriNexus's weather-triggered nudges align with farmer decision-making precisely when conditions are optimal — and the closed-loop accountability ("हो गया" — *done*) is what turns advice into behavior change, not just information delivery.

Extension agents are chronically under-resourced: one agent for 800-1,000 farmers in many districts. AgriNexus doesn't replace them — it scales their reach. One agent managing the system serves thousands of farmers simultaneously, with consistent advice, in their language, at the right moment.

---

## How I Built This

### The Stack

AgriNexus is fully serverless on AWS, designed with EARS (Easy Approach to Requirements Syntax) methodology (100+ traceable requirements) and built using Kiro AI (spec-to-code):

| Layer | Technology |
|---|---|
| Messaging | WhatsApp Business API + API Gateway |
| Intelligence | Amazon Bedrock (Claude 3 Sonnet) + RAG |
| Knowledge Base | Bedrock Knowledge Bases + OpenSearch Serverless |
| Voice In | Amazon Transcribe (hi-IN, mr-IN, te-IN, en-IN) |
| Voice Out | Amazon Polly (Aditi/Kajal neural voices) |
| Vision | Claude 3 Sonnet multimodal |
| Nudge Engine | EventBridge Scheduler + Step Functions + DynamoDB Streams |
| Storage | DynamoDB single-table + S3 |
| Orchestration | AWS SAM, Lambda (Python 3.11) |

![AgriNexus serverless architecture on AWS](<Architecture Diagram - Overall Serverless System Architecture-1.png>)

---

### Foundation: Onboarding State Machine

Before any of the four flows are accessible, Ramesh completes onboarding — a five-state machine (`language → location → crop → consent → complete`) running entirely inside MessageProcessor Lambda. No typing required at any step: language selection uses a WhatsApp list message (supports 4 options — one more than the 3-button reply cap), every subsequent step uses reply buttons rendered in the farmer's chosen script, and the complete profile is written to DynamoDB in under two minutes. Every downstream interaction — RAG responses, nudge targeting, Polly voice selection — is personalised against this profile.

![AgriNexus onboarding state machine — language, district, crop, consent states with DynamoDB profile output](onboarding-diagram.png)

---

### How Each Flow Traverses the Architecture

The four flows share common infrastructure — one API Gateway, one WebhookHandler Lambda, one MessageProcessor Lambda — but route differently depending on message type. Each diagram below traces a complete closed-loop round-trip: from Ramesh's phone into AWS and back.

#### Flow 1: Text Chat
![AgriNexus text chat — API Gateway through Bedrock RAG to WhatsApp reply](<Architecture Diagram - Text.png>)

```
① Ramesh sends Hindi text via WhatsApp
② API Gateway receives HTTPS POST
③ WebhookHandler Lambda validates HMAC-SHA256 signature, checks DynamoDB idempotency (wamid)
④ Message queued to SQS FIFO (per-phone deduplication)
⑤ MessageProcessor Lambda retrieves farmer profile from DynamoDB
⑥ Bedrock Knowledge Base queried with RAG (FAO + ICAR manuals)
⑦ Retrieved context + farmer profile passed to Claude 3 Sonnet
⑧ Claude generates response in farmer's dialect with source citations
⑨ WhatsApp Business API delivers text reply to Ramesh
```

#### Flow 2: Voice
![AgriNexus voice pipeline — WhatsApp audio through Transcribe, re-queued to RAG, Polly TTS reply](<Architecture Diagram - Voice.png>)

```
① Ramesh sends OGG/OPUS voice note via WhatsApp
② API Gateway → WebhookHandler detects media type, routes to Voice Queue (SQS FIFO)
③ VoiceProcessor Lambda downloads audio from WhatsApp media servers
④ Audio file stored temporarily in S3
⑤ Amazon Transcribe job launched (dialect-matched: hi-IN, mr-IN, te-IN, en-IN)
⑥ Transcribed text returned from Transcribe
⑦ Transcript re-queued to MessageProcessor (same RAG pipeline as text)
⑧ Claude 3 Sonnet generates response
⑨ Amazon Polly converts response to speech (Aditi/Kajal neural voices)
⑩ Ramesh receives both audio reply and text (for reference)
```

#### Flow 3: Vision / Image Analysis
![AgriNexus vision flow — crop photo through Claude Vision to pest diagnosis reply](<Architecture Diagram - Vision.png>)

```
① Ramesh photographs a diseased leaf and sends it via WhatsApp
② API Gateway → WebhookHandler detects image media type
③ MessageProcessor Lambda downloads image from WhatsApp media servers
④ Image re-uploaded to S3 with temporary public URL
⑤ S3 URL + agronomic system prompt sent to Claude 3 Sonnet Vision
⑥ Claude identifies pest/disease, confidence level, severity
⑦ Response includes: identification, recommended pesticide, dosage, application timing, safety warning
⑧ Reply delivered to Ramesh; S3 image cleaned up
```

#### Flow 4: Nudge Loop — Behavioral Engine
![AgriNexus nudge loop — weather-triggered closed-loop behavioral engine with DONE confirmation](<Architecture Diagram - Nudge Flow.png>)

```
① EventBridge Scheduler triggers WeatherPoller Lambda daily at 7 AM
② WeatherPoller checks conditions: wind speed, rain forecast, temperature
③ If wind < 15 km/h and no rain: Step Functions nudge workflow starts
④ Step Functions queries DynamoDB for farmers by region + crop + nudge consent
   (also checks: no nudge already sent today — duplicate prevention)
⑤ NudgeSender Lambda sends WhatsApp message with crop-specific nudge + interactive buttons:
   "आज गेहूं में फफूंदनाशक स्प्रे के लिए अच्छा मौसम है। हवा 8 km/h। [हो गया] [अभी नहीं]"
   (Today is good weather for fungicide spray on wheat. Wind: 8 km/h. [Done ✓] [Not now])
⑥ EventBridge Scheduler records T+24h and T+48h reminder targets
⑦ [If no response] ReminderSender Lambda fires at T+24h with follow-up
⑧ [If no response] ReminderSender fires again at T+48h — final reminder
⑨ Ramesh taps "हो गया" (done)
⑩ DynamoDB Streams triggers ResponseDetector Lambda
⑪ ResponseDetector detects DONE keyword (हो गया / झाला / అయ్యింది / DONE)
   (done in Hindi / Marathi / Telugu)
⑫ Pending T+48h schedules deleted from EventBridge; nudge marked COMPLETED in DynamoDB
```

Flow 4 is the only flow with no human-initiated trigger. Flows 1–3 wait for Ramesh to ask a question. Flow 4 proactively finds him — at 7 AM, when conditions are right — and doesn't close until he confirms he acted.

---

### Key Architecture Decisions

Five decisions shaped the system. They fall into two themes: how data flows and persists, and how the AI handles human language.

#### Data & Orchestration

**1. Single-Table DynamoDB Design**

One table handles user profiles, message idempotency, and nudge tracking. Composite keys (`PK=USER#<phone>`, `SK=PROFILE|MSG#<timestamp>|NUDGE#<id>`) with GSI (Global Secondary Index) indexes for region-based targeting. The access patterns were defined before the schema was designed — that discipline is the only reason it works cleanly at query time.

**2. EventBridge Scheduler Instead of Step Functions Wait States**

Keeping a Step Functions execution alive for 72 hours to fire T+24h/T+48h reminders would be expensive at scale — state transition costs accumulate fast. Instead: Step Functions workflow completes in seconds, creating EventBridge Scheduler targets for each reminder. When Ramesh responds, ResponseDetector deletes those schedules. Event-driven cleanup, no long-running executions.

**3. DynamoDB Streams for Real-Time Response Detection**

Real-time "हो गया" detection without polling. The stream triggers ResponseDetector Lambda, which checks for DONE keywords across all supported languages, updates status, and cancels pending reminders. Reactive architecture that scales linearly with message volume.


![EventBridge Scheduler vs Step Functions Wait States](<Step function vs Event Scheduler-1.jpg>)


---

#### AI & Language

**4. Code-Switching (Hinglish) Support**

Farmers naturally mix scripts: "Mere cotton mein pests hain." Script detection (Devanagari/Telugu/Latin) handles routing, but Claude 3 Sonnet handles the linguistic nuance. The lesson: don't over-engineer language detection — let the model handle what it's trained for.

**5. Voice Latency Trade-off**

Current batch transcription adds 20-34 seconds of latency. Acceptable for async WhatsApp — farmers aren't expecting sub-second voice responses. Post-MVP will migrate to Amazon Transcribe Streaming (<2s). Ship the MVP first; optimize based on actual user feedback, not speculation.

![Hinglish code-switching handling and voice latency roadmap](Code-switching-voice-latency-1.jpg)


---

### Technical Challenges Solved

| Challenge | Solution |
|---|---|
| Duplicate WhatsApp deliveries (race condition) | Conditional DynamoDB put with `wamid` as idempotency key |
| Long-wait Step Functions at scale | EventBridge Scheduler pattern: short-lived execution + scheduled targets |
| Multi-language prompt inconsistency | Language-specific system prompts + explicit output format instructions |
| Nudge duplicate prevention | Query for existing pending nudges before creating new ones |
| Orphaned reminder schedules after completion | DynamoDB Streams triggers cleanup on DONE detection |
| S3 temporary image access for Vision | Bucket policy + public access block settings in SAM template |

### How Kiro and EARS Shaped the Build

I used Kiro AI throughout: EARS requirements → auto-generated design specs → code stubs → iterative deployment. The EARS format produced requirements like:

- *"WHEN a farmer sends a voice note, the system SHALL transcribe it using Amazon Transcribe in the farmer's registered dialect and process it identically to a text message."*
- *"WHEN wind speed exceeds 15 km/h, the system SHALL NOT send a spray nudge."*
- *"WHERE the farmer's crop is wheat, the nudge message SHALL reference fungicide, not generic 'spray'."*

100+ structured requirements made architecture decisions obvious — each requirement mapped directly to a Lambda, a DynamoDB pattern, or an EventBridge rule. EARS prevented scope creep; Kiro generated SAM boilerplate. The hardest work was business logic, not scaffolding.

![EARS requirement mapped directly to deployed Lambda code](image.png)

---

## The Build Journey: Week by Week

AgriNexus went from zero to a production-deployed, end-to-end system in four weeks. Here's how each week stacked.

![AgriNexus 4-week build timeline](timeline.jpg)

### Week 1 — Intelligence First

**Milestone 1: RAG Foundation**

The first question I had to answer: can a RAG system grounded in FAO and ICAR PDFs actually give a farmer useful, accurate advice? Before writing any WhatsApp integration code, I loaded the knowledge base — FAO (Food and Agriculture Organization) cotton production manuals, ICAR-CICR (Indian Council of Agricultural Research – Central Institute for Cotton Research) pest advisories, NIPHM (National Institute of Plant Health Management) guidelines — and ran golden question tests. Iterating on chunking strategy and prompt structure got RAG accuracy to 95% on the test set. Every response includes source citations; without them, there's no way to catch a hallucination.

*Challenge:* RAG retrieval quality varied dramatically by query phrasing.
*Solution:* Prompt refinement + knowledge base chunking optimization until retrieval was consistent across query types.

**Milestone 2: Multi-Lingual Support**

Language-first onboarding wasn't an afterthought — it was the first user interaction designed. Hindi, Marathi, Telugu, English — each with dialect-aware response templates and code-switching detection for Hinglish ("Mere cotton mein pests hain"). Amazon Polly voices matched to language: Aditi for Hindi/Marathi, Kajal for English.

*Challenge:* Telugu has no native Amazon Polly voice.
*Solution:* Text-only responses for Telugu users — documented limitation, not a hidden gap.

---

### Week 2 — Multi-Modal Pipelines

**Milestone 3: Voice Pipeline**

Voice went from add-on to primary interface once I tested it with real inputs. The pipeline: OGG audio from WhatsApp → S3 → Amazon Transcribe (dialect-matched) → transcript re-queued to the same RAG pipeline as text → Claude 3 Sonnet response → Amazon Polly neural TTS → audio + text reply back to WhatsApp. An end-to-end voice testing suite validated the full round-trip.

*Challenge:* Batch transcription latency of 20-34 seconds.
*Solution:* Documented as an acceptable MVP trade-off for async WhatsApp; roadmap includes Transcribe Streaming for <2s. Ship first, optimize with real user feedback.

**Milestone 4: Vision / Image Analysis**

Farmers can send a photo of a diseased leaf and get a diagnosis. The pipeline: image downloaded from WhatsApp media servers → re-uploaded to S3 → S3 URL + agronomic system prompt sent to Claude 3 Sonnet Vision → pest/disease identification with confidence level, recommended pesticide, dosage, and application timing. Achieved 85%+ confidence on test images across cotton bollworm, leaf curl, and spider mite cases.

*Challenge:* S3 temporary public access configuration for Vision API image URLs.
*Solution:* Explicit bucket policy + public access block settings in the SAM CloudFormation template.

---

### Week 3 — The Nudge Engine

**Milestone 5: Behavioral Nudge Engine**

The core innovation. WeatherPoller Lambda runs daily at 7 AM via EventBridge Scheduler, checks wind speed and rain forecast, and if conditions are right, starts a Step Functions nudge workflow. The workflow queries DynamoDB for eligible farmers by region + crop + consent status, then NudgeSender fires a crop-specific WhatsApp message with interactive buttons.

*Challenge:* Step Functions Wait states for T+24h/T+48h reminders kept executions alive for days — expensive and messy at scale.
*Solution:* Short-lived Step Functions (completes in seconds) + EventBridge Scheduler targets for each reminder. Cleaner, cheaper, scalable.

**Milestone 6: Closed-Loop Accountability**

The nudge loop only closes when the farmer acts. ResponseDetector Lambda listens on DynamoDB Streams for DONE keywords across all languages (हो गया *(done, Hindi)* / झाला *(done, Marathi)* / అయ్యింది *(done, Telugu)* / DONE). On detection: pending EventBridge Scheduler targets deleted, nudge marked COMPLETED. A T+72h timeout handler marks non-responders as `no_response` for analytics. CloudWatch custom metrics — NudgesSent, NudgesCompleted — track completion rates from day one.

*Challenge:* Race condition from duplicate WhatsApp message delivery.
*Solution:* Idempotency check — conditional DynamoDB put using WhatsApp's `wamid` as a unique key. First write wins, duplicates rejected.

---

### Week 4 — Testing, Hardening, Deployment

**Milestone 7: Testing & Validation**

A full E2E test suite covering onboarding, text Q&A, voice round-trip, vision analysis, and the nudge flow. Golden question tests (100+ agricultural queries across crops and languages). Integration tests for all AWS services. Demo scripts for multi-language testing with real phone numbers.

*Challenge:* WhatsApp test numbers don't support media messages (voice/image).
*Solution:* Documented as a hard requirement — real WhatsApp Business number needed for full E2E testing.

**Milestone 8: Production Deployment**

Deployed with AWS SAM (Serverless Application Model, `template-week2.yaml`), WhatsApp webhook configured with HMAC-SHA256 signature verification, CloudWatch dashboard with custom metrics live, deployment runbooks written.

*Challenge:* Secrets management for WhatsApp credentials (access token, app secret, phone number ID, verify token).
*Solution:* AWS Secrets Manager with IAM role-based access per Lambda — no secrets in environment variables, no secrets in code.

---

Four weeks. Eight milestones. One end-to-end system live on WhatsApp.

---

## Performance & Cost

### System Metrics

| Metric | Value |
|---|---|
| API response time | 3-5 seconds (p95, including Bedrock) |
| Lambda cold start | <2 seconds (Python 3.11) |
| RAG accuracy | 95% on golden question test set |
| Vision confidence | 85%+ on pest identification |
| Voice transcription accuracy | 87%+ (Hindi/English) |
| DynamoDB query latency | <10ms |

### Cost for 1,000 Active Farmers/Month

**Fixed infrastructure (always-on):**

| Service | Monthly Cost | Notes |
|---|---|---|
| OpenSearch Serverless (Bedrock Knowledge Base) | ~$174 | Minimum 0.5 OCU × 2 at $0.24/OCU-hr; always-on regardless of query volume |

**Variable costs (~3,000 queries + 500 voice minutes/month across 1,000 farmers):**

| Service | Monthly Cost |
|---|---|
| Amazon Bedrock (Claude 3 Sonnet — RAG + Vision) | ~$25 |
| Amazon Transcribe (~500 voice minutes at $0.024/min) | ~$12 |
| Amazon Polly (neural TTS voice replies) | ~$1 |
| Amazon DynamoDB (on-demand) | ~$1 |
| Amazon EventBridge Scheduler | ~$1 |
| API Gateway, SQS, Step Functions, S3, Lambda | ~$0 (free tier / minimal) |
| WhatsApp Business API | ~$0 (first 1,000 conversations/month free) |
| **Variable total** | **~$40/month** |

| | |
|---|---|
| **Total (fixed + variable)** | **~$214/month** |

OpenSearch Serverless is the dominant cost — it's always-on infrastructure, not pay-per-query. The key insight is that this fixed cost amortizes sharply with scale.

![AgriNexus cost breakdown — $214/month for 1,000 active farmers, dominated by fixed OpenSearch infrastructure](image-6.png)

At **10,000 farmers**, fixed infrastructure stays at ~$174/month while variable costs scale to ~$400/month — total ~$574/month, or **under $0.70/farmer/year**. Serverless isn't just an engineering choice — it's the economic model that makes this viable for NGO (Non-Governmental Organization) and government deployment at scale.

> **Cost optimization path:** Replacing OpenSearch Serverless with Aurora PostgreSQL + pgvector or Pinecone free tier reduces the fixed floor to near-zero, bringing 1,000-farmer cost down to ~$40/month for teams with cost constraints.

### MVP Built Within Competition Budget

The complete AgriNexus MVP — all four flows deployed to production, end-to-end tested — was built within the AWS Builder 10,000 AIdeas competition budget:

| Resource | Amount | Used for |
|---|---|---|
| AWS Credits | $200 | All AWS infrastructure: Lambda, Bedrock, Transcribe, Polly, DynamoDB, SQS, EventBridge, Step Functions, OpenSearch Serverless, API Gateway, S3 |
| Kiro Credits | 2,000 (Pro+ equivalent) | Spec-to-code: EARS requirements → design specs → Lambda stubs → SAM templates |

Building a production-deployed, multi-modal, serverless AI system on $200 of AWS credits was possible because of three decisions: architecture-first (define access patterns before writing code), test early and tear down (OpenSearch Serverless is expensive when idle — spin up for testing, evaluate costs, tear down), and Kiro eliminated boilerplate so credits went to actual service invocations, not iteration cycles.

---

## What I Learned

![6 things AgriNexus taught me — builder insights from 4 weeks of serverless AI on AWS](what-i-learned.png)

**Voice is the interface, not a feature.**
When I first built AgriNexus, voice was an add-on. Testing changed my thinking. Typing in Devanagari on a basic Android phone is slow and error-prone. Sending a voice note is natural — it's what farmers already do to communicate. Voice needs to be the *primary* interface, not a bonus feature.

**Behavioral nudges require closed loops.**
Sending a spray reminder is easy. Knowing whether it worked is hard — and it matters. The T+24h/T+48h reminder chain with interactive DONE/NOT YET buttons came from thinking about what actually changes behavior. An advice bot is useful; a behavior-change loop is transformative.

**Crop-specific context builds trust.**
Early nudges said "spray करने के लिए" (time to spray). Farmers found it vague. When the message said "गेहूं में फफूंदनाशक" (fungicide for wheat) — specific to their crop — engagement increased immediately. Context is credibility.

**Prompt engineering is iterative, not one-shot.**
Initial prompts produced ~60% accuracy. Structured prompts with explicit format instructions and language-specific system messages reached 95%. Treat the AI as a collaborator that needs clear instructions — not a magic oracle.

**Event-driven architecture beats polling.**
DynamoDB Streams for DONE detection, EventBridge Scheduler for delayed reminders, SQS for async processing — events scale better than polling loops. Embrace async patterns from day one.

**Serverless economics work for social impact.**
The full stack runs ~$214/month for 1,000 active farmers — 81% of that is fixed OpenSearch Serverless infrastructure that barely moves as you add users. At 10,000 farmers, total cost reaches ~$574/month, or under $0.70/farmer/year. Serverless isn't just a deployment choice here — it's the economic model that makes this viable for NGOs and government programs.

**Kiro + EARS accelerated everything.**
Writing requirements in EARS format before touching code sounds slow. It was actually the fastest path. Clear requirements eliminated rework, prevented gold-plating, and made architecture decisions obvious. The hardest work became business logic — not boilerplate.

---

## What's Next
![AgriNexus product roadmap](<Next Steps.jpg>)

**Immediate (next 30 days):**
- Real weather API integration (IMD — India Meteorological Department / Open-Meteo) replacing mock data
- Expanded knowledge base: maize and soybean disease corpus
- Market price queries (mandi prices from public APIs) — conversational first, nudges later
- SMS fallback for farmers without WhatsApp data access
- Amazon Transcribe Streaming migration for <2s voice latency

**Medium-term (3-6 months):**
- Pilot with 2-3 NGOs in Maharashtra and Telangana (target: 500 farmers)
- **Expanded nudge triggers:** market timing alerts, crop stage reminders, area-wide pest outbreak warnings
- Group broadcast for extension agents (one agent to 50 farmers in a village)
- Seasonal calendar: pre-emptive advice by crop stage and historical patterns
- Analytics dashboard: nudge completion rates by region/crop, pest outbreak detection
- Gamification: streak rewards and priority access for farmers who consistently act on nudges

**Long-term:**
- Government integration: state agricultural department helpline routing
- IoT: soil moisture sensors triggering irrigation nudges
- Yield tracking: closed-loop from advice to action to outcome
- Expansion to Bangladesh and sub-Saharan Africa (same last-mile problem)
- Goal: 15-20% crop loss reduction across 1 million farmers

---

## Final Thought

The technology to help Ramesh already exists. Amazon Bedrock provides world-class AI. WhatsApp provides distribution at 500 million users. Serverless AWS provides economics that NGOs and governments can sustain. The only thing missing was putting them together in a way that actually reached the farmer — in Hindi, at 7 AM, when the wind is low and the conditions are right.

AgriNexus is proof that the last mile problem is solvable today.

![The last mile problem is solvable today — AgriNexus AI](final-cta.png)

![Vote for AgriNexus AI — your vote helps this reach 100M+ smallholder farmers in India](vote-cta-card.png)

---

### Resources

- **GitHub:** https://github.com/prasadt1/agrinexus-ai
- **Knowledge Base Sources:** FAO Cotton Production Manual, FAO IPM (Integrated Pest Management) Guide, ICAR-CICR Pest Advisory 2024, NIPHM Cotton Advisory 2022, PAU (Punjab Agricultural University) Package of Practices (Kharif 2024)

---

*Built with Kiro AI, EARS requirements methodology, Amazon Bedrock (Claude 3 Sonnet, Transcribe, Polly, Bedrock Knowledge Bases), AWS Lambda, DynamoDB, EventBridge Scheduler, Step Functions, SQS FIFO, and WhatsApp Business API.*
