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
Free-tier-leaning serverless architecture with pay-as-you-go Bedrock. Estimated cost: ~$50/month for 1,000 users, with OpenSearch Serverless (~$20) and Bedrock (~$15) as the primary cost drivers.

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

**REQ-CONV-001**: When a farmer sends a message via WhatsApp, the system shall process it using Amazon Bedrock Agent with Claude 3 Sonnet.

**REQ-CONV-002**: When the Bedrock agent receives a query, the system shall retrieve relevant agronomic knowledge from the S3-backed knowledge base using RAG (Retrieval Augmented Generation).

**REQ-CONV-003**: The system shall respond to farmer queries in Hindi, Marathi, or Telugu based on the user's profile dialect preference.

**REQ-CONV-004**: Every advisory response shall include a simplified source citation (e.g., "Source: FAO Cotton Guide, Section 3").

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

**REQ-GUARD-001**: The guardrails shall block 100% of requests for banned pesticides including Paraquat, Endosulfan, and other substances on India's banned list.

**REQ-GUARD-002**: The system shall include explicit disclaimers when providing pesticide dosage information, directing farmers to read product labels.

**REQ-GUARD-003**: The system shall escalate to "contact your local Krishi Vigyan Kendra (KVK)" for severe infestations, unknown diseases, livestock health, and human health concerns.

**REQ-GUARD-004**: The system shall not recommend specific pesticide brands or commercial products.

**REQ-GUARD-005**: The system shall include a disclaimer that advice is supplementary and does not replace professional agricultural extension services.

**REQ-GUARD-006**: The system shall refuse to provide medical advice for humans or animals.

**REQ-GUARD-007**: The guardrail test suite shall include at minimum: 5 banned pesticide scenarios, 5 medical/veterinary advice attempts, 5 dosage-specific queries, 5 edge cases (e.g., mixing chemicals, organic certification claims).

### 2.5 Visual Verification (Tier 2 - Working Implementation)

**REQ-VIS-001**: When a farmer sends an image via WhatsApp, the system shall process it using Claude 3 Vision via direct invoke_model API (separate from the Bedrock Agent conversation flow).

**REQ-VIS-002**: The system shall respond with diagnosis, confidence level, and recommended actions in the user's dialect.

**REQ-VIS-003**: When confidence is below 70%, the system shall request a clearer image with specific guidance in the user's dialect (e.g., Hindi: "Photo thoda paas se lein" / "Take a closer photo").

**REQ-VIS-004**: The system shall respond within 15 seconds for image analysis.

**REQ-VIS-005**: When visual analysis is complete, the system shall delete the temporary image from S3 to minimize storage costs.

**REQ-VIS-006**: One working happy path (cotton pest image → diagnosis in user's dialect) is sufficient for MVP demo.

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

**REQ-VOICE-006**: The system shall complete voice round-trip (transcribe → Bedrock → Polly) within 10 seconds.

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

### 2.10 Profile Management (Tier 3 - Cut for MVP)

**REQ-PROFILE-001**: The system shall support a RESET command to re-initiate onboarding for profile updates.

**REQ-PROFILE-002**: The system shall allow farmers to delete their profile and all associated data by sending a "DELETE MY DATA" command.

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

**REQ-ERROR-008**: When the weather API is unavailable, the system shall use cached weather data and inform farmers that data may be outdated.

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

**REQ-PERF-005**: Voice round-trip (Transcribe + Bedrock + Polly) shall complete within 10 seconds.

**REQ-PERF-006**: The system shall achieve 99% uptime during business hours (6 AM - 10 PM IST).

### 3.2 Scalability

**REQ-SCALE-001**: The system shall support up to 1,000 registered farmers during the MVP phase.

**REQ-SCALE-002**: Post-MVP scaling to 10,000 concurrent farmers requires paid tier services.

### 3.3 Cost Optimization

**REQ-COST-001**: The system shall use Lambda functions for all compute operations to minimize costs.

**REQ-COST-002**: The system shall use DynamoDB on-demand pricing to avoid provisioned capacity costs.

**REQ-COST-003**: The system shall implement S3 lifecycle policies to automatically delete temporary images after 24 hours.

**REQ-COST-004**: The system shall use CloudWatch Logs with retention policies to limit log storage costs.

**REQ-COST-005**: The system shall target ~$50/month operational cost for 1,000 users, with OpenSearch Serverless and Bedrock as the primary cost drivers.

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

**REQ-MON-004**: The system shall track ModelLatency (p95) for Claude 3 Sonnet only.

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

**REQ-TEST-007**: The system shall test voice round-trip: voice note → Transcribe → Bedrock → Polly → audio response ≤10s.

**REQ-TEST-008**: The system shall test vision happy path: cotton pest image → diagnosis in Hindi with confidence ≥70% within 15s.

**REQ-TEST-009**: The system shall test dialect quality: Bedrock responds coherently in Hindi, Marathi, Telugu from English KB sources.

## 5. Acceptance Criteria

### 5.1 Canonical Demo Scenario: Aurangabad Cotton Farmer

**AC-DEMO-001**: When a user sends "Namaste", the system shall respond within 2s with dialect/crop selection via WhatsApp interactive buttons.

**AC-DEMO-002**: When a user sends Hindi voice note "Mere cotton mein kab spray karein?", the system shall transcribe and respond with audio citation within 5s.

**AC-DEMO-003**: When a user sends photo of spotted cotton leaf, the system shall return diagnosis with confidence and FAO source reference within 15s.

**AC-DEMO-004**: When EventBridge detects wind <10km/h and no rain, the system shall send "Aaj spray ke liye sahi mausam hai" via WhatsApp template.

**AC-DEMO-005**: When a user replies voice/text "Ho gaya", the system shall log SUCCESS in DynamoDB and increment completion metric.

**AC-DEMO-006**: When a judge views CloudWatch Dashboard, it shall reflect +1 nudge sent, +1 completed, 100% completion rate, p95 latency <5s.

### 5.2 General Acceptance Criteria

**AC-001**: A new farmer can complete onboarding in under 3 minutes by providing dialect, location, and crop information via WhatsApp Interactive Buttons.

**AC-002**: A farmer can send a message in Hindi, Marathi, or Telugu and receive a relevant agronomic response with FAO citation within 5 seconds.

**AC-003**: A farmer can send a crop image and receive a pest diagnosis with recommended actions within 15 seconds.

**AC-004**: The system sends a behavioral nudge when favorable weather conditions are detected and follows up with reminders at T+24h and T+48h via EventBridge Scheduler.

**AC-005**: A farmer can respond with DONE keywords in any supported dialect and the system updates the task status accordingly.

**AC-006**: The system maintains conversation context through Bedrock Agent's native session management.

**AC-007**: A farmer can send voice notes and receive voice responses in Hindi (Aditi/Neural voice).

**AC-008**: A farmer can request help and receive a clear menu of available commands and example questions.

**AC-009**: When errors occur, the system provides clear, actionable guidance in the farmer's dialect via DLQ handler.

**AC-010**: The system operates within free-tier-leaning architecture with estimated cost ~$50/month for 1,000 users.

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


