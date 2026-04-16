# Competitive Evidence Notes (Public Sources)

Date reviewed: April 2026  
Purpose: support the "Competitive Landscape" snapshot in `docs/FINAL-ARTICLE-SUBMISSION.md` with auditable public evidence.

## Scope and method

- Only publicly accessible product pages were reviewed.
- This is a transparency snapshot of published claims, not a claim about unpublished/internal features.
- Capability labels in the article are therefore marked as `Yes`, `Partial`, or `Unclear` based on what is explicitly visible in source pages.

## Sources and observed evidence

### Farmer.Chat (Digital Green)

Source: <https://farmer.chat/>

Observed page text:
- "Farmers can ask questions using text, voice notes, or photos, and receive responses in various formats."
- "Image Diagnosis"
- "Receive push notifications for weather updates, pest forecasts, and market prices."

Interpretation used in table:
- WhatsApp-first: **Yes** (conversational assistant framing with broad channel usage)
- Voice + image support: **Yes**
- Structured photo diagnosis format details: **Partial** (image diagnosis is clear; output schema details are not fully specified on this page)
- Closed-loop `done` confirmation + schedule cancellation: **Unclear**

### iSDA Virtual Agronomist

Source: <https://www.isda-africa.com/virtual-agronomist>

Observed page text:
- "Virtual Agronomist uses artificial intelligence to communicate directly with farmers through WhatsApp..."
- Feature list includes "Pest and disease diagnosis."
- Mentions "continuous support... throughout the growing season."

Interpretation used in table:
- WhatsApp-first: **Yes**
- Voice/TTS details: **Partial/unclear** on this page
- Photo pipeline details (capture -> diagnosis schema): **Partial/unclear**
- Explicit "done loop" reminder cancellation behavior: **Unclear**

### AgriChat.AI

Source: <https://www.agrichat.ai/>

Observed page text:
- "farmer chat • predict • advice • grow all in whatsapp."
- "No app install... in WhatsApp."
- Capability list includes "Hyperlocal Weather Forecasting," "Disease & Pest Risk Radar," and "WhatsApp Advisory Automation."

Interpretation used in table:
- WhatsApp-first: **Yes**
- Voice + synthesized reply details: **Partial/unclear** on this page
- Structured photo diagnosis specifics: **Partial/unclear**
- Explicit weather-gated `done` loop mechanics: **Unclear**

### Weather Impact (Uliza-WI Chatbot)

Source: <https://www.weatherimpact.com/chatbot/>

Observed page text:
- "Uliza-WI Chatbot on Telegram and... also on WhatsApp..."
- "Location-specific weather forecast"
- "goes beyond traditional SMS... to include images, voice messages, and even video content."
- "two-way communication"

Interpretation used in table:
- WhatsApp availability: **Yes**
- Voice/media interaction: **Partial** (media support stated; voice-in + synthesized voice-reply behavior not clearly specified)
- Structured image diagnosis schema: **Unclear**
- Explicit `done` confirmation + follow-up cancellation loop: **Unclear**

## Why AgriNexus remains differentiated in this article

The article's differentiator claim is narrowly defined as publicly evidenced behavior:
- weather-gated nudges,
- explicit user completion intent (`done`/equivalent),
- and cancellation of pending reminders after completion detection.

This specific loop is described in AgriNexus architecture and flow sections and was not clearly evidenced in the reviewed public peer pages above.
