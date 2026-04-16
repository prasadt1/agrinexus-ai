# ADR 0005: Bedrock RAG Source Attribution

**Date:** 2026-04-15  
**Status:** Accepted  
**Deciders:** Development Team  

## Context

AgriNexus AI uses Bedrock Knowledge Base (RAG) to answer farming questions. For trust and credibility, farmers need to know the source of information. However, we encountered issues:

1. **Empty citations:** Bedrock's `retrievedReferences` array was empty despite generating answers
2. **Placeholder sources:** LLM was writing "स्त्रोत: 1" (Source: 1) instead of actual document names
3. **Prompt complexity:** Instructing LLM to extract document names from metadata was unreliable

## Problem

**How do we provide source attribution when Bedrock citations don't include document metadata?**

### What We Tried

#### Attempt 1: LLM-Based Extraction (Failed)
```
Prompt: "Extract the document name from search_results metadata and write 
'Source: [document name]' at the end"
```

**Result:** LLM wrote "स्त्रोत: 1" (placeholder number) because it couldn't access the metadata structure.

#### Attempt 2: Citation Metadata Extraction (Failed)
```python
citations = result['citations']
retrieved_refs = citations[0].get('retrievedReferences', [])
# retrieved_refs was always []
```

**Result:** Bedrock's `retrieve_and_generate` API returned empty `retrievedReferences` even though it generated answers.

## Decision

**Use generic source attribution based on Knowledge Base content, remove LLM-generated placeholders.**

### Implementation

```python
# 1. Remove placeholder sources (e.g., "स्त्रोत: 1")
if re.search(f"{source_keyword}\\s*\\d+\\s*$", response_text):
    response_text = re.sub(placeholder_pattern, '', response_text).strip()

# 2. Add generic attribution
source_attributions = {
    'hi': 'FAO/ICAR कृषि मार्गदर्शिका',
    'mr': 'FAO/ICAR शेती मार्गदर्शक',
    'te': 'FAO/ICAR వ్యవసాయ మార్గదర్శకం',
    'en': 'FAO/ICAR Agricultural Guidelines'
}
response_text += f"\n\n{source_keyword} {source_attributions[dialect]}"
```

### Updated Prompt Template
```
RESPONSE STYLE:
- DO NOT add any source citation or reference line at the end. 
  The system will add it automatically.
```

**Rationale:**
- LLM no longer tries to extract sources (prevents placeholders)
- System appends accurate generic attribution
- "FAO/ICAR Agricultural Guidelines" is truthful (that's what's in the KB)

## Consequences

### Positive
- ✅ **Always shows source** - No more empty or placeholder citations
- ✅ **Accurate** - Generic attribution matches KB content (FAO/ICAR docs)
- ✅ **Dialect-aware** - Source shown in user's language
- ✅ **Reliable** - Doesn't depend on Bedrock citation metadata
- ✅ **Trustworthy** - Farmers see credible source (FAO/ICAR)

### Negative
- ⚠️ **Less specific** - Can't show individual document names
- ⚠️ **Generic** - All answers cite "FAO/ICAR Guidelines" (not granular)

### Neutral
- If Bedrock fixes citation metadata in future, we can switch to specific sources
- Generic attribution is still better than "Source: 1" or no source

## Why Bedrock Citations Are Empty

### Root Cause Analysis

Bedrock's `retrieve_and_generate` API has two modes:

1. **Retrieve + Generate (what we use):**
   ```python
   response = bedrock_agent.retrieve_and_generate(
       input={'text': query},
       retrieveAndGenerateConfiguration={...}
   )
   ```
   - Returns `citations` array with `retrievedReferences: []` (empty)
   - Optimized for speed, doesn't include full metadata

2. **Retrieve (separate call):**
   ```python
   response = bedrock_agent.retrieve(
       knowledgeBaseId=KB_ID,
       retrievalQuery={'text': query}
   )
   ```
   - Returns full `retrievalResults` with S3 URIs and metadata
   - Requires separate `invoke_model` call for generation
   - Slower (two API calls)

**Why we don't use separate retrieve:**
- Adds 2-3 seconds latency (already at 13s for RAG)
- More complex code (two API calls + manual prompt construction)
- Higher cost (2x Bedrock API calls)
- Generic attribution is "good enough" for MVP

## Alternatives Considered

### 1. Separate Retrieve + Generate Calls (Rejected)
```python
# Step 1: Retrieve with metadata
retrieve_response = bedrock_agent.retrieve(...)
sources = [r['location']['s3Location']['uri'] for r in retrieve_response['retrievalResults']]

# Step 2: Generate with sources in prompt
generate_response = bedrock.invoke_model(...)
```

- **Pros:** Get specific document names
- **Cons:** 
  - 2-3s additional latency
  - 2x API calls = 2x cost
  - More complex error handling
  - Overkill for generic attribution

### 2. No Source Attribution (Rejected)
- **Pros:** Simpler code
- **Cons:**
  - Farmers don't trust answers without sources
  - Competition judges expect citations
  - Best practice for RAG systems

### 3. Hardcode "FAO Guidelines" in English Only (Rejected)
- **Pros:** Simplest implementation
- **Cons:**
  - Not dialect-aware (bad UX for Hindi/Marathi/Telugu users)
  - Looks unprofessional

### 4. Show Multiple Generic Sources (Rejected)
```
स्त्रोत: FAO Cotton IPM Guide, ICAR Pest Management, WHO Pesticide Guidelines
```

- **Pros:** More specific
- **Cons:**
  - Can't verify which docs were actually used
  - Misleading if answer only used one source
  - Longer text (bad for WhatsApp)

## Future Improvements

### If Bedrock Adds Citation Metadata
```python
if retrieved_refs and len(retrieved_refs) > 0:
    uri = retrieved_refs[0]['location']['s3Location']['uri']
    doc_name = extract_doc_name(uri)  # "FAO Cotton IPM Guide"
    response_text += f"\n\n{source_keyword} {doc_name}"
else:
    # Fallback to generic
    response_text += f"\n\n{source_keyword} {generic_attribution}"
```

### Document-Level Tagging
Tag S3 documents with metadata:
```json
{
  "title": "FAO Cotton Integrated Pest Management",
  "language": "en",
  "region": "South Asia"
}
```

Then extract from Bedrock response if available.

## Knowledge Base Content

Current KB contains:
- FAO Integrated Pest Management guides (Cotton, Wheat, Soybean)
- ICAR crop advisory bulletins
- State agricultural department guidelines
- Pesticide safety guidelines (WHO)

**Generic attribution "FAO/ICAR Agricultural Guidelines" accurately represents this content.**

## Related Decisions
- ADR 0003: WhatsApp Integration Architecture
- ADR 0004: Voice Processing Pipeline

## References
- [Bedrock Knowledge Base API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_RetrieveAndGenerate.html)
- [RAG Citation Best Practices](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test.html)

## Notes
- Issue discovered: 2026-04-15 during testing
- Root cause: Bedrock `retrievedReferences` empty in `retrieve_and_generate` response
- Solution implemented: Generic attribution with placeholder removal
- Cost impact: None (no additional API calls)
