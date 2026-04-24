# AgriNexus AI — Production Metrics & Monitoring

> **For judges, reviewers, and operators.** This document captures the observability posture of the live AgriNexus AI stack: what's instrumented, what's alarmed, what the system is actually doing in production right now, and what's on the roadmap. Numbers are from the running environment, not projections.
>
> **See also:** [README — Production Evidence](../README.md#production-evidence) · [Operations Runbook](operations/RUNBOOK-ALERTS.md) · [FinOps breakdown](finops-public.md)

**Last updated:** April 23, 2026 · **Rolling window:** 7 days · **Environment:** dev (production) · **Stack:** `agrinexus-week2`

---

## Metrics Summary Table

| Category | Metric | Type | Source | Status | Alert Threshold | Current Value |
|----------|--------|------|--------|--------|----------------|---------------|
| **BUSINESS METRICS** |
| Nudges | NudgesSent | Custom | CloudWatch | ✅ Active | - | ~4/day |
| Nudges | NudgesCompleted | Custom | CloudWatch | ✅ Active | - | Variable |
| Nudges | Completion Rate | Calculated | Dashboard | ✅ Active | - | ~25-50% |
| Users | Total Registered | Manual | DynamoDB | ✅ Active | - | 7 users |
| Users | Allowlisted | Manual | DynamoDB | ✅ Active | - | 1 user |
| Messages | WhatsApp Messages | Manual | CloudWatch | ✅ Active | - | ~115/week |
| Messages | Web Demo Requests | Manual | CloudWatch | ✅ Active | - | ~50/week |
| **OPERATIONAL METRICS** |
| Lambda | Invocations | AWS | CloudWatch | ✅ Active | - | ~724/week |
| Lambda | Errors | AWS | CloudWatch | ✅ Alarmed | >5 in 5min | 0 (last 3 days) |
| Lambda | Duration (p95) | AWS | CloudWatch | ✅ Active | - | <3s |
| Lambda | Concurrency | AWS | CloudWatch | 🛠️ Roadmap | - | Variable |
| SQS | Queue Depth | AWS | CloudWatch | ✅ Alarmed | >10 | 0 |
| SQS | Message Age | AWS | CloudWatch | ✅ Alarmed | >300s | 0 |
| SQS | DLQ Depth | AWS | CloudWatch | ✅ Alarmed | >5 | 0 |
| API Gateway | Request Count | AWS | CloudWatch | ✅ Active | - | ~724/week |
| API Gateway | 4XX Errors | AWS | CloudWatch | ✅ Active | - | Low |
| API Gateway | 5XX Errors | AWS | CloudWatch | ✅ Active | - | 0 |
| DynamoDB | Read Capacity | AWS | CloudWatch | ✅ Active | - | On-demand |
| DynamoDB | Write Capacity | AWS | CloudWatch | ✅ Active | - | On-demand |
| DynamoDB | Throttles | AWS | CloudWatch | ✅ Active | >0 | 0 |
| Step Functions | Executions Succeeded | AWS | CloudWatch | ✅ Active | - | 100% |
| Step Functions | Executions Failed | AWS | CloudWatch | ✅ Alarmed | >0 | 0 |
| Step Functions | Duration (p95) | AWS | CloudWatch | ✅ Active | - | <1s |
| **COST METRICS** |
| Cost | Daily Estimated | AWS | CloudWatch | ✅ Alarmed | >$5/day | ~$1.70/day |
| Cost | Monthly Total | Manual | Billing | ✅ Active | - | ~$53/month |
| Cost | Per Farmer | Calculated | Manual | ✅ Active | - | $0.053/month |
| Cost | Secrets Manager | AWS | Billing | ✅ Active | - | ~$0.40/month |
| Cost | Lambda | AWS | Billing | ✅ Active | - | ~$15/month |
| Cost | DynamoDB | AWS | Billing | ✅ Active | - | ~$10/month |
| Cost | Bedrock | AWS | Billing | ✅ Active | - | ~$20/month |
| **SECURITY METRICS** |
| Auth | Invalid Signatures | Manual | CloudWatch | 🛠️ Roadmap | - | 0 |
| Auth | Rate Limit Hits | Manual | CloudWatch | 🛠️ Roadmap | - | 0 |
| PII | Redacted Logs | Manual | CloudWatch | ✅ Active | - | 100% |
| IAM | Least Privilege | Manual | Template | 🛠️ Roadmap (Polly) | - | Partial |
| **RELIABILITY METRICS** |
| Uptime | System Availability | Manual | CloudWatch | ✅ Active | - | 100% |
| Errors | Error Rate | AWS | CloudWatch | ✅ Alarmed | >5% | 0% |
| Latency | Response Time | AWS | CloudWatch | ✅ Active | <3s | <2s |
| DLQ | Failed Messages | AWS | CloudWatch | ✅ Alarmed | >5 | 0 |

---

## 🎯 Business Metrics

### Nudge Performance

| Metric | Description | Current | Target | Tracking |
|--------|-------------|---------|--------|----------|
| Nudges Sent | Total nudges delivered | ~4/day | 100/day | ✅ CloudWatch |
| Nudges Completed | Farmers marked "done" | Variable | 50% | ✅ CloudWatch |
| Completion Rate | % of nudges acted upon | 25-50% | 60% | ✅ Dashboard |
| Response Time | Time to farmer action | Not tracked | <24h | 🛠️ Roadmap |

### User Engagement

| Metric | Description | Current | Target | Tracking |
|--------|-------------|---------|--------|----------|
| Total Users | Registered farmers | 7 | 1,000 | ✅ DynamoDB |
| Active Users | Used in last 7 days | 1 | 500 | ⚠️ Manual |
| Messages/User | Avg messages per user | ~16/user | 10/user | ⚠️ Manual |
| Retention Rate | Users active after 30d | Not tracked | 80% | 🛠️ Roadmap |

### Message Volume

| Metric | Description | Current | Target | Tracking |
|--------|-------------|---------|--------|----------|
| WhatsApp Messages | Total messages received | ~115/week | 1,000/week | ✅ CloudWatch |
| Web Demo Requests | Public demo usage | ~50/week | 100/week | ✅ CloudWatch |
| Voice Messages | Audio queries | Low | 50/week | ✅ CloudWatch |
| Image Messages | Vision queries | Low | 20/week | ✅ CloudWatch |

---

## ⚙️ Operational Metrics

### Lambda Performance

| Function | Invocations/Week | Errors | Duration (p95) | Status |
|----------|------------------|--------|----------------|--------|
| Webhook | ~724 | 0 | <1s | ✅ Healthy |
| Processor | ~724 | 0 | <3s | ✅ Healthy |
| Voice | Low | 0 | <5s | ✅ Healthy |
| Weather Poller | 28 (4×/day) | 0 | <2s | ✅ Healthy |
| Nudge Sender | ~4 | 0 | <2s | ✅ Healthy |
| Reminder | Variable | 0 | <1s | ✅ Healthy |
| Response Detector | ~115 | 0 | <1s | ✅ Healthy |
| DLQ | 0 | 0 | <1s | ✅ Healthy |

### Queue Health

| Queue | Depth | Age (max) | DLQ Depth | Status |
|-------|-------|-----------|-----------|--------|
| Messages | 0 | 0s | 0 | ✅ Healthy |
| Voice | 0 | 0s | 0 | ✅ Healthy |
| Messages DLQ | 0 | - | - | ✅ Healthy |

### API Gateway

| Endpoint | Requests/Week | 4XX | 5XX | Latency (p95) |
|----------|---------------|-----|-----|---------------|
| /webhook | ~724 | Low | 0 | <500ms |
| /chat (web demo) | ~50 | Low | 0 | <2s |

### DynamoDB

| Metric | Value | Status |
|--------|-------|--------|
| Mode | On-Demand | ✅ Optimal |
| Read Capacity | Auto-scaled | ✅ Healthy |
| Write Capacity | Auto-scaled | ✅ Healthy |
| Throttles | 0 | ✅ Healthy |
| Item Count | ~100 | ✅ Healthy |

---

## 💰 Cost Metrics

### Monthly Cost Breakdown

| Service | Cost/Month | % of Total | Per 1,000 Farmers | Status |
|---------|------------|------------|-------------------|--------|
| **Total** | **~$53** | **100%** | **~$53** | ✅ Optimized |
| Bedrock (RAG) | ~$20 | 38% | ~$20 | ✅ Efficient |
| Lambda | ~$15 | 28% | ~$15 | ✅ Efficient |
| DynamoDB | ~$10 | 19% | ~$10 | ✅ Efficient |
| S3 (vectors) | ~$3 | 6% | ~$3 | ✅ Efficient |
| API Gateway | ~$2 | 4% | ~$2 | ✅ Efficient |
| EventBridge | ~$1 | 2% | ~$1 | ✅ Efficient |
| Secrets Manager | ~$0.40 | 1% | ~$0.40 | ✅ Efficient |
| CloudWatch | ~$1 | 2% | ~$1 | ✅ Efficient |
| Step Functions | ~$0.60 | 1% | ~$0.60 | ✅ Efficient |

### Cost Efficiency

| Metric | Value | Benchmark | Status |
|--------|-------|-----------|--------|
| Cost per Farmer | $0.053/month | <$0.10 | ✅ Excellent |
| Cost per Message | $0.46/message | <$1.00 | ✅ Excellent |
| Savings vs Step Functions Wait States | ~67× cheaper | - | ✅ Optimized |

> **Note on scale projection:** Modeled cost at 10,000 active farmers is ~$0.54/farmer/year. This is a **scale projection**, not a current measurement — see [finops-public.md](finops-public.md) for full assumptions.

---

## 🔒 Security Metrics

### Authentication & Authorization

| Metric | Status | Details |
|--------|--------|---------|
| Signature Verification | ✅ Always On | Meta HMAC-SHA256, no bypass possible |
| Rate Limiting | ✅ Active | 10 msgs/hour per user |
| Allowlist Gating | ✅ Active | Nudges/voice gated |
| PII Redaction | ✅ Active | All phone numbers redacted in logs |

### IAM & Permissions

| Resource | Scope | Status | Note |
|----------|-------|--------|------|
| DynamoDB | Table-specific | ✅ Good | |
| S3 | Bucket-specific | ✅ Good | |
| Bedrock | Model-specific | ✅ Good | |
| Polly | `Resource: '*'` | 🛠️ Roadmap | Scope to specific voices |
| Secrets Manager | Secret-specific | ✅ Good | |

### Compliance

| Requirement | Status | Evidence |
|-------------|--------|----------|
| PII Protection | ✅ Pass | Logs show `491***` format |
| Data Retention | ✅ Pass | TTL on all items (7-180 days) |
| Encryption at Rest | ✅ Pass | DynamoDB default encryption |
| Encryption in Transit | ✅ Pass | HTTPS only |

---

## 📈 Reliability Metrics

### Availability

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Uptime (last 7 days) | 100% | 99.9% | ✅ Excellent |
| Error Rate | 0% | <1% | ✅ Excellent |
| DLQ Messages | 0 | <10/day | ✅ Excellent |

### Performance

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Webhook Latency (p95) | <500ms | <1s | ✅ Excellent |
| Processor Latency (p95) | <3s | <5s | ✅ Good |
| Voice Latency (p95, end-to-end) | ~20–34s | <60s | ✅ Good |
| Queue Processing Time | <1s | <5s | ✅ Excellent |

---

## 🚨 Alarms & Alerts

### Active Alarms (9 total)

All alarms publish to SNS topic `agrinexus-alerts-{env}`.

| Alarm | Threshold | Status |
|-------|-----------|--------|
| Nudge Workflow Failures | >0 failures | ✅ Active |
| Cost Alert | >$5/day | ✅ Active |
| Processor Errors | >5 in 5min | ✅ Active |
| Webhook Errors | >5 in 5min | ✅ Active |
| Web Chat Errors | >5 in 5min | ✅ Active |
| Voice Errors | >5 in 5min | ✅ Active |
| Queue Backlog | Age >300s | ✅ Active |
| DLQ Depth | >5 messages | ✅ Active |
| Voice DLQ Depth | >5 messages | ✅ Active |

---

## 📊 Dashboards

### CloudWatch Dashboard

**Template:** [`dashboards/cloudwatch-dashboard.json`](../dashboards/cloudwatch-dashboard.json) · **Widgets:** 9

| Widget | Metrics | Purpose |
|--------|---------|---------|
| Lambda Invocations | All functions | Traffic monitoring |
| Lambda Errors | All functions | Error tracking |
| Lambda Duration | Key functions (p95) | Performance monitoring |
| SQS Queue Depth | All queues | Queue health |
| API Gateway | Errors & count | API monitoring |
| DynamoDB | Capacity & throttles | Database health |
| Step Functions | Success/failure | Workflow monitoring |
| Step Functions Duration | Execution time (p95) | Performance |
| Nudge Completion Rate | Custom metric | Business KPI |

---

## 🛠️ Roadmap

Honest inventory of what's next on the observability and reliability front. Nothing below blocks current operations — these are improvements for scale (1K+ active users) and tighter security posture.

### Short-term (next 2 weeks)

**Observability**
- Concurrency limits per Lambda function — cost protection at scale
- Invalid signature alarm — security monitoring (>10/hour threshold)
- Rate limit abuse alarm — abuse detection (>50/hour threshold)
- Scope Polly IAM to specific voices (least-privilege hardening)
- Business KPI dashboard (nudge completion rate, user retention)

**Business metrics**
- Response time tracking (nudge → farmer action)
- User retention rate (active at 30/60/90 days)
- Cohort analytics per district / crop

### Medium-term (1-3 months)

- Web demo RUM (CloudWatch Real User Monitoring)
- Distributed tracing across full voice pipeline (X-Ray segments)
- Cache hit rate for repeated RAG queries
- Cold-start rate monitoring for latency-sensitive Lambdas
- Per-partner dashboards (NGO / KVK / state agri department tenants)

### Long-term (post-MVP / productization)

- Predictive scaling metrics based on weather-trigger patterns
- Custom anomaly detection on farmer engagement patterns
- Per-crop / per-region cost attribution
- Cross-region replication for disaster recovery

---

## Summary

**Currently instrumented:**
- ✅ Comprehensive Lambda monitoring across 9 functions
- ✅ 9 active alarms covering reliability, cost, and queue health
- ✅ Custom business metrics (NudgesSent, NudgesCompleted)
- ✅ Cost tracking with automated alert at $5/day threshold
- ✅ Queue health monitoring (depth, age, DLQ)
- ✅ Security controls: HMAC verification, PII redaction, TTL retention

**Operating posture:** 100% uptime / 0% error rate / 0 DLQ messages over rolling 7-day window, running at ~$1.70/day against a $5/day alarm threshold.

**Next observability milestones:** concurrency limits, security event alarms, and the business KPI dashboard — see Roadmap above.

For the full production evidence summary, see [README — Production Evidence](../README.md#production-evidence).

