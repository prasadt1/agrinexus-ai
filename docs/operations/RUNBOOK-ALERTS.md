# Operations runbook — alerts and demos

This runbook matches CloudWatch alarms defined in [template-week2.yaml](../../template-week2.yaml) and the SNS topic **`agrinexus-alerts-${Environment}`**.

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
| `agrinexus-messages-dlq-depth-*` | **DLQ** has ≥ 1 visible message | Messages failed after retries; inspect DLQ payload, run **DLQHandler** logs, fix root cause and re-drive if needed. |

## Public web demo — abuse envelope

Three independent layers limit the web chat endpoint:

1. **Application** — 5 questions/hour per hashed IP **and** per `client_id` ([src/web-chat/handler.py](../../src/web-chat/handler.py)).
2. **API Gateway** — stage throttling (see template `MethodSettings` on Web Chat API).
3. **WAF** — IP rate limit on URI path ending with `/chat` (5-minute evaluation window).

Aggressive load tests will hit **429/403** by design; tune thresholds only if legitimate demos are blocked.

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
