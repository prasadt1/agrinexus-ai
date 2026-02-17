# WhatsApp Interactive Buttons - Implementation Guide

## What Changed

We've upgraded the onboarding flow from plain text responses to WhatsApp Reply Buttons for a better user experience.

## Button Implementation

### 1. Dialect Selection (State: language)
**Message:** "नमस्ते! AgriNexus AI में आपका स्वागत है। मैं आपकी खेती में मदद करूंगा। कृपया अपनी भाषा चुनें:"

**Buttons:**
- [Hindi]
- [Marathi]
- [Telugu]

**User Action:** Click button or type language name

---

### 2. Location Input (State: location)
**Message (in selected dialect):** "बढ़िया! अब मुझे बताएं आप किस जिले में हैं?"

**Input Type:** Free text (no buttons)

**Valid Districts:** Aurangabad, Jalna, Nagpur

**User Action:** Type district name

---

### 3. Crop Selection (State: crop)
**Message (in selected dialect):** "धन्यवाद! आप कौन सी फसल उगाते हैं?"

**Buttons:**
- [Cotton]
- [Wheat]
- [Soybean]

**Fallback:** User can type "Other" or any crop name if not in buttons

**User Action:** Click button or type crop name

---

### 4. Consent (State: consent)
**Message (in selected dialect):** "अंतिम प्रश्न: क्या आप मौसम के अनुसार खेती की सलाह प्राप्त करना चाहते हैं?"

**Buttons (Hindi):**
- [हाँ ✅]
- [नहीं ❌]

**Buttons (Marathi):**
- [होय ✅]
- [नाही ❌]

**Buttons (Telugu):**
- [అవును ✅]
- [కాదు ❌]

**User Action:** Click button or type yes/no

---

## Technical Details

### WhatsApp API Format

```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "phone_number",
  "type": "interactive",
  "interactive": {
    "type": "button",
    "body": {
      "text": "Your message text here"
    },
    "action": {
      "buttons": [
        {
          "type": "reply",
          "reply": {
            "id": "btn_0",
            "title": "Button Text"
          }
        }
      ]
    }
  }
}
```

### Button Limitations

- **Max 3 buttons** per message (WhatsApp API limit)
- **Max 20 characters** per button title
- Buttons are **reply buttons** (not persistent, disappear after click)
- Works in **conversational context** (no template approval needed)

### Response Handling

When user clicks a button, WhatsApp sends the button title as a text message:
- Click [Hindi] → receives "Hindi"
- Click [हाँ ✅] → receives "हाँ ✅"

The processor handles both button clicks and typed text, so users can:
1. Click the button (recommended)
2. Type the text manually (fallback)

## Testing the New Flow

### Test Script

1. **Start Onboarding:**
   - Send "Namaste" to WhatsApp number
   - You should see 3 buttons: [Hindi] [Marathi] [Telugu]

2. **Select Language:**
   - Click [Hindi] button
   - You should see text prompt: "बढ़िया! अब मुझे बताएं आप किस जिले में हैं?"

3. **Enter Location:**
   - Type "Aurangabad"
   - You should see 3 buttons: [Cotton] [Wheat] [Soybean]

4. **Select Crop:**
   - Click [Cotton] button
   - You should see 2 buttons: [हाँ ✅] [नहीं ❌]

5. **Give Consent:**
   - Click [हाँ ✅] button
   - You should see: "बधाई हो! आपका प्रोफाइल तैयार है..."

### Expected User Experience

**Before (Plain Text):**
```
Bot: कृपया अपनी भाषा चुनें:
User: hindi
Bot: बढ़िया! अब मुझे बताएं आप किस जिले में हैं?
```

**After (Interactive Buttons):**
```
Bot: कृपया अपनी भाषा चुनें:
     [Hindi] [Marathi] [Telugu]
User: *clicks [Hindi]*
Bot: बढ़िया! अब मुझे बताएं आप किस जिले में हैं?
```

## Benefits

1. **Better UX:** Visual buttons are more intuitive than typing
2. **Fewer Errors:** No typos (e.g., "Hind" instead of "Hindi")
3. **Faster Onboarding:** One tap vs typing
4. **Professional Look:** Modern messaging interface
5. **Accessibility:** Easier for users with low literacy

## Code Changes

### Files Modified

1. **src/processor/handler.py**
   - Added `send_whatsapp_buttons()` function
   - Modified `handle_onboarding()` to return dict with type and buttons
   - Updated lambda handler to send buttons when appropriate
   - Added Wheat to VALID_CROPS

### Key Functions

```python
def send_whatsapp_buttons(phone_number: str, body_text: str, buttons: list):
    """Send interactive reply buttons via WhatsApp Business API"""
    # Formats buttons for WhatsApp API
    # Max 3 buttons supported
    # Returns formatted interactive message

def handle_onboarding(...) -> Dict[str, Any]:
    """Returns: {'type': 'text'|'buttons', 'content': str, 'buttons': list}"""
    # Determines whether to send text or buttons
    # Handles both button clicks and typed text
```

## Deployment

```bash
# Build and deploy
sam build --template-file template-week2.yaml
sam deploy --template-file .aws-sam/build/template.yaml \
  --stack-name agrinexus-week2 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1 \
  --resolve-s3
```

**Status:** ✅ Deployed successfully (2026-02-17 13:08)

## Next Steps

Test the new button flow on WhatsApp to verify:
1. Buttons appear correctly
2. Button clicks are processed
3. Fallback text input still works
4. All dialects show correct button labels

