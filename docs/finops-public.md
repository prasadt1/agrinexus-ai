# AgriNexus Cost Model (Public Appendix)

This note backs the article claim:

- **Modeled at 10,000 active farmers:** **~$450/month**
- Equivalent to **~$0.54/farmer/year**

These are modeled figures (not a final invoice snapshot), based on expected async WhatsApp usage, mixed text/voice traffic, and periodic weather-gated nudges.

## Semi-final baseline (for context)

Before the finalist optimization pass, the semi-final cost shape at **1,000 farmers/month** was:

- **~$214/month total**
- With a fixed OpenSearch floor of **~$174/month** (always-on OCUs), plus variable usage costs

That fixed floor is exactly what motivated the OpenSearch → S3 Vectors migration.

## Modeled monthly breakdown (10K active farmers)

| Cost bucket | Modeled monthly cost (USD) | Notes |
|---|---:|---|
| Bedrock generation + retrieval tokens | 170 | Dominant variable cost for advisory responses |
| Vector retrieval/storage (S3 Vectors path) | 90 | Replaced always-on OpenSearch profile |
| Transcribe (voice notes) | 95 | Depends on voice-note mix and duration |
| Polly (voice replies) | 25 | Optional audio reply path |
| Serverless infra (Lambda/SQS/Step Functions/DynamoDB/S3/logs) | 70 | Lower share vs AI/voice services |
| **Total** | **450** | Matches article claim |

## Performance snapshot (semi-final test context)

These were article-level benchmark targets used in the semi-final narrative:

| Metric | Snapshot |
|---|---|
| API response time | 3–5s (p95, including Bedrock path) |
| Lambda cold start | <2s (Python 3.11) |
| RAG accuracy | ~95% on golden question set |
| Vision confidence | 85%+ on pest identification set |
| Voice transcription accuracy | 87%+ (Hindi/English mix) |
| DynamoDB query latency | <10ms |

## Key assumptions

- Async workflow (not real-time streaming) for voice MVP.
- Mixed traffic across text and voice, with moderate nudge cadence.
- Retrieval/storage path optimized for pay-per-use economics.
- Public-demo throttles and evaluator access controls remain enabled.

## AWS Credits note (Builder phase)

Builder-phase experimentation (Kiro-assisted development, demos, and iteration) used AWS promotional credits where available.  
The **$450/month** steady-state model above represents projected recurring run costs, not one-time build-phase credit effects.

### Competition budget context

| Resource | Amount | Used for |
|---|---:|---|
| AWS credits | 200 | Infra + Bedrock + Transcribe/Polly + orchestration services during build/demo |
| Kiro credits | 2,000 (Pro+ equivalent) | EARS requirements, design specs, scaffolding acceleration |

## Scope note

Final pilot invoices will vary by message mix, seasonality, and adoption behavior.

