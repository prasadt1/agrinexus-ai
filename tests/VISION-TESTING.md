# Vision Testing Guide

## Quick Test

Since WhatsApp test numbers don't support media, test vision in isolation:

### Step 1: Get a Test Image

Download a cotton pest/disease image:

**Option A: Google Images**
1. Search: "cotton bollworm damage" or "cotton aphid infestation"
2. Download any clear image
3. Save as `cotton-pest.jpg`

**Option B: Sample URLs**
- Cotton Bollworm: https://www.cottoninfo.com.au/sites/default/files/images/Bollworm.jpg
- Cotton Aphid: https://www.cottoninfo.com.au/sites/default/files/images/Aphids.jpg
- Cotton Leaf Curl: Search "cotton leaf curl virus symptoms"

### Step 2: Run Vision Test

```bash
# English
python tests/test_vision.py cotton-pest.jpg en cotton

# Hindi
python tests/test_vision.py cotton-pest.jpg hi cotton

# Marathi
python tests/test_vision.py cotton-pest.jpg mr cotton
```

### Step 3: Review Results

The test will show:
- **Diagnosis**: What pest/disease was identified
- **Severity**: low/medium/high
- **Recommendations**: Treatment advice in the selected language
- **Confidence**: high/medium/low

## What Gets Tested

✅ **Claude 3 Sonnet Vision** - Image analysis  
✅ **Multi-language responses** - Hindi, Marathi, Telugu, English  
✅ **Pest identification** - Bollworm, aphids, whitefly, etc.  
✅ **Disease identification** - Leaf curl, wilt, blight, etc.  
✅ **Nutrient deficiency** - Nitrogen, potassium, etc.  
✅ **Actionable recommendations** - Pesticides, dosage, timing  

## Example Output

```
======================================================================
TEST: EN - Cotton pest/disease identification
======================================================================
Image: cotton-bollworm.jpg
Dialect: en
Crop: cotton
======================================================================

1. Image loaded: 245678 bytes

2. Analyzing with Claude 3 Sonnet Vision...

3. ✓ Analysis complete!

======================================================================
RESULTS
======================================================================

Diagnosis: Cotton Bollworm (Helicoverpa armigera)
Severity: high
Confidence: high

Recommendations:
**Diagnosis:**
The image shows severe cotton bollworm (Helicoverpa armigera) damage to cotton bolls. Multiple larvae are visible feeding on the developing bolls.

**Severity:**
High - Immediate action required to prevent crop loss

**Recommendations:**
1. **Chemical Control:**
   - Spray Emamectin Benzoate 5% SG @ 200g/ha
   - Or use Spinosad 45% SC @ 125ml/ha
   - Apply in evening hours (5-7 PM) when larvae are active
   
2. **Cultural Practices:**
   - Remove and destroy damaged bolls
   - Install pheromone traps (8-10 per hectare)
   - Maintain field sanitation
   
3. **Timing:**
   - Spray immediately
   - Repeat after 10-12 days if infestation persists
   
4. **Prevention:**
   - Monitor regularly during flowering and boll formation
   - Use trap crops (marigold, pigeon pea) around field borders

**Confidence:**
High - Clear visual identification of bollworm larvae and damage patterns

======================================================================

✓ TEST PASSED
```

## Testing Different Scenarios

### Healthy Plant
```bash
# Download healthy cotton plant image
python tests/test_vision.py healthy-cotton.jpg en cotton
```

Expected: "No significant pest or disease detected. Plant appears healthy."

### Nutrient Deficiency
```bash
# Yellow leaves image
python tests/test_vision.py yellow-leaves.jpg hi cotton
```

Expected: Nitrogen deficiency diagnosis with fertilizer recommendations

### Multiple Issues
```bash
# Image with both pests and disease
python tests/test_vision.py complex-issue.jpg en cotton
```

Expected: Identification of multiple problems with prioritized recommendations

## Limitations

⚠️ **Image Quality**: Blurry or dark images may result in low confidence  
⚠️ **Uncommon Pests**: Rare pests may not be identified accurately  
⚠️ **Telugu**: Vision works but recommendations may be less detailed  

## For Competition Demo

1. **Prepare 2-3 test images**:
   - Cotton bollworm (common pest)
   - Cotton aphid (common pest)
   - Healthy plant (negative case)

2. **Run tests in English and Hindi**:
   ```bash
   python tests/test_vision.py bollworm.jpg en cotton
   python tests/test_vision.py bollworm.jpg hi cotton
   ```

3. **Show judges**:
   - Image → Claude Vision → Diagnosis → Recommendations
   - Multi-language support
   - Actionable advice with pesticide names and dosages

4. **Explain**:
   - "WhatsApp test numbers don't support images"
   - "But code is production-ready"
   - "Farmers send photo → get instant diagnosis"

## Troubleshooting

### "Image file not found"
```bash
ls -la cotton-pest.jpg  # Check file exists
python tests/test_vision.py ./cotton-pest.jpg en cotton  # Use full path
```

### "Error analyzing image"
- Check image format (JPG, PNG supported)
- Ensure image is not corrupted
- Try a different image

### "Low confidence" results
- Use clearer, well-lit images
- Focus on affected area (close-up)
- Avoid images with multiple plants

### "Analysis too generic"
- Use images showing clear symptoms
- Ensure pest/disease is visible
- Try different angles or lighting
