# RAG Best Practices for AgriNexus

## Core Philosophy

**Quality over Quantity**: 5-10 well-curated, authoritative documents beat 100 random PDFs.

**Licensing First**: Only use documents you have clear rights to use in production.

**Test-Driven**: Every document addition should improve your golden question scores.

## Document Curation Hierarchy

### Tier 1: Government Extension Materials (Highest Priority)
- **Indian Sources**: PPQS, NIPHM, ICAR, State Agricultural Universities
- **International**: FAO, USDA Extension, CABI
- **Characteristics**:
  - Public domain or CC BY license
  - Practical, farmer-facing advice
  - Region-specific recommendations
  - Current pest alerts and advisories

**Examples**:
- PPQS cotton pest advisories
- NIPHM pest alerts
- State "Package of Practices" bulletins
- FAO IPM manuals

### Tier 2: Open Access Research (Use Selectively)
- **Sources**: FAO AGRIS ODS, PubMed Central, institutional repositories
- **Characteristics**:
  - Explicitly marked open access (CC BY, CC0)
  - Peer-reviewed technical depth
  - Comprehensive pest biology and management

**Warning**: ResearchGate uploads are often copyrighted. Verify before using.

### Tier 3: Commercial/Proprietary (Avoid for Now)
- Textbooks, commercial pest guides
- Requires licensing agreements
- Not suitable for public-facing RAG

## The Manifest System

### Why Track Metadata?

Every document in your KB should have an entry in `kb_manifest.csv`:

```csv
filename,title,source_url,year,license,region,crop,pests
ppqs-pink-bollworm.pdf,Advisory on Pink Bollworm,https://ppqs.gov.in/,2023,Public Domain,India,Cotton,Pink Bollworm
```

### Benefits:

1. **Licensing Compliance**: Know what you can legally use
2. **Citation Tracking**: Provide proper attribution in responses
3. **Quality Control**: Easy to audit what's in your KB
4. **Filtering**: Enable region/crop/pest-specific queries
5. **Evaluation**: Track which documents improve RAG performance

## The Golden Question Workflow

### 1. Define Your Slice
- **Crop**: Cotton
- **Region**: India (Gujarat, Punjab, Maharashtra)
- **Pests**: Pink bollworm, whitefly, aphids, bollworms
- **Languages**: Hindi, Marathi, Telugu

### 2. Collect 5-10 Core Documents
Apply three tests:
- ✅ From government/FAO or clearly open access
- ✅ Concrete recommendations (not just theory)
- ✅ Recent (last 10-15 years) or still in use

### 3. Create Golden Questions (15-20)
Examples:
```python
{
    "question": "Cotton mein aphids ka control kaise karein?",
    "expected_keywords": ["neem", "imidacloprid", "spray"],
    "banned_keywords": ["paraquat"],
    "language": "Hindi"
}
```

### 4. Ingest & Test
```bash
# Upload documents
aws s3 sync data/fao-pdfs/en/new-sources/ s3://your-bucket/

# Sync KB
aws bedrock-agent start-ingestion-job --knowledge-base-id YOUR_KB_ID

# Test
pytest tests/test_golden_questions.py -v
```

### 5. Iterate
- Document passes tests? Keep it.
- Document doesn't help? Remove it.
- Missing information? Find better sources.

## Scaling the Pattern

Once cotton pests work well, repeat for:

### Phase 2: Major Crops
- **Wheat**: Rust, aphids, termites
- **Rice**: Blast, stem borer, brown planthopper
- **Maize**: Fall armyworm, stem borer

### Phase 3: Regional Expansion
- North India (Punjab, Haryana)
- Central India (MP, Maharashtra)
- South India (Karnataka, Tamil Nadu, Telangana)

### Phase 4: Language Coverage
- Hindi (primary)
- Marathi, Telugu, Kannada
- Punjabi, Gujarati

## Common Pitfalls to Avoid

### ❌ Don't Do This:
1. **Download everything from ResearchGate**
   - Many are copyrighted
   - Quality varies wildly
   - Hard to maintain

2. **Ignore licensing**
   - Legal risk for production
   - Can't provide proper citations
   - Ethical issues

3. **No testing**
   - Don't know if documents help
   - Can't measure improvements
   - Waste of ingestion costs

4. **Too many documents**
   - Dilutes signal with noise
   - Increases costs
   - Harder to maintain

### ✅ Do This Instead:
1. **Start with government sources**
   - Clear licensing
   - Practical advice
   - Trusted by farmers

2. **Track everything in manifest**
   - Know what you have
   - Easy to audit
   - Enables citations

3. **Test systematically**
   - Golden questions
   - Before/after comparisons
   - Track improvements

4. **Keep it focused**
   - 5-10 docs per topic
   - High signal-to-noise
   - Easy to maintain

## Measuring Success

### Metrics to Track:

1. **Golden Question Pass Rate**
   - Target: >80% for core questions
   - Track per language
   - Track per pest type

2. **Citation Quality**
   - Are responses citing the right documents?
   - Are citations relevant to the question?
   - Are banned pesticides properly flagged?

3. **Response Specificity**
   - Generic IPM advice vs. specific recommendations
   - Presence of thresholds, timings, dosages
   - Regional adaptations

4. **User Feedback** (when deployed)
   - Farmer satisfaction
   - KVK officer feedback
   - Accuracy reports

## Next Steps for Your Project

### Immediate (This Week):
1. ✅ Download PPQS and NIPHM advisories
2. ✅ Fill out kb_manifest.csv
3. ✅ Upload and sync KB
4. ✅ Run tests and measure improvement

### Short Term (This Month):
1. Expand golden questions to 20-30
2. Add more NIPHM advisories (other pests)
3. Find FAO cotton IPM manuals (CC BY)
4. Test with actual Hindi/Marathi/Telugu questions

### Medium Term (Next Quarter):
1. Add wheat and rice pest documents
2. Expand to more Indian states
3. Improve guardrails for banned pesticides
4. Add KVK contact information

### Long Term (6 Months):
1. Cover top 10 crops in India
2. Full language coverage (6+ languages)
3. Regional customization
4. Integration with real-time pest alerts

## Resources

### Finding Open Access Documents:
- **FAO AGRIS**: https://agris.fao.org/
- **ICAR Publications**: http://krishi.icar.gov.in/
- **State Ag Universities**: Search "[state] agricultural university publications"
- **PubMed Central**: https://www.ncbi.nlm.nih.gov/pmc/ (filter for open access)

### Licensing Guides:
- **Creative Commons**: https://creativecommons.org/licenses/
- **Public Domain**: Government works in India are generally public domain
- **Fair Use**: Not reliable for commercial RAG systems

### RAG Evaluation:
- Track golden question scores over time
- A/B test document additions
- Monitor citation relevance
- Collect user feedback

## Summary

Building a production RAG system is about:
1. **Curation** over collection
2. **Licensing** compliance
3. **Testing** systematically
4. **Iterating** based on results

Start small, measure everything, and expand methodically. Your farmers deserve accurate, trustworthy advice backed by authoritative sources.
