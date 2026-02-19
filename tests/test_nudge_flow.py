import json
import os
from datetime import datetime

import types

import importlib

os.environ.setdefault("TABLE_NAME", "agrinexus-data")

import src.nudge.sender as sender
import src.nudge.reminder as reminder
import src.nudge.detector as detector

sender = importlib.reload(sender)
reminder = importlib.reload(reminder)
detector = importlib.reload(detector)


class FakeTable:
    def __init__(self):
        self.items = []
        self.updated = []
        self.puts = []
        self.get_item_response = None
        self.query_response = None

    def query(self, **kwargs):
        if self.query_response is not None:
            return self.query_response
        return {"Items": self.items}

    def put_item(self, **kwargs):
        self.puts.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def update_item(self, **kwargs):
        self.updated.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_item(self, **kwargs):
        if self.get_item_response is not None:
            return self.get_item_response
        return {"Item": None}


class FakeResponse:
    def __init__(self, status_code=200, text="ok"):
        self.status_code = status_code
        self.text = text

    def json(self):
        return {"status": "ok"}


def test_has_pending_nudge_detects_sent_and_reminded(monkeypatch):
    today = datetime.utcnow().date().isoformat()
    fake_table = FakeTable()
    fake_table.items = [
        {"SK": f"NUDGE#{today}T00:00:00#spray", "status": "SENT"},
        {"SK": f"NUDGE#{today}T01:00:00#spray", "status": "REMINDED"},
    ]
    monkeypatch.setattr(sender, "table", fake_table)

    assert sender.has_pending_nudge("+919876543210", "spray") is True


def test_template_language_code_selection(monkeypatch):
    os.environ["NUDGE_TEMPLATE_NAME"] = "weather_nudge_spray"
    os.environ["USE_NUDGE_TEMPLATE"] = "true"
    sender.NUDGE_TEMPLATE_NAME = "weather_nudge_spray"
    sender.USE_NUDGE_TEMPLATE = True

    fake_table = FakeTable()
    fake_table.query_response = {
        "Items": [
            {"phone_number": "+911", "dialect": "mr"}
        ]
    }
    monkeypatch.setattr(sender, "table", fake_table)
    monkeypatch.setattr(sender, "has_pending_nudge", lambda *args, **kwargs: False)

    captured = {}

    def fake_template(phone_number, template_name, language_code):
        captured["phone_number"] = phone_number
        captured["template_name"] = template_name
        captured["language_code"] = language_code
        return True

    monkeypatch.setattr(sender, "send_whatsapp_template", fake_template)
    monkeypatch.setattr(sender, "send_whatsapp_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(sender, "create_reminder_schedule", lambda *args, **kwargs: None)

    sender.lambda_handler({"location": "Aurangabad", "weather": {"wind_speed": 8.5}, "activity": "spray"}, None)

    assert captured["template_name"] == "weather_nudge_spray"
    assert captured["language_code"] == "mr"


def test_reminder_sender_updates_status(monkeypatch):
    fake_table = FakeTable()
    fake_table.get_item_response = {
        "Item": {"status": "SENT"}
    }
    monkeypatch.setattr(reminder, "table", fake_table)

    def fake_get_secret_value(SecretId):
        return {"SecretString": "dummy"}

    monkeypatch.setattr(reminder.secrets, "get_secret_value", fake_get_secret_value)

    def fake_post(*args, **kwargs):
        return FakeResponse(200)

    import requests
    monkeypatch.setattr(requests, "post", fake_post)

    event = {
        "phone_number": "+911",
        "nudge_id": "2026-02-19T00:00:00#spray",
        "reminder_type": "T+24h",
        "dialect": "hi"
    }

    result = reminder.lambda_handler(event, None)

    assert result["statusCode"] == 200
    assert fake_table.updated, "Expected update_item to be called"


def test_detector_marks_done_and_deletes_schedule(monkeypatch):
    fake_table = FakeTable()
    fake_table.items = [
        {"SK": "NUDGE#2026-02-19T00:00:00#spray", "status": "SENT"}
    ]
    monkeypatch.setattr(detector, "table", fake_table)

    delete_calls = []

    class FakeScheduler:
        def delete_schedule(self, Name):
            delete_calls.append(Name)

    monkeypatch.setattr(detector, "scheduler", FakeScheduler())

    def fake_get_secret_value(SecretId):
        return {"SecretString": "dummy"}

    monkeypatch.setattr(detector.secrets, "get_secret_value", fake_get_secret_value)

    def fake_post(*args, **kwargs):
        return FakeResponse(200)

    import requests
    monkeypatch.setattr(requests, "post", fake_post)

    event = {
        "Records": [
            {
                "eventName": "INSERT",
                "dynamodb": {
                    "NewImage": {
                        "PK": {"S": "USER#+911"},
                        "SK": {"S": "MSG#2026-02-19T00:01:00"},
                        "message": {
                            "M": {
                                "text": {"M": {"body": {"S": "हो गया"}}}
                            }
                        }
                    }
                }
            }
        ]
    }

    detector.lambda_handler(event, None)

    assert fake_table.updated, "Expected update_item to be called"
    assert delete_calls, "Expected scheduled reminders to be deleted"
