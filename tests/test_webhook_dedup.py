"""Dedup must not swallow a message whose enqueue failed."""
import importlib
import json
import os

import pytest


@pytest.fixture
def webhook(monkeypatch):
    os.environ["QUEUE_URL"] = "https://sqs.local/live"
    os.environ["QUEUE_URL_BETA"] = ""
    os.environ["TABLE_NAME"] = "tbl"
    os.environ["VERIFY_SIGNATURE"] = "false"
    os.environ["BETA_PHONES"] = ""
    monkeypatch.setenv("VOICE_QUEUE_URL", "https://sqs.local/voice")
    from src.webhook import handler as wh
    importlib.reload(wh)
    monkeypatch.setattr(wh, "check_rate_limit", lambda *_a, **_k: True)
    monkeypatch.setattr(wh, "is_approved_user", lambda *_a, **_k: True)
    monkeypatch.setattr(wh, "send_voice_received_ack", lambda *_a, **_k: None)
    monkeypatch.setattr(wh, "send_whatsapp_message", lambda *_a, **_k: None)
    return wh


class _Table:
    def __init__(self, wh):
        self.items = {}
        self._exc = wh.dynamodb.meta.client.exceptions.ConditionalCheckFailedException

    def put_item(self, Item, ConditionExpression=None):
        key = (Item["PK"], Item["SK"])
        if ConditionExpression and key in self.items:
            raise self._exc({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        self.items[key] = Item
        return {}

    def delete_item(self, Key, **_k):
        self.items.pop((Key["PK"], Key["SK"]), None)
        return {}

    def query(self, **_k):
        return {"Count": 0, "Items": []}

    def get_item(self, **_k):
        return {}


class _Sqs:
    def __init__(self, fail_times=0):
        self.sent = []
        self.fail_times = fail_times

    def send_message(self, **kwargs):
        if self.fail_times:
            self.fail_times -= 1
            raise RuntimeError("sqs down")
        self.sent.append(kwargs)
        return {"MessageId": "m"}


def _event(entries):
    return {"httpMethod": "POST", "path": "/webhook", "headers": {}, "body": json.dumps({"entry": entries})}


def _msg(wamid, kind="text", frm="15550001111"):
    m = {"id": wamid, "from": frm, "type": kind}
    if kind == "text":
        m["text"] = {"body": "my cotton leaves are yellow"}
    else:
        m["audio"] = {"id": "a1"}
    return m


def _one(m):
    return [{"changes": [{"value": {"messages": [m]}}]}]


@pytest.mark.parametrize("kind", ["text", "audio"])
def test_failed_enqueue_does_not_leave_dedup_row(webhook, monkeypatch, kind):
    table, sqs = _Table(webhook), _Sqs(fail_times=1)
    monkeypatch.setattr(webhook, "table", table)
    monkeypatch.setattr(webhook, "sqs", sqs)
    with pytest.raises(Exception):
        webhook.lambda_handler(_event(_one(_msg("wamid.A", kind))), None)
    # The dedup row is keyed by a hash of the message ID, so look for any dedup row.
    assert not [key for key in table.items if key[1] == "DEDUP"]

    resp = webhook.lambda_handler(_event(_one(_msg("wamid.A", kind))), None)
    assert resp["statusCode"] == 200
    assert len(sqs.sent) == 1


def test_successful_enqueue_still_dedups_redelivery(webhook, monkeypatch):
    table, sqs = _Table(webhook), _Sqs()
    monkeypatch.setattr(webhook, "table", table)
    monkeypatch.setattr(webhook, "sqs", sqs)
    webhook.lambda_handler(_event(_one(_msg("wamid.B"))), None)
    webhook.lambda_handler(_event(_one(_msg("wamid.B"))), None)
    assert len(sqs.sent) == 1
    assert len([key for key in table.items if key[1] == "DEDUP"]) == 1


def test_two_messages_get_two_dedup_rows(webhook, monkeypatch):
    table, sqs = _Table(webhook), _Sqs()
    monkeypatch.setattr(webhook, "table", table)
    monkeypatch.setattr(webhook, "sqs", sqs)
    webhook.lambda_handler(_event(_one(_msg("wamid.C"))), None)
    webhook.lambda_handler(_event(_one(_msg("wamid.D"))), None)
    assert len(sqs.sent) == 2
    assert len([key for key in table.items if key[1] == "DEDUP"]) == 2
