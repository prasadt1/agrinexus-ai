"""Nudge copy template tests — message generation, all languages, reminders."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "nudge"))
from nudge_copy import (
    build_nudge_message,
    build_reminder_message,
    get_nudge_message,
    get_reminder_message,
)


# ---------------------------------------------------------------------------
# Initial nudge messages
# ---------------------------------------------------------------------------

class TestNudgeMessage:
    @pytest.mark.parametrize("dialect", ["hi", "mr", "te", "en"])
    def test_all_dialects_return_nonempty(self, dialect):
        msg = get_nudge_message(dialect, "Nagpur", "Cotton", 8.5)
        assert len(msg) > 20

    def test_hindi_contains_district_and_crop(self):
        msg = get_nudge_message("hi", "Nagpur", "Cotton", 8.5)
        assert "Nagpur" in msg
        assert "कपास" in msg

    def test_marathi_contains_spray(self):
        msg = get_nudge_message("mr", "Jalna", "Cotton", 7.0)
        assert "फवारणी" in msg

    def test_english_contains_wind_speed(self):
        msg = get_nudge_message("en", "Latur", "Soybean", 9.0)
        assert "9 km/h" in msg

    def test_wind_speed_rounded_to_whole_number(self):
        # Regression: the raw m/s->km/h conversion upstream yields floats like
        # 23.508000000000003; farmers must never see that — only a clean integer.
        msg = get_nudge_message("hi", "Latur", "Cotton", 23.508000000000003)
        assert "24 km/h" in msg
        assert "23.5" not in msg

    def test_telugu_contains_spray(self):
        msg = get_nudge_message("te", "Nagpur", "Wheat", 6.0)
        assert "స్ప్రే" in msg

    def test_unknown_dialect_falls_back_to_english(self):
        msg = get_nudge_message("fr", "Nagpur", "Cotton", 8.0)
        assert "Weather" in msg or "spray" in msg.lower()

    def test_unknown_crop_uses_raw_name(self):
        msg = get_nudge_message("en", "Nagpur", "Sugarcane", 8.0)
        assert "Sugarcane" in msg


# ---------------------------------------------------------------------------
# build_nudge_message with context override
# ---------------------------------------------------------------------------

class TestBuildNudgeMessage:
    def test_without_override(self):
        msg = build_nudge_message("en", "Nagpur", "Cotton", 8.5)
        assert "spray" in msg.lower()

    def test_with_context_override(self):
        msg = build_nudge_message("en", "Nagpur", "Cotton", 8.5,
                                  context_hint_override="Check for bollworm eggs.")
        assert "Check for bollworm eggs." in msg
        assert "spray" in msg.lower()

    def test_empty_override_ignored(self):
        base = build_nudge_message("en", "Nagpur", "Cotton", 8.5)
        with_empty = build_nudge_message("en", "Nagpur", "Cotton", 8.5,
                                         context_hint_override="  ")
        assert base == with_empty


# ---------------------------------------------------------------------------
# Reminder messages
# ---------------------------------------------------------------------------

class TestReminderMessage:
    @pytest.mark.parametrize("dialect", ["hi", "mr", "te", "en"])
    def test_t24h_all_dialects(self, dialect):
        msg = get_reminder_message(dialect, "T+24h", "Nagpur", "Cotton")
        assert len(msg) > 20

    @pytest.mark.parametrize("dialect", ["hi", "mr", "te", "en"])
    def test_t48h_all_dialects(self, dialect):
        msg = get_reminder_message(dialect, "T+48h", "Nagpur", "Cotton")
        assert len(msg) > 20

    def test_t24h_hindi_asks_if_sprayed(self):
        msg = get_reminder_message("hi", "T+24h", "Nagpur", "Cotton")
        assert "अभी तक" in msg or "नहीं" in msg

    def test_t48h_english_says_final(self):
        msg = get_reminder_message("en", "T+48h", "Nagpur", "Cotton")
        assert "final" in msg.lower() or "Final" in msg

    def test_build_reminder_delegates(self):
        a = build_reminder_message("en", "T+24h", "Nagpur", "Cotton")
        b = get_reminder_message("en", "T+24h", "Nagpur", "Cotton")
        assert a == b
