"""The response detector skips malformed stream records and reports only failed records for retry."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def det(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    table = types.SimpleNamespace(query=lambda **kw: {"Items": []}, update_item=lambda **kw: {}, get_item=lambda **kw: {})
    boto3 = types.ModuleType("boto3")
    boto3.resource = lambda svc, **kw: types.SimpleNamespace(Table=lambda name: table)
    boto3.client = lambda svc, **kw: types.SimpleNamespace(
        put_metric_data=lambda **kw: {}, delete_schedule=lambda **kw: {}
    )
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    layer = str(ROOT / "src" / "common-layer" / "python")
    if layer not in sys.path:
        sys.path.insert(0, layer)
    for name in [m for m in sys.modules if m == "common" or m.startswith("common.")]:
        monkeypatch.delitem(sys.modules, name)
    whatsapp = types.ModuleType("common.whatsapp")
    whatsapp.send_whatsapp_message = lambda *a, **kw: None
    monkeypatch.setitem(sys.modules, "common.whatsapp", whatsapp)
    spec = importlib.util.spec_from_file_location("detector_under_test", ROOT / "src" / "nudge" / "detector.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _record(seq, text="DONE", phone="15550001111", event="INSERT"):
    return {
        "eventName": event,
        "dynamodb": {
            "SequenceNumber": seq,
            "NewImage": {
                "PK": {"S": f"USER#{phone}"},
                "SK": {"S": "MSG#2026-10-02T10:00:00"},
                "message": {"M": {"text": {"M": {"body": {"S": text}}}}},
            },
        },
    }


BAD_RECORDS = [
    {},
    {"eventName": "INSERT"},
    {"eventName": "INSERT", "dynamodb": {}},
    {"eventName": "INSERT", "dynamodb": {"SequenceNumber": "9", "NewImage": None}},
    {"eventName": "INSERT", "dynamodb": {"SequenceNumber": "9", "NewImage": {"SK": "MSG#x"}}},
    {"eventName": "INSERT", "dynamodb": {"SequenceNumber": "9", "NewImage": {"SK": {"S": "MSG#x"}, "message": {"M": "oops"}}}},
    "not-a-dict",
]


@pytest.mark.parametrize("bad", BAD_RECORDS)
def test_malformed_record_is_skipped_not_retried(det, bad):
    out = det.lambda_handler({"Records": [bad, _record("2", text="hello")]}, None)
    assert out.get("batchItemFailures", []) == []


def test_missing_records_key_is_tolerated(det):
    assert det.lambda_handler({}, None).get("batchItemFailures", []) == []


def test_processing_error_reports_that_record_and_stops(det, monkeypatch):
    seen = []

    def nudges(phone):
        seen.append(phone)
        if phone == "15550002222":
            raise RuntimeError("dynamo throttled")
        return []

    monkeypatch.setattr(det, "get_active_nudges", nudges)
    out = det.lambda_handler(
        {"Records": [_record("1"), _record("2", phone="15550002222"), _record("3", phone="15550003333")]}, None
    )
    assert out["batchItemFailures"] == [{"itemIdentifier": "2"}]
    # Streams retry from the reported record onward; record 3 must not be handled twice.
    assert "15550003333" not in seen


def test_done_reply_still_marks_nudge_done(det, monkeypatch):
    updates, sent = [], []
    monkeypatch.setattr(det, "get_active_nudges", lambda p: [{"SK": "NUDGE#n1"}])
    monkeypatch.setattr(det.table, "update_item", lambda **kw: updates.append(kw), raising=False)
    monkeypatch.setattr(det, "send_whatsapp_message", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(det, "delete_scheduled_reminders", lambda nid: None)
    out = det.lambda_handler({"Records": [_record("1")]}, None)
    assert out.get("batchItemFailures", []) == []
    assert updates and updates[0]["ExpressionAttributeValues"][":status"] == "DONE"
    assert sent
