# Cost Alignment Fixes - Week 1

## Issue Summary

Two critical alignment issues were identified:

1. **Cost Discrepancy**: Architecture spec claimed "Bedrock Managed Vector Store (no additional cost)" but implementation uses OpenSearch Serverless (~$20/month minimum)
2. **Schema Alignment**: Template.yaml used REGION# PK pattern but design.md GSI definitions didn't match the generic GSI1PK/GSI1SK approach

## Changes Made

### 1. Cost Updates Across All Documents

**Updated from**: ~$30/month  
**Updated to**: ~$50/month

#### Files Changed:

**architecture.md**:
- Line 12: Updated cost estimate from $30 to $50/month
- Line 18: Updated cost-conscious principle from $30 to $50/month
- Line 139: Changed "Bedrock Managed Vector Store (no additional cost)" to "OpenSearch Serverless vector store (~$20/month for 1 OCU)"
- Line 145: Changed "managed vector store" to "OpenSearch Serverless vector store"
- Lines 730-745: Added OpenSearch Serverless line item (~$20), updated total from $30 to $50/month
- Updated cost driver notes: OpenSearch Serverless (40%), Bedrock (30%), DynamoDB (25%)

**requirements.md**:
- Line 18: Updated cost from $30 to $50/month
- Line 288: Updated REQ-COST-005 from $30 to $50/month
- Line 406: Updated AC-010 from $30 to $50/month

**README.md**:
- Architecture section: Updated cost from $30 to $50/month
- Cost breakdown table: Added note about OpenSearch Serverless fixed minimum cost

**WEEK1-SUMMARY.md**:
- Cost Analysis section: Expanded explanation of OpenSearch Serverless cost
- Added cost optimization options (Aurora Serverless v2, accept cost, etc.)
- Updated full system cost projection to $50/month

**DEPLOYMENT.md**:
- Cost concerns section: Added detailed breakdown showing OpenSearch Serverless as 40% of total cost
- Added explanation of $0.24/hour per OCU (1 indexing + 1 search = ~$20/month)

**template.yaml**:
- Added cost warning comment above OpenSearch Serverless resource definition

### 2. Schema Alignment Fixes

**design.md Section 2.4 (Global Secondary Indexes)**:

**Before**:
```
GSI-1: SessionIndex (sessionId, timestamp)
GSI-2: StatusIndex (status, scheduledReminderAt)
GSI-3: RegionActivityIndex (region, createdAt)
```

**After**:
```
GSI1: Region/Activity Index (GSI1PK, GSI1SK)
  - GSI1PK = REGION#{region}
  - GSI1SK = NUDGE#{timestamp}
  
GSI2: Status/Reminder Index (GSI2PK, GSI2SK)
  - GSI2PK = STATUS#{status}
  - GSI2SK = scheduledReminderAt
```

**Rationale**: Generic GSI attribute names (GSI1PK/GSI1SK) follow single-table design best practices and allow flexible overloading of indexes for multiple access patterns.

**design.md Section 2.3.4 (Nudge Entity)**:

Added GSI attributes to the RegionalNudge entity example:
```json
{
  "PK": "REGION#Aurangabad District",
  "SK": "NUDGE#1707955200#spray-pesticide",
  "GSI1PK": "REGION#Aurangabad District",
  "GSI1SK": "NUDGE#1707955200",
  "GSI2PK": "STATUS#pending",
  "GSI2SK": 1707955200,
  ...
}
```

Also fixed TTL attribute from "TTL" to "ttl" (lowercase) to match DynamoDB convention.

## Cost Breakdown (Updated)

### Week 1 Only
| Service | Cost |
|---------|------|
| OpenSearch Serverless | ~$20 |
| Bedrock KB queries | ~$5 |
| Other (DynamoDB, S3, Lambda) | ~$0 |
| **Total** | **~$25/month** |

### Full System (Weeks 1-4)
| Service | Cost | % of Total |
|---------|------|------------|
| OpenSearch Serverless | ~$20 | 40% |
| Bedrock (Claude 3 Sonnet) | ~$15 | 30% |
| DynamoDB overage | ~$12.50 | 25% |
| Transcribe + Polly | ~$2.40 | 5% |
| Other services | ~$0.10 | <1% |
| **Total** | **~$50/month** | 100% |

## Why OpenSearch Serverless?

**Pros**:
- Fully managed (no maintenance)
- Auto-scaling
- Integrated with Bedrock Knowledge Bases
- Production-grade vector search
- High availability

**Cons**:
- Minimum cost ~$20/month (1 OCU indexing + 1 OCU search)
- Cannot scale to zero
- Fixed cost even with low usage

**Alternatives Considered**:

1. **Aurora Serverless v2** (with pgvector)
   - Lower minimum cost (~$0.12/hour when idle = ~$3.60/month)
   - Requires custom vector store implementation
   - Not integrated with Bedrock Knowledge Bases
   - More complex setup

2. **Pinecone/Weaviate** (third-party)
   - Free tiers available
   - Adds external dependency
   - Data residency concerns
   - Not AWS-native

3. **Accept OpenSearch Serverless cost**
   - ✓ Simplest implementation
   - ✓ Production-ready
   - ✓ AWS-native
   - ✓ $50/month is reasonable for 1,000 users

**Decision**: Accept OpenSearch Serverless cost. For a production system serving 1,000 farmers, $50/month (~$0.05 per user) is reasonable and competitive.

## Billing Alarm Threshold Logic

**Baseline Cost**: $50/month

**Alarm Thresholds**:
1. **$50 alarm**: Baseline - normal operation, no alert needed
2. **$75 alarm** (150% of baseline): First warning - investigate usage patterns
3. **$100 alarm** (200% of baseline): Critical alert - immediate action required

**Rationale**: 
- First alarm at baseline would trigger constantly during normal operation
- 50% buffer ($50 → $75) allows for natural usage variation
- 100% buffer ($50 → $100) catches runaway costs before they double

**CloudWatch Alarm**: Set at $75 (150% of baseline) for proactive monitoring

**Success Metric**: <$60 during MVP phase (20% buffer above baseline for testing/development spikes)

## Competition Alignment

**For AWS 10,000 AIdeas judges**:

- Original pitch: "Free-tier-leaning serverless architecture"
- Updated reality: "Free-tier-leaning serverless with pay-as-you-go vector search"
- Cost: $50/month for 1,000 users = $0.05 per user per month
- Comparison: Commercial agricultural advisory services charge $5-10 per user per month
- Value proposition: 100x cost reduction while maintaining quality

**Key message**: The $20/month OpenSearch Serverless cost is a necessary investment for production-grade RAG capabilities. The total $50/month cost is still extremely competitive for the social impact delivered.

## Verification Checklist

- [x] All cost references updated from $30 to $50/month
- [x] OpenSearch Serverless cost explicitly called out in all documents
- [x] Cost breakdown shows OpenSearch as 40% of total
- [x] GSI definitions in design.md match template.yaml (GSI1PK/GSI1SK pattern)
- [x] REGION# PK pattern documented in Access Patterns (AP5)
- [x] RegionalNudge entity includes GSI attributes
- [x] Cost optimization alternatives documented
- [x] Competition alignment messaging prepared
- [x] Billing alarm thresholds updated to $50, $75, $100 (baseline at $50)
- [x] CloudWatch alarm threshold updated from $50 to $75
- [x] Success metrics updated from <$35 to <$60 for MVP phase

## Files Modified

1. architecture.md (8 changes)
   - Line 12: Cost estimate $30 → $50
   - Line 18: Cost principle $30 → $50
   - Line 139: Vector store description updated
   - Line 145: Vector store terminology updated
   - Lines 730-745: Cost table with OpenSearch Serverless
   - Line 605: Billing alarm $50 → $75
   - Line 828: Cost audit $30 → $50
   - Line 855: Billing alarms $25/$50/$75 → $50/$75/$100
   - Line 877: Success metric <$35 → <$60
2. requirements.md (3 changes)
3. design.md (2 changes)
4. README.md (2 changes)
5. WEEK1-SUMMARY.md (1 change)
6. DEPLOYMENT.md (1 change)
7. template.yaml (1 change)

**Total**: 7 files, 18 changes

## Next Steps

1. Review changes with user
2. Confirm $50/month cost is acceptable for competition
3. Proceed with Week 2 implementation
4. Monitor actual costs during development
5. Consider Aurora Serverless v2 migration post-MVP if cost becomes an issue
