"""
Bedrock Guardrail helpers: detect intervention and localize the refusal.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

# Must stay in sync with template.yaml BlockedInputMessaging / BlockedOutputsMessaging
# (English canonical string used when the guardrail intervenes).
BLOCKED_MESSAGING_EN = (
    "I can only help with farming questions — crops, pests, weather, soil, or irrigation. "
    "Please ask something related to agriculture."
)

LOCALIZED_REFUSAL = {
    "en": BLOCKED_MESSAGING_EN,
    "hi": (
        "मैं केवल खेती से जुड़े सवालों में मदद कर सकता हूँ — फसल, कीट, मौसम, मिट्टी या सिंचाई। "
        "कृपया खेती से जुड़ा सवाल पूछें।"
    ),
    "mr": (
        "मी फक्त शेतीशी संबंधित प्रश्नांत मदत करू शकतो — पीक, कीड, हवामान, माती किंवा सिंचन. "
        "कृपया शेतीशी संबंधित प्रश्न विचारा."
    ),
    "te": (
        "నేను వ్యవసాయ సంబంధిత ప్రశ్నలకు మాత్రమే సహాయం చేయగలను — పంటలు, పురుగులు, వాతావరణం, నేల లేదా నీటిపారుదల. "
        "దయచేసి వ్యవసాయం గురించి అడగండి."
    ),
}

# Compact fingerprint of the English blocked message for fuzzy match
_BLOCKED_FINGERPRINT = re.compile(
    r"only help with farming|crops,\s*pests,\s*weather|ask something related to agriculture",
    re.IGNORECASE,
)


def localized_guardrail_refusal(dialect: str) -> str:
    d = (dialect or "en").strip().lower()
    return LOCALIZED_REFUSAL.get(d, LOCALIZED_REFUSAL["en"])


def configured_blocked_messaging() -> str:
    """Optional override via env; default matches SAM template English string."""
    return (os.environ.get("GUARDRAIL_BLOCKED_MESSAGING") or BLOCKED_MESSAGING_EN).strip()


def guardrail_intervened(response: Optional[Dict[str, Any]], output_text: str = "") -> bool:
    """
    True when RetrieveAndGenerate (or similar) was blocked by a guardrail.

    Detects:
    - top-level or nested guardrailAction == INTERVENED
    - output text equal to / fingerprint-matching the configured blocked messaging
    """
    if not response and not output_text:
        return False

    def _action_intervened(obj: Any) -> bool:
        if not isinstance(obj, dict):
            return False
        action = obj.get("guardrailAction") or obj.get("action")
        if isinstance(action, str) and action.upper() == "INTERVENED":
            return True
        # Nested shapes seen in some Bedrock responses
        for key in ("guardrail", "guardrailAssessment", "guardrailAssessmentList"):
            nested = obj.get(key)
            if isinstance(nested, dict) and _action_intervened(nested):
                return True
            if isinstance(nested, list):
                for item in nested:
                    if _action_intervened(item):
                        return True
        return False

    if response and _action_intervened(response):
        return True

    text = (output_text or "").strip()
    if not text and isinstance(response, dict):
        out = response.get("output") or {}
        if isinstance(out, dict):
            text = str(out.get("text") or "").strip()
        elif isinstance(response.get("text"), str):
            text = response["text"].strip()

    if not text:
        return False

    blocked = configured_blocked_messaging()
    if text == blocked or text.replace("\n", " ").strip() == blocked.replace("\n", " ").strip():
        return True
    # Partial match if Bedrock trims/whitespace-differs
    if _BLOCKED_FINGERPRINT.search(text) and len(text) < 400:
        return True
    return False


def apply_localized_guardrail_reply(
    response: Dict[str, Any],
    dialect: str,
) -> Dict[str, Any]:
    """
    If the RAG response was guardrail-blocked, replace text with a localized refusal
    and clear citations. Otherwise return response unchanged.
    """
    text = ""
    if isinstance(response.get("text"), str):
        text = response["text"]
    elif isinstance(response.get("output"), dict):
        text = str(response["output"].get("text") or "")

    if not guardrail_intervened(response, text):
        return response

    out = dict(response)
    out["text"] = localized_guardrail_refusal(dialect)
    out["citations"] = []
    out["guardrail_localized"] = True
    return out
