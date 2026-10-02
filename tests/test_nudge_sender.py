"""Nudge sender tests — float conversion, pending nudge check, handler."""
import importlib.util
import json
import os
import sys
import types
from datetime import datetime, timedelta
from decimal import Decimal

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:aws:iam::123:role/test")
    monkeypatch.setenv("REMINDER_FUNCTION_ARN", "arn:aws:lambda:us-east-1:123:function:test")
    # Production code uses REMINDER_LAMBDA_ARN
    monkeypatch.setenv("REMINDER_LAMBDA_ARN", "arn:aws:lambda:us-east-1:123:function:test")


@pytest.fixture()
def sender(monkeypatch):
    """Import nudge sender with boto3 mocked."""
    mock_boto3 = types.ModuleType("boto3")
    mock_table = types.SimpleNamespace(
        query=lambda **kw: {"Items": []},
        put_item=lambda **kw: {},
        update_item=lambda **kw: {},
    )
    mock_dynamo = types.SimpleNamespace(Table=lambda name: mock_table)
    mock_cw = types.SimpleNamespace(put_metric_data=lambda **kw: {})
    mock_scheduler = types.SimpleNamespace(create_schedule=lambda **kw: {})

    def _client(svc, **kw):
        if svc == "cloudwatch":
            return mock_cw
        if svc == "scheduler":
            return mock_scheduler
        return types.SimpleNamespace(get_secret_value=lambda **kw: {"SecretString": "tok"})

    mock_boto3.resource = lambda svc, **kw: mock_dynamo
    mock_boto3.client = _client
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

    layer = os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python")
    if layer not in sys.path:
        sys.path.insert(0, layer)
    # Drop any prior stub so real common.redact can load from the layer path
    for name in list(sys.modules):
        if name == "common" or name.startswith("common."):
            sys.modules.pop(name, None)
    import importlib
    redact_mod = importlib.import_module("common.redact")
    advice_mod = importlib.import_module("common.advice_filter")
    advice_mod._cloudwatch = mock_cw

    common_mod = types.ModuleType("common")
    common_mod.__path__ = []  # mark as package for submodule imports
    common_mod.whatsapp = types.ModuleType("common.whatsapp")
    common_mod.whatsapp.send_whatsapp_message = lambda **kw: True
    common_mod.whatsapp.send_whatsapp_buttons = lambda **kw: True
    common_mod.whatsapp.send_whatsapp_template = lambda **kw: True
    common_mod.allowlist = types.ModuleType("common.allowlist")
    common_mod.allowlist.is_approved_user = lambda table, phone: True
    common_mod.redact = redact_mod
    monkeypatch.setitem(sys.modules, "common", common_mod)
    monkeypatch.setitem(sys.modules, "common.whatsapp", common_mod.whatsapp)
    monkeypatch.setitem(sys.modules, "common.allowlist", common_mod.allowlist)
    monkeypatch.setitem(sys.modules, "common.redact", redact_mod)
    monkeypatch.setitem(sys.modules, "common.advice_filter", advice_mod)

    # Avoid importing a cached sender from a previous test
    sys.modules.pop("nudge_sender", None)

    spec = importlib.util.spec_from_file_location(
        "nudge_sender",
        os.path.join(os.path.dirname(__file__), "..", "src", "nudge", "sender.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# convert_floats_to_decimal
# ---------------------------------------------------------------------------

class TestConvertFloats:
    def test_float_to_decimal(self, sender):
        assert sender.convert_floats_to_decimal(3.14) == Decimal("3.14")

    def test_int_unchanged(self, sender):
        assert sender.convert_floats_to_decimal(42) == 42

    def test_string_unchanged(self, sender):
        assert sender.convert_floats_to_decimal("hello") == "hello"

    def test_dict_recursive(self, sender):
        result = sender.convert_floats_to_decimal({"wind": 8.5, "rain": 0})
        assert result["wind"] == Decimal("8.5")
        assert result["rain"] == 0

    def test_list_recursive(self, sender):
        result = sender.convert_floats_to_decimal([1.1, 2.2, "x"])
        assert result[0] == Decimal("1.1")
        assert result[2] == "x"

    def test_nested_dict_in_list(self, sender):
        result = sender.convert_floats_to_decimal([{"temp": 28.5}])
        assert result[0]["temp"] == Decimal("28.5")

    def test_none_unchanged(self, sender):
        assert sender.convert_floats_to_decimal(None) is None

    def test_bool_unchanged(self, sender):
        assert sender.convert_floats_to_decimal(True) is True


# ---------------------------------------------------------------------------
# has_open_nudge
# ---------------------------------------------------------------------------

class TestHasOpenNudge:
    def test_no_pending(self, sender, monkeypatch):
        mock_table = types.SimpleNamespace(
            query=lambda **kw: {"Items": []}
        )
        monkeypatch.setattr(sender, "table", mock_table)
        assert sender.has_open_nudge("491234", "spray") is False

    def test_has_sent_nudge(self, sender, monkeypatch):
        # Relative timestamp — absolute April 2026 dates go stale past max_age_hours=96
        ts = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        mock_table = types.SimpleNamespace(
            query=lambda **kw: {"Items": [
                {"SK": f"NUDGE#{ts}#spray", "status": "SENT"}
            ]}
        )
        monkeypatch.setattr(sender, "table", mock_table)
        assert sender.has_open_nudge("491234", "spray") is True

    def test_has_reminded_nudge(self, sender, monkeypatch):
        ts = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        mock_table = types.SimpleNamespace(
            query=lambda **kw: {"Items": [
                {"SK": f"NUDGE#{ts}#spray", "status": "REMINDED"}
            ]}
        )
        monkeypatch.setattr(sender, "table", mock_table)
        assert sender.has_open_nudge("491234", "spray") is True

    def test_done_nudge_not_pending(self, sender, monkeypatch):
        ts = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        mock_table = types.SimpleNamespace(
            query=lambda **kw: {"Items": [
                {"SK": f"NUDGE#{ts}#spray", "status": "DONE"}
            ]}
        )
        monkeypatch.setattr(sender, "table", mock_table)
        assert sender.has_open_nudge("491234", "spray") is False

    def test_expired_nudge_not_pending(self, sender, monkeypatch):
        ts = (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
        mock_table = types.SimpleNamespace(
            query=lambda **kw: {"Items": [
                {"SK": f"NUDGE#{ts}#spray", "status": "EXPIRED"}
            ]}
        )
        monkeypatch.setattr(sender, "table", mock_table)
        assert sender.has_open_nudge("491234", "spray") is False

    def test_stale_sent_nudge_past_max_age_not_open(self, sender, monkeypatch):
        """Production rule: SENT older than 96h is not 'open' (demo lock escape)."""
        ts = (datetime.utcnow() - timedelta(hours=120)).strftime("%Y-%m-%dT%H:%M:%S")
        mock_table = types.SimpleNamespace(
            query=lambda **kw: {"Items": [
                {"SK": f"NUDGE#{ts}#spray", "status": "SENT"}
            ]}
        )
        monkeypatch.setattr(sender, "table", mock_table)
        assert sender.has_open_nudge("491234", "spray") is False

    def test_different_activity_not_pending(self, sender, monkeypatch):
        mock_table = types.SimpleNamespace(
            query=lambda **kw: {"Items": [
                {"SK": "NUDGE#2026-04-25T10:00:00#irrigate", "status": "SENT"}
            ]}
        )
        monkeypatch.setattr(sender, "table", mock_table)
        assert sender.has_open_nudge("491234", "spray") is False

    def test_old_stale_nudge_does_not_block_forever(self, sender, monkeypatch):
        mock_table = types.SimpleNamespace(
            query=lambda **kw: {"Items": [
                {"SK": "NUDGE#2020-01-01T10:00:00#spray", "status": "SENT"}
            ]}
        )
        monkeypatch.setattr(sender, "table", mock_table)
        assert sender.has_open_nudge("491234", "spray") is False


# ---------------------------------------------------------------------------
# Scheduler idempotency / graceful degradation
# ---------------------------------------------------------------------------

class TestScheduleCreation:
    def test_create_reminder_schedule_conflict_is_ok(self, sender, monkeypatch, capsys):
        def _conflict(**_kwargs):
            raise Exception("ConflictException")

        monkeypatch.setattr(sender.scheduler, "create_schedule", _conflict)
        sender.create_reminder_schedule("491234", "2026-04-25T10:00:00#spray", 24, "hi")
        out = capsys.readouterr().out
        assert "already exists" in out.lower()

    def test_create_reminder_schedule_other_errors_do_not_crash(self, sender, monkeypatch, capsys):
        def _throttle(**_kwargs):
            raise Exception("ThrottlingException")

        monkeypatch.setattr(sender.scheduler, "create_schedule", _throttle)
        sender.create_reminder_schedule("491234", "2026-04-25T10:00:00#spray", 24, "hi")
        out = capsys.readouterr().out
        assert "failed to create reminder schedule" in out.lower()

    def test_create_expiry_schedule_other_errors_do_not_crash(self, sender, monkeypatch, capsys):
        def _boom(**_kwargs):
            raise Exception("ServiceUnavailable")

        monkeypatch.setattr(sender.scheduler, "create_schedule", _boom)
        sender.create_expiry_schedule("491234", "2026-04-25T10:00:00#spray", 72)
        out = capsys.readouterr().out
        assert "failed to create expiry schedule" in out.lower()


class TestScheduleCleanup:
    @pytest.mark.parametrize("make", ["reminder", "expiry"])
    def test_one_shot_schedules_delete_themselves(self, sender, monkeypatch, make):
        calls = []
        monkeypatch.setattr(sender.scheduler, "create_schedule", lambda **kw: calls.append(kw) or {})
        monkeypatch.setenv("REMINDER_LAMBDA_ARN", "arn:lambda")
        monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:role")
        if make == "reminder":
            sender.create_reminder_schedule("491234", "2026-04-25T10:00:00#spray", 24, "hi")
        else:
            sender.create_expiry_schedule("491234", "2026-04-25T10:00:00#spray", 72)
        assert calls and calls[0]["ActionAfterCompletion"] == "DELETE"
