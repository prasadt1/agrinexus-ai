"""Per-number, per-day feature quota tests — vision / voice cost cap."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))
from common.quota import check_feature_quota, daily_limit


# ---------------------------------------------------------------------------
# Fake DynamoDB table
# ---------------------------------------------------------------------------

class FakeTable:
    def __init__(self, returned_count):
        self.returned_count = returned_count
        self.calls = []

    def update_item(self, **kw):
        self.calls.append(kw)
        return {"Attributes": {"count": self.returned_count}}


class ErrorTable:
    def __init__(self):
        self.calls = []

    def update_item(self, **kw):
        self.calls.append(kw)
        raise RuntimeError("DynamoDB unavailable")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCheckFeatureQuota:
    PHONE = "+14155550001"

    def test_within_limit_returns_true(self, monkeypatch):
        """First call (count=1) with default limit 10 → True; Key shape is correct."""
        monkeypatch.delenv("FEATURE_QUOTA_DISABLED", raising=False)
        monkeypatch.delenv("FEATURE_QUOTA_BYPASS_PHONES", raising=False)
        monkeypatch.delenv("VISION_DAILY_LIMIT", raising=False)

        table = FakeTable(returned_count=1)
        result = check_feature_quota(table, self.PHONE, "vision")

        assert result is True
        assert len(table.calls) == 1
        key = table.calls[0]["Key"]
        assert key["PK"] == f"QUOTA#{self.PHONE}"
        # SK starts with "vision#" followed by a YYYY-MM-DD date
        assert key["SK"].startswith("vision#")
        date_part = key["SK"].split("#", 1)[1]
        assert len(date_part) == 10  # YYYY-MM-DD

    def test_at_limit_boundary_returns_true(self, monkeypatch):
        """count == limit (10) → True (within means <=, not <)."""
        monkeypatch.delenv("FEATURE_QUOTA_DISABLED", raising=False)
        monkeypatch.delenv("FEATURE_QUOTA_BYPASS_PHONES", raising=False)
        monkeypatch.delenv("VISION_DAILY_LIMIT", raising=False)

        table = FakeTable(returned_count=10)
        assert check_feature_quota(table, self.PHONE, "vision") is True

    def test_over_limit_returns_false(self, monkeypatch):
        """count == limit+1 (11) → False."""
        monkeypatch.delenv("FEATURE_QUOTA_DISABLED", raising=False)
        monkeypatch.delenv("FEATURE_QUOTA_BYPASS_PHONES", raising=False)
        monkeypatch.delenv("VISION_DAILY_LIMIT", raising=False)

        table = FakeTable(returned_count=11)
        assert check_feature_quota(table, self.PHONE, "vision") is False

    def test_disabled_env_returns_true_no_db_call(self, monkeypatch):
        """FEATURE_QUOTA_DISABLED=true → True, update_item never called."""
        monkeypatch.setenv("FEATURE_QUOTA_DISABLED", "true")
        monkeypatch.delenv("FEATURE_QUOTA_BYPASS_PHONES", raising=False)

        table = FakeTable(returned_count=999)
        result = check_feature_quota(table, self.PHONE, "vision")

        assert result is True
        assert len(table.calls) == 0

    def test_bypass_phone_returns_true_no_db_call(self, monkeypatch):
        """Phone in FEATURE_QUOTA_BYPASS_PHONES → True, update_item never called."""
        monkeypatch.delenv("FEATURE_QUOTA_DISABLED", raising=False)
        monkeypatch.setenv("FEATURE_QUOTA_BYPASS_PHONES", f"{self.PHONE},+19999999999")

        table = FakeTable(returned_count=999)
        result = check_feature_quota(table, self.PHONE, "vision")

        assert result is True
        assert len(table.calls) == 0

    def test_limit_zero_returns_true_no_db_call(self, monkeypatch):
        """VISION_DAILY_LIMIT=0 → True, update_item never called (unlimited / disabled)."""
        monkeypatch.delenv("FEATURE_QUOTA_DISABLED", raising=False)
        monkeypatch.delenv("FEATURE_QUOTA_BYPASS_PHONES", raising=False)
        monkeypatch.setenv("VISION_DAILY_LIMIT", "0")

        table = FakeTable(returned_count=999)
        result = check_feature_quota(table, self.PHONE, "vision")

        assert result is True
        assert len(table.calls) == 0

    def test_negative_limit_returns_true_no_db_call(self, monkeypatch):
        """A negative limit is treated like 0 (no cap) → True, update_item never called."""
        monkeypatch.delenv("FEATURE_QUOTA_DISABLED", raising=False)
        monkeypatch.delenv("FEATURE_QUOTA_BYPASS_PHONES", raising=False)
        monkeypatch.setenv("VISION_DAILY_LIMIT", "-1")

        table = FakeTable(returned_count=999)
        result = check_feature_quota(table, self.PHONE, "vision")

        assert result is True
        assert len(table.calls) == 0

    def test_table_error_fails_open(self, monkeypatch):
        """Any DynamoDB exception → True (fail-open, never break the demo)."""
        monkeypatch.delenv("FEATURE_QUOTA_DISABLED", raising=False)
        monkeypatch.delenv("FEATURE_QUOTA_BYPASS_PHONES", raising=False)
        monkeypatch.delenv("VISION_DAILY_LIMIT", raising=False)

        table = ErrorTable()
        result = check_feature_quota(table, self.PHONE, "vision")

        assert result is True

    def test_env_override_limit_voice(self, monkeypatch):
        """VOICE_DAILY_LIMIT=2: count=3 → False; count=2 → True."""
        monkeypatch.delenv("FEATURE_QUOTA_DISABLED", raising=False)
        monkeypatch.delenv("FEATURE_QUOTA_BYPASS_PHONES", raising=False)
        monkeypatch.setenv("VOICE_DAILY_LIMIT", "2")

        table_over = FakeTable(returned_count=3)
        assert check_feature_quota(table_over, self.PHONE, "voice") is False

        table_at = FakeTable(returned_count=2)
        assert check_feature_quota(table_at, self.PHONE, "voice") is True
