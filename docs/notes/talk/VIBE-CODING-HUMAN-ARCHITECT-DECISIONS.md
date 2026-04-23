# Human Architect + AI Vibe Coding: Key Design Decisions in AgriNexus

## Overview
This document captures the sophisticated architectural decisions that demonstrate how **human domain expertise and architectural experience** guided AI to build a production-grade system. These decisions show the value of "vibe coding" with an experienced architect steering the AI.

---

## 🎯 Critical Architectural Decisions

### 1. **EventBridge Scheduler vs Step Functions Wait States** (ADR 0007)

**The Problem:**
Need to send reminders at T+24h, T+48h, T+72h after initial nudge. How to schedule delayed executions?

**Naive AI Approach Would Be:**
Use Step Functions Wait states (keeps execution open for 3 days)

**Human Architect Decision:**
Use EventBridge Scheduler for one-time scheduled tasks

**Why This Matters:**
- **67x cheaper**: $3 vs $200 per million nudges
- **No long-running executions**: Step Functions exits in <5 seconds vs 72 hours
- **Cancellable**: Can delete schedules when farmer responds "DONE"
- **Real savings**: $719/year for 10,000 farmers/day (98.5% reduction)

**Domain Insight:**
"Step Functions Wait is not designed for multi-day delays. EventBridge Scheduler is purpose-built for this exact use case."

---

### 2. **S3 Vectors vs OpenSearch Serverless** (ADR 0008)

**The Problem:**
Need vector storage for Bedrock Knowledge Base RAG

**Initial Implementation:**
OpenSearch Serverless: **$174/month fixed cost**

**Human Architect Decision (April 4, 2026):**
Migrate to S3 vectors: **$1.30/month pay-per-query**

**Why This Matters:**
- **75% cost reduction**: $214/month → $53/month
- **Pay-per-query model**: Aligns with serverless philosophy
- **Acceptable latency**: 100-800ms is fine for chatbot use case
- **No fixed costs**: Perfect for MVP with variable usage

**Domain Insight:**
"For a chatbot with <1000 queries/day, fixed-cost OpenSearch is overkill. S3 vectors launched in late 2024 specifically for this use case."

---

### 3. **Webhook → SQS → Processor Architecture** (ADR 0003)

**The Problem:**
WhatsApp requires webhook response within 2 seconds, but Bedrock RAG takes ~13 seconds

**Naive AI Approach Would Be:**
Direct webhook → Lambda (would timeout)

**Human Architect Decision:**
```
WhatsApp → API Gateway → Webhook Lambda → SQS Queues → Processor Lambdas
                              ↓
                         DynamoDB (dedup)
```

**Why This Matters:**
- **Fast webhook response**: <500ms (WhatsApp requirement: <2s)
- **Reliable processing**: SQS handles retries, DLQ for failures
- **Deduplication**: Prevents duplicate processing (WhatsApp sends duplicates)
- **Voice ACK**: Immediate feedback before transcription
- **Scalability**: SQS buffers load, Lambdas scale independently

**Domain Insight:**
"Never do long-running work in a webhook handler. Acknowledge immediately, process asynchronously."

---

### 4. **Public Web Demo Abuse Protection** (ADR 0001)

**The Problem:**
Public `/chat` API without login is vulnerable to abuse and cost spikes

**Naive AI Approach Would Be:**
Just add application-layer rate limiting

**Human Architect Decision:**
**Defense in depth** with 3 layers:
1. **API Gateway throttling**: 2 req/sec, burst 5
2. **AWS WAF**: 300 requests / 5 minutes per IP
3. **Application rate limiting**: 5 queries/hour per IP

**Why This Matters:**
- **Edge protection**: Stops abuse before it hits Lambda/Bedrock
- **Cost control**: Prevents runaway Bedrock spend
- **Visibility**: WAF metrics + sampled requests for monitoring
- **Low friction**: No login required, but protected

**Domain Insight:**
"Public APIs need edge-layer protection. Application-layer rate limiting alone is too late—the request already consumed Lambda/API Gateway resources."

---

### 5. **Common Layer Dependency Management** (ADR 0002)

**The Problem:**
Lambda Layer needs `requests` library, but SAM build wasn't installing it

**Naive AI Approach Would Be:**
Manual `pip install` in layer directory

**Human Architect Decision:**
Use `requirements.txt` in layer directory, let SAM handle installation

**Why This Matters:**
- **Reproducible builds**: Works in CI/CD without manual steps
- **Documented dependencies**: `requirements.txt` is source of truth
- **No surprises**: Deployment matches local development

**Domain Insight:**
"Infrastructure as Code means dependencies too. Manual steps break CI/CD and create 'works on my machine' problems."

---

### 6. **Single-Table DynamoDB Design**

**The Problem:**
Need to store user profiles, messages, nudges, allowlist

**Naive AI Approach Would Be:**
4 separate tables (users, messages, nudges, allowlist)

**Human Architect Decision:**
Single table with composite keys:
```
PK: USER#+919876543210, SK: PROFILE
PK: USER#+919876543210, SK: MSG#2026-04-11T12:00:00
PK: USER#+919876543210, SK: NUDGE#2026-04-11T10:00:00#spray
PK: ALLOWLIST, SK: USER#+919876543210
```

**Why This Matters:**
- **Cost reduction**: 1 table vs 4 (fewer capacity units)
- **Atomic transactions**: Can update profile + message in single transaction
- **Efficient queries**: GSI for location/crop queries
- **Simpler operations**: One table to monitor, backup, restore

**Domain Insight:**
"DynamoDB single-table design is a best practice for serverless. Multiple tables are an anti-pattern that increases costs and complexity."

---

### 7. **Voice ACK Before Transcription**

**The Problem:**
Voice transcription takes 5-10 seconds, farmer gets no feedback

**Naive AI Approach Would Be:**
Wait for transcription, then send response

**Human Architect Decision:**
Send immediate ACK ("Voice received, processing...") before queuing to Voice Queue

**Why This Matters:**
- **User experience**: Farmer gets feedback in <1 second
- **Trust building**: Shows system is working
- **Webhook compliance**: Returns 200 OK quickly
- **Async processing**: Transcription happens in background

**Domain Insight:**
"In voice interfaces, immediate acknowledgment is critical for trust. Users need to know their message was received, even if processing takes time."

---

### 8. **Demo Tier Behavior (Public vs Full)**

**The Problem:**
Public demo users shouldn't get T+24h/T+48h reminders (cost + UX)

**Naive AI Approach Would Be:**
Same behavior for all users

**Human Architect Decision:**
```python
demo_tier = profile.get('demo_tier', 'public')

if demo_tier == 'public':
    # Send one nudge, no follow-ups
    send_nudge(phone_number, message)
else:
    # Full closed-loop with reminders
    send_nudge(phone_number, message)
    create_reminder_schedule(phone_number, nudge_id, 24)
    create_reminder_schedule(phone_number, nudge_id, 48)
    create_reminder_schedule(phone_number, nudge_id, 72)
```

**Why This Matters:**
- **Cost control**: Public demo doesn't create 3 schedules per nudge
- **UX appropriate**: Demo users see the feature, don't get spammed
- **Flexible**: Can upgrade users to full tier without code changes

**Domain Insight:**
"Public demos and production features need different behavior. Build the flexibility in from day one."

---

### 9. **Allowlist-Gated Features**

**The Problem:**
Voice, images, and nudges are expensive—can't offer to all public users

**Naive AI Approach Would Be:**
Either enable for everyone or disable completely

**Human Architect Decision:**
DynamoDB-backed allowlist:
```python
def is_approved_user(table, phone_number: str) -> bool:
    item = table.get_item(Key={"PK": "ALLOWLIST", "SK": f"USER#{phone_number}"})
    return bool(item.get("approved", False))

# In webhook handler
if message_type == "audio" and not is_approved_user(table, phone_number):
    send_message(phone_number, "Voice is enabled for evaluators (allowlist)")
    return
```

**Why This Matters:**
- **Cost control**: Expensive features gated to known users
- **Flexible**: Can add/remove users without deployment
- **Graceful degradation**: Public users still get text chat
- **Evaluation-friendly**: Easy to onboard pilot users

**Domain Insight:**
"Public demos need feature gating. Build a simple allowlist system that doesn't require auth but controls access to expensive features."

---

### 10. **Architecture Decision Records (ADRs)**

**The Problem:**
Complex architectural decisions need to be documented for future reference

**Naive AI Approach Would Be:**
Comments in code or README

**Human Architect Decision:**
Formal ADR process with 8 documented decisions:
- ADR 0001: Public web demo abuse protection
- ADR 0002: Common layer dependency management
- ADR 0003: WhatsApp integration architecture
- ADR 0004: Voice processing pipeline
- ADR 0005: Bedrock RAG source attribution
- ADR 0006: Observability X-Ray tracing
- ADR 0007: EventBridge Scheduler vs Step Functions Wait
- ADR 0008: S3 Vectors vs OpenSearch

**Why This Matters:**
- **Knowledge preservation**: Future developers understand "why"
- **Decision tracking**: Can revisit decisions with full context
- **Onboarding**: New team members learn architectural rationale
- **Credibility**: Shows thoughtful engineering process

**Domain Insight:**
"ADRs are the difference between a prototype and a production system. They capture the 'why' that code can't express."

---

## 🎨 UX/Design Decisions

### 11. **Dialect-Native Responses**

**Human Decision:**
Store user's preferred dialect (hi/mr/te/en) in profile, respond in that dialect

**Why This Matters:**
- **Trust building**: Farmers trust advice in their native language
- **Accessibility**: Removes language barrier
- **Code-switching support**: Handles Hinglish naturally

**Domain Insight:**
"For rural users, language isn't just preference—it's trust. English-only systems fail in the field."

---

### 12. **Interactive Buttons for Nudge Responses**

**Human Decision:**
Use WhatsApp interactive buttons ("हो गया" / "अभी नहीं") instead of free text

**Why This Matters:**
- **Lower friction**: Tap button vs type message
- **Structured data**: Easy to detect DONE/NOT YET
- **Dialect-appropriate**: Buttons in user's language
- **Accessibility**: Works for low-literacy users

**Domain Insight:**
"For behavioral interventions, reduce friction to zero. Buttons beat typing every time."

---

### 13. **Context-Aware Nudge Messages**

**Human Decision:**
Include district, crop, wind speed, and actionable hint in nudge:
```
"Latur: गेहूं में स्प्रे के लिए मौसम अनुकूल है। हवा 8.0 km/h है। कृपया स्प्रे करें।"
```

**Why This Matters:**
- **Relevance**: Farmer sees their specific context
- **Actionability**: Clear what to do and why
- **Trust**: Shows system understands their situation

**Domain Insight:**
"Generic nudges get ignored. Context-specific nudges drive action."

---

## 💰 Cost Optimization Decisions

### 14. **On-Demand DynamoDB (Not Provisioned)**

**Human Decision:**
Use on-demand billing for DynamoDB

**Why This Matters:**
- **Variable usage**: MVP usage is unpredictable
- **No capacity planning**: Auto-scales with load
- **Cost-effective at low scale**: ~$0.90/month for 1,000 farmers

**Domain Insight:**
"For MVPs with <1M requests/month, on-demand beats provisioned. Switch to provisioned only when usage is predictable."

---

### 15. **S3 Lifecycle Policies**

**Human Decision:**
Auto-delete temp images after 24 hours, voice files after 1 day

**Why This Matters:**
- **Storage cost**: Prevents accumulation of temp files
- **Privacy**: Sensitive data auto-deleted
- **Compliance**: Minimal data retention

**Domain Insight:**
"Temporary storage should be truly temporary. Lifecycle policies enforce this automatically."

---

### 16. **TTL on DynamoDB Items**

**Human Decision:**
- Messages: 90-day TTL
- Nudges: 180-day TTL

**Why This Matters:**
- **Storage cost**: Old data auto-deleted
- **Performance**: Smaller table = faster queries
- **Compliance**: Data retention policy enforced

**Domain Insight:**
"DynamoDB TTL is free. Use it to keep tables lean and costs low."

---

## 🔒 Security Decisions

### 17. **Webhook Signature Validation**

**Human Decision:**
Validate `X-Hub-Signature-256` on every webhook POST

**Why This Matters:**
- **Prevents spoofing**: Only Meta can send valid webhooks
- **Cost protection**: Blocks fake requests before processing
- **Security best practice**: Never trust incoming webhooks

**Domain Insight:**
"Webhook signature validation is non-negotiable. Without it, anyone can impersonate WhatsApp and drain your Bedrock budget."

---

### 18. **Secrets Manager for Credentials**

**Human Decision:**
Store WhatsApp tokens in AWS Secrets Manager, not environment variables

**Why This Matters:**
- **Rotation**: Can rotate secrets without redeployment
- **Audit trail**: CloudTrail logs secret access
- **Encryption**: Secrets encrypted at rest with KMS

**Domain Insight:**
"Environment variables are visible in Lambda console. Secrets Manager is the right tool for sensitive credentials."

---

## 📊 Observability Decisions

### 19. **Custom CloudWatch Metrics**

**Human Decision:**
Emit custom metrics for business logic:
- `NudgesSent`
- `NudgesCompleted`
- `NudgeCompletionRate` (calculated)

**Why This Matters:**
- **Business visibility**: Track what matters (completion rate)
- **Alerting**: Can alert on low completion rates
- **Dashboard**: Single pane of glass for operations

**Domain Insight:**
"AWS metrics tell you if the system is running. Custom metrics tell you if it's working."

---

### 20. **CloudWatch RUM for Web Demo**

**Human Decision:**
Add CloudWatch RUM for browser-side telemetry on web demo

**Why This Matters:**
- **User experience**: Track page loads, errors, latency
- **No third-party analytics**: Stays in AWS ecosystem
- **Optional**: Can be disabled by clearing config IDs

**Domain Insight:**
"For public demos, you need to know if users are actually visiting the page vs just hitting the API. RUM tracks browser behavior."

---

## 🏗️ Infrastructure Decisions

### 21. **SAM (Not CDK or Terraform)**

**Human Decision:**
Use AWS SAM for infrastructure as code

**Why This Matters:**
- **Serverless-native**: Built for Lambda/API Gateway/DynamoDB
- **Simple syntax**: YAML is more readable than CDK TypeScript
- **Local testing**: `sam local` for development
- **CloudFormation**: Compiles to CFN for deployment

**Domain Insight:**
"For serverless-only projects, SAM is simpler than CDK. CDK shines when you need custom constructs or multi-service orchestration."

---

### 22. **FIFO Queues (Not Standard)**

**Human Decision:**
Use FIFO queues for message processing

**Why This Matters:**
- **Ordering**: Per-user message order preserved
- **Deduplication**: Built-in dedup by `MessageDeduplicationId`
- **Exactly-once**: No duplicate processing

**Domain Insight:**
"For conversational AI, message order matters. FIFO queues guarantee this without custom logic."

---

## 🎓 Key Lessons for Vibe Coding

### What Human Architects Bring:

1. **Cost Awareness**: Knowing EventBridge Scheduler is 67x cheaper than Step Functions Wait
2. **Service Selection**: Choosing S3 vectors over OpenSearch for variable workloads
3. **Defense in Depth**: Layering API Gateway + WAF + app-level rate limiting
4. **UX Intuition**: Immediate voice ACK before transcription
5. **Operational Maturity**: ADRs, custom metrics, RUM monitoring
6. **Security Mindset**: Webhook signature validation, Secrets Manager, allowlists
7. **Cost Optimization**: On-demand billing, TTL, lifecycle policies
8. **Domain Knowledge**: Dialect-native responses, interactive buttons, context-aware nudges

### What AI Brings:

1. **Rapid Implementation**: Turns architectural decisions into working code
2. **Consistency**: Applies patterns uniformly across codebase
3. **Documentation**: Generates comprehensive docs from decisions
4. **Boilerplate**: Handles repetitive code (Lambda handlers, IAM policies)

### The Magic Combination:

**Human**: "Use EventBridge Scheduler for T+24h reminders, not Step Functions Wait. It's 67x cheaper and purpose-built for this."

**AI**: *Generates complete implementation with scheduler creation, cancellation logic, IAM roles, and error handling in minutes*

**Human**: "Add demo_tier flag to skip reminders for public users."

**AI**: *Updates sender logic, adds profile check, documents behavior in ADR*

---

## 📈 Impact of These Decisions

### Cost Savings:
- S3 vectors vs OpenSearch: **$1,548/year saved** (75% reduction)
- EventBridge vs Step Functions: **$719/year saved** (98.5% reduction)
- Demo tier behavior: **~$500/year saved** (estimated)
- **Total: ~$2,767/year saved** through architectural decisions

### Operational Benefits:
- **8 ADRs** documenting key decisions
- **CloudWatch dashboard** with custom metrics
- **RUM monitoring** for web demo
- **Allowlist system** for cost control
- **Defense-in-depth** security

### User Experience:
- **<1 second** voice ACK (vs 5-10 second wait)
- **Dialect-native** responses (hi/mr/te/en)
- **Interactive buttons** (low friction)
- **Context-aware nudges** (district + crop + weather)

---

## 🎤 Talking Points for Your Presentation

### "How Human Architect Makes AI Better"

1. **Cost Awareness**: "AI suggested Step Functions Wait. I knew EventBridge Scheduler would be 67x cheaper. That's $719/year saved on a single decision."

2. **Service Selection**: "AI defaulted to OpenSearch Serverless. I knew S3 vectors launched in 2024 for exactly this use case. 75% cost reduction."

3. **Defense in Depth**: "AI added app-level rate limiting. I added API Gateway throttling and WAF. Public APIs need edge protection."

4. **UX Intuition**: "AI would wait for transcription. I added immediate voice ACK. Users need feedback in <1 second."

5. **Operational Maturity**: "AI wrote code. I wrote ADRs. Future developers need to understand 'why', not just 'what'."

### "Vibe Coding in Action"

**Me**: "Use EventBridge Scheduler for reminders"  
**AI**: *Generates complete implementation in 30 seconds*

**Me**: "Add demo_tier flag to skip reminders"  
**AI**: *Updates logic, adds docs, handles edge cases*

**Me**: "Migrate to S3 vectors"  
**AI**: *Refactors Knowledge Base config, updates costs in docs*

**Speed**: What would take a junior dev 2 weeks took us 2 days.  
**Quality**: Production-grade with ADRs, monitoring, security.

---

## 📚 Documentation Evidence

All these decisions are documented in the codebase:
- **8 ADRs** in `docs/adr/`
- **Architecture doc** (`architecture.md`) - 954 lines
- **48 documentation files** covering every aspect
- **CloudWatch dashboard** JSON in `dashboards/`
- **RUM config** in `docs/web-demo/assets/`

This isn't a prototype. It's a production system built with AI, guided by human expertise.

---

*"AI is a force multiplier. But you need to know what to multiply."*
