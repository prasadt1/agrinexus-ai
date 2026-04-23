# Frankfurt AI Meetup Talk Package (April 2026)
**Talk title**: Building with AI Without Being an AI Expert: What Vibe Coding Actually Looks Like  
**Format**: 30 minutes, no live demo, no product marketing  
**Speaker persona**: Solutions Architect (15+ years), not an AI/ML engineer

---

## Table of contents
1. Run-of-show (30 minutes)
2. Slide-by-slide blueprint (minimal on-screen text + visuals)
3. Conversational speaker notes (per slide + transitions)
4. Prompt Evolution (3-step examples for Slide 15)
5. Vibe Coding Tool Matrix (Slide 16 + talk track)
6. Anticipated Q&A bank (20 questions + pivots)
7. Stage-fright operating procedure (on-stage protocol)
8. 1-page takeaway handout (print/PDF-ready)

---

## 1) Run-of-show (30 minutes)

**00:00–00:45 — Walk-on + opening line (memorized)**
- “I’m a Solutions Architect. I’ve shipped enterprise systems for years. I’m not an AI engineer. And that’s exactly why I’m here.”
- Set expectation: practical story, not theory, not marketing.

**00:45–02:30 — What “vibe coding” means in plain language**
- Human describes intent → AI generates → human steers → repeat.
- Thesis: “AI writes the syntax; you design the system.”
- Transition: “Let me show you where this breaks in real life.”

**02:30–06:30 — The demo-to-product gap (the uncomfortable truth)**
- AI is great at happy path + boilerplate; weak at edges + architecture.
- Checklist: latency, retries/timeouts, auth/abuse, observability, cost, UX constraints.
- Transition: “First story: WhatsApp. It forces you to respect reality.”

**06:30–07:30 — Case Study 1 setup: AgriNexus AI (WhatsApp)**
- Audience + constraints (low literacy, network reliability, strict timeouts).
- Transition: “Here’s the first thing that went wrong.”

**07:30–10:00 — Failure moment: heavy RAG → WhatsApp timeout**
- Symptoms: delays, retries, silence.
- Principle: “In chat, latency is product.”
- Transition: “The fix wasn’t a better prompt. It was architecture.”

**10:00–13:30 — Fix: decouple + async processing**
- Fast acknowledgement; slow reasoning behind queues.
- Add retries, idempotency, observability without breaking UX.
- Principle: “Async is a feature, not a refactor.”
- Transition: “Once it worked, the next constraint showed up: cost.”

**13:30–15:30 — Trade-off: OpenSearch → S3 vectors**
- Frame as constraint fit, not “best tool.”
- Transition: “Second story: a web app, different failure mode.”

**15:30–16:15 — Reset / palate cleanser**
- “Different app, same pattern: AI got me 80% fast, then tried to kill me in the last 20%.”
- Transition: “Photography coach: the loop problem.”

**16:15–18:45 — Case Study 2 setup: AI Photography Coach (web)**
- Multi-dimensional spatial feedback; actionable prioritization.
- Transition: “The first failure wasn’t accuracy. It was control.”

**18:45–21:00 — Failure: infinite prompt loops**
- Symptoms: runaway calls, cost spike, no “done.”
- Fix principle: explicit state + stop conditions + max iterations.
- Transition: “Then I hit a second trap: retrieval that looks right and feels wrong.”

**21:00–23:30 — Failure: useless vector matches**
- “Semantically similar” ≠ “helpful.”
- Fix principle: weighting + filters + eval set (“golden questions”).
- Transition: “How do you keep enterprise-scale costs predictable?”

**23:30–25:30 — Cost control: context caching**
- Cache stable context; don’t cache volatile personal content.
- Claim framing: “In my case, caching reduced repeat-token spend dramatically—75–90% depending on traffic shape.”
- Transition: “So what does vibe coding look like when you do it responsibly?”

**25:30–28:00 — Prompt evolution (the ‘how’)**
- Feature request → constraints → production hardening.
- Principle: “Add constraints, not adjectives.”
- Transition: “Here’s the tooling reality: what each tool is best used for.”

**28:00–29:15 — Vibe Coding Tool Matrix**
- Intent vs execution; explore vs harden; switch tools when job changes.
- Transition: “Let me land this with three principles you can steal tomorrow.”

**29:15–30:00 — Close + Q&A setup**
- “Name constraints & invariants.”
- “Instrument reality: latency, loops, retrieval quality, cost.”
- “Ship the boring parts: retries, abuse controls, observability.”
- Q&A invite: “Ask where it broke—and what I changed.”

---

## 2) Slide-by-slide blueprint (minimal on-screen text + visuals)

**Global slide rules**
- Max 12–18 words of body text per slide (excluding lesson bubble).
- One visual per slide (diagram OR screenshot OR chips).
- Lesson bubble: 4–7 words, same position on every slide.

### Slide 1 — Title
**On-screen**
- Building with AI Without Being an AI Expert
- What vibe coding actually looks like

**Lesson bubble**: You don’t need ML to ship.  
**Visual**: calm, minimal background.

### Slide 2 — Who I am / what this is
**On-screen**
- Solutions Architect (15+ years)
- Not an AI engineer
- Two products. Two failures. Real fixes.

**Lesson bubble**: This is a builder’s story.  
**Visual**: small “disclaimer” card style.

### Slide 3 — What vibe coding looks like (loop)
**On-screen**
- Intent → Code → Reality → Fix → Repeat

**Lesson bubble**: Iteration beats prompts.  
**Diagram**: 5-node loop (Intent, AI_generates, Human_reviews, Run_in_reality, Refine_constraints).

### Slide 4 — Demo vs Product gap (chips)
**On-screen (chips)**
- Latency
- Retries & timeouts
- Auth & abuse
- Observability
- Cost & limits

**Lesson bubble**: Non-functionals decide success.  
**Visual**: five rounded chips.

## AgriNexus (Slides 5–9)

### Slide 5 — Context + constraints
**On-screen**
- WhatsApp advisor for smallholder farmers
- Low literacy, flaky networks, strict timeouts

**Lesson bubble**: Design for the channel.  
**Visual**: WhatsApp screenshot (sanitized) OR icon + 3 constraint chips.

### Slide 6 — Architecture “before” (sync)
**On-screen**
- Everything happens in one request

**Lesson bubble**: Fast AI ≠ fast product.  
**Diagram**: WhatsApp_webhook → API → RAG_query → LLM → Reply (timeout risk over RAG+LLM).

### Slide 7 — Failure moment (timeout)
**On-screen**
- Users saw: delays, retries, silence
- I saw: timeouts + dropped messages

**Lesson bubble**: Latency is product.  
**Visual**: pseudo-log screenshot (2–4 lines).

### Slide 8 — Architecture “after” (async)
**On-screen**
- Acknowledge fast
- Process slow
- Deliver later

**Lesson bubble**: Async is a feature.  
**Diagram**: Webhook → API_fast_ack → Queue → Worker → RAG+LLM → Outbound_sender → WhatsApp_message.

### Slide 9 — Cost trade-off
**On-screen**
- Vector store choice is architecture
- $174/mo → ~$50/mo (for my needs)

**Lesson bubble**: Cost is architecture.  
**Visual**: two bars, vendor names off-slide (optional in notes).

## Photo Coach (Slides 10–14)

### Slide 10 — What it does (screenshot)
**On-screen**
- Spatial feedback, not just “nice photo”
- Impact levels: Critical / Medium / Low

**Lesson bubble**: Make feedback actionable.  
**Visual**: app screenshot with 3 callouts.

### Slide 11 — Failure: infinite prompt loops
**On-screen**
- It wouldn’t stop “thinking”
- Calls kept chaining

**Lesson bubble**: Guardrails stop spirals.  
**Visual**: loop arrow + “max iterations?” callout.

### Slide 12 — Fix: state + stop conditions
**On-screen**
- State machine > vibe alone
- Stop rules + budgets + timeouts

**Lesson bubble**: Control beats cleverness.  
**Diagram**: Intake → Analyze → Summarize → Done; side labels: max_steps, max_tokens, timeout, no_repeat_check.

### Slide 13 — Failure: useless vector matches
**On-screen**
- “Similar” results
- Wrong for the user’s intent

**Lesson bubble**: Retrieval needs judgment.  
**Visual**: two example cards: “Looks related” vs “Actually helpful.”

### Slide 14 — Fix: weighting + eval set + caching
**On-screen**
- Weight signals (not just cosine)
- Golden questions to test changes
- Cache stable context

**Lesson bubble**: Measure before you tune.  
**Visual**: 3 columns: Weighting / Eval_set / Caching.

### Slide 15 — Prompt Evolution
**On-screen**
- Prompt v1: “Build it”
- Prompt v2: “Build it + constraints”
- Prompt v3: “Build it + production rules”

**Lesson bubble**: Add constraints, not adjectives.  
**Visual**: three side-by-side prompt cards (cropped to 3–5 lines each).

### Slide 16 — Vibe Coding Tool Matrix (2×2)
**On-screen**
- Intent ↔ Execution
- Explore ↔ Harden

**Lesson bubble**: Use tools for roles.  
**Diagram**: 2×2 axes; labels only (generic, non-promotional).

### Slide 17 — Closing
**On-screen**
- Name constraints & invariants
- Instrument reality (latency, loops, retrieval)
- Ship the boring parts

**Lesson bubble**: Ship the boring parts.  
**Visual**: lots of whitespace.

---

## 3) Conversational speaker notes (per slide + transitions)

### Slide 1 — Title
**Say**
- “I want to tell a builder’s story about ‘vibe coding’—what it actually looks like when you try to ship something, not just demo it.”
- “Quick disclaimer: I’m not an AI/ML engineer. I’ve never trained a model. My job is systems that work on bad days.”
**Transition**: “So—here’s who you’re listening to, and what this talk is not.”

### Slide 2 — Who I am / what this talk is
**Say**
- “I’m a Solutions Architect, mostly enterprise: SAP, cloud, the boring reliability stuff.”
- “This isn’t a theory talk and it’s not a marketing talk. It’s two products I built, two big failures, and what I changed.”
**If time**: “I’m deliberately not going to explain backprop. If you ask me, I’ll happily admit I can’t.”
**Transition**: “Now, when people say ‘vibe coding’—this is the simplest honest version.”

### Slide 3 — Vibe coding loop
**Say**
- “It’s a loop: I describe intent, AI generates code, I run it in reality, reality breaks it, then I tighten constraints and iterate.”
- “The key isn’t the prompt. The key is the iteration speed plus your judgment.”
**If time**: “Where people get burned is they think the loop ends at ‘code compiles.’ It doesn’t.”
**Transition**: “And the moment you try to ship, the loop hits a wall.”

### Slide 4 — Demo vs Product gap
**Say**
- “A demo is: it works once, for me, on my laptop, with perfect inputs.”
- “A product is: latency, retries, timeouts, auth, abuse, observability, cost—plus actual UX constraints.”
- “AI writes the syntax; you still design the system.”
**Transition**: “First story: WhatsApp. It forces you to respect constraints immediately.”

## AgriNexus

### Slide 5 — Context + constraints
**Say**
- “AgriNexus is a WhatsApp-based agricultural advisor for smallholder farmers in India.”
- “Constraints drove everything: low literacy, variable connectivity, and strict time limits.”
**Transition**: “Here’s the first architecture I started with—because it’s the obvious one.”

### Slide 6 — Before (sync)
**Say**
- “Webhook comes in, we do retrieval, we call the model, we reply. One request, one response.”
- “It’s clean on a whiteboard, and it hides the biggest risk: latency stacking.”
**If time**: “RAG isn’t free—variance is what kills you in chat.”
**Transition**: “And this is the moment it failed in the real world.”

### Slide 7 — Failure (timeout)
**Say**
- “Users experienced it as silence. Or they’d resend. Or they’d give up.”
- “I experienced it as timeouts and dropped conversations.”
- “In chat, latency isn’t a metric—it’s the product.”
**Transition**: “The fix wasn’t ‘a better prompt.’ The fix was changing the shape of the system.”

### Slide 8 — After (async)
**Say**
- “Acknowledge fast, process slow, deliver later.”
- “Now I can add retries, idempotency, and observability without breaking UX.”
**If time**: “Async is control: budgets, timeouts, backpressure.”
**Transition**: “Once it worked reliably, the next constraint was predictable: cost.”

### Slide 9 — Cost trade-off
**Say**
- “I originally paid for capability I didn’t need.”
- “I moved to a simpler vector storage approach: fewer features, lower cost, acceptable quality for this use case.”
- “Not ‘best tool’—just ‘right trade-off under constraints.’”
**Transition**: “Okay—second story. Different app, different failure mode: control.”

## Photo Coach

### Slide 10 — What it does
**Say**
- “This web app gives spatial feedback on photos—multi-dimensional, not just ‘nice shot.’”
- “It buckets issues by impact so the advice is actionable.”
**Transition**: “The first major failure wasn’t accuracy. It was: it wouldn’t stop.”

### Slide 11 — Failure (loops)
**Say**
- “Runaway calls, no ‘done,’ escalating cost.”
- “If you don’t design stop conditions, the AI will happily keep producing.”
**Transition**: “So the fix was boring—and absolutely necessary.”

### Slide 12 — Fix (state + stops)
**Say**
- “Explicit state: intake → analyze → summarize → done.”
- “Guardrails: max steps, max tokens, timeouts, and ‘don’t repeat yourself’ checks.”
- “This is control systems, not magic.”
**Transition**: “Once it stopped looping, the next failure was subtler: retrieval that looks right but feels wrong.”

### Slide 13 — Failure (retrieval mismatch)
**Say**
- “‘Semantically similar’ isn’t the same as ‘helpful.’”
- “Sometimes hallucinations are caused by your retrieval layer, not the model.”
**Transition**: “So I fixed retrieval like any system: better signals, and a way to test changes.”

### Slide 14 — Fix (weighting + eval + caching)
**Say**
- “Weighting: multiple signals, not just nearest neighbor.”
- “A small eval set—golden questions—so prompt changes don’t become guesswork.”
- “Context caching for stable bits to reduce repeat-token spend.”
**Transition**: “Now I want to show you the ‘how’ of vibe coding in one slide: prompt evolution.”

### Slide 15 — Prompt Evolution
**Say**
- “v1: build the feature. Works… barely.”
- “v2: add constraints—timeouts, budgets, uncertainty behavior.”
- “v3: production rules—abuse, rate limits, logging, operability.”
- “Don’t add adjectives. Add constraints.”
**Transition**: “And here’s the tooling reality: different tools are good at different parts of the loop.”

### Slide 16 — Tool Matrix
**Say**
- “There’s intent work and execution work; exploration and hardening.”
- “My early mistake was using one tool for every quadrant. The fix was switching tools when the job changed.”
**Transition**: “Let me land this with three principles you can steal tomorrow.”

### Slide 17 — Closing
**Say**
- “Name constraints and invariants. That’s your job.”
- “Instrument reality—latency, loops, retrieval quality, cost.”
- “Ship the boring parts—retries, abuse controls, observability.”
- “Ask me where it broke—and what I changed.”

---

## 4) Prompt Evolution (3-step examples for Slide 15)

### A) AgriNexus (WhatsApp advisor)

**Prompt v1 (feature intent)**
- Build a WhatsApp agricultural advisor.
- Use retrieval over a knowledge base.
- Answer in plain language.
- Ask one clarifying question if needed.

**Prompt v2 (constraints: survive the channel)**
- Must respond within 2 seconds with an ACK.
- Do heavy retrieval + reasoning asynchronously.
- If uncertain, say so and offer 2 button options.
- Never block on slow calls.

**Prompt v3 (production: safe + operable)**
- Add idempotency for duplicate webhook events.
- Add retries with backoff for outbound messages.
- Rate-limit per user; detect spam bursts.
- Emit structured logs + trace IDs per message.

### B) Photo Coach (web app)

**Prompt v1 (feature intent)**
- Analyze a photo and give spatial feedback.
- Categorize issues: Critical / Medium / Low.
- Provide 3 concrete improvement suggestions.

**Prompt v2 (constraints: stop loops)**
- Use explicit states: Intake → Analyze → Summarize → Done.
- Max 3 iterations; hard timeout 20s.
- If repeating, stop and summarize current best result.
- Track token/call budget per request.

**Prompt v3 (production: retrieval quality + cost discipline)**
- Retrieval: weight by recency + user intent + similarity.
- Maintain a small eval set (“golden photos/questions”).
- Cache stable context; never cache user images.
- Log: loop_count, retrieval_hits, cost_estimate per request.

One-liner for Slide 15: **Feature → Constraints → Operability.**

---

## 5) Vibe Coding Tool Matrix (roles, strengths, failure modes, switch rules)

**Axes**
- X-axis: Intent → Execution
- Y-axis: Explore → Harden

**Quadrants (on-slide labels)**
1) Explore+Intent: Clarify what we’re building  
2) Explore+Execution: Generate first draft  
3) Harden+Intent: Define constraints & invariants  
4) Harden+Execution: Make it operable

**Talk track**
- “I don’t have ‘an AI tool.’ I have roles in a workflow. Wrong tool for the role creates hallucinations, loops, and architectural blind spots.”

### Explore + Intent
**Best for**: crisp scope, acceptance criteria, edge cases, constraints discovery  
**Failure mode**: sounds complete but isn’t testable  
**Switch rule**: “If I can’t write 3 acceptance tests from it, it’s not done.”

### Explore + Execution
**Best for**: boilerplate, scaffolds, first-pass integration glue  
**Failure mode**: confident wrong logic; missing error paths/timeouts  
**Switch rule**: “The moment it runs once, I stop exploring and start hardening.”

### Harden + Intent
**Best for**: invariants, threat model, budgets, termination conditions  
**Failure mode**: over-constraints or non-enforceable policy statements  
**Switch rule**: “If it can’t be enforced in code/infra, rewrite it until it can.”

### Harden + Execution
**Best for**: refactoring, tests, state, retries/backoff, idempotency, observability, cost guards  
**Failure mode**: patching symptoms because you stopped thinking about boundaries  
**Switch rule**: “If I patch the same class of bug twice, redesign the boundary.”

Cheat sheet:
- Explore→Harden: **when it works once**
- Intent→Execution: **when you can write acceptance criteria**
- Back to Intent: **when you’re debugging the same confusion repeatedly**

---

## 6) Anticipated Q&A bank (20 questions + pivots)

Each answer is 15–30 seconds plus a pivot question to keep it conversational.

### Architecture & reliability
1) **Why async for WhatsApp—couldn’t you just optimize RAG?**  
Answer: Tail latency kills chat; async changes the contract (fast ACK, slow work, reliable delivery).  
Pivot: “Who here has built on channels with hard timeouts?”

2) **Biggest architectural mistake early?**  
Answer: assuming request/response default; should design for slow path first (timeouts/queues/idempotency).  
Pivot: “What’s your default architecture reflex when moving fast?”

3) **Retries without duplicate messages?**  
Answer: idempotency keys + message IDs; assume duplicates and design for it.  
Pivot: “Do you already have idempotency patterns?”

4) **Where did you put observability?**  
Answer: at boundaries: inbound, enqueue, worker start/finish, outbound; trace end-to-end per message.  
Pivot: “What’s your minimum telemetry bar?”

5) **How decide queue vs direct call?**  
Answer: if UX needs fast response but work is slow/variable, queue; otherwise sync with strict budgets.  
Pivot: “Where do your users tolerate waiting?”

### Retrieval / hallucinations
6) **How tell retrieval vs model error?**  
Answer: log retrieved context; if context is wrong, retrieval issue; if context is good, reasoning/constraints issue.  
Pivot: “Do you store retrieved context with responses?”

7) **What are golden questions?**  
Answer: small fixed eval set; without it you can’t detect regressions.  
Pivot: “Do you have any quality tests for AI outputs?”

8) **Confidence without overengineering eval?**  
Answer: start with 20–50 cases; simple labels; iterate.  
Pivot: “Would a small eval set be easier than ‘AI governance’?”

9) **Why FAISS matches felt useless?**  
Answer: similarity ≠ usefulness; intent matters; weighting/filtering adds practical signals.  
Pivot: “What makes results useful in your domain?”

10) **Do you ever say ‘I don’t know’?**  
Answer: yes; uncertainty is UX; offer next-step options rather than confident nonsense.  
Pivot: “Do your users prefer certainty or control?”

### Cost & performance
11) **What drives cost most in real products?**  
Answer: tokens + retries + loops + repeated context; control flow often matters more than model choice.  
Pivot: “Where do you see runaway costs today?”

12) **What’s safe to cache?**  
Answer: stable non-sensitive context; avoid caching personal/user images unless privacy is designed.  
Pivot: “What’s your ‘never cache’ list?”

13) **How justify cheaper vector store?**  
Answer: match capability to requirements; evaluate quality; pay only for what you need.  
Pivot: “Do you pay for unused features today?”

14) **Prompt optimize for cost?**  
Answer: after fixing loops and retrieval; first reduce calls, then reduce prompt size.  
Pivot: “In your stack, fewer calls or shorter prompts?”

### Security & abuse
15) **#1 security concern with vibe coding?**  
Answer: shipping code you don’t understand; missing threat models/rate limits/data boundaries.  
Pivot: “How do you review AI-generated code now?”

16) **Prompt injection in RAG?**  
Answer: treat retrieved text as untrusted; separate instructions from content; constrain actions; log attempts.  
Pivot: “Do you classify inputs by trust level today?”

17) **Did you implement rate limiting early?**  
Answer: not early enough; once it works it will be stressed; quotas and fail-closed are readiness.  
Pivot: “Where would abuse show up first for you?”

### Process & working as a non-ML person
18) **If you’re not an AI expert, what mattered most?**  
Answer: system design fundamentals + humility to test/measure/roll back.  
Pivot: “Which fundamental feels weakest in your AI projects?”

19) **How avoid being misled by confident AI output?**  
Answer: assume wrong until reality checks pass; enforce constraints in prompt and code.  
Pivot: “Do you have a red-team prompt set?”

20) **What would you do differently?**  
Answer: build rails first—eval, observability, termination, latency contract—then iterate on quality.  
Pivot: “Which rail would you add tomorrow?”

**Boundary phrases (memorize 3)**
- “I can’t speak to training internals, but I can tell you what broke in production and how I redesigned around it.”
- “I don’t know the universal answer—here’s what worked under these constraints.”
- “If we had more time, I’d measure it two ways: latency tails and quality on a golden set.”

---

## 7) Stage-fright operating procedure (practical, rehearsable)

### 15 minutes before (backstage)
**Body reset (2 min)**: inhale 4, hold 2, exhale 6 × 6 cycles (“Slow is smooth”).  
**Voice warm-up (1 min)**: repeat your first line 3 times, slower each time.

**First minute script (memorize exactly)**
> “I’m a Solutions Architect. I’ve shipped enterprise systems for years. I’m not an AI engineer. And that’s exactly why I’m here. This is not a theory talk and not a marketing talk—just two products I built, what broke, and what I changed.”

**Pocket card (4 lines)**
- Thesis: syntax vs system
- AgriNexus: timeout → async
- Photo: loops → state
- Close: 3 principles

### On-stage autopilot
- Speak at 80% speed for first 3 minutes.
- Every slide change: one silent exhale before you speak.
- 3 friendly faces: left/center/right rotation.
- Water cues: sip at Slide 5 and Slide 10.

### If you blank (recovery scripts)
- “Give me one second—I want to say this clearly.” → “The point here is…”
- “Let me step up a level. The principle is…” (say the lesson bubble)
- “Here’s what happened first… then what I changed… then the lesson.”

### Time checkpoints + cuts
- 7:00 start Slide 5 (AgriNexus)
- 16:00 start Slide 10 (Photo Coach)
- 25:30 start Slide 15 (Prompt Evolution)

Pre-decided cuts if behind:
- Compress Slide 9 (cost) to one sentence.
- Compress Slide 13/14 nuance to: “similar ≠ useful” + “eval set.”

### Q&A anxiety reducer
- Repeat the question → answer in your constraint frame → ask a pivot back to room.

---

## 8) 1-page takeaway handout (print/PDF-ready)

**Title**: Building with AI Without Being an AI Expert  
**Thesis**: Vibe coding is real. AI writes syntax; humans design the system.

### Core idea
Humans own:
- Constraints (latency, privacy, budgets, UX)
- Invariants (“must never happen”)
- Operability (retries, observability, abuse controls)
- Quality (evaluation, regressions, failure behavior)

### Case Study 1: AgriNexus (WhatsApp advisor)
**Broke**: heavy RAG + reasoning → timeouts → silence/confusion  
**Changed**: fast ACK + async queue/worker + retries + idempotency + uncertainty UX  
**Lesson**: In chat, latency is product. Async is a feature.

### Case Study 2: Photo Coach (web app)
**Broke**: infinite loops + “similar but useless” retrieval  
**Changed**: explicit state + stop rules + weighted retrieval + eval set + caching stable context  
**Lesson**: Control beats cleverness. Retrieval needs judgment. Measure before tuning.

### Production readiness checklist (AI features)
**Latency & flow**: define latency contract; design for tail latency; choose sync vs async  
**Reliability**: retries/backoff; idempotency; clear fallback behavior  
**Security & abuse**: rate limits/quotas; treat external text as untrusted; invariants  
**Observability**: structured logs + trace IDs; track p95/p99, loop count, retrieval hits, cost estimate  
**Quality**: small eval set; helpful/unhelpful + safe/unsafe; re-test after changes  
**Cost**: stop loops; avoid repeated context; budget per request

### Prompt Evolution template
**v1 Feature**: “Build X that does Y for user Z.”  
**v2 Constraints**: “Must respond within ___; if uncertain do ___; never block on ___; stop after ___.”  
**v3 Operability**: “Add retries/idempotency/rate limits; emit logs/metrics; enforce budgets; define fallbacks.”

