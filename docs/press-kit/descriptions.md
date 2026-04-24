# Project descriptions

## 100-word description

AgriNexus AI is a closed-loop agricultural advisor that turns agronomic knowledge into action on WhatsApp. Farmers can ask questions via text, voice notes, or crop photos and receive grounded, source-based guidance powered by AWS Serverless and Amazon Bedrock. What makes AgriNexus different is its behavioral nudge engine: weather-timed reminders follow up until the farmer confirms “हो गया” (done) or opts out—bridging the last-mile gap between advice and follow-through. The system supports Hindi, Marathi, Telugu, and English and is designed for low-friction adoption (no app install) and low operating cost at scale.

## 250-word description

AgriNexus AI is a WhatsApp-first advisory system built to close the last mile in agricultural extension—where knowledge exists, but arrives too late or doesn’t translate into action. Farmers interact with AgriNexus on the channel they already use: WhatsApp. They can ask questions in Hindi, Marathi, Telugu, or English, send voice notes, or share crop photos. The system responds with grounded, source-based guidance using Amazon Bedrock Knowledge Base RAG (with citations), plus optional voice output for supported languages.

The key differentiator is a closed-loop behavioral nudge engine. Most agri-advice tools stop at delivering information. AgriNexus follows through: when weather conditions are suitable for spraying, it sends a reminder and tracks whether the farmer acted. If the farmer replies “हो गया” (done), follow-ups are cancelled immediately. If not, the system can schedule reminders (T+24h, T+48h) and auto-expire nudges when appropriate. This turns advice into measurable follow-through—advice plus accountability.

AgriNexus is built on AWS Serverless primitives (Lambda, DynamoDB, SQS, EventBridge Scheduler, Step Functions, API Gateway, WAF) with production observability (CloudWatch metrics/dashboards and alarms) and strong hygiene around secrets and PII redaction. It is designed to be deployable, auditable, and cost-efficient at scale.

## 500-word description

AgriNexus AI is a closed-loop WhatsApp advisory system for smallholder farmers, built to address a persistent problem in agricultural extension: knowledge exists, but the follow-through often fails because advice arrives after the spray window closes, and extension resources are stretched. AgriNexus focuses on the “last mile” by meeting farmers where they already are—on WhatsApp—without requiring an app install or training.

Farmers can ask questions in Hindi, Marathi, Telugu, or English. They can type a message, send a voice note, or share a crop photo. AgriNexus uses Amazon Bedrock Knowledge Base RAG to produce grounded answers with citations, and can optionally provide voice output for supported languages. For crop images, it performs structured vision analysis (pest/disease/nutrient deficiency) and produces actionable recommendations with safety gating for non-agricultural images.

What makes AgriNexus distinct is its closed-loop behavioral nudge engine. Most agri-advice systems deliver information and stop. AgriNexus tracks action. When weather conditions are favorable for spraying, the system sends a reminder and records the nudge state. If the farmer replies “हो गया” (done), the system cancels follow-up schedules instantly. If the farmer replies “अभी नहीं” (not yet), it can schedule reminders (T+24h, T+48h) and auto-expire nudges to avoid spamming. This is an accountability loop designed for real-world behavior change, not just Q&A.

Technically, AgriNexus is built on AWS Serverless primitives: Lambda for compute, DynamoDB for a single-table data model and rate limits, SQS for decoupled processing, EventBridge Scheduler and Step Functions for the nudge workflow, API Gateway and WAF for public endpoints, and Secrets Manager for sensitive configuration. The system includes production observability: CloudWatch dashboards and alarms cover errors, queue backlogs, workflow failures, and cost thresholds. A judge-friendly health endpoint and a mocked end-to-end happy-path test demonstrate deployability and CI hygiene without relying on live Bedrock calls.

AgriNexus is source-available for evaluation and competition review. For commercial deployments or partner rollouts (NGOs, KVKs, state agriculture programs), licensing and integration discussions are available.

