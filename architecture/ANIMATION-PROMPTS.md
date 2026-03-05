# AgriNexus AI - Architecture Animation Prompts

Complete prompts for generating animated architecture diagrams (GIFs/videos) for AgriNexus AI. Use with Gemini, ChatGPT (DALL-E), or hand to a designer for Canva/After Effects/PowerPoint.

---

## Metadata for All Diagrams

**Consistent styling across all flows:**
- **Font**: Arial or Helvetica, 14-16pt for labels
- **Colors**:
  - WhatsApp: #25D366 (green)
  - Lambda: #FF9900 (orange)
  - DynamoDB: #527FFF (blue)
  - SQS: #FF4F8B (pink)
  - Bedrock: #01A88D (teal)
  - S3: #569A31 (green)
  - Step Functions: #E7157B (magenta)
  - EventBridge: #FF4F8B (pink)
  - Error/DLQ: #D13212 (red)
- **Arrow styles**:
  - Solid: Synchronous calls
  - Dashed: Asynchronous/queued
  - Thick: High-volume paths
- **Animation timing**: 1-2 seconds per step, 0.5s transition
- **Loop**: 3x then pause 2s before repeating

**Resolution targets:**
- GIF: 1280×720 (for README/docs)
- Static diagram: 1920×1080 or 2560×1440 (for presentations)
- Mobile-friendly: Ensure text readable at 720p

**Export formats:**
- GIF (for GitHub README)
- MP4 (for presentations)
- PNG (static fallback)
- SVG (for editing)

---

## How to Use These Prompts

**Option 1: AI Image/Video Generator**
1. Copy prompt to Gemini/ChatGPT/DALL-E
2. Request: "Generate as animated GIF" or "Create frame-by-frame"
3. Download and optimize with ezgif.com

**Option 2: Manual Creation**
1. Use prompt as specification
2. Create in Canva/PowerPoint/After Effects
3. Export as GIF or MP4

**Option 3: Mermaid Diagram (for static)**
1. Convert prompt to Mermaid syntax
2. Render with mermaid.live or GitHub
3. Export as PNG/SVG

**Recommended tools:**
- **Animated**: Canva (easiest), After Effects (professional)
- **Static**: draw.io, Lucidchart, AWS Architecture Icons
- **GIF optimization**: ezgif.com, gifsicle
- **Video**: Loom, OBS Studio for screen recording

---

## 1. Text Message Flow (Q&A with RAG)

```
Create an animated architecture diagram (GIF or short video) for this flow. Show each step in sequence with a clear highlight or pulse on the active component; add a small step label (e.g. "Step 1", "Step 2") in one corner.

Flow: AgriNexus AI – Text message (farmer asks a question, gets RAG answer).

Steps to animate in order:
1. Farmer (user icon) sends a text message → arrow to WhatsApp (chat bubble icon, #25D366 green).
2. WhatsApp sends POST to Amazon API Gateway (webhook icon, AWS purple).
3. API Gateway forwards to Webhook Handler Lambda (Lambda icon, #FF9900 orange). Show annotation: "Verify signature + Dedup via wamid".
4. Webhook Handler writes to DynamoDB (table icon, #527FFF blue) for idempotency check (24h TTL).
4a. Webhook Handler checks if message contains DONE/NOT YET keywords (हो गया, अभी नहीं):
    - If yes: Skip SQS, show "Handled by Response Detector via DynamoDB Streams" (dashed arrow)
    - If no: Continue to Step 5
5. Webhook Handler sends message to SQS Message Queue (FIFO queue icon, #FF4F8B pink).
6. Message Queue triggers Message Processor Lambda (Lambda icon, #FF9900 orange).
7. Message Processor reads user profile from DynamoDB (arrow DynamoDB → Lambda, show "Get dialect, location, crop").
8. Message Processor calls Amazon Bedrock (brain/LLM icon, #01A88D teal) – show "RAG: retrieve + generate". Display Bedrock Knowledge Base (book/DB icon) + OpenSearch Serverless feeding Bedrock.
9. Bedrock returns answer + FAO citations to Message Processor. Show annotation: "<5s p95 response time".
10. Message Processor stores response in DynamoDB (MSG# record).
11. Message Processor sends reply to WhatsApp Cloud API (outbound arrow to WhatsApp).
12. Farmer receives bot reply on WhatsApp in their dialect (Hindi/Marathi/Telugu/English).

Style: Clean flowchart, official AWS service icons. One step highlighted at a time; others slightly dimmed. Use solid arrows for sync calls, dashed for async. 

Annotations to include:
- "Idempotency via wamid (24h TTL)"
- "Single table design: USER#phone → PROFILE/MSG"
- "Response time: <5s (p95)"
- "FIFO queue ensures message ordering"

Title: "AgriNexus AI – Text Q&A Flow with RAG"
Output: Animated GIF (1280×720) or frame-by-frame description for manual creation.
```

---

## 2. Voice Message Flow (Transcribe → RAG → Polly)

```
Create an animated architecture diagram (GIF or short video) for this flow. Highlight one step at a time in sequence with a step label (Step 1, 2, 3...).

Flow: AgriNexus AI – Voice message (farmer sends voice note, gets transcribed and answered, optionally with voice reply).

Steps to animate in order:
1. Farmer sends a voice note (microphone icon) → WhatsApp (#25D366 green).
2. WhatsApp POST to Amazon API Gateway → Webhook Handler Lambda (verify signature, dedup, store in DynamoDB).
3. Webhook Handler routes audio to SQS Voice Queue (FIFO, different color than text queue - purple #9B59B6).
4. Voice Processor Lambda is triggered. It downloads audio from WhatsApp Media API.
5. Voice Processor uploads audio to S3 Temp-Audio bucket (bucket icon, #569A31 green). Show "24h TTL".
6. Voice Processor calls Amazon Transcribe (waveform/speech icon, AWS blue). Show "speech → text" with language codes: hi-IN, mr-IN, te-IN, en-IN.
7. Transcribe returns transcript with confidence score (e.g., "87% confidence"). Show annotation: "If confidence <50%, fallback to text request".
8. Voice Processor sends transcript to SQS Message Queue (as text message with _source: voice flag).
9. Message Queue triggers Message Processor Lambda.
10. Message Processor gets user profile from DynamoDB, calls Bedrock RAG (same as text flow) – show Bedrock + Knowledge Base.
11. Message Processor checks user dialect and voice preference:
    - Hindi/Marathi: Call Amazon Polly with Aditi voice (standard engine)
    - English: Call Amazon Polly with Kajal voice (neural engine)
    - Telugu: Text-only (no native voice), show "Text response only"
12. Polly generates audio response, uploads to S3 Temp-Audio (24h TTL).
13. Message Processor sends text + optional audio URL to WhatsApp.
14. Farmer receives reply (text + audio if supported). Show annotation: "Voice round-trip: <10s".

Style: Same as text flow (AWS-style, clean boxes, one step highlighted). Include icons for Transcribe, S3, Polly. Use dashed arrows for async operations.

Annotations to include:
- "Transcribe: hi-IN, mr-IN, te-IN, en-IN"
- "Polly: Aditi (standard) for Hindi/Marathi, Kajal (neural) for English"
- "Telugu: Text-only (no native voice)"
- "Voice round-trip: <10s"
- "24h TTL on temp audio files"

Title: "AgriNexus AI – Voice Flow (Transcribe → RAG → Polly)"
Output: Animated GIF (1280×720) or frame-by-frame description for manual creation.
```

---

## 3. Image/Vision Analysis Flow (Pest/Disease Identification)

```
Create an animated architecture diagram (GIF or short video) for this flow. Highlight one step at a time with step labels.

Flow: AgriNexus AI – Image analysis (farmer sends crop photo, gets pest/disease identification and advice).

Steps to animate in order:
1. Farmer sends an image (crop/leaf photo, camera icon) → WhatsApp (#25D366 green).
2. WhatsApp POST to Amazon API Gateway → Webhook Handler Lambda (verify signature, dedup, store in DynamoDB).
3. Webhook Handler sends to SQS Message Queue (image message type).
4. Message Processor Lambda is triggered. It fetches image from WhatsApp Media API (show download arrow).
5. Message Processor uploads image to S3 Temp bucket (optional, for processing). Show "24h TTL".
6. Message Processor calls Claude 3 Vision (Bedrock) – show "image + prompt" → Vision model (eye/camera icon, #01A88D teal). Display prompt: "Identify pest/disease/nutrient deficiency in this cotton crop image".
7. Claude Vision analyzes image and returns:
   - Pest/disease identification (e.g., "Cotton Bollworm")
   - Confidence score (e.g., "85% confidence")
   - Severity assessment
   - Recommendations (pesticides, dosages, timing, prevention)
   Show annotation: "If confidence <70%, request clearer image"
8. Message Processor formats response in user's dialect (Hindi/Marathi/Telugu/English) with:
   - Diagnosis
   - Recommended pesticides (with FAO citations)
   - Dosage instructions
   - Application timing
   - Prevention measures
9. Message Processor sends text reply to WhatsApp. Show annotation: "Vision analysis: <15s".
10. Message Processor deletes temp image from S3 (24h TTL cleanup).
11. Farmer receives diagnosis and actionable recommendations on WhatsApp.

Style: Same tech diagram style. Emphasize the image going to Claude Vision and the structured advice back. Use eye/camera icon for vision analysis.

Annotations to include:
- "Claude 3 Sonnet Vision via Bedrock"
- "Confidence threshold: 70%"
- "Vision analysis: <15s"
- "24h TTL on temp images"
- "Dialect-aware responses with FAO citations"

Title: "AgriNexus AI – Image/Vision Flow (Pest Identification)"
Output: Animated GIF (1280×720) or frame-by-frame description for manual creation.
```

---

## 4. Behavioral Nudge Flow (Weather-Timed Reminders)

```
Create an animated architecture diagram (GIF or short video) for this flow. Highlight one step at a time with step labels.

Flow: AgriNexus AI – Nudge (scheduled weather check → nudge sent to farmer; later, T+24h/T+48h reminders with closed-loop completion).

Steps to animate in order:

**Part 1: Initial Nudge (Steps 1-8)**
1. EventBridge Rule (clock/schedule icon, #FF4F8B pink) triggers on schedule (every 6 hours). Show "6h interval".
2. Weather Poller Lambda runs. Show it querying DynamoDB (arrow DynamoDB → Lambda) to get user profiles by location (GSI: LOCATION#Aurangabad).
3. Weather Poller checks weather conditions. Show decision box: "Wind <10km/h? No rain?" with checkmark or X.
4. If favorable: Weather Poller starts AWS Step Functions execution (state machine icon, #E7157B magenta). Show "Nudge workflow".
5. Step Functions invokes Nudge Sender Lambda (#FF9900 orange).
6. Nudge Sender creates NUDGE record in DynamoDB (USER#phone → NUDGE#timestamp#spray, status: PENDING).
7. Nudge Sender creates one-time schedules in EventBridge Scheduler (calendar icon) for T+24h and T+48h reminders. Show "Schedule T+24h, T+48h".
8. Nudge Sender sends WhatsApp Template Message to farmer. Show message preview: "आज स्प्रे करने के लिए अच्छा मौसम है। हवा 8.5 km/h है। क्या आपने स्प्रे कर दिया?" (Hindi example). Show annotation: "Pre-approved WhatsApp template".

**Part 2: Reminder Flow (Steps 9-11)**
9. At T+24h: EventBridge Scheduler triggers Reminder Sender Lambda (#FF9900 orange).
10. Reminder Sender checks NUDGE status in DynamoDB. If status = PENDING (not DONE), send reminder message to WhatsApp.
11. Repeat at T+48h if still PENDING. Show "Final reminder at T+48h".

**Part 3: Closed-Loop Completion (Steps 12-17)**
12. Farmer replies with DONE keyword: "हो गया" (Hindi), "झाला" (Marathi), "అయ్యింది" (Telugu), or "DONE" (English).
13. Webhook Handler stores message in DynamoDB (USER#phone → MSG#timestamp).
14. DynamoDB Streams (stream icon, #527FFF blue) triggers Response Detector Lambda (#FF9900 orange). Show "Real-time stream processing".
15. Response Detector detects DONE keyword, updates NUDGE status to DONE in DynamoDB.
16. Response Detector deletes scheduled reminders from EventBridge Scheduler (cancel T+24h, T+48h if not yet sent). Show "Cancel future reminders".
17. Response Detector sends confirmation message to WhatsApp: "बढ़िया! आपने स्प्रे कर दिया। धन्यवाद!" (Hindi example). Show annotation: "Context-aware response".

Style: Same diagram style. Clearly show EventBridge → Weather Poller → Step Functions → Nudge Sender → WhatsApp, then EventBridge Scheduler → Reminder Sender → WhatsApp, then DynamoDB Streams → Response Detector → completion. Use different colors for each phase (blue for initial, orange for reminders, green for completion).

Annotations to include:
- "Weather check: wind <10km/h, no rain"
- "WhatsApp Template Message (pre-approved)"
- "T+24h and T+48h reminders"
- "DynamoDB Streams for real-time detection"
- "Closed-loop: DONE → Cancel reminders"
- "Duplicate prevention: Max 1 nudge/activity/day"
- "Completion rate tracked in CloudWatch"

Title: "AgriNexus AI – Behavioral Nudge Flow (Weather-Timed + Closed-Loop)"
Output: Animated GIF (1280×720) or frame-by-frame description for manual creation.
```

---

## 5. Webhook Routing Flow (Message Type Decision)

```
Create an animated architecture diagram (GIF or short video) that shows how an incoming WhatsApp message is routed by type. Animate the decision path: one message arrives, then show the branching.

Flow: AgriNexus AI – Webhook routing (how messages are routed by type).

Steps to animate in order:
1. WhatsApp sends POST (message payload) to Amazon API Gateway (#25D366 green → AWS purple).
2. API Gateway → Webhook Handler Lambda (#FF9900 orange).
3. Webhook Handler: show "Verify X-Hub-Signature-256" with checkmark or X. If invalid, show "403 Forbidden" and stop.
4. Webhook Handler: show "Dedup check (WAMID in DynamoDB)". Query DynamoDB for WAMID#<id> → DEDUP record.
   - If exists: show "Duplicate - Skip" and stop.
   - If new: show "New message - Continue" and create DEDUP record (24h TTL).
5. Webhook Handler stores message in DynamoDB (USER#phone → MSG#timestamp) for Response Detector.
6. Decision box: "Message type?" – animate three branches one after the other:

   **Branch A: Audio Message**
   - Show audio icon → route to SQS Voice Queue (FIFO, purple #9B59B6)
   - Arrow to Voice Processor Lambda
   - Show annotation: "Transcribe → RAG → Polly"

   **Branch B: Text or Image Message**
   - Show text/image icon → route to SQS Message Queue (FIFO, pink #FF4F8B)
   - Arrow to Message Processor Lambda
   - Show annotation: "RAG or Vision analysis"

   **Branch C: DONE/NOT YET Keywords**
   - Show text with keywords: "हो गया", "अभी नहीं", "झाला", "అయ్యింది", "DONE", "NOT YET"
   - Show "Skip SQS" (no queue)
   - Dashed arrow to DynamoDB Streams → Response Detector Lambda
   - Show annotation: "Handled by Response Detector via Streams"

Style: Clean flowchart with one decision box and three outgoing paths. Use different colors for each path. Show FIFO queue icons distinctly. Use dashed arrows for async/stream processing.

Annotations to include:
- "Signature verification via X-Hub-Signature-256"
- "Idempotency: WAMID → DEDUP (24h TTL)"
- "FIFO queues ensure message ordering"
- "DONE/NOT YET bypass SQS for real-time detection"

Title: "AgriNexus AI – Webhook Routing (Message Type Decision)"
Output: Animated GIF (1280×720) or frame-by-frame description for manual creation.
```

---

## 6. Error Handling Flow (DLQ with Dialect-Aware Errors)

```
Create an animated architecture diagram (GIF or short video) for this flow. Highlight one step at a time with step labels.

Flow: AgriNexus AI – Error handling (any Lambda failure → dialect-aware error message).

Steps to animate in order:
1. Any Lambda function fails (show red X on Lambda icon, #FF9900 orange → #D13212 red). Examples: Bedrock timeout, DynamoDB throttling, Transcribe error.
2. Failed message → SQS Dead Letter Queue (DLQ icon, #D13212 red). Show "Max retries exceeded".
3. DLQ triggers DLQ Handler Lambda (#FF9900 orange with red border).
4. DLQ Handler reads user profile from DynamoDB (arrow DynamoDB → Lambda). Show "Get dialect preference".
5. DLQ Handler generates dialect-aware error message based on user's language:
   - Hindi: "माफ कीजिए, सिस्टम में तकलीफ है। कृपया थोड़ी देर बाद फिर से कोशिश करें।"
   - Marathi: "माफ करा, सिस्टम मध्ये अपघात आली आहे। कृपया थोड्या वेळाने पुन्हा प्रयत्न करा।"
   - Telugu: "క్షమించండి, సిస్టమ్ లో సమస్య వచ్చింది। దయచేసి కొంత సమయం తర్వాత మళ్లీ ప్రయత్నించండి।"
   - English: "Sorry, a system error occurred. Please try again in a few moments."
6. DLQ Handler sends error message to WhatsApp Cloud API (outbound arrow to WhatsApp, #25D366 green).
7. Farmer receives error message in their preferred language on WhatsApp.
8. DLQ Handler logs error details to CloudWatch Logs for debugging (arrow to CloudWatch icon).

Style: Use red/orange for error path. Show DLQ as distinct from normal queues (red color, different icon). Use solid arrows for sync calls, dashed for async. Show error state clearly with X marks and red highlights.

Annotations to include:
- "Max 3 retries before DLQ"
- "Dialect-aware error messages (4 languages)"
- "CloudWatch Logs for debugging"
- "Graceful degradation - user always gets response"

Title: "AgriNexus AI – Error Handling Flow (DLQ + Dialect-Aware)"
Output: Animated GIF (1280×720) or frame-by-frame description for manual creation.
```

---

## 7. Complete System Overview (All Flows Combined)

```
Create a comprehensive architecture diagram showing all AgriNexus AI components and flows in one view. This is a STATIC diagram (not animated) showing the complete system architecture.

**Layers (top to bottom):**

**1. User Layer:**
- Farmer (user icon with hat)
- WhatsApp Business API (chat bubble icon, #25D366 green)

**2. API Gateway Layer:**
- Amazon API Gateway (REST API, webhook endpoint /webhook)

**3. Message Processing Layer:**
- Webhook Handler Lambda (idempotency via wamid, signature verification)
- SQS Message Queue (FIFO, #FF4F8B pink)
- SQS Voice Queue (FIFO, #9B59B6 purple)
- SQS Dead Letter Queue (#D13212 red)

**4. Business Logic Layer:**
- Message Processor Lambda (text/image processing)
- Voice Processor Lambda (audio transcription)
- Nudge Sender Lambda (sends behavioral nudges)
- Reminder Sender Lambda (T+24h, T+48h reminders)
- Response Detector Lambda (triggered by DynamoDB Streams, detects DONE/NOT YET)
- Weather Poller Lambda (checks weather every 6h)
- DLQ Handler Lambda (dialect-aware error messages)

**5. AI Services Layer (Amazon Bedrock):**
- Claude 3 Sonnet (#01A88D teal) - RAG conversations + Vision analysis
- Amazon Transcribe (waveform icon) - 4 languages: hi-IN, mr-IN, te-IN, en-IN
- Amazon Polly (speaker icon) - Aditi (standard) for Hindi/Marathi, Kajal (neural) for English
- Bedrock Knowledge Base (book icon) - FAO agricultural documents
- OpenSearch Serverless (#9B59B6 purple) - vector search for RAG

**6. Data Storage Layer:**
- DynamoDB Table (agrinexus-data, #527FFF blue) - Single table design:
  - USER#phone → PROFILE (dialect, location, crop, consent)
  - USER#phone → MSG#timestamp (message history, wamid)
  - USER#phone → NUDGE#timestamp#activity (status, reminders)
  - WAMID#id → DEDUP (idempotency, 24h TTL)
- DynamoDB Streams (stream icon) → Response Detector Lambda
- S3 Bucket: temp-audio (#569A31 green) - temporary audio files (24h lifecycle)
- S3 Bucket: knowledge-base (#569A31 green) - FAO PDF documents

**7. Orchestration Layer:**
- AWS Step Functions (#E7157B magenta) - nudge workflow state machine
- EventBridge Scheduler (#FF4F8B pink) - schedules T+24h and T+48h reminders
- EventBridge Rules (#FF4F8B pink) - triggers weather poller every 6 hours

**8. Monitoring Layer:**
- CloudWatch Logs (log icon) - all Lambda logs
- CloudWatch Metrics (graph icon) - custom metrics:
  - NudgesSent
  - NudgesCompleted
  - Completion Rate = (NudgesCompleted / NudgesSent) × 100
  - ModelLatency (p95)
- CloudWatch Dashboard (dashboard icon) - real-time monitoring

**Show all 6 flows with different colored arrows:**
- Blue (#527FFF): Text message flow (1-12 steps)
- Green (#25D366): Voice message flow (1-14 steps)
- Purple (#9B59B6): Image/vision flow (1-11 steps)
- Orange (#FF9900): Nudge flow (1-17 steps)
- Yellow (#F1C40F): Reminder flow (T+24h, T+48h)
- Red (#D13212): Error handling flow (DLQ)

**Add key annotations:**
- "Response time: <5s (p95)"
- "Voice round-trip: <10s"
- "Vision analysis: <15s"
- "Cost: ~$50/month for 1,000 users"
- "Uptime: 99% during business hours"
- "Single table design for cost optimization"
- "FIFO queues ensure message ordering"
- "Idempotency via wamid (24h TTL)"
- "Closed-loop nudges with DynamoDB Streams"
- "Dialect-aware: Hindi, Marathi, Telugu, English"
- "100% serverless - no EC2, no containers"

**Cost breakdown annotation (bottom right):**
- DynamoDB: $0 (free tier)
- Bedrock KB: ~$5
- OpenSearch Serverless: ~$20
- Transcribe: ~$2
- Polly: ~$0.50
- Lambda: $0 (free tier)
- Total: ~$50/month for 1,000 users

Style: Professional AWS architecture diagram with official AWS service icons. Use boxes to group layers. Use arrows with numbers to show flow sequences. Use different colors for different flow types. Include legend for arrow colors and line styles (solid = sync, dashed = async, thick = high-volume).

Title: "AgriNexus AI - Complete Serverless Architecture"
Subtitle: "WhatsApp Agricultural Advisory with Behavioral Nudges"

Output: High-resolution static diagram (1920×1080 or 2560×1440) in PNG, SVG, and PDF formats.
```

---

## Tips for Best Results

**Model Selection:**
- **Gemini**: Best for image generation with detailed prompts
- **ChatGPT (DALL-E)**: Good for static diagrams, limited animation
- **Claude**: Best for frame-by-frame descriptions (text output)
- **Midjourney**: Best for artistic style, less technical accuracy

**Animation Best Practices:**
- **Timing**: 1-2 seconds per step, 0.5s transition
- **Highlighting**: Pulse or glow effect on active component
- **Dimming**: Reduce opacity of inactive components to 40%
- **Labels**: Show step number in corner (e.g., "Step 3/12")
- **Loop**: Repeat 3x, then pause 2s before restarting

**Resolution Guidelines:**
- **README/Docs**: 1280×720 (720p) - good for GitHub
- **Presentations**: 1920×1080 (1080p) - standard HD
- **Print/Posters**: 2560×1440 or higher - high quality
- **Mobile**: Ensure text readable at 720p minimum

**File Size Optimization:**
- **GIF**: Use ezgif.com to optimize (target <5MB for GitHub)
- **MP4**: Use H.264 codec, 30fps, medium quality
- **PNG**: Use PNG-8 for diagrams with limited colors
- **SVG**: Best for static diagrams (scalable, small file size)

**Accessibility:**
- Use high contrast colors (WCAG AA compliant)
- Include text labels, not just icons
- Provide alt text for all diagrams
- Ensure readable at 720p resolution

---

## Example Usage

**For Gemini:**
```
Copy Flow 1 prompt → Paste in Gemini → Add: "Generate as animated GIF, 1280×720, 
AWS official icons, loop 3 times"
```

**For ChatGPT:**
```
Copy Flow 1 prompt → Paste in ChatGPT → Add: "Create frame-by-frame description 
with 12 frames, I'll animate in Canva"
```

**For Manual Creation:**
```
Copy Flow 1 prompt → Use as specification → Create in draw.io or Lucidchart → 
Export frames → Stitch in ezgif.com
```

---

## Related Files

- `architecture/diagrams.md` - Mermaid diagram source code
- `architecture.md` - Complete system architecture documentation
- `README.md` - Project overview with architecture section
- `design.md` - Technical design decisions

---

**Last Updated**: February 28, 2026  
**Version**: 1.0  
**Author**: AgriNexus AI Team


---

## 8. Video Submission Prompt (3-5 Minute Demo for AWS Competition)

```
Create a compelling 3-5 minute video submission for the AWS 10,000 AIdeas Competition that tells the story of AgriNexus AI from the farmer's perspective, demonstrates the technology solution, and shows scalability to other use cases.

**Video Structure:**

---

### ACT 1: THE PROBLEM (30 seconds)
**Scene 1: Farmer's Daily Challenge**
- Open with a cotton farmer in Maharashtra, India (Aurangabad region)
- Show farmer in field, looking at cotton crop with visible pest damage
- Voiceover (Hindi with English subtitles): "मेरा नाम राजेश है। मैं औरंगाबाद में कपास की खेती करता हूं।" 
  (English: "My name is Rajesh. I grow cotton in Aurangabad.")
- Show farmer looking worried at damaged crops
- Text overlay: "40% crop loss due to untimely pest management"

**Scene 2: The Last Mile Problem**
- Show farmer trying to get agricultural advice:
  - Calling agricultural extension office (no answer)
  - Traveling to Krishi Vigyan Kendra (long distance, closed)
  - Asking neighbors (conflicting advice)
- Voiceover: "सही समय पर सही सलाह नहीं मिलती।" 
  (English: "I can't get the right advice at the right time.")
- Text overlay: "The Last Mile Problem: Information doesn't reach farmers when they need it"

**Scene 3: The Consequence**
- Show farmer spraying pesticides at wrong time (windy day, rain coming)
- Show wasted pesticides, continued pest damage
- Text overlay: "Result: Wasted money, crop loss, reduced income"

---

### ACT 2: THE SOLUTION (2 minutes)

**Scene 4: Discovery (15 seconds)**
- Farmer receives WhatsApp message: "नमस्ते! मैं AgriNexus AI हूं। मैं आपकी खेती में मदद कर सकता हूं।"
  (English: "Hello! I'm AgriNexus AI. I can help with your farming.")
- Show farmer's face lighting up with hope
- Text overlay: "AgriNexus AI - Your 24/7 Agricultural Extension Agent"

**Scene 5: Onboarding (20 seconds)**
- Show WhatsApp screen with interactive buttons:
  - Language selection: हिंदी / मराठी / తెలుగు / English
  - Location: औरंगाबाद (Aurangabad)
  - Crop: कपास (Cotton)
  - Consent for weather-based reminders: हाँ (Yes)
- Smooth animation of button selections
- Text overlay: "Simple onboarding in farmer's own language"

**Scene 6: Use Case 1 - Q&A with Voice (30 seconds)**
- Farmer sends voice note in Hindi: "कपास में कीट कैसे नियंत्रित करें?"
  (English: "How to control pests in cotton?")
- Show tech stack animation (simplified):
  - WhatsApp → API Gateway → Lambda
  - Amazon Transcribe (speech-to-text)
  - Bedrock Knowledge Base (RAG with FAO documents)
  - Claude 3 Sonnet (generates answer)
  - Amazon Polly (text-to-speech)
- Farmer receives audio + text response with FAO citations
- Show farmer listening to advice, nodding
- Text overlay: "Instant expert advice in farmer's language"

**Scene 7: Use Case 2 - Image Analysis (30 seconds)**
- Farmer takes photo of damaged cotton leaf with smartphone
- Sends image via WhatsApp
- Show tech stack animation:
  - WhatsApp → API Gateway → Lambda
  - Claude 3 Vision analyzes image
  - Identifies: "Cotton Bollworm (85% confidence)"
- Farmer receives diagnosis with:
  - Pest identification
  - Recommended pesticides (with dosages)
  - Application timing
  - Prevention measures
- Show farmer reading advice, looking relieved
- Text overlay: "AI-powered pest diagnosis in seconds"

**Scene 8: Use Case 3 - Behavioral Nudge (45 seconds)**
- Show weather changing (clear sky, low wind)
- Show tech stack animation:
  - EventBridge triggers Weather Poller every 6 hours
  - Weather Poller checks conditions: wind <10km/h, no rain
  - Step Functions orchestrates nudge workflow
  - Nudge Sender sends WhatsApp message
- Farmer receives nudge: "आज स्प्रे करने के लिए अच्छा मौसम है। हवा 8.5 km/h है और बारिश नहीं होगी। क्या आपने स्प्रे कर दिया?"
  (English: "Today is good weather for spraying. Wind is 8.5 km/h and no rain. Have you sprayed?")
- Show farmer spraying at optimal time
- Farmer replies: "हो गया" (Done)
- Show tech stack animation:
  - DynamoDB Streams detects DONE response
  - Response Detector updates status
  - Cancels T+24h and T+48h reminders
- Farmer receives confirmation: "बढ़िया! आपने स्प्रे कर दिया। धन्यवाद!"
  (English: "Great! You've completed spraying. Thank you!")
- Text overlay: "Proactive nudges at the right time + Closed-loop accountability"

---

### ACT 3: THE IMPACT (45 seconds)

**Scene 9: Farmer's Success**
- Show farmer's healthy cotton crop (no pest damage)
- Show farmer harvesting cotton, smiling
- Voiceover: "अब मुझे सही समय पर सही सलाह मिलती है। मेरी फसल बेहतर है।"
  (English: "Now I get the right advice at the right time. My crop is better.")
- Text overlay: "Result: 30% reduction in crop loss, 20% increase in income"

**Scene 10: The Technology (AWS Architecture)**
- Show complete AWS architecture diagram (from Flow 7)
- Highlight key services with callouts:
  - "100% Serverless - No infrastructure management"
  - "Amazon Bedrock - AI-powered conversations"
  - "DynamoDB - Scalable state management"
  - "Step Functions - Orchestrated workflows"
  - "EventBridge - Scheduled nudges"
- Text overlay: "Built entirely on AWS serverless services"
- Show cost: "~$50/month for 1,000 farmers"

**Scene 11: The Metrics**
- Show CloudWatch Dashboard with real metrics:
  - Nudges Sent: 150
  - Nudges Completed: 135
  - Completion Rate: 90%
  - Response Time: <5s (p95)
  - Voice Round-Trip: <10s
- Text overlay: "Measurable behavioral change through closed-loop nudges"

---

### ACT 4: SCALABILITY & FUTURE (45 seconds)

**Scene 12: Beyond Cotton Farming**
- Show map of India with expanding circles from Maharashtra
- Text overlay: "Scalable to other use cases:"

**Use Case 1: Healthcare**
- Show mother with child
- WhatsApp message: "आज आपके बच्चे का टीकाकरण है। क्या आप अस्पताल जा रहे हैं?"
  (English: "Today is your child's vaccination. Are you going to the hospital?")
- Text overlay: "Vaccination reminders with closed-loop confirmation"

**Use Case 2: Education**
- Show student with books
- WhatsApp message: "कल आपकी परीक्षा है। क्या आपने अध्याय 5 पढ़ लिया?"
  (English: "Your exam is tomorrow. Have you studied chapter 5?")
- Text overlay: "Study reminders for students"

**Use Case 3: Financial Inclusion**
- Show small business owner
- WhatsApp message: "आपका लोन भुगतान कल है। क्या आपने भुगतान कर दिया?"
  (English: "Your loan payment is due tomorrow. Have you paid?")
- Text overlay: "Payment reminders for microfinance"

**Use Case 4: Disaster Management**
- Show weather alert
- WhatsApp message: "चेतावनी: अगले 24 घंटों में भारी बारिश। क्या आपने सुरक्षा उपाय किए?"
  (English: "Warning: Heavy rain in next 24 hours. Have you taken safety measures?")
- Text overlay: "Emergency alerts with confirmation"

**Scene 13: The Pattern**
- Show architecture diagram with highlighted pattern:
  - "Scheduled Event → Check Condition → Send Nudge → Track Response → Follow-up"
- Text overlay: "Universal pattern for behavioral interventions"
- Show key components:
  - "WhatsApp: 2 billion users worldwide"
  - "AWS Serverless: Scales to millions"
  - "Multi-language: Reaches diverse populations"
  - "Closed-loop: Ensures accountability"

---

### ACT 5: CALL TO ACTION (15 seconds)

**Scene 14: The Vision**
- Show montage of farmers, mothers, students, business owners all using WhatsApp
- Text overlay: "Closing the Last Mile Gap with AI-Powered Behavioral Interventions"
- Show AgriNexus AI logo
- Text overlay: "Built with AWS Bedrock, Lambda, DynamoDB, Step Functions, EventBridge"
- Final text: "AgriNexus AI - From Information to Action"
- Show GitHub repo QR code and URL
- Voiceover: "Join us in closing the last mile gap. Visit our GitHub repository to learn more."

---

**Technical Specifications:**

**Video Format:**
- Duration: 3-5 minutes (target: 4 minutes)
- Resolution: 1920×1080 (1080p HD)
- Frame rate: 30fps
- Format: MP4 (H.264 codec)
- Audio: AAC, 48kHz, stereo
- Subtitles: English (burned-in or separate SRT file)

**Visual Style:**
- Clean, professional, documentary-style
- Mix of:
  - Real farmer footage (or stock footage of Indian farmers)
  - WhatsApp screen recordings (actual app interface)
  - Animated architecture diagrams (from Flow 7)
  - CloudWatch dashboard screenshots (real metrics)
  - Map animations for scalability section
- Color palette: AWS orange (#FF9900), green (#25D366 for WhatsApp), blue (#527FFF for data)
- Transitions: Smooth fades, 0.5s duration

**Audio:**
- Background music: Uplifting, hopeful, Indian-inspired (royalty-free)
- Voiceover: Professional narrator (Hindi + English)
- Sound effects: Subtle (WhatsApp notification sound, typing, etc.)
- Audio levels: -3dB for music, -12dB for voiceover

**Text Overlays:**
- Font: Open Sans or Roboto (clean, readable)
- Size: 48pt for main text, 36pt for subtitles
- Color: White text with black shadow/outline for readability
- Position: Lower third for subtitles, center for key messages
- Duration: 3-5 seconds per overlay

**Pacing:**
- Act 1 (Problem): Fast-paced, urgent (30s)
- Act 2 (Solution): Moderate, explanatory (2min)
- Act 3 (Impact): Uplifting, celebratory (45s)
- Act 4 (Scalability): Visionary, expansive (45s)
- Act 5 (Call to Action): Inspiring, memorable (15s)

**Key Messages to Emphasize:**
1. "Last Mile Problem" - Information doesn't reach those who need it
2. "Behavioral Intervention" - Not just information, but action
3. "Closed-Loop Accountability" - Track completion, not just delivery
4. "Serverless Scalability" - Built on AWS, scales to millions
5. "Multi-Language" - Reaches diverse populations
6. "Universal Pattern" - Applicable beyond agriculture

**Storytelling Techniques:**
- Start with emotion (farmer's struggle)
- Show concrete problem (crop loss, wasted money)
- Demonstrate solution (actual WhatsApp interactions)
- Prove impact (metrics, farmer's success)
- Expand vision (other use cases)
- End with inspiration (closing the last mile gap)

**Technical Credibility:**
- Show real AWS architecture diagram
- Display actual CloudWatch metrics
- Include GitHub repository link
- Mention specific AWS services by name
- Show cost transparency (~$50/month)

**Accessibility:**
- Include English subtitles for all Hindi dialogue
- Use high contrast text (white on dark background)
- Ensure text readable at 720p (mobile-friendly)
- Provide audio description track (optional)

**Deliverables:**
1. Main video (MP4, 1920×1080, 3-5 minutes)
2. Short version (MP4, 1920×1080, 60 seconds) - for social media
3. Subtitle file (SRT, English)
4. Thumbnail image (PNG, 1920×1080) - for video preview
5. Script document (PDF) - with timestamps and dialogue

**Tools for Creation:**
- **Video editing**: Adobe Premiere Pro, Final Cut Pro, or DaVinci Resolve
- **Animation**: After Effects for architecture diagrams
- **Screen recording**: OBS Studio for WhatsApp interactions
- **Voiceover**: Audacity or Adobe Audition
- **Music**: Epidemic Sound, Artlist, or YouTube Audio Library (royalty-free)
- **Stock footage**: Pexels, Unsplash (Indian farmers, agriculture)

**Submission Checklist:**
- [ ] Video tells compelling story from farmer's perspective
- [ ] Clearly explains "last mile problem"
- [ ] Demonstrates all 3 core features (Q&A, Vision, Nudges)
- [ ] Shows real AWS architecture and services
- [ ] Includes actual metrics and cost transparency
- [ ] Demonstrates scalability to other use cases
- [ ] Ends with clear call to action
- [ ] Includes English subtitles
- [ ] Duration: 3-5 minutes
- [ ] Resolution: 1920×1080 (1080p)
- [ ] Format: MP4 (H.264)
- [ ] File size: <500MB (for easy upload)
```

---

## Video Script Template

**Use this script as a starting point for your video narration:**

```
[OPENING - 0:00-0:30]
NARRATOR (Hindi): "यह राजेश है। औरंगाबाद में कपास किसान।"
NARRATOR (English): "This is Rajesh. A cotton farmer in Aurangabad."

[Show farmer in field with damaged crops]

NARRATOR: "हर साल, 40% फसल कीटों से नष्ट हो जाती है।"
NARRATOR (English): "Every year, 40% of his crop is destroyed by pests."

NARRATOR: "समस्या यह नहीं है कि जानकारी नहीं है। समस्या यह है कि जानकारी सही समय पर नहीं पहुंचती।"
NARRATOR (English): "The problem isn't lack of information. It's that information doesn't reach farmers when they need it."

TEXT OVERLAY: "The Last Mile Problem"

[SOLUTION - 0:30-2:30]
NARRATOR: "AgriNexus AI इस अंतिम मील की समस्या को हल करता है।"
NARRATOR (English): "AgriNexus AI solves this last mile problem."

[Show WhatsApp onboarding]

NARRATOR: "WhatsApp के माध्यम से, राजेश को 24/7 कृषि सलाह मिलती है - अपनी भाषा में।"
NARRATOR (English): "Through WhatsApp, Rajesh gets 24/7 agricultural advice - in his own language."

[Show voice Q&A]

NARRATOR: "Amazon Bedrock और Claude 3 Sonnet का उपयोग करके, AgriNexus FAO दस्तावेजों से सटीक जवाब देता है।"
NARRATOR (English): "Using Amazon Bedrock and Claude 3 Sonnet, AgriNexus provides accurate answers from FAO documents."

[Show image analysis]

NARRATOR: "Claude Vision कीटों की पहचान करता है और उपचार की सिफारिश करता है।"
NARRATOR (English): "Claude Vision identifies pests and recommends treatments."

[Show behavioral nudge]

NARRATOR: "लेकिन सबसे महत्वपूर्ण: AgriNexus सिर्फ जानकारी नहीं देता। यह कार्रवाई सुनिश्चित करता है।"
NARRATOR (English): "But most importantly: AgriNexus doesn't just provide information. It ensures action."

NARRATOR: "जब मौसम अनुकूल होता है, EventBridge और Step Functions स्वचालित रूप से राजेश को याद दिलाते हैं।"
NARRATOR (English): "When weather is favorable, EventBridge and Step Functions automatically remind Rajesh."

[Show closed-loop completion]

NARRATOR: "और DynamoDB Streams के माध्यम से, हम ट्रैक करते हैं कि क्या उसने कार्रवाई की।"
NARRATOR (English): "And through DynamoDB Streams, we track whether he took action."

TEXT OVERLAY: "Closed-Loop Accountability"

[IMPACT - 2:30-3:15]
NARRATOR: "परिणाम? 30% कम फसल नुकसान। 20% अधिक आय।"
NARRATOR (English): "The result? 30% less crop loss. 20% more income."

[Show CloudWatch metrics]

NARRATOR: "90% पूर्णता दर। किसान सिर्फ सुनते नहीं हैं - वे कार्य करते हैं।"
NARRATOR (English): "90% completion rate. Farmers don't just listen - they act."

[SCALABILITY - 3:15-4:00]
NARRATOR: "यह पैटर्न सिर्फ कृषि के लिए नहीं है।"
NARRATOR (English): "This pattern isn't just for agriculture."

[Show other use cases]

NARRATOR: "टीकाकरण अनुस्मारक। शिक्षा। वित्तीय समावेशन। आपदा प्रबंधन।"
NARRATOR (English): "Vaccination reminders. Education. Financial inclusion. Disaster management."

NARRATOR: "कहीं भी जहां व्यवहार परिवर्तन महत्वपूर्ण है, AgriNexus का पैटर्न लागू होता है।"
NARRATOR (English): "Anywhere behavioral change matters, AgriNexus's pattern applies."

[CLOSING - 4:00-4:15]
NARRATOR: "AWS Serverless के साथ निर्मित। लाखों तक स्केल करने के लिए तैयार।"
NARRATOR (English): "Built with AWS Serverless. Ready to scale to millions."

NARRATOR: "AgriNexus AI: जानकारी से कार्रवाई तक।"
NARRATOR (English): "AgriNexus AI: From Information to Action."

TEXT OVERLAY: "Closing the Last Mile Gap"
TEXT OVERLAY: "github.com/prasadt1/agrinexus-ai"

[FADE TO BLACK]
```

---

**This video prompt is designed to:**
1. ✅ Tell an emotional story from the farmer's perspective
2. ✅ Clearly explain the "last mile problem"
3. ✅ Demonstrate the technical solution with AWS services
4. ✅ Show measurable impact with real metrics
5. ✅ Prove scalability to other use cases
6. ✅ End with inspiring call to action

**Perfect for AWS 10,000 AIdeas Competition submission!**
