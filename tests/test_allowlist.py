"""Allowlist module tests — key generation, approval check, expiry hints."""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))
from common.allowlist import allowlist_key, is_approved_user, allowlist_expiry_hint


# ---------------------------------------------------------------------------
# allowlist_key
# ---------------------------------------------------------------------------

class TestAllowlistKey:
    def test_key_structure(self):
        key = allowlist_key("491234567890")
        assert key["PK"] == "ALLOWLIST"
        assert key["SK"] == "USER#491234567890"

    def test_different_numbers(self):
        k1 = allowlist_key("111")
        k2 = allowlist_key("222")
        assert k1["SK"] != k2["SK"]


# ---------------------------------------------------------------------------
# is_approved_user
# ---------------------------------------------------------------------------

class TestIsApprovedUser:
    def test_open_demo_always_approved(self):
        # The demo is intentionally open: returns True regardless of table contents.
        for table in (
            types.SimpleNamespace(get_item=lambda Key: {"Item": {"approved": False}}),
            types.SimpleNamespace(get_item=lambda Key: {}),
            None,
        ):
            assert is_approved_user(table, "491234") is True


# ---------------------------------------------------------------------------
# allowlist_expiry_hint
# ---------------------------------------------------------------------------

class TestExpiryHint:
    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_all_languages_return_string(self, lang):
        hint = allowlist_expiry_hint(lang)
        assert isinstance(hint, str)
        assert len(hint) > 10

    def test_unknown_language_falls_back_to_english(self):
        hint = allowlist_expiry_hint("fr")
        assert "allowlist" in hint.lower() or "evaluator" in hint.lower()

    def test_hindi_is_devanagari(self):
        hint = allowlist_expiry_hint("hi")
        assert "सुविधा" in hint

    def test_english_mentions_evaluators(self):
        hint = allowlist_expiry_hint("en")
        assert "evaluator" in hint.lower()
