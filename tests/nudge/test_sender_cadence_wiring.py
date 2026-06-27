"""Sender-level regression: lambda_handler honors optional `rules` cadence,
and preserves the legacy 24/48/72 schedule when `rules` is absent."""
import os
import sys
import importlib

# Add the common layer to path so `from common.whatsapp import ...` resolves.
# NOTE: this file is in tests/nudge/, so go up TWO levels to the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'common-layer', 'python'))
os.environ.setdefault("TABLE_NAME", "agrinexus-data")

import src.nudge.sender as sender  # noqa: E402
sender = importlib.reload(sender)


def _wire_one_qualifying_farmer(monkeypatch, calls):
    """One allowlisted, consented, non-demo (paid) farmer in 'Latur'; capture cadence calls."""
    farmer = {"phone_number": "+910000000001", "dialect": "hi"}
    profile = {"onboarding_complete": True, "consent": "granted", "crop": "Cotton",
               "location": "Latur", "demo_tier": "paid"}

    class FakeTable:
        def query(self, **k):
            return {"Items": [farmer]}

        def get_item(self, **k):
            return {"Item": profile}

        def put_item(self, **k):
            return {}

    monkeypatch.setattr(sender, "table", FakeTable())
    monkeypatch.setattr(sender, "has_open_nudge", lambda *a, **k: False)
    monkeypatch.setattr(sender, "build_nudge_message", lambda *a, **k: "msg")
    monkeypatch.setattr(sender, "send_whatsapp_buttons", lambda *a, **k: True)
    monkeypatch.setattr(sender, "emit_metric", lambda *a, **k: None)
    monkeypatch.setattr(sender, "create_reminder_schedule",
                        lambda phone, nid, hours, dialect: calls["reminders"].append(hours))
    monkeypatch.setattr(sender, "create_expiry_schedule",
                        lambda phone, nid, hours: calls.__setitem__("expiry", hours))


def test_no_rules_yields_legacy_schedule(monkeypatch):
    calls = {"reminders": []}
    _wire_one_qualifying_farmer(monkeypatch, calls)
    result = sender.lambda_handler(
        {"location": "Latur", "weather": {"wind_speed": 8.5, "rain": 0}, "activity": "spray"}, None)
    assert result["nudges_sent"] == 1
    assert calls["reminders"] == [24, 48]
    assert calls["expiry"] == 72


def test_rules_override_schedule(monkeypatch):
    calls = {"reminders": []}
    _wire_one_qualifying_farmer(monkeypatch, calls)
    result = sender.lambda_handler(
        {"location": "Latur", "weather": {"wind_speed": 8.5, "rain": 0}, "activity": "spray",
         "rules": {"reminderIntervals": [12], "expiryHours": 48}}, None)
    assert result["nudges_sent"] == 1
    assert calls["reminders"] == [12]
    assert calls["expiry"] == 48
