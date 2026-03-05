# Prompts for Animated Architecture GIFs (Gemini / ChatGPT)

Use these prompts with **Gemini** or **ChatGPT** (including image/video-capable versions) to get **animated diagram descriptions** or **frame-by-frame specs** for each AgriNexus AI flow. You can then:
- Use an AI image generator to create each frame and stitch into a GIF (e.g. with ezgif.com or similar).
- Feed the same prompt to a video-capable model to request a short animated sequence.
- Hand the description to a designer to build in Canva, After Effects, or PowerPoint.

**Style to request:** Clean tech architecture diagram. Icons or labeled boxes for: Farmer/User, WhatsApp, API Gateway, Lambda, SQS, DynamoDB, Bedrock, Transcribe, Polly, Vision, Step Functions, EventBridge. Arrows show data flow. Animation: highlight or pulse **one step at a time** in sequence, with a short label (e.g. “1. Farmer sends text”). Keep colors consistent (e.g. green for WhatsApp, orange for Lambda, blue for DynamoDB). Minimal text; readable at 1280×720 or 1920×1080.

---

## 1. Text message flow (Q&A)

Copy and paste this prompt (edit the bracketed part if needed).

```
Create an animated architecture diagram (GIF or short video) for this flow. Show each step in sequence with a clear highlight or pulse on the active component; add a small step label (e.g. "Step 1", "Step 2") in one corner.

Flow: AgriNexus AI – Text message (farmer asks a question, gets RAG answer).

Steps to animate in order:
1. Farmer (user icon) sends a text message → arrow to WhatsApp (chat bubble icon).
2. WhatsApp sends POST to API Gateway (webhook icon).
3. API Gateway forwards to Webhook Lambda (Lambda icon). Show "verify + dedup".
4. Webhook Lambda writes to DynamoDB (table icon) for dedup, then sends message to SQS Message Queue (queue icon).
5. Message Queue triggers Message Processor Lambda (Lambda icon).
6. Message Processor reads user profile from DynamoDB (arrow DynamoDB → Lambda).
7. Message Processor calls Bedrock (brain/LLM icon) – "RAG: retrieve + generate". Show Knowledge Base (book/DB icon) feeding Bedrock.
8. Bedrock returns answer + citations to Message Processor.
9. Message Processor sends reply to WhatsApp Cloud API (outbound arrow to WhatsApp).
10. Farmer receives bot reply on WhatsApp.

Style: Clean flowchart, AWS-style colors (orange Lambda, blue DynamoDB, green for external WhatsApp). One step highlighted at a time; others slightly dimmed. Title: "AgriNexus AI – Text Q&A flow". Output: either a short animated sequence (GIF/video) or a precise frame-by-frame description so I can create the GIF myself.
```

---

## 2. Voice message flow

```
Create an animated architecture diagram (GIF or short video) for this flow. Highlight one step at a time in sequence with a step label (Step 1, 2, 3...).

Flow: AgriNexus AI – Voice message (farmer sends voice note, gets transcribed and answered, optionally with voice reply).

Steps to animate in order:
1. Farmer sends a voice note → WhatsApp.
2. WhatsApp POST to API Gateway → Webhook Lambda (verify, dedup, store in DynamoDB).
3. Webhook Lambda routes audio to SQS Voice Queue (different queue icon than text).
4. Voice Processor Lambda is triggered. It downloads audio from WhatsApp, uploads to S3 (bucket icon).
5. Voice Processor calls Amazon Transcribe (waveform/speech icon). Show "speech → text".
6. Transcribe returns transcript. Voice Processor sends transcript to SQS Message Queue (as text + _source: voice).
7. Message Queue triggers Message Processor Lambda.
8. Message Processor gets profile from DynamoDB, calls Bedrock RAG (same as text flow) – show Bedrock + Knowledge Base.
9. Message Processor optionally calls Amazon Polly (speaker icon) for text-to-speech reply.
10. Message Processor sends text + optional audio URL to WhatsApp; farmer receives reply.

Style: Same as text flow (AWS-style, clean boxes, one step highlighted). Include icons for Transcribe, S3, Polly. Title: "AgriNexus AI – Voice flow". Output: animated sequence or frame-by-frame description for a GIF.
```

---

## 3. Image / vision analysis flow (pest/disease)

```
Create an animated architecture diagram (GIF or short video) for this flow. Highlight one step at a time with step labels.

Flow: AgriNexus AI – Image analysis (farmer sends crop photo, gets pest/disease identification and advice).

Steps to animate in order:
1. Farmer sends an image (crop/leaf photo) → WhatsApp.
2. WhatsApp POST to API Gateway → Webhook Lambda (verify, dedup, store in DynamoDB).
3. Webhook Lambda sends to SQS Message Queue (image type).
4. Message Processor Lambda is triggered. It fetches image from WhatsApp media URL (optional: show download step).
5. Message Processor calls Claude Vision (Bedrock) – show "image + prompt" → Vision model (eye/camera icon).
6. Vision returns analysis: pest/disease/nutrient deficiency + recommendations.
7. Message Processor sends text reply (advice, pesticides, dosages) to WhatsApp.
8. Farmer receives diagnosis and recommendations on WhatsApp.

Style: Same tech diagram style. Emphasize the image going to Vision (Claude) and the structured advice back. Title: "AgriNexus AI – Image / vision flow". Output: animated sequence or frame-by-frame description for a GIF.
```

---

## 4. Nudge flow (weather-timed reminder + reminders)

```
Create an animated architecture diagram (GIF or short video) for this flow. Highlight one step at a time with step labels.

Flow: AgriNexus AI – Nudge (scheduled weather check → nudge sent to farmer; later, T+24h/T+48h reminders).

Steps to animate in order:
1. EventBridge (clock/schedule icon) triggers on a schedule (e.g. every 6 hours).
2. Weather Poller Lambda runs. Show it reading locations from DynamoDB (user profiles).
3. Weather Poller checks weather (optional: show "favorable?" decision – wind, rain).
4. If favorable: Weather Poller starts Step Functions execution (state machine icon).
5. Step Functions invokes Nudge Sender Lambda.
6. Nudge Sender sends a "time to spray" template message to WhatsApp → farmer receives nudge.
7. Nudge Sender creates one-time schedules in EventBridge Scheduler for T+24h and T+48h (calendar icon).
8. (Optional second part of animation) At T+24h: EventBridge Scheduler triggers Reminder Sender Lambda.
9. Reminder Sender sends follow-up message to WhatsApp → farmer receives reminder.
10. (Optional) Show DynamoDB Streams → Response Detector Lambda when farmer replies "Done" (हो गया); update state and cancel future reminders.

Style: Same diagram style. Clearly show EventBridge → Weather Poller → Step Functions → Nudge Sender → WhatsApp, then EventBridge Scheduler → Reminder Sender → WhatsApp. Title: "AgriNexus AI – Nudge flow". Output: animated sequence or frame-by-frame description for a GIF.
```

---

## 5. Webhook routing (single diagram: how message type is chosen)

```
Create an animated architecture diagram (GIF or short video) that shows how an incoming WhatsApp message is routed by type. Animate the decision path: one message arrives, then show the branching.

Flow: AgriNexus AI – Webhook routing.

Steps to animate in order:
1. WhatsApp sends POST (message payload) to API Gateway.
2. API Gateway → Webhook Lambda.
3. Webhook Lambda: show "Verify signature" (checkmark or X). If invalid, show 403.
4. Webhook Lambda: "Dedup (WAMID in DynamoDB)" – if duplicate, show "Skip". If new, continue.
5. Webhook Lambda stores message in DynamoDB (for response detector).
6. Decision: "Message type?" – animate three branches one after the other (or three small animations):
   a. Audio → route to Voice Queue (arrow to Voice Queue icon).
   b. Text or Image → route to Message Queue (arrow to Message Queue icon).
   c. Text = "Done" / "Not yet" (e.g. हो गया) → Skip (no queue); show "handled by Response Detector via DynamoDB Streams".

Style: Clean flowchart with one decision box and three outgoing paths. Title: "AgriNexus AI – Webhook routing". Output: animated sequence or frame-by-frame description for a GIF.
```

---

## Tips for best results

- **Model:** Use a model that supports image or video generation (e.g. Gemini with image output, or ChatGPT with DALL·E / video). If the model only outputs text, you’ll get a frame-by-frame description to build the GIF elsewhere.
- **One flow per prompt:** Run one prompt at a time (text, voice, image, nudge, webhook) so each animation stays focused.
- **Resolution:** Ask for 1280×720 or 1920×1080 if the tool allows; good for slides and docs.
- **Loop:** Request a **looping GIF** (3–5 seconds per step, then repeat) so it can run in a slide or README.
- **Labels:** If the model generates a single image, ask for a **second version with step numbers overlaid** (1, 2, 3...) so you can animate by revealing them in order in a video editor.

Use these prompts as-is or adapt them for your preferred tool (e.g. add “in Mermaid diagram style” or “in draw.io style” if you want a different look). The flows match `architecture/diagrams.md` and the actual AgriNexus AI implementation.
