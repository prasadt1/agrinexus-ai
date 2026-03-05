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
│ 2. PYTHON CODE CALLS BEDROCK API                               │
│    bedrock_agent.retrieve_and_generate()                       │
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
│    ├── Search OpenSearch Serverless                            │
│    │   Query: Find similar vectors                             │
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
│    Step B: AUGMENT (Add context to prompt)                     │
│    ├── Take retrieved chunks                                   │
│    ├── Build enhanced prompt:                                  │
│    │   "You are an agricultural advisor.                       │
│    │    Based on this FAO content:                             │
│    │    [Chunk 1] [Chunk 2] [Chunk 3]                         │
│    │    Answer in Hindi: Cotton mein aphids ka control        │
│    │    kaise karein?"                                         │
│    │                                                            │
│    └── Send to Claude 3 Sonnet                                 │
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
│ 4. GUARDRAILS CHECK (Before returning)                         │
│    ├── Check for banned pesticides ❌ Paraquat                 │
│    ├── Check for medical advice ❌ Human health                │
│    ├── Anonymize PII ❌ Phone numbers                          │
│    └── If blocked → Return KVK redirect message                │
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
→ [0.234, -0.567, 0.891, 0.123, ...]  # 1536 dimensions

# FAO content embeddings (stored in OpenSearch)
"Aphid Control: Use neem oil..."
→ [0.245, -0.543, 0.876, 0.134, ...]  # Similar vector!

# Cosine similarity = 0.92 (very similar!)
# This chunk gets retrieved
```

### 3. **Citations Prove Grounding**
Every response includes:
- Source document (which PDF)
- Exact text that was used
- S3 location

This prevents hallucinations - Claude can only use what's in the PDFs.

### 4. **Guardrails Work at Two Points**

**Input Guardrails** (before LLM):
```
Question: "Paraquat kahan se milega?"
→ Guardrail detects "Paraquat" (banned pesticide)
→ Blocks request
→ Returns: "I cannot provide advice on banned pesticides. 
           Please contact your local KVK."
```

**Output Guardrails** (after LLM):
```
If Claude somehow mentions banned content:
→ Guardrail blocks output
→ Returns safe message instead
```

## Testing the Logic

### Option 1: Run the example script
```bash
# After deploying infrastructure
python3 test_rag_example.py
```

### Option 2: Run full test suite
```bash
# Tests all 20 golden questions
pytest tests/test_golden_questions.py -v
```

### Option 3: Manual test with AWS CLI
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
4. **Safety Guardrails**: Blocks harmful content
5. **Scalable**: OpenSearch handles millions of queries
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

## Next Steps

Once Week 1 RAG is working:
- Week 2: Connect to WhatsApp (real user queries)
- Week 3: Add voice I/O (Transcribe + Polly)
- Week 4: Add vision (pest diagnosis with Claude Vision)

The RAG foundation you're building now powers all of these features!
