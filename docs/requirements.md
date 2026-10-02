# AgriNexus AI - Requirements Specification

**Project**: AgriNexus AI - Behavioral AI Extension Agent for Smallholder Farmers  
**Competition**: AWS 10,000 AIdeas Competition (Social Impact Track)  
**Deadline**: March 13, 2026  
**Version**: 1.0  
**Date**: February 13, 2026

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements for AgriNexus AI, a behavioral intervention engine and behavioral AI extension agent designed to close the "last mile" gap in agricultural extension for smallholder farmers. Unlike reactive information systems, AgriNexus utilizes a proactive, weather-timed behavioral nudge engine with closed-loop accountability to ensure agronomic advice translates into field action.

### 1.2 Scope
AgriNexus AI delivers agronomic advice through WhatsApp, using Amazon Bedrock for dialect-aware conversations (Hindi, Marathi, Telugu), EventBridge Scheduler for behavioral nudges, Claude 3 Vision for pest diagnosis, and Amazon Transcribe + Polly for voice accessibility. The system prioritizes trust through dialect-native voice interactions and evidence-backed citations from validated FAO sources.

### 1.3 Architecture
Serverless architecture with pay-as-you-go Bedrock. **Current stack** (Bedrock Knowledge Base with **S3 Vectors**, migrated April 2026): estimated **~$53/month** for 1,000 active farmers (S3 vectors ~$1.30 + Bedrock ~$39 + other ~$13—see `README.md`). Older documentation referenced OpenSearch Serverless (~$174/month fixed) and **~$214/month** totals; that cost model applies only to historical deployments. At 10,000 farmers, modeled cost is on the order of **~$0.54–0.70/farmer/year** depending on usage.

### 1.4 EARS Syntax Convention
All functional requirements follow EARS (Easy Approach to Requirements Syntax):
- **Ubiquitous**: The [System] shall [Response]
- **Event-driven**: When [Event], the [System] shall [Response]
- **State-driven**: While [State], the [System] shall [Response]
- **Optional**: Where [Feature], the [System] shall [Response]
- **Unwanted**: If [Condition], then the [System] shall [Response]

### 1.5 Core Success Metric

**Primary Metric**: Nudge Completion Rate  
**Calculation**: (Confirmed DONE Responses / Total Favorable-Condition Nudges Sent) × 100  
**Tracking Window**: A response must be confirmed within 72 hours of the initial nudge to be counted

## 2. Functional Requirements

### 2.1 User Onboarding (Tier 1 - Full Depth)

**REQ-ONBOARD-001**: When a farmer sends their first message to the system, the system shall initiate the onboarding workflow.

**REQ-ONBOARD-002**: When onboarding starts, the system shall send a welcome message explaining AgriNexus AI's purpose and capabilities.

**REQ-ONBOARD-003**: The system shall use WhatsApp Interactive Buttons for dialect selection presenting options: Hindi, Marathi, Telugu.

**REQ-ONBOARD-004**: When the farmer selects a dialect, the system shall store the language preference in DynamoDB and continue onboarding in that dialect.

**REQ-ONBOARD-005**: The system shall prompt for location via district/village name, validated against a district lookup table.

**REQ-ONBOARD-006**: If location validation fails, then the system shall ask the user to clarify or select from nearby districts.

**REQ-ONBOARD-007**: The system shall use WhatsApp Interactive Buttons for crop selection presenting common options (Cotton, Wheat, Rice, Soybean, Other).

**REQ-ONBOARD-008**: When the farmer selects "Other", the system shall accept free-text input for the crop type.

**REQ-ONBOARD-009**: The system shall request the farmer's farm size (optional) in local units (acres or hectares).

**REQ-ONBOARD-010**: When all required information is collected, the system shall explain data usage and request consent before completing registration.

**REQ-ONBOARD-011**: The system shall inform the user they can send STOP at any time to disable nudges, or DELETE MY DATA to remove their profile.

**REQ-ONBOARD-012**: When onboarding is complete, the system shall send a confirmation message with a summary of stored information and instructions on how to ask questions.

**REQ-ONBOARD-013**: If a farmer abandons onboarding mid-process, then the system shall save partial profile data and resume onboarding on their next message.

**REQ-ONBOARD-014**: The system shall complete the onboarding process within 6 conversational turns to minimize friction.

**REQ-ONBOARD-015**: When a returning farmer with incomplete profile sends a message, the system shall resume onboarding before processing their query.

### 2.2 Dialect-Native Conversation (Tier 1 - Full Depth)

**REQ-CONV-001**: When a farmer sends a message via WhatsApp, the system shall process it using Amazon Bedrock Agent Runtime (`retrieve_and_generate`) with the Claude model configured by the `BedrockModelId` SAM parameter.

**REQ-CONV-002**: When the Bedrock agent receives a query, the system shall retrieve relevant agronomic knowledge from the S3-backed knowledge base using RAG (Retrieval Augmented Generation).

**REQ-CONV-003**: The system shall respond to farmer queries in Hindi, Marathi, or Telugu based on the user's profile dialect preference.

**REQ-CONV-004** (amended 2 Oct 2026): When a retrieved document name is available, the advisory response shall name it as the source. When none is available, the system shall not add a generic source line. Source lines written by the model shall be removed. Knowledge base refusals shall carry no source line.

**REQ-CONV-005**: The system shall log the full source attribution (document name, chunk, confidence score) to CloudWatch for auditability.

**REQ-CONV-006**: When the Bedrock agent generates a response, the system shall apply configured guardrails to ensure safe and appropriate content.

**REQ-CONV-007**: If a query cannot be answered from the knowledge base, then the system shall provide a fallback response directing the farmer to contact their local Krishi Vigyan Kendra (KVK).

**REQ-CONV-008**: The system shall handle code-switching naturally (e.g., Hinglish - mixed Hindi/English).

### 2.3 Knowledge Base Management (Tier 1 - Full Depth)

**REQ-KB-001**: The system shall store validated agricultural PDF manuals in S3 in English only, organized by topic.

**REQ-KB-002**: When PDFs are uploaded to S3, the system shall trigger Bedrock knowledge base synchronization.

**REQ-KB-003**: The system shall maintain metadata for each knowledge base document including source URL, publication date, validation date, and locale applicability.

**REQ-KB-004**: The system shall version knowledge base content to enable rollback if needed.

**REQ-KB-005**: The system shall implement 20 "golden question" evaluation tests to measure RAG retrieval quality with accuracy target ≥90% on factual crop data, tested across all three dialects (Hindi, Marathi, Telugu).

### 2.4 Safety Guardrails (Tier 1 - Full Depth)

**REQ-GUARD-001** (rewritten 2 Oct 2026): The system shall not name a pesticide on India's banned list (CIB&RC "banned for manufacture, import and use", plus endosulfan) in any farmer-facing advice. The output filter (REQ-GUARD-008 to 010) enforces this: it lists those actives by name in Latin script, and the commonest in Devanagari and Telugu. A question asking for a banned pesticide receives the pesticide policy reply (REQ-GUARD-013). Questions are not blocked on input; the earlier wording promised input-side blocking that was never built.

**REQ-GUARD-002** (retired 2 Oct 2026, superseded by REQ-GUARD-008): ~~The system shall include explicit disclaimers when providing pesticide dosage information, directing farmers to read product labels.~~

**REQ-GUARD-003**: The system shall escalate to "contact your local Krishi Vigyan Kendra (KVK)" for severe infestations, unknown diseases, livestock health, and human health concerns.

**REQ-GUARD-004** (folded into REQ-GUARD-008, 2 Oct 2026): The system shall not recommend specific pesticide brands or commercial products.

**REQ-GUARD-005**: The system shall include a disclaimer that advice is supplementary and does not replace professional agricultural extension services.

**REQ-GUARD-006**: The system shall refuse to provide medical advice for humans or animals.

**REQ-GUARD-007**: The guardrail test suite shall include at minimum: 5 banned pesticide scenarios, 5 medical/veterinary advice attempts, 5 dosage-specific queries, 5 edge cases (e.g., mixing chemicals, organic certification claims).

#### Identify and refer (added 2 Oct 2026)

The product identifies the pest or problem and gives non-chemical steps. It does not name pesticide products or doses on any channel; chemical choice and rate are referred to the farmer's local KVK. The photo path has no retrieval and no citations, so any product name or rate it produced came from the model's own knowledge.

**REQ-GUARD-008**: The system shall not include a pesticide product name, brand, active ingredient, formulation strength or application dose in any farmer-facing advice message on WhatsApp text, WhatsApp voice, WhatsApp photo, or web chat.

**REQ-GUARD-009**: When a farmer-facing advice message is ready to send, the system shall pass it through the advice output filter before sending it and before converting it to speech.

**REQ-GUARD-010** (amended 2 Oct 2026): If the output filter detects an active ingredient name, a brand, a name ending typical of a pesticide class (for example -fos, -thrin, -conazole, -cloprid, -mectin), a formulation strength, a dilution, or a small-unit amount per acre or hectare in a sentence, then the system shall remove that sentence and keep the rest of the message. Quantities written as digits or as number words (English, Hindi, Marathi, Telugu) count. A bare quantity shall be removed only when the same sentence concerns spraying, mixing, a pesticide, neem or a trap, or uses an apply/use verb and is not about fertilizer, seed or irrigation.

**REQ-GUARD-011**: When the output filter removes content, the system shall emit the CloudWatch metric `AgriNexus/Advice` `AdviceFilterHit` with the channel and the kind of match.

**REQ-GUARD-012**: The system shall end every advice message with a line in the farmer's language stating that the answer is automated and can be wrong and directing the farmer to the nearest KVK for the pesticide and quantity, and shall carry any contact details in that same footer rather than adding a second one.

**REQ-GUARD-013**: When a farmer asks which pesticide to use or how much, the system shall reply with the identification and non-chemical steps it can give plus the KVK referral, and shall not name a product.

**REQ-GUARD-014**: The system may name neem, yellow sticky traps and pheromone traps as practices, and shall not state a quantity or dilution for them.

**REQ-GUARD-015**: Every Bedrock model call on the WhatsApp photo path shall carry the content guardrail. If the guardrail intervenes on a diagnosis call, the system shall send only the localized farming-only refusal for that photo and no diagnosis.

### 2.5 Visual Verification (Tier 2 - Working Implementation)

**REQ-VIS-001**: When a farmer sends an image via WhatsApp, the system shall process it using Claude 3 Vision via direct invoke_model API (separate from the Bedrock Agent conversation flow).

**REQ-VIS-002** (amended 2 Oct 2026): The system shall respond with diagnosis, severity, non-chemical steps, confidence and the KVK referral, in the user's dialect.

**REQ-VIS-003**: When confidence is below 70%, the system shall request a clearer image with specific guidance in the user's dialect (e.g., Hindi: "Photo thoda paas se lein" / "Take a closer photo").

**REQ-VIS-004**: The system shall respond within 15 seconds for image analysis.

**REQ-VIS-005**: When visual analysis is complete, the system shall delete the temporary image from S3 to minimize storage costs.

**REQ-VIS-006**: One working happy path (cotton pest image → diagnosis in user's dialect) is sufficient for MVP demo.

**REQ-VIS-007** (added 2 Oct 2026): Before diagnosis, the system shall classify each photo as farm photo, not a farm photo, or unclear, using a model that is in service on Bedrock. Photos of crop pests (insects, larvae, caterpillars, mites) shall count as farm photos. When the check errors or is blocked by the guardrail, the photo shall be treated as unclear and still pass through the diagnosis model's own non-photo check.

### 2.6 Behavioral Nudge Engine (Tier 1 - Full Depth)

**REQ-NUDGE-001**: The system shall poll weather data via EventBridge scheduled rules at 6-hour intervals.

**REQ-NUDGE-002**: When weather conditions match a favorable window for agricultural activities (wind <10km/h, no rain forecast), the system shall trigger the nudge workflow in Step Functions.

**REQ-NUDGE-003**: When a nudge is triggered, the system shall retrieve farmer profiles from DynamoDB filtered by location and crop type.

**REQ-NUDGE-004**: The system shall send personalized behavioral nudges via WhatsApp containing the recommended action and timing rationale.

**REQ-NUDGE-005**: When a nudge is sent, the system shall create EventBridge Scheduler records for T+24h and T+48h reminders.

**REQ-NUDGE-006**: When the T+24h reminder time arrives, the system shall check DynamoDB status and send a follow-up message if not marked DONE.

**REQ-NUDGE-007**: When the T+48h reminder time arrives, the system shall check DynamoDB status and send a second follow-up message if not marked DONE.

**REQ-NUDGE-008**: When a farmer responds with DONE keywords (Hindi: "ho gaya", "kar diya"; Marathi: "zhala"; Telugu: "ayyindi"; English: "done"), the system shall mark the task as completed in DynamoDB and delete pending EventBridge Scheduler records.

**REQ-NUDGE-009**: When a farmer responds with NOT YET keywords (Hindi: "abhi nahi", "baad mein"; Marathi: "nahi zhala"; Telugu: "inkaa ledu"; English: "not yet"), the system shall log the response and continue with scheduled reminders.

**REQ-NUDGE-010**: If no response is received within 72 hours, then the system shall mark the nudge as "no_response" and log for analytics.

**REQ-NUDGE-011**: The system shall limit nudges to a maximum of 2 per farmer per day to avoid notification fatigue.

### 2.7 WhatsApp Integration (Tier 1 - Full Depth)

**REQ-WA-001**: When a WhatsApp message is received, the system shall validate the webhook signature (X-Hub-Signature-256) to ensure authenticity.

**REQ-WA-002**: The system shall accept incoming messages via API Gateway webhook endpoint configured for WhatsApp Business API.

**REQ-WA-003**: The system shall return HTTP 200 OK within 2 seconds to avoid WhatsApp timeout.

**REQ-WA-004**: The system shall use WhatsApp message ID (wamid) as an idempotency key to prevent duplicate processing of webhook retries.

**REQ-WA-005**: The system shall use DynamoDB conditional writes for nudge status updates to prevent race conditions from duplicate responses.

**REQ-WA-006**: When sending responses, the system shall format messages according to WhatsApp Business API specifications.

**REQ-WA-007**: The system shall support text messages, images, and audio messages as input formats.

**REQ-WA-008**: The system shall use registered WhatsApp message templates for nudges and alerts.

### 2.8 Voice Input/Output (Tier 2 - Working Implementation)

**REQ-VOICE-001**: When a user sends a voice note via WhatsApp, the system shall transcribe it using Amazon Transcribe.

**REQ-VOICE-002**: When transcription completes, the Bedrock Agent shall process the transcribed text as a standard message.

**REQ-VOICE-003**: When a user has sent a voice note (or has voice preference enabled), the system shall respond with audio via Amazon Polly using Hindi Aditi/Neural voice.

**REQ-VOICE-004**: If transcription confidence is below 0.5, then the system shall fall back to a text response asking the user to resend or type their question.

**REQ-VOICE-005**: Marathi and Telugu voice output is best-effort — if Polly lacks native voices, the system shall respond with text in those dialects.

**REQ-VOICE-006**: The MVP shall complete voice round-trip (batch Transcribe → Bedrock → Polly → WhatsApp) with typical end-to-end latency **~30–45 seconds**; a short **voice-received** text is sent from the webhook immediately after accept. **Phase 2** (streaming STT / pipeline optimization) targets **sub-10s** — see `docs/VOICE-LATENCY-PHASE2-PLAN.md`.

**REQ-VOICE-007**: Amazon Transcribe support for Marathi and Telugu shall be verified; if unavailable, voice input falls back to Hindi-only for MVP while text input works for all three dialects.

### 2.9 User State Management (Tier 1 - Full Depth)

**REQ-STATE-001**: When a new farmer first interacts with the system, the system shall create a user profile in DynamoDB single table `agrinexus-data` with PK=USER#<phone>, SK=PROFILE.

**REQ-STATE-002**: The system shall store farmer location (district and state) in the user profile.

**REQ-STATE-003**: The system shall store primary crop type(s) in the user profile for targeted nudges.

**REQ-STATE-004**: The system shall store preferred dialect (Hindi, Marathi, or Telugu) in the user profile.

**REQ-STATE-005**: The system shall store voice preference and consent status in the user profile.

**REQ-STATE-006**: When a conversation occurs, the system shall store messages in DynamoDB with PK=USER#<phone>, SK=MSG#<timestamp>, including wamid, source_citation, and TTL (90 days).

**REQ-STATE-007**: The system shall track nudge history with PK=USER#<phone>, SK=NUDGE#<timestamp>#<activity>, including status, scheduledReminderAt, and TTL (180 days).

**REQ-STATE-008**: When user profile data is updated, the system shall timestamp the modification for audit purposes.

### 2.9b re:Invent visitor path (conference demo)

**REQ-VISITOR-001**: When an unknown number’s first message contains `re:invent` or `reinvent` (case-insensitive), the system shall enter the visitor path and shall not run farmer onboarding.

**REQ-VISITOR-002**: On visitor entry, the system shall reply in English with a short welcome and an interactive list of five sample questions plus a photo-diagnosis option and a farmer-onboarding option.

**REQ-VISITOR-003**: The system shall accept free-text farming questions from visitors in English via the existing RAG path.

**REQ-VISITOR-004**: When a visitor selects the photo-diagnosis list option, the system shall run the real vision path on the stored sample image and return the model result.

**REQ-VISITOR-005**: While `demo_tier` is `visitor`, the system shall accept visitor-uploaded crop photos through the real vision path, subject to the same visitor answer caps.

**REQ-VISITOR-006**: Visitor profiles shall use `demo_tier=visitor` and `source=reinvent-2026`, with TTL of `VisitorTtlDays` (default 7) on profile and conversation items.

**REQ-VISITOR-007**: The system shall not send nudges, reminders, or any other proactive messages to visitor-tier numbers.

**REQ-VISITOR-008**: The system shall enforce a per-visitor daily answer cap and a global daily visitor answer cap (SAM parameters; defaults 10 and 300); on either cap, it shall send one fixed message and shall not call Bedrock.

**REQ-VISITOR-009** (amended 2 Oct 2026): Allowlisted numbers shall be exempt from visitor caps. A number counts as allowlisted only while it has an approved allowlist row whose `expires_at`, if set, is in the future; a missing row, a past or unreadable `expires_at`, or a lookup error counts as not allowlisted.

**REQ-VISITOR-010**: Visitor activity shall be counted separately and shall not increment farmer nudge sent/completed metrics.

**REQ-CROP-001**: When a real crop photo shows a visible problem, crop confidence is not `high`, and the model's inferred crop does not contradict the farmer's registered crop, the system shall return the full diagnosis using the registered crop, state that assumption in the message, and offer a one-reply correction.

**REQ-CROP-002**: When a real crop photo shows a visible problem and either no crop is registered or the model's inferred crop contradicts the registered crop, the system shall state what was observed and then ask the farmer to pick the crop. This applies at any crop confidence, including `high`.

**REQ-CROP-003**: While a crop-confirm reply is pending from an assumed-crop answer, the system shall treat only a reply of at most three words naming a different crop as a correction.

**REQ-CROP-004**: When the crop a farmer picks contradicts the crop the model inferred from the image, the system shall ask once more before returning crop-specific advice, and shall accept the farmer's second answer.

**REQ-CROP-005**: When a crop is supplied as fact (farmer-confirmed, assumed from profile, or configured for the visitor sample), the system shall state the crop as given in the vision prompt, shall not ask for another photo to identify the crop, and shall return the four-section diagnosis, severity, recommendations and confidence output.

**REQ-CROP-006**: When a message is sent under an assumed crop, the confidence section shall state that the pest reading is the model's and the crop is taken from the profile and not confirmed from the photo, keeping the model's own confidence wording.

**REQ-I18N-001**: Section labels shall use the farmer's own language; Marathi output shall not reuse Hindi labels.

**REQ-PRIV-001** (amended 2 Oct 2026): When any number sends `DELETE` or `DELETE MY DATA`, the system shall erase that number’s profile and conversation rows and its stored photos (`images/`), voice notes (`voice/`) and spoken replies (`voice-output/`), and confirm in one message. Media under those prefixes also expires automatically (photos 7 days, voice notes and spoken replies 1 day).

**REQ-SEC-GUARD-001**: WhatsApp RAG and web-chat RAG shall invoke the configured Bedrock Guardrail (content filters, prompt-attack filter, and a polite redirect for non-farming questions).

### 2.10 Profile Management (Tier 3 - Cut for MVP)

**REQ-PROFILE-001**: The system shall support a RESET command to re-initiate onboarding for profile updates.

**REQ-PROFILE-002**: The system shall allow farmers to delete their profile and all associated data by sending a "DELETE MY DATA" command. *(Implemented via **REQ-PRIV-001**; `DELETE` is also accepted.)*

**REQ-PROFILE-003**: When a deletion request is received, the system shall confirm the action and require explicit confirmation before proceeding.

**REQ-PROFILE-004**: When profile deletion is confirmed, the system shall remove all user data from DynamoDB within 24 hours and send a final confirmation.

### 2.11 Help and Support (Tier 2 - Working Implementation)

**REQ-HELP-001**: When a farmer sends "HELP" or equivalent command, the system shall provide a menu of available commands and features.

**REQ-HELP-002**: The system shall provide examples of questions farmers can ask (e.g., "When should I spray cotton?", "How do I control aphids?").

**REQ-HELP-003**: When a farmer sends "ABOUT", the system shall provide information about AgriNexus AI, its purpose, and data usage policies.

**REQ-HELP-004**: The system shall provide a command to contact human support (e.g., "CONTACT SUPPORT") that provides local Krishi Vigyan Kendra (KVK) contact information.

### 2.12 Error Handling and Fallbacks (Tier 1 - Full Depth)

**REQ-ERROR-001**: When the system cannot understand a farmer's message, the system shall respond with a clarifying question in the farmer's dialect.

**REQ-ERROR-002**: If the Bedrock agent fails to respond within 5 seconds, then the system shall send an apology message in the user's dialect and retry the request.

**REQ-ERROR-003**: When a retry fails, the system shall route the message to SQS Dead Letter Queue for processing by dlq-handler Lambda.

**REQ-ERROR-004**: The dlq-handler Lambda shall read the user's dialect preference from DynamoDB and send an apology in their language (Hindi: "Maaf kijiyega, system mein takleef hai"; Marathi: "Maaf kara, system madhe apatti aali aahe"; Telugu: "Kshaminchandi, system lo samasya vachindi").

**REQ-ERROR-005**: If the knowledge base returns no relevant results, then the system shall acknowledge the limitation and direct the farmer to contact their local KVK.

**REQ-ERROR-006**: When an image upload fails, the system shall inform the farmer and request they resend the image.

**REQ-ERROR-007**: If Claude Vision cannot analyze an image, then the system shall explain the issue in the user's dialect and provide guidance for better photos.

**REQ-ERROR-008** (amended 2 Oct 2026): When the weather API key is missing, the request fails, or the response has no usable wind reading, the system shall treat that district as unfavorable (reason `weather_unavailable`), send no spray nudge for it in that cycle, and emit the `AgriNexus/Weather` `WeatherFetchFailed` metric. Demo weather shall be used only when `MOCK_WEATHER=true` is set explicitly, never as an error fallback.

**REQ-ERROR-009**: The system shall gracefully handle unsupported message types (e.g., videos, documents) by informing the farmer of supported formats.

**REQ-ERROR-010**: When DynamoDB throttling occurs, the system shall implement exponential backoff and retry up to 3 times.

### 2.13 Session Management (Tier 1 - Full Depth)

**REQ-SESSION-001**: The Bedrock Agent shall manage conversation sessions internally.

**REQ-SESSION-002**: The system shall store messages in DynamoDB for analytics and nudge context only — not as the primary session store.

**REQ-SESSION-003**: When a farmer sends a message, the system shall associate it with the Bedrock Agent session ID.

**REQ-SESSION-004**: The system shall maintain conversation context through Bedrock Agent's native session management.

## 3. Non-Functional Requirements

### 3.1 Performance

**REQ-PERF-001**: The system shall respond to text conversation queries within 5 seconds (p95).

**REQ-PERF-002**: The system shall process incoming WhatsApp webhooks and return HTTP 200 OK within 2 seconds.

**REQ-PERF-003**: When visual analysis is requested, the system shall return results within 15 seconds.

**REQ-PERF-004**: Text-processing Lambda functions shall execute within 1 second (excluding Bedrock API calls).

**REQ-PERF-005**: Voice round-trip (batch Transcribe + Bedrock + Polly) is expected **~30–45s p95** in MVP; **Phase 2** targets **<10s** with streaming STT.

**REQ-PERF-006**: The system shall achieve 99% uptime during business hours (6 AM - 10 PM IST).

### 3.2 Scalability

**REQ-SCALE-001**: The system shall support up to 1,000 registered farmers during the MVP phase.

**REQ-SCALE-002**: Post-MVP scaling to 10,000 concurrent farmers requires paid tier services.

### 3.3 Cost Optimization

**REQ-COST-001**: The system shall use Lambda functions for all compute operations to minimize costs.

**REQ-COST-002**: The system shall use DynamoDB on-demand pricing to avoid provisioned capacity costs.

**REQ-COST-003**: The system shall implement S3 lifecycle policies to automatically delete temporary images after 24 hours.

**REQ-COST-004**: The system shall use CloudWatch Logs with retention policies to limit log storage costs.

**REQ-COST-005**: The system shall target sustainable operational cost for 1,000 farmers using **S3 Vectors + Bedrock** (order of **~$53/month** all-in at light–moderate usage per `README.md`), not legacy OpenSearch-fixed **~$214/month** economics. At 10,000 farmers, target on the order of **~$0.54–0.70/farmer/year** (usage-dependent).

### 3.4 Security

**REQ-SEC-001**: The system shall encrypt all data at rest using AWS KMS.

**REQ-SEC-002**: The system shall encrypt all data in transit using TLS 1.2 or higher.

**REQ-SEC-003**: The system shall validate and sanitize all user inputs to prevent injection attacks.

**REQ-SEC-004**: The system shall implement IAM roles with least-privilege access for all AWS services.

**REQ-SEC-005**: The system shall store WhatsApp access token and Weather API key in AWS Secrets Manager (not environment variables).

**REQ-SEC-006**: When storing farmer data, the system shall store only phone_number as PK with no names or Aadhaar numbers.

**REQ-SEC-007**: The system shall store location as region name (not precise GPS coordinates).

**REQ-SEC-008**: The system shall implement DynamoDB TTL: MSG# items = 90 days, NUDGE# items = 180 days.

**REQ-SEC-009**: The system shall delete S3 temp images after 24 hours.

**REQ-SEC-010**: Onboarding must include consent step with STOP/UNSUBSCRIBE and DELETE MY DATA options.

### 3.5 Reliability

**REQ-REL-001**: When a Lambda function fails, the system shall retry up to 3 times with exponential backoff.

**REQ-REL-002**: The system shall implement dead letter queues for failed message processing in downstream Lambdas (not webhook handler).

**REQ-REL-003**: The webhook handler shall always return HTTP 200 to WhatsApp; async failures in downstream processing shall be caught by DLQ.

### 3.6 Monitoring and Observability (Tier 1 - Full Depth)

**REQ-MON-001**: The system shall log all API Gateway requests with request ID for tracing.

**REQ-MON-002**: The system shall emit CloudWatch metrics for message volume, response times, and error rates.

**REQ-MON-003**: The system shall emit custom metric for Nudge Completion Rate: (NudgesCompleted / NudgesSent) × 100.

**REQ-MON-004**: The system shall track ModelLatency (p95) for the configured Bedrock Claude model (the model referenced by `BedrockModelId`) used for conversations and vision.

**REQ-MON-005**: The system shall monitor DLQ depth and alert if > 5 messages.

**REQ-MON-006**: When errors occur, the system shall log detailed error information including stack traces.

**REQ-MON-007**: The system shall create CloudWatch alarms for critical failures and cost threshold breaches.

**REQ-MON-008**: The system shall provide a CloudWatch Dashboard showing: NudgesSent vs NudgesCompleted, Completion Rate Trend, ModelLatency p95, DLQDepth, Message Volume, Response Time (p50/p95/p99), and Cost Estimate.

## 4. Development Requirements

### 4.1 Code Quality (Kiro Hooks)

**REQ-DEV-001**: When code is committed, the system shall execute pre-commit hooks to run linting checks.

**REQ-DEV-002**: When code is pushed, the system shall execute pre-push hooks to run security scans using tools like Bandit or Safety.

**REQ-DEV-003**: The system shall enforce code formatting standards using Black (Python) or Prettier (JavaScript).

**REQ-DEV-004**: If security vulnerabilities are detected, then the push shall be blocked until issues are resolved.

### 4.2 Testing

**REQ-TEST-001**: The system shall include unit tests with minimum 70% code coverage.

**REQ-TEST-002**: The system shall implement 20 "golden question" RAG tests with ≥90% accuracy on factual crop data across Hindi, Marathi, Telugu.

**REQ-TEST-003**: The system shall implement 20 guardrail test scenarios with 100% refusal rate on medical advice and banned pesticides.

**REQ-TEST-004**: The system shall test idempotency: simulated 3x webhook retry results in only 1 DynamoDB message entry.

**REQ-TEST-005**: The system shall test nudge closed-loop: simulated "Ho gaya" response updates nudge SK to DONE and updates StatusIndex GSI.

**REQ-TEST-006**: The system shall perform load testing with 10 concurrent users achieving p95 text response ≤5s.

**REQ-TEST-007**: The system shall test voice round-trip: voice note → Transcribe → Bedrock → Polly → audio response; assert pipeline completes and record end-to-end time (MVP batch path **~30–45s**; Phase 2 **≤10s** target).

**REQ-TEST-008**: The system shall test vision happy path: cotton pest image → diagnosis in Hindi with confidence ≥70% within 15s.

**REQ-TEST-009**: The system shall test dialect quality: Bedrock responds coherently in Hindi, Marathi, Telugu from English KB sources.

## 5. Acceptance Criteria

### 5.1 Canonical Demo Scenario: Latur Cotton Farmer

**AC-DEMO-001**: When a user sends "Namaste", the system shall respond within 2s with dialect/crop selection via WhatsApp interactive buttons.

**AC-DEMO-002**: When a user sends Hindi voice note "Mere cotton mein kab spray karein?", the system shall transcribe and respond with audio citation; MVP batch pipeline typically **~30–45s** end-to-end (webhook ACK within seconds).

**AC-DEMO-003**: When a user sends photo of spotted cotton leaf, the system shall return diagnosis with confidence and FAO source reference within 15s.

**AC-DEMO-004**: When EventBridge detects wind <10km/h and no rain, the system shall send "Aaj spray ke liye sahi mausam hai" via WhatsApp template.

**AC-DEMO-005**: When a user replies voice/text "Ho gaya", the system shall log SUCCESS in DynamoDB and increment completion metric.

**AC-DEMO-006**: When a judge views CloudWatch Dashboard, it shall reflect +1 nudge sent, +1 completed, 100% completion rate; **text** p95 latency **<5s** where applicable (voice end-to-end tracked separately).

### 5.2 General Acceptance Criteria

**AC-001**: A new farmer can complete onboarding in under 3 minutes by providing dialect, location, and crop information via WhatsApp Interactive Buttons.

**AC-002**: A farmer can send a message in Hindi, Marathi, or Telugu and receive a relevant agronomic response within 5 seconds.

**AC-003**: A farmer can send a crop image and receive a pest diagnosis with recommended actions within 15 seconds.

**AC-004**: The system sends a behavioral nudge when favorable weather conditions are detected and follows up with reminders at T+24h and T+48h via EventBridge Scheduler.

**AC-005**: A farmer can respond with DONE keywords in any supported dialect and the system updates the task status accordingly.

**AC-006**: The system maintains conversation context through Bedrock Agent's native session management.

**AC-007**: A farmer can send voice notes and receive voice responses in Hindi (Aditi/Neural voice).

**AC-008**: A farmer can request help and receive a clear menu of available commands and example questions.

**AC-009**: When errors occur, the system provides clear, actionable guidance in the farmer's dialect via DLQ handler.

**AC-010**: The system operates within serverless architecture with estimated cost ~$214/month for 1,000 farmers (~$0.70/farmer/year at 10K scale).

**AC-011**: Pre-commit and pre-push hooks successfully block commits with linting errors or security vulnerabilities.

**AC-012**: All guardrail tests achieve 100% refusal rate on banned pesticides and medical advice.

**AC-013**: RAG golden questions achieve ≥90% accuracy across all three dialects.

## 6. Out of Scope (MVP Phase)

**Tier 3 - Cut for MVP:**
- Feedback System (REQ-FEEDBACK-* removed)
- Granular Profile Management (replaced with RESET command)
- Sentiment Detection (REQ-HELP-005 removed)
- GOODBYE command (REQ-SESSION-007 removed)
- Rate Limiting (not required for 1k user demo)
- Additional dialects beyond Hindi, Marathi, Telugu (Kannada, Tamil, Bengali, Punjabi are Phase 2)
- Advanced analytics dashboard (basic CloudWatch dashboard only for MVP)
- IoT sensor integration
- Offline mode support
- 2-way Amazon Connect escalation
- Multi-image comparison for vision
- Government scheme integration


