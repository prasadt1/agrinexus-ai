# Sources for Cotton Pest Management Information

## Problem Identified
Your current FAO PDFs don't contain specific pest control information (aphid treatments, pesticide recommendations, etc.) that your tests expect. The RAG system is working correctly but returning generic IPM information.

## Recommended Sources

### 1. Research Papers (Free & Detailed)
The ResearchGate paper "Insect Pests of Cotton" (2018) by Rajendran et al. contains:
- Detailed aphid, whitefly, bollworm biology
- Specific pesticide recommendations (imidacloprid, thiamethoxam, neem, etc.)
- Economic threshold levels
- IPM strategies for Indian conditions

**URL**: https://www.researchgate.net/publication/326762536_Insect_Pests_of_Cotton

### 2. Indian Government Resources

**HIGH PRIORITY - These are official Indian government sources in regional languages!**

- **PPQS** (Directorate of Plant Protection, Quarantine & Storage): https://ppqs.gov.in/advisories-section
  - Advisory on Pink boll worm (Pectinophora gossypiella) - 1.35 MB
  - Advisory on White fly (Bemisia tabaci) - 1.82 MB
  - These are official pest management advisories

- **NIPHM** (National Institute of Plant Health Management): https://niphm.gov.in/
  - Pest Alerts section has multiple cotton advisories:
    - Advisory for cotton pests (Sept 2022) - 604 KB
    - Pest Alert and Advisory for Cotton (Sept 2021) - 484 KB
    - Pest Advisory in Cotton (May 2020) - 108 KB
    - Pest warning and management advice in Cotton crop (July & Aug 2019) - 344-544 KB
  - These contain region-specific, timely pest management advice

- **ICAR-CICR** (Central Institute for Cotton Research): http://cicr.org.in/
  - Pest management guides
  - IPM packages
  - Regional recommendations

### 3. State Agricultural Universities
- **University of Agricultural Sciences, Dharwad** (Karnataka)
- **Punjab Agricultural University, Ludhiana**
- **Tamil Nadu Agricultural University, Coimbatore**

These publish extension bulletins in regional languages (Hindi, Marathi, Telugu).

### 4. International Resources
- **ICAC** (International Cotton Advisory Committee)
- **Cotton Australia** - Cotton Pest Management Guide (very detailed)
- **Texas A&M AgriLife Extension** - Cotton Insect Management Guide

## What to Look For

Your tests expect information on:
1. **Aphid control**: neem, imidacloprid, spray timing, threshold (5-10 aphids/leaf)
2. **Whitefly control**: thiamethoxam, acetamiprid, leaf underside treatment
3. **Bollworm control**: Bt cotton, pheromone traps, square formation timing
4. **Weather conditions for spraying**: wind speed <10 km/h, no rain 24h, morning/evening
5. **Irrigation**: 7-10 day intervals during flowering/boll formation
6. **Nitrogen**: 120-150 kg/ha, split application
7. **Banned pesticides**: paraquat, monocrotophos, endosulfan (redirect to KVK)

## Next Steps

1. Download the Rajendran et al. (2018) paper - it has most of what you need
2. Extract relevant sections on:
   - Aphids (pages 368-369)
   - Whiteflies (pages 369-370)
   - Bollworms (pages 377-384)
   - Pesticide recommendations (Table 11.5, page 400)
   - IPM strategies (pages 396-405)

3. Convert to clean PDFs and upload to your S3 bucket
4. Re-run ingestion in Bedrock Knowledge Base
5. Run tests again

## Alternative: Update Test Expectations

If you want to keep current PDFs, update test expectations to match what's actually in them:
- Generic IPM principles
- Farmer Field Schools
- Integrated approaches
- No specific pesticide names
