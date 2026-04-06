# AgriNexus AI — Final demo video (consolidated)

**Audience:** AWS community, judges, English-primary network  
**Product proof:** Hindi (and optional Marathi) on WhatsApp — **narration stays English**; use **burned-in English subtitles** for the few Hindi lines that matter.  
**Target length:** ~**2:45–2:55** spoken + **~8–10 s** end card → **under 3:00** total  
**Production order:** (1) Record **English** voiceover in a quiet room → (2) Record **iPhone WhatsApp** screens → (3) **CapCut**: align video to audio → add **subtitles** on key beats → add **bed** at **10–15%** under voice → export **1080p**

**Alignment:** Matches `architecture.md` / `README.md` **modeled** costs (~**$53/mo @ 1K**, ~**$450/mo projected @ 10K** → ~**$0.64** / ~**$0.54** per farmer/year — **not** Cost Explorer). Implementation: wind **&lt; 10 km/h**, **OpenWeatherMap**, buttons **हो गया** / **अभी नहीं**, **T+24h / T+48h** reminders, batch **Transcribe** + **Polly**.

**Nudges (don’t mis-speak on camera):** Messages are **contextual** — **district**, **crop**, **spray type** (pesticide vs fungicide), **live wind**, plus a **short scouting / awareness line** (extension-style: what to watch in the field, **KVK/dealer** wording, **no product names or doses** in the default copy). Optionally, if **`NUDGE_BEDROCK_LINER=true`** in deploy, the **first** hint line can be a **single Bedrock Haiku sentence** (still scouting-only). That line is **not** Knowledge Base **RAG** — **RAG** is **`retrieve_and_generate`** in the **message** processor for farmer Q&A. **Say:** “crop- and district-aware nudge” or “scouting line” — **not** “RAG nudge.”

---

## Hook: what to show on screen (data validity)

Use **one** of these for **~3–4 s** at **0:00** — **headline + source line** in tiny caption (outlet + date). You are establishing **newsroom / official data**, not inventing stats.

| Priority | Source | What it gives you | Caption example |
|----------|--------|-------------------|-----------------|
| **A (recommended)** | [**Indian Express** — *Explained: The crisis in India’s cotton production*](https://indianexpress.com/article/explained/explained-economics/a-cotton-emergency-9928795/) (2025) | Pink bollworm, production slide, **Cotton Advisory Board / CAI** chart references | `Source: Indian Express Explained, 2025 · Data: Cotton Advisory Board / CAI` |
| **B** | **PIB** / Ministry press note on cotton or **CAB** release — if you have a clean PDF screenshot | Official tone | `Source: PIB India` or `Source: Cotton Advisory Board` |
| **C** | **ReliefWeb / ODI** — only if you use **exact** survey wording and sample size in voiceover | Qualitative “farmer losses” framing | `Source: ODI/ReliefWeb, [study title], [year]` — **read the study first** |
| **D** | **Agricultural Census** table (GoI) — marginal/small holdings | Supports “**100M+**” / **126M** holdings language | `Source: Agriculture Census of India` |

**Avoid:** citing **CivilsDaily**, **MDPI**, or second-hand blogs **unless** you have verified the claim against the **primary** chart or paper. **Indian Express + CAB path** is the strongest **fast** hook for cotton + PBW + data lineage.

---

## Background audio (bed) — per section

Keep bed **low** (**~10–15%** of voice); **duck** under narration.

| Section | Time (approx.) | Bed style | Royalty-free search terms (examples) |
|---------|----------------|------------|----------------------------------------|
| 1 Hook | 0:00–0:28 | Soft rural morning — birds, light wind | `rural india morning ambience`, `gentle field dawn` |
| 2 Nudge | 0:28–1:00 | Dawn → subtle notification tension | `rooster distant`, `soft suspense ambient` (very light) |
| 3 Text RAG | 1:00–1:22 | Almost silent | `minimal room tone`, `barely there ambient` |
| 4 Voice | 1:22–1:50 | Outdoor, walking | `field footsteps`, `countryside light` |
| 5 Vision | 1:50–2:15 | Slightly more “focus” | `soft discovery`, `quiet tension` (still low) |
| 6 Onboarding | 2:15–2:32 | Light, quick | `upbeat minimal`, `soft positive` |
| 6b Marathi (opt.) | 2:32–2:38 | Same as 3 or mute | — |
| 7 Impact | 2:38–2:55 | Warm, hopeful lift | `documentary piano minimal`, `hopeful ambient` |
| 8 End card | 2:55–3:05 | Fade to silence | — |

---

## Subtitle rule

For **5–7** beats only, add **`[Subtitle: …]`** in CapCut — **English gloss** of the **one** Hindi line that matters. **Do not** subtitle every bubble.

---

# NARRATION SCRIPT (English) + production notes

### SECTION 1 — Hook (0:00–0:28)

**[Music: Row 1]**  
**[Visual: 3–4 s — Indian Express (or CAB/PIB) still from table above → fade to cotton / your “problem” slide]**

**Narration:**

“India has **well over a hundred million** small and marginal farm holdings — official agriculture statistics have used figures in that range for years. **Extension** still doesn’t reach everyone: older FAO and national studies often put **effective reach** in the **single digits** — the gap isn’t new.

Meet **Ramesh**. He grows **cotton** in **Latur, Maharashtra**. The agronomist might visit **once in a while**. Search results often come back in **English**. And the **spray window** for some pests is measured in **days**.

**Press reports**, using **official cotton statistics**, have documented **sharp stress** in India’s cotton belt — including **pink bollworm** pressure and **falls from peak production**. The point isn’t one number — it’s that **timing and language** decide whether advice is usable.”

**[Subtitle (optional):]** none — your headline still is the proof.

---

### SECTION 2 — Nudge differentiator (0:28–1:00)

**[Music: Row 2]**  
**[Visual: Real WhatsApp — Hindi nudge; tap **अभी नहीं**; show **T+24h** reminder if recorded; then **हो गया** → confirmation]**

**Narration:**

“What if the advice **came to Ramesh** — **in Hindi**, when **weather** is right?

**AgriNexus** pulls **current** wind and rain for his **district** from **OpenWeatherMap**. When the spray window looks good — **wind under ten kilometers per hour** and **no recent rain** — it sends a **WhatsApp nudge**.

The nudge isn’t generic spam: it carries **his district and crop**, and leads with a **short field-scouting line** — what to **watch** this week, in an **extension** tone — **not** a product pitch. *(Optional in your deployment: that line can be **LLM-generated** for variety; the Q&A path still uses **document RAG** — different feature.)*

He taps **‘not yet’** — **अभी नहीं**. The system **reminds him** at **twenty-four** and **forty-eight hours**. When he’s finished, he taps **‘done’** — **हो गया** — and the loop **closes**.

That’s **advice plus follow-through** — not a one-off chat.”

**[Subtitle examples]:** first line of nudge body (English) · `(Not yet)` on tap · `(Done)` on **हो गया**.

**Note:** If your screenshot shows **8 km/h**, you can say “eight” in voice; else keep **“under ten.”**

**If 30s feels tight:** Drop the *italic* parenthetical sentence and keep only: “it carries **his district and crop**, and leads with a **short scouting line** — **awareness**, not a product pitch.”

---

### SECTION 3 — Text RAG (1:00–1:22)

**[Music: Row 3]**  
**[Visual: Hindi question → answer with **Source:** line visible]**

**Narration:**

“He asks a **follow-up** in Hindi — for example about **yellowing leaves** on cotton.

**Moments later**, **AgriNexus** answers using **retrieval** from documents like **FAO** and **ICAR** materials — **in Hindi**, with a **visible source citation**. Not a random web tip.”

**[Subtitle]:** one Hindi question line + English · **“Source: …”** line in English.

---

### SECTION 4 — Voice (1:22–1:50)

**[Music: Row 4]**  
**[Visual: Voice note → optional **Processing…** overlay → text + Polly voice reply — **do not** speed-ramp to fake speed]**

**Narration:**

“Typing in **Devanagari** on a basic phone is slow — so Ramesh sends a **voice note** in **Hindi**.

**Amazon Transcribe** turns it to text; the same **Bedrock** pipeline answers; **Amazon Polly** can read the reply back.

The **full** path — transcribe, retrieve, generate, synthesize — takes **tens of seconds**, not milliseconds. What matters for farmers is: **no new app**, and **no English required**.”

**[Subtitle]:** optional **“Processing…”** if shown.

---

### SECTION 5 — Vision (1:50–2:15)

**[Music: Row 5]**  
**[Visual: Photo → structured reply — **hold** so pest name, confidence, safety, **source** are readable]**

**Narration:**

“In the field he spots **something wrong** on a leaf — and sends a **photo**.

The model returns a **structured** readout: **what it might be**, **confidence**, **severity**, **safety**, and a **citation**. **Decision support** — **not** a substitute for local regulation or a dealer’s label.

Details stay **on screen** — you don’t need to **read chemical names aloud** in a public demo.”

**[Subtitle]:** pest name + **“Source: …”** if one line fits.

---

### SECTION 6 — Onboarding (2:15–2:32)

**[Music: Row 6]**  
**[Visual: Fast taps — language → district → crop → nudge consent]**

**Narration:**

“How did he get here? He messaged **Namaste** on the **AgriNexus WhatsApp** number.

**Language**, **district**, **crop**, **nudge consent** — mostly **buttons**. **No new download**. **Under two minutes** in the product flow.

**WhatsApp** is already where hundreds of millions of people in India **message every day**.”

**[Subtitle]:** optional **“Profile ready”** line in English if shown.

---

### SECTION 6b — Optional: Marathi proof (2:32–2:38) *[insert or skip]*

**[Music: Row 6b]**  
**[Visual: After **reset profile**, re-onboard **mr** — one **Marathi** bot reply or nudge line — **2–4 s**]**

**Narration:**

“The same stack works in **Marathi** and **Telugu** — here’s **Marathi** on the same channel.”

**[Subtitle]:** one-line English gloss of the Marathi text.

**Prereq:** Reset user (`scripts/reset-profile.sh` / your deploy’s reset), complete **Marathi** onboarding, then capture **one** real exchange.

---

### SECTION 7 — Impact + cost + AWS (2:38–2:55) *[shift times if 6b omitted]*

**[Music: Row 7]**  
**[Visual: closing slide / architecture still]**

**Narration:**

“At national scale, the problem is **reach** and **timeliness**. **AgriNexus** meets farmers on **WhatsApp** — **retrieval-grounded** answers, **voice**, **vision**, and **weather-timed nudges** with a **closed loop**.

It’s **serverless on AWS** — **Bedrock**, **Transcribe**, **Polly**, **Lambda**, **DynamoDB**, **SQS**, **Step Functions**, **EventBridge**.

Modeled cloud cost in our **architecture** is on the order of **fifty dollars a month** at **about a thousand** active users — and scales to a projected **few hundred dollars a month** at **tens of thousands** — **directional**, not a bill from **Cost Explorer**. At that upper projection, it’s on the order of **fifty cents per farmer per year** — **under a dollar** in plain language.

The **distribution** already exists. **AgriNexus** tries to **close the last mile**.”

---

### SECTION 8 — End card (2:55–3:05)

**[Music: silence]**  
**[Visual only ~8–10 s]**

- Logo · **Close the last mile**  
- **QR** → finalist article  
- **GitHub:** `https://github.com/prasadt1/agrinexus-ai`  
- **Vote for AgriNexus AI**  
- Hashtags per competition rules (e.g. `#aideas-2025` — **dedupe** if two lines)

---

## Recording checklist

- [ ] English VO in sections; **Hindi** (and optional **Marathi**) **only** on phone screen  
- [ ] **Subtitles** on 5–7 key beats  
- [ ] Buttons match build: **हो गया** / **अभी नहीं**  
- [ ] Hook still: **Indian Express** or **CAB/PIB** with **captioned source**  
- [ ] Voice section: **honest** wait or **Processing…** — no fake 1-second latency  
- [ ] Cost language: **modeled** / **directional**  
- [ ] Marathi insert: **real** profile after **reset**  
- [ ] Export **1080p**, total **&lt; 3:00**

---

## Changelog

- **2026-04:** Consolidated Cursor + Claude + repo alignment; hook source table; music map; optional Marathi beat; cost wording per `README.md` / `architecture.md`.
- **2026-04:** Nudge clarification — contextual / scouting-aware nudge copy; optional Haiku line **≠** KB RAG; wording for Section 2 + alignment bullet.
