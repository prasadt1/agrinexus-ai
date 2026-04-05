# How Bedrock RAG Works - Detailed Explanation

## The Complete Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER ASKS QUESTION (Hindi/Marathi/Telugu)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        "Cotton mein aphids ka control kaise karein?"
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. LAMBDA CALLS BEDROCK AGENT RUNTIME                          │
│    bedrock_agent.retrieve_and_generate() (see handler.py)      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. BEDROCK KNOWLEDGE BASE PROCESSES REQUEST                    │
│                                                                 │
│    Step A: RETRIEVE (Search)                                   │
│    ├── Convert question to embedding vector                    │
│    │   [0.234, -0.567, 0.891, ...]                            │
│    │                                                            │
│    ├── Vector search over the Knowledge Base index             │
│    │   (S3 Vectors in current AWS setup; older deployments     │
│    │    used OpenSearch Serverless — same retrieve API)       │
│    │   Query: Find similar embeddings                          │
│    │                                                            │
│    └── Return top 5 relevant chunks from FAO PDFs              │
│        ┌─────────────────────────────────────────┐            │
│        │ Chunk 1: "Aphid Control: Use neem oil  │            │
│        │ 5ml/liter or imidacloprid 0.3ml/liter" │            │
│        │ Source: ipm-guide.pdf, page 23          │            │
│        └─────────────────────────────────────────┘            │
│        ┌─────────────────────────────────────────┐            │
│        │ Chunk 2: "Threshold: 5-10 aphids per   │            │
│        │ leaf. Spray during early morning..."    │            │
│        │ Source: cotton-production.pdf, page 45  │            │
│        └─────────────────────────────────────────┘            │
│        ┌─────────────────────────────────────────┐            │
│        │ Chunk 3: "Weather conditions: No rain  │            │
│        │ for 24h, wind speed < 10 km/h..."      │            │
│        │ Source: pesticide-application.pdf, p12  │            │
│        └─────────────────────────────────────────┘            │
│                                                                 │
│    Step B: AUGMENT (RAG prompt with $query$ + $search_results$)│
│    ├── Take retrieved chunks                                   │
│    ├── Build enhanced prompt:                                  │
│    │   "You are an agricultural advisor.                       │
│    │    Based on this FAO content:                             │
│    │    [Chunk 1] [Chunk 2] [Chunk 3]                         │
│    │    Answer in Hindi: Cotton mein aphids ka control        │
│    │    kaise karein?"                                         │
│    │                                                            │
│    └── Send to the foundation model (default Claude 3 Sonnet   │
│        in code; override with MODEL_ARN env if set)            │
│                                                                 │
│    Step C: GENERATE (LLM creates response)                     │
│    ├── Claude reads FAO content                                │
│    ├── Understands question is in Hindi                        │
│    ├── Generates response in Hindi                             │
│    ├── Includes specific recommendations                       │
│    └── Adds citations to sources                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. GUARDRAILS (Optional — if GUARDRAIL_ID is set on Lambda)    │
│    generationConfiguration.guardrailConfiguration in Bedrock   │
│    Policy depends on your guardrail in Bedrock (e.g. banned     │
│    substances, off-topic). If GUARDRAIL_ID is empty, this step │
│    is skipped — only the prompt’s domain rules apply.          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. RESPONSE RETURNED TO PYTHON                                 │
│                                                                 │
│    {                                                            │
│      'output': {                                                │
│        'text': 'Aphids ke liye neem oil (5ml/liter) ya        │
│                 imidacloprid (0.3ml/liter) spray karein.       │
│                 Subah ya shaam ko spray karein jab hawa        │
│                 kam ho. 24 ghante tak barish nahi honi         │
│                 chahiye.'                                       │
│      },                                                         │
│      'citations': [                                             │
│        {                                                        │
│          'retrievedReferences': [                               │
│            {                                                    │
│              'content': {'text': 'Aphid Control: Use neem...'},│
│              'location': {                                      │
│                's3Location': {                                  │
│                  'uri': 's3://bucket/en/ipm-guide.pdf'         │
│                }                                                │
│              }                                                  │
│            }                                                    │
│          ]                                                      │
│        }                                                        │
│      ]                                                          │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. TEST VALIDATES RESPONSE                                     │
│    ✓ Contains expected keywords: neem, imidacloprid, spray    │
│    ✓ No banned keywords: paraquat, monocrotophos              │
│    ✓ Has citations from FAO sources                           │
│    ✓ Response is in Hindi (matches question language)         │
└─────────────────────────────────────────────────────────────────┘
```

## Key Points

### 1. **Multilingual Magic**
- FAO PDFs are in **English**
- Question is in **Hindi/Marathi/Telugu**
- Claude 3 Sonnet automatically:
  - Understands the question language
  - Reads English FAO content
  - Generates response in the question's language

### 2. **Vector Search**
```python
# Question embedding
"Cotton mein aphids ka control kaise karein?"
→ [0.234, -0.567, ...]  # length set by the embedding model (not always 1536)

# FAO content embeddings (stored in OpenSearch)
"Aphid Control: Use neem oil..."
→ [0.245, -0.543, 0.876, 0.134, ...]  # Similar vector!

# Cosine similarity ranks chunks; top results feed the model.
# Embedding dimension depends on the model (e.g. Titan Embed Text v2 → 1024 dims).
```

### 3. **Citations Prove Grounding**
Every response includes:
- Source document (which PDF)
- Exact text that was used
- S3 location

This prevents hallucinations - Claude can only use what's in the PDFs.

### 4. **Guardrails (when configured)**

Bedrock Knowledge Bases can attach a **guardrail** to generation. This project passes `guardrailConfiguration` only when `GUARDRAIL_ID` is non-empty (`src/processor/handler.py`). Behavior (input vs output interception) is defined in the Bedrock guardrail resource, not in this repo’s Python code.

## Testing the Logic

### Option 1: Golden-question tests (recommended)
```bash
export KNOWLEDGE_BASE_ID=your_kb_id   # required — tests skip if unset
pytest tests/test_golden_questions.py -v
```

### Option 2: Manual test with AWS CLI
```bash
KB_ID="your-kb-id"

aws bedrock-agent-runtime retrieve-and-generate \
  --region us-east-1 \
  --input '{"text":"Cotton mein aphids ka control kaise karein?"}' \
  --retrieve-and-generate-configuration '{
    "type": "KNOWLEDGE_BASE",
    "knowledgeBaseConfiguration": {
      "knowledgeBaseId": "'$KB_ID'",
      "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"
    }
  }'
```

## What Makes This Production-Ready

1. **Grounded in Facts**: Only uses FAO content (no hallucinations)
2. **Multilingual**: Handles Hindi, Marathi, Telugu automatically
3. **Cited Sources**: Every answer includes references
4. **Safety Guardrails**: When `GUARDRAIL_ID` is set, Bedrock applies your guardrail; otherwise domain rules rely on the prompt
5. **Scalable**: Managed vector storage (S3 Vectors or OpenSearch) behind the same API
6. **Monitored**: CloudWatch tracks latency, errors, costs

## Common Issues & Solutions

### Issue: "No relevant content found"
**Cause**: KB ingestion not complete or PDFs empty
**Solution**: 
```bash
# Check ingestion status
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID

# Re-trigger ingestion
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id $KB_ID \
  --data-source-id $DATA_SOURCE_ID
```

### Issue: "Response not in Hindi"
**Cause**: Claude defaults to English if prompt unclear
**Solution**: Already handled in code with explicit language instruction

### Issue: "No citations returned"
**Cause**: Guardrails blocked content or KB misconfigured
**Solution**: Check guardrail logs in CloudWatch

## Production stack (this repo)

RAG answers are invoked from the **MessageProcessor** Lambda after WhatsApp → SQS. Voice and vision use separate paths (Transcribe/Polly and Bedrock Vision) but text RAG uses the same `retrieve_and_generate` flow described above.

See `architecture.md` and `README.md` for the full pipeline and KB rebuild notes (`REBUILD-KB-WITH-S3-VECTORS.md` if you use S3 Vectors).
