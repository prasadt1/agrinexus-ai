"""Webhook rate limit should count inbound user messages only, not assistant MSG# rows."""

import importlib
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src" / "common-layer" / "python"))


def test_check_rate_limit_uses_filter_excluding_response_rows(monkeypatch):
    os.environ.setdefault("QUEUE_URL", "https://sqs.local/q")
    os.environ.setdefault("QUEUE_URL_BETA", "")
    os.environ["TABLE_NAME"] = "tbl"
    os.environ["RATE_LIMIT_DISABLED"] = "false"
    os.environ["RATE_LIMIT_BYPASS_PHONES"] = ""
    os.environ["RATE_LIMIT_MESSAGES"] = "10"
    os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "3600"

    captured: dict = {}

    class _FakeTable:
        def query(self, **kwargs):
            captured.clear()
            captured.update(kwargs)
            return {"Count": 0}

    from src.webhook import handler as webhook

    importlib.reload(webhook)
    monkeypatch.setattr(webhook, "table", _FakeTable())

    assert webhook.check_rate_limit("919876543210") is True
    assert "FilterExpression" in captured
    assert "attribute_not_exists" in captured["FilterExpression"]
    assert captured.get("ExpressionAttributeNames", {}).get("#resp") == "response"
