# Operations runbook — alerts and demos

This runbook matches CloudWatch alarms defined in [template.yaml](../../template.yaml) and the SNS topic **`agrinexus-alerts-${Environment}`**.

## Subscribe to alerts

1. In **AWS Console → SNS → Topics**, open `agrinexus-alerts-dev` (or your environment).
2. Create a **subscription** (email or SMS) and confirm it.

## Alarm summary

| Alarm | Meaning | First actions |
|-------|---------|----------------|
| `agrinexus-nudge-workflow-failures-*` | Step Functions nudge workflow failed | CloudWatch Logs for `NudgeSender` / state machine execution; check Dynamo profile and scheduler permissions. |
| `agrinexus-high-cost-*` | Estimated daily AWS charges ≥ **$20** | Cost Explorer → service breakdown; check Bedrock / Transcribe spikes after traffic. |
| `agrinexus-processor-errors-*` | **MessageProcessor** ≥ 5 errors / 5 min | Lambda log group `agrinexus-processor-dev`; check Bedrock KB, Dynamo, SQS permissions. |
| `agrinexus-webhook-errors-*` | **WebhookHandler** ≥ 5 errors / 5 min | Webhook logs; verify Meta payload format, Secrets Manager, SQS send. |
| `agrinexus-web-chat-errors-*` | **WebChatHandler** ≥ 3 errors / 5 min | Public demo path; check KB id env, Bedrock quotas, Dynamo rate-limit table. |
| `agrinexus-voice-errors-*` | **VoiceProcessor** ≥ 3 errors / 5 min | Transcribe / S3 temp bucket / Polly; often media or quota related. |
| `agrinexus-messages-queue-age-*` | Oldest SQS message age **> 300 s** (2 consecutive periods) | Processor stuck or throttled; check queue depth and processor concurrency/errors. |
| `agrinexus-visitor-whatsapp-volume-*` | WhatsApp visitor answers passed **500** in a day (`VisitorVolumeAlarmThreshold`) | Real interest or abuse? Check `AgriNexus/Visitor` metrics and the webhook logs for many numbers in a short time. Raise caps below if real. |
| `agrinexus-visitor-web-volume-*` | Web demo answers passed **500** in a day | Check `web_question_answered` and WAF sampled requests for one IP or a burst of new client IDs. |
| `agrinexus-messages-dlq-depth-*` | **DLQ** has ≥ 1 visible message | Messages failed after retries; inspect DLQ payload, run **DLQHandler** logs, fix root cause and re-drive if needed. |

## Public web demo — abuse envelope

Three independent layers limit the web chat endpoint:

1. **Application** — 20 questions/hour per browser (`client_id`) and 300/hour per source IP, plus 2,000 answers/day across all web visitors ([src/web-chat/handler.py](../../src/web-chat/handler.py)). The per-IP limit is loose on purpose: venue Wi-Fi and mobile carriers put many people behind one address.
2. **API Gateway** — stage throttling (see template `MethodSettings` on Web Chat API).
3. **WAF** — IP rate limit on URI path ending with `/chat` (5-minute evaluation window).

Aggressive load tests will hit **429/403** by design; tune thresholds only if legitimate demos are blocked.

## Changing visitor limits during an event (no deploy)

The daily caps are circuit breakers, not budgets. If a volume alarm fires and the traffic is real, raise them in the Lambda console instead of redeploying:

| Limit | Function | Environment variable |
|-------|----------|----------------------|
| Web, per browser per hour | `agrinexus-web-chat-dev` | `WEB_RATE_LIMIT` |
| Web, per IP per hour | `agrinexus-web-chat-dev` | `WEB_IP_RATE_LIMIT` |
| Web, per day (all) | `agrinexus-web-chat-dev` | `WEB_DAILY_GLOBAL_CAP` |
| WhatsApp visitor, per number per day | `agrinexus-processor-dev` | `VISITOR_DAILY_PER_USER_CAP` |
| WhatsApp visitor, per day (all) | `agrinexus-processor-dev` | `VISITOR_DAILY_GLOBAL_CAP` |

AWS Console → Lambda → the function → Configuration → Environment variables → Edit → Save. New invocations pick up the value. The next `sam deploy` resets it to the template value, so pass the same number as a parameter override (`WebDailyGlobalCap`, `VisitorDailyGlobalCap`, ...) when you next deploy.

## Pre-demo smoke (automated)

From repo root:

```bash
./scripts/e2e-smoke.sh
```

With optional Bedrock and API checks:

```bash
export KNOWLEDGE_BASE_ID=YOUR_KB_ID
export WEB_CHAT_URL='https://YOUR_API.execute-api.us-east-1.amazonaws.com/dev/chat'
./scripts/e2e-smoke.sh
```

See [E2E-TEST-CHECKLIST.md](../testing/E2E-TEST-CHECKLIST.md) for the full manual checklist.
