"""scripts/expire-unfinished-signups.py: old unfinished sign-ups get an expiry, nothing else does."""
import importlib.util
import sys
import time
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("expire_unfinished_signups", ROOT / "scripts" / "expire-unfinished-signups.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

UNFINISHED = {"PK": "USER#4915112345678", "SK": "PROFILE", "onboarding_complete": False, "onboarding_state": "language"}
FINISHED = {"PK": "USER#919876543210", "SK": "PROFILE", "onboarding_complete": True, "demo_tier": "public"}
VISITOR = {"PK": "USER#15550001111", "SK": "PROFILE", "onboarding_complete": True, "demo_tier": "visitor", "ttl": 1790000000}
EXPIRING = {"PK": "USER#15550002222", "SK": "PROFILE", "onboarding_complete": False, "ttl": 1790000000}
MESSAGE = {"PK": "USER#4915112345678", "SK": "MSG#2026-10-01T10:00:00", "message": {"text": {"body": "Hello"}}}


def _matches(condition, row) -> bool:
    """Evaluate the boto3 condition the script built against a plain dict."""
    expr = condition.get_expression()
    operator, values = expr["operator"], expr["values"]
    if operator == "AND":
        return all(_matches(v, row) for v in values)
    if operator == "=":
        name, wanted = values[0].name, values[1]
        return name in row and type(row[name]) is type(wanted) and row[name] == wanted
    if operator == "attribute_not_exists":
        return values[0].name not in row
    raise AssertionError(f"filter uses an operator this fake does not know: {operator}")


class _Table:
    """Scan with the script's own filter, evaluated against plain dicts, one row per page."""

    def __init__(self, rows):
        self.rows = {(r["PK"], r["SK"]): dict(r) for r in rows}
        self.updates = []

    def scan(self, FilterExpression, ProjectionExpression, ExclusiveStartKey=None):
        assert ProjectionExpression == "PK, SK"
        matches = sorted(k for k, r in self.rows.items() if _matches(FilterExpression, r))
        start = matches.index(ExclusiveStartKey) + 1 if ExclusiveStartKey else 0
        page = matches[start:start + 1]
        out = {"Items": [{"PK": k[0], "SK": k[1]} for k in page]}
        if start + 1 < len(matches):
            out["LastEvaluatedKey"] = page[0]
        return out

    def update_item(self, Key, UpdateExpression, ConditionExpression, ExpressionAttributeNames, ExpressionAttributeValues):
        row = self.rows[(Key["PK"], Key["SK"])]
        if "ttl" in row or row.get("onboarding_complete") is not False:
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}}, "UpdateItem")
        assert UpdateExpression == "SET #ttl = :ttl" and ExpressionAttributeNames == {"#ttl": "ttl"}
        row["ttl"] = ExpressionAttributeValues[":ttl"]
        self.updates.append(Key)


def _run(monkeypatch, table, *argv):
    monkeypatch.setattr(script.boto3, "resource", lambda *a, **k: type("R", (), {"Table": lambda self, name: table})())
    monkeypatch.setattr(sys, "argv", ["expire-unfinished-signups.py", *argv])
    script.main()


def test_finds_only_unfinished_signups_without_an_expiry_across_pages():
    second = {**UNFINISHED, "PK": "USER#4915199999999"}
    table = _Table([UNFINISHED, second, FINISHED, VISITOR, EXPIRING, MESSAGE])
    assert script.find_unfinished(table) == [
        {"PK": "USER#4915112345678", "SK": "PROFILE"},
        {"PK": "USER#4915199999999", "SK": "PROFILE"},
    ]


def test_dry_run_changes_nothing_and_prints_no_full_number(monkeypatch, capsys):
    table = _Table([UNFINISHED, FINISHED, VISITOR, EXPIRING, MESSAGE])
    _run(monkeypatch, table)
    out = capsys.readouterr().out
    assert table.updates == []
    assert "1 unfinished sign-up(s) without an expiry" in out
    assert "would expire USER#491***" in out
    assert "4915112345678" not in out


def test_apply_sets_a_7_day_expiry_on_unfinished_rows_only(monkeypatch, capsys):
    table = _Table([UNFINISHED, FINISHED, VISITOR, EXPIRING, MESSAGE])
    _run(monkeypatch, table, "--apply")
    assert table.updates == [{"PK": "USER#4915112345678", "SK": "PROFILE"}]
    ttl = table.rows[("USER#4915112345678", "PROFILE")]["ttl"]
    assert abs(ttl - (time.time() + 7 * 24 * 3600)) < 60
    assert "ttl" not in table.rows[("USER#919876543210", "PROFILE")]
    assert table.rows[("USER#15550001111", "PROFILE")]["ttl"] == 1790000000
    assert table.rows[("USER#15550002222", "PROFILE")]["ttl"] == 1790000000
    assert "4915112345678" not in capsys.readouterr().out


def test_a_signup_finished_since_the_scan_is_left_alone():
    table = _Table([UNFINISHED])
    key = {"PK": "USER#4915112345678", "SK": "PROFILE"}
    table.rows[("USER#4915112345678", "PROFILE")]["onboarding_complete"] = True
    assert script.set_expiry(table, key, 1800000000) is False
    assert "ttl" not in table.rows[("USER#4915112345678", "PROFILE")]


def test_other_errors_are_not_swallowed():
    class _Broken:
        def update_item(self, **_k):
            raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "x"}}, "UpdateItem")

    with pytest.raises(ClientError):
        script.set_expiry(_Broken(), {"PK": "USER#1", "SK": "PROFILE"}, 1800000000)
