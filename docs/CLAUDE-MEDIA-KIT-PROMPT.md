# Prompt for Claude: AgriNexus AI Media Kit

**How to use:** Copy everything below the line (from "You are an expert..." through "...social posts and hashtags.") and paste it into a new Claude conversation. Claude will have full context to generate a winning-worthy media kit.

---

You are an expert at creating competition-ready media kits for developer and social-impact contests. Your task is to create a **winning-worthy media kit** for the project below, so it stands out to judges and gathers maximum votes from peers in the **AWS Builder 10,000 AIdeas** competition. The goal is to reach the **semi-finals** via votes and judge appeal.

---

## Project: AgriNexus AI

**Tagline:** Close the last mile—AI-powered agronomic advice and weather-timed nudges for smallholder farmers, in their language, on WhatsApp.

**What it is:** A WhatsApp-based agricultural advisory and behavioral nudge system for smallholder farmers in India (Maharashtra focus, cotton farmers). It is not just Q&A: it proactively sends weather-timed spray reminders and tracks whether farmers completed the action (“हो गया” / done), with T+24h and T+48h follow-ups.

**Problem:** The “last mile” of agricultural extension: good advice exists (FAO, ICAR, research) but doesn’t reach farmers in time or in their language. Missing the right window for spraying → crop loss and income loss. Voice and local language are critical for trust and adoption.

**Solution:**
- **Multi-modal input:** Text, voice notes (transcribed), and crop photos.
- **RAG-based Q&A:** Answers grounded in FAO manuals and Indian agricultural research, with source citations in every response.
- **Voice in/out:** Amazon Transcribe for input; Amazon Polly (Hindi Aditi, English Kajal/neural) for optional audio replies.
- **Vision:** Claude 3 Sonnet for pest/disease/nutrient deficiency from crop images, with specific pesticides, dosages, and timing.
- **Behavioral nudges:** Weather-based “time to spray” reminders; closed-loop tracking with “done” keywords (Hindi, Marathi, Telugu); smart reminders at T+24h and T+48h; max one nudge per activity per day.
- **Languages:** Hindi, Marathi, Telugu, English (onboarding and responses in user’s chosen dialect).

**Tech stack (competition-mandated):**
- **Kiro:** Used for requirements → design → code → deploy (spec-to-code workflow).
- **EARS:** Easy Approach to Requirements Syntax; 100+ requirements in `requirements.md`, full traceability to code and tests.
- **Amazon Bedrock:** RAG (knowledge base), Claude 3 Sonnet (chat + vision), Amazon Transcribe, Amazon Polly.
- **AWS serverless:** Lambda, DynamoDB (single-table), SQS (FIFO), EventBridge Scheduler, Step Functions, S3, API Gateway. No servers; ~$50/month for 1,000 users.

**Competition details:**
- **Name:** AWS Builder 10,000 AIdeas Competition.
- **Category:** Agriculture & Food Security (Social Impact).
- **Requirements:** App must use Kiro for at least part of development; use Bedrock; AWS infrastructure. EARS-based spec dev is part of the intended workflow.
- **Goal:** Get votes from fellow competitors and peers and impress judges to advance to the **semi-finals**.
- **Audience:** Judges (technical + impact), fellow builders (technical, “would I vote for this?”), and AWS/Builder community.

**Differentiators to stress:**
- Real behavioral change (nudges + closed-loop “done”), not just chat.
- Full competition stack: Kiro, EARS, Bedrock, serverless—all visible and documented.
- Production-ready: deployed, multi-language, voice, vision, RAG, citations.
- Clear impact narrative: right advice at the right time, in their language → less crop loss, more income.

**Key phrases (for consistency):**
- “Close the last mile”; “weather-timed nudges”; “in their language, on WhatsApp”; “हो गया” (done) for closed loop.
- “Built with Kiro, EARS, and Amazon Bedrock”; “100+ EARS requirements”; “RAG, voice, vision, nudges on serverless AWS.”

---

## What to create

Produce a **complete, competition-ready media kit** that I can use as-is or adapt. Include:

1. **Video script (60–90 seconds)**  
   Word-for-word voiceover (and optional on-screen text) with timings. Structure: hook (problem) → solution (AgriNexus in one sentence) → quick demo beats (voice Q&A, photo → pest ID, nudge + “done”) → competition stack (Kiro, EARS, Bedrock) → clear “vote for us” ask. Make it memorable and shareable.

2. **One-pager (PDF-ready copy)**  
   Single-page narrative: title, problem (2–3 bullets), solution (2–3 bullets), tech (Kiro, EARS, Bedrock, AWS), impact (users, outcome, cost), and call-to-action (“Vote for AgriNexus”). Formatted so it can be dropped into a doc and exported to PDF.

3. **Pitch deck outline (5–7 slides)**  
   Slide title + 3–5 bullet points or short sentences per slide. Covers: title/tagline, problem, solution, how we built it (competition stack), demo (what to show), impact & ask, thank you. Include one-line speaker notes where it helps.

4. **Social and community copy**  
   Ready-to-post versions:
   - **LinkedIn:** 2–3 short paragraphs (hook, what it does, why it matters, ask for vote + link).
   - **Twitter/X:** 2–3 tweet options (under 280 chars each) + suggested hashtags.
   - **AWS Builder / community:** One “project showcase” blurb (150–200 words) and a one-line elevator pitch.
   Include recommended hashtags (e.g. #10000AIdeas #AWS #AmazonBedrock #Kiro #AgriNexus #SocialImpact #Agriculture).

5. **Optional: taglines and sound bites**  
   3–5 alternative taglines or one-liners for thumbnails, headers, or verbal pitch.

Keep tone professional, clear, and impact-focused. Emphasize both **social impact** (farmers, crop loss, income) and **competition alignment** (Kiro, EARS, Bedrock, serverless). Make the “vote for us” and “try it / see the repo” ask explicit and easy to act on. Do not invent technical details; stick to the project description above. Output everything in one response so I can copy-paste into documents or scripts.
