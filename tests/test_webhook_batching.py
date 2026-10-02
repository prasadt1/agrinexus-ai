"""Every entry and change in a webhook payload is processed."""
import json

import pytest

from tests.test_webhook_dedup import _Table, _Sqs, _event, _msg, webhook  # noqa: F401


def test_all_entries_and_changes_are_processed(webhook, monkeypatch):
    table, sqs = _Table(webhook), _Sqs()
    monkeypatch.setattr(webhook, "table", table)
    monkeypatch.setattr(webhook, "sqs", sqs)
    entries = [
        {"changes": [
            {"value": {"messages": [_msg("w1")]}},
            {"value": {"statuses": [{"id": "s1"}]}},
            {"value": {"messages": [_msg("w2", frm="15550002222")]}},
        ]},
        {"changes": [{"value": {"messages": [_msg("w3", frm="15550003333"), _msg("w4", frm="15550003333")]}}]},
    ]
    resp = webhook.lambda_handler(_event(entries), None)
    assert resp["statusCode"] == 200
    assert sorted(json.loads(s["MessageBody"])["wamid"] for s in sqs.sent) == ["w1", "w2", "w3", "w4"]


def test_metadata_comes_from_the_message_own_change(webhook, monkeypatch):
    table, sqs = _Table(webhook), _Sqs()
    monkeypatch.setattr(webhook, "table", table)
    monkeypatch.setattr(webhook, "sqs", sqs)
    entries = [
        {"changes": [{"value": {"metadata": {"phone_number_id": "P1"}, "messages": [_msg("w1")]}}]},
        {"changes": [{"value": {"metadata": {"phone_number_id": "P2"}, "messages": [_msg("w2", frm="15550002222")]}}]},
    ]
    webhook.lambda_handler(_event(entries), None)
    meta = {json.loads(s["MessageBody"])["wamid"]: json.loads(s["MessageBody"])["metadata"] for s in sqs.sent}
    assert meta == {"w1": {"phone_number_id": "P1"}, "w2": {"phone_number_id": "P2"}}


def test_empty_or_status_only_payload_returns_200(webhook, monkeypatch):
    monkeypatch.setattr(webhook, "table", _Table(webhook))
    monkeypatch.setattr(webhook, "sqs", _Sqs())
    for entries in ([], [{}], [{"changes": []}], [{"changes": [{"value": {"statuses": [{}]}}]}]):
        assert webhook.lambda_handler(_event(entries), None)["statusCode"] == 200
