"""
Unit tests for guardrail intervention detection and localized refusal.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
COMMON = str(REPO / "src" / "common-layer" / "python")
if COMMON not in sys.path:
    sys.path.insert(0, COMMON)

from common.guardrail_reply import (  # noqa: E402
    BLOCKED_MESSAGING_EN,
    LOCALIZED_REFUSAL,
    apply_localized_guardrail_reply,
    guardrail_intervened,
    localized_guardrail_refusal,
)


class TestGuardrailDetection:
    def test_intervened_action(self):
        assert guardrail_intervened({"guardrailAction": "INTERVENED", "text": "x"})

    def test_blocked_messaging_match(self):
        assert guardrail_intervened({}, BLOCKED_MESSAGING_EN)

    def test_normal_farming_answer_not_intervened(self):
        text = (
            "For pesticide spray safety, wear gloves, a mask, and long sleeves. "
            "Wash after application and keep children away from the field."
        )
        assert not guardrail_intervened({"text": text, "guardrailAction": "NONE"}, text)


class TestLocalizedRefusal:
    def test_dialects(self):
        for d in ("hi", "mr", "te", "en"):
            assert localized_guardrail_refusal(d) == LOCALIZED_REFUSAL[d]
        assert localized_guardrail_refusal("unknown") == LOCALIZED_REFUSAL["en"]

    def test_apply_replaces_intervened_with_hindi(self):
        resp = {
            "text": BLOCKED_MESSAGING_EN,
            "citations": [{"x": 1}],
            "guardrailAction": "INTERVENED",
        }
        out = apply_localized_guardrail_reply(resp, "hi")
        assert out["text"] == LOCALIZED_REFUSAL["hi"]
        assert out["citations"] == []
        assert out.get("guardrail_localized") is True

    def test_apply_leaves_pesticide_exposure_answer(self):
        """Pesticide-exposure advisory must not be replaced by a refusal."""
        text = (
            "If pesticide got on your skin while spraying cotton, wash with soap and water, "
            "remove contaminated clothes, and avoid further exposure. For severe symptoms "
            "seek medical care; this is occupational spray-safety guidance."
        )
        resp = {"text": text, "citations": [{"retrievedReferences": []}]}
        out = apply_localized_guardrail_reply(resp, "hi")
        assert out["text"] == text
        assert not out.get("guardrail_localized")

    def test_apply_leaves_ppe_answer(self):
        """Protective-equipment (PPE) questions must not be blocked/replaced."""
        text = (
            "Use chemical-resistant gloves, long-sleeved clothing, goggles, and a mask "
            "when mixing or spraying insecticides. Rinse PPE after use."
        )
        resp = {"text": text, "citations": []}
        out = apply_localized_guardrail_reply(resp, "mr")
        assert out["text"] == text

    def test_off_topic_blocked_returns_marathi_refusal(self):
        resp = {
            "text": BLOCKED_MESSAGING_EN,
            "citations": [{"id": "c1"}],
            "guardrailAction": "INTERVENED",
        }
        out = apply_localized_guardrail_reply(resp, "mr")
        assert out["text"] == LOCALIZED_REFUSAL["mr"]
        assert out["citations"] == []


class TestKbNoAnswer:
    def test_marker_becomes_localized_refusal(self):
        from common.guardrail_reply import LOCALIZED_NO_ANSWER, apply_kb_no_answer

        out = apply_kb_no_answer({"text": "NO_KB_ANSWER", "citations": [{"x": 1}]}, "mr")
        assert out["text"] == LOCALIZED_NO_ANSWER["mr"]
        assert out["citations"] == [] and out["kb_no_answer"] is True

    def test_marker_with_stray_words_still_replaced(self):
        from common.guardrail_reply import LOCALIZED_NO_ANSWER, apply_kb_no_answer

        out = apply_kb_no_answer({"text": "NO_KB_ANSWER\n\nस्त्रोत: 1"}, "te")
        assert out["text"] == LOCALIZED_NO_ANSWER["te"]

    def test_bedrock_decline_becomes_localized_refusal(self):
        from common.guardrail_reply import (
            KB_DECLINE_FALLBACK_EN,
            LOCALIZED_NO_ANSWER,
            apply_kb_no_answer,
        )

        out = apply_kb_no_answer({"text": KB_DECLINE_FALLBACK_EN}, "hi")
        assert out["text"] == LOCALIZED_NO_ANSWER["hi"]

    def test_real_answer_unchanged(self):
        from common.guardrail_reply import apply_kb_no_answer

        resp = {"text": "पिवळे चिकट सापळे लावा.", "citations": []}
        assert apply_kb_no_answer(resp, "mr") is resp

    def test_unknown_dialect_falls_back_to_english(self):
        from common.guardrail_reply import LOCALIZED_NO_ANSWER, localized_no_answer

        assert localized_no_answer("xx") == LOCALIZED_NO_ANSWER["en"]

    def test_not_farming_marker_becomes_localized_off_topic_refusal(self):
        from common.guardrail_reply import apply_kb_no_answer

        out = apply_kb_no_answer({"text": "NOT_FARMING", "citations": []}, "hi")
        assert out["text"] == LOCALIZED_REFUSAL["hi"]
