"""Nudge reminder tests — reminder buttons, handler logic, expiry."""
import importlib.util
import json
import os
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")


@pytest.fixture()
def reminder(monkeypatch):
    """Import nudge reminder with boto3 + common mocked."""
    mock_boto3 = types.ModuleType("boto3")
    mock_table = types.SimpleNamespace(
        get_item=lambda **kw: {"Item": {"status": "SENT", "crop": "Cotton"}},
        update_item=lambda **kw: {},
    )
    mock_dynamo = types.SimpleNamespace(Table=lambda name: mock_table)
    mock_boto3.resource = lambda svc, **kw: mock_dynamo
    mock_boto3.client = lambda svc, **kw: types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

    common_mod = types.ModuleType("common")
    common_mod.whatsapp = types.ModuleType("common.whatsapp")
    common_mod.whatsapp.send_whatsapp_message = lambda phone_number, message, **kw: True
    common_mod.whatsapp.send_whatsapp_buttons = lambda phone_number, body_text, buttons, **kw: True
    monkeypatch.setitem(sys.modules, "common", common_mod)
    monkeypatch.setitem(sys.modules, "common.whatsapp", common_mod.whatsapp)

    spec = importlib.util.spec_from_file_location(
        "nudge_reminder",
        os.path.join(os.path.dirname(__file__), "..", "src", "nudge", "reminder.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# REMINDER_BUTTONS
# ---------------------------------------------------------------------------

class TestReminderButtons:
    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_all_languages_have_buttons(self, reminder, lang):
        assert lang in reminder.REMINDER_BUTTONS
        buttons = reminder.REMINDER_BUTTONS[lang]
        assert len(buttons) == 2

    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_buttons_have_done_and_not_yet(self, reminder, lang):
        buttons = reminder.REMINDER_BUTTONS[lang]
        ids = {b["id"] for b in buttons}
        assert "done" in ids
        assert "not_yet" in ids

    def test_hindi_done_button_text(self, reminder):
        done_btn = [b for b in reminder.REMINDER_BUTTONS["hi"] if b["id"] == "done"][0]
        assert "हो गया" in done_btn["title"]

    def test_english_done_button_text(self, reminder):
        done_btn = [b for b in reminder.REMINDER_BUTTONS["en"] if b["id"] == "done"][0]
        assert done_btn["title"] == "Done"


# ---------------------------------------------------------------------------
# lambda_handler
# ---------------------------------------------------------------------------

class TestReminderHandler:
    def test_nudge_not_found(self, reminder, monkeypatch):
        mock_table = types.SimpleNamespace(
            get_item=lambda **kw: {},
        )
        monkeypatch.setattr(reminder, "table", mock_table)
        result = reminder.lambda_handler({
            "phone_number": "491234",
            "nudge_id": "2026-04-20T10:00:00#spray",
            "reminder_type": "T+24h",
        }, None)
        assert result["statusCode"] == 404

    def test_already_done_skips_send(self, reminder, monkeypatch):
        mock_table = types.SimpleNamespace(
            get_item=lambda **kw: {"Item": {"status": "DONE", "crop": "Cotton"}},
        )
        monkeypatch.setattr(reminder, "table", mock_table)
        result = reminder.lambda_handler({
            "phone_number": "491234",
            "nudge_id": "2026-04-20T10:00:00#spray",
            "reminder_type": "T+24h",
        }, None)
        assert "already completed" in result["message"].lower()

    def test_expiry_marks_expired(self, reminder, monkeypatch):
        updates = []
        mock_table = types.SimpleNamespace(
            get_item=lambda **kw: {"Item": {"status": "REMINDED", "crop": "Cotton"}},
            update_item=lambda **kw: updates.append(kw),
        )
        monkeypatch.setattr(reminder, "table", mock_table)
        result = reminder.lambda_handler({
            "phone_number": "491234",
            "nudge_id": "2026-04-20T10:00:00#spray",
            "reminder_type": "EXPIRY",
        }, None)
        assert "expired" in result["message"].lower()
        assert len(updates) == 1

    def test_expiry_skips_if_already_done(self, reminder, monkeypatch):
        updates = []
        mock_table = types.SimpleNamespace(
            get_item=lambda **kw: {"Item": {"status": "DONE", "crop": "Cotton"}},
            update_item=lambda **kw: updates.append(kw),
        )
        monkeypatch.setattr(reminder, "table", mock_table)
        result = reminder.lambda_handler({
            "phone_number": "491234",
            "nudge_id": "2026-04-20T10:00:00#spray",
            "reminder_type": "EXPIRY",
        }, None)
        assert len(updates) == 0  # No update for already-done

    def test_sends_reminder_for_sent_status(self, reminder, monkeypatch):
        sent_messages = []
        updates = []
        mock_table = types.SimpleNamespace(
            get_item=lambda **kw: {"Item": {"status": "SENT", "crop": "Cotton", "district": "Nagpur"}},
            update_item=lambda **kw: updates.append(kw),
        )
        monkeypatch.setattr(reminder, "table", mock_table)
        monkeypatch.setattr(reminder, "send_whatsapp_buttons",
                            lambda phone_number, body_text, buttons, **kw: sent_messages.append(body_text) or True)
        result = reminder.lambda_handler({
            "phone_number": "491234",
            "nudge_id": "2026-04-20T10:00:00#spray",
            "reminder_type": "T+24h",
        }, None)
        assert result["statusCode"] == 200
        assert "sent" in result["message"].lower()
        assert len(sent_messages) == 1
        assert len(updates) == 1
