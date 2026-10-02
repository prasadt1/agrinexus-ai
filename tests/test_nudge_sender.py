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


# ---------------------------------------------------------------------------
# Send window and cooldown
# ---------------------------------------------------------------------------

# 10:00 Asia/Kolkata
NOW = datetime(2026, 10, 3, 4, 30)


def _ist(hour, minute=0, day=3):
    return datetime(2026, 10, day, hour, minute) - timedelta(hours=5, minutes=30)


def _run_handler(sender, monkeypatch, now=NOW, nudges=(), force=None):
    farmer = {"phone_number": "491234", "dialect": "en"}
    profile = {
        "onboarding_complete": True, "consent": True, "crop": "Cotton",
        "location": "Latur", "demo_tier": "full",
    }
    puts, metrics, sends = [], [], []

    def query(**kw):
        if kw.get("IndexName") == "GSI1":
            return {"Items": [farmer]}
        return {"Items": list(nudges)}

    monkeypatch.setattr(sender, "table", types.SimpleNamespace(
        query=query,
        get_item=lambda **kw: {"Item": profile},
        put_item=lambda **kw: puts.append(kw),
    ))
    monkeypatch.setattr(sender, "_utcnow", lambda: now)
    monkeypatch.setattr(sender, "emit_metric", lambda name, value=1.0: metrics.append(name))
    monkeypatch.setattr(sender, "send_whatsapp_buttons", lambda *a, **k: sends.append(a) or True)
    monkeypatch.setattr(sender, "create_reminder_schedule", lambda *a, **k: None)
    monkeypatch.setattr(sender, "create_expiry_schedule", lambda *a, **k: None)
    event = {"location": "Latur", "weather": {"wind_speed": 5.0}, "activity": "spray"}
    if force is not None:
        event["force"] = force
    out = sender.lambda_handler(event, None)
    return out, puts, metrics, sends


class TestSendWindow:
    def test_night_run_defers_instead_of_sending(self, sender, monkeypatch):
        out, puts, metrics, sends = _run_handler(sender, monkeypatch, now=_ist(23))
        assert out["nudges_sent"] == 0
        assert puts == [] and sends == []
        assert "NudgesDeferred" in metrics
        assert "NudgesSent" not in metrics

    def test_daytime_run_sends(self, sender, monkeypatch):
        out, puts, metrics, sends = _run_handler(sender, monkeypatch, now=_ist(10))
        assert out["nudges_sent"] == 1 and len(sends) == 1
        assert "NudgesDeferred" not in metrics

    @pytest.mark.parametrize("hour,minute,inside", [
        (5, 59, False), (6, 0, True), (18, 59, True), (19, 0, False), (0, 30, False),
    ])
    def test_window_is_0600_to_1900_kolkata(self, sender, hour, minute, inside):
        assert sender.in_send_window(_ist(hour, minute)) is inside

    def test_window_hours_come_from_env(self, sender, monkeypatch):
        monkeypatch.setenv("NUDGE_WINDOW_START_HOUR", "8")
        monkeypatch.setenv("NUDGE_WINDOW_END_HOUR", "12")
        assert sender.in_send_window(_ist(7, 30)) is False
        assert sender.in_send_window(_ist(11, 59)) is True
        assert sender.in_send_window(_ist(12)) is False

    @pytest.mark.parametrize("start,end", [("x", "19"), ("19", "6"), ("6", "6")])
    def test_unreadable_window_sends_nothing(self, sender, monkeypatch, start, end):
        monkeypatch.setenv("NUDGE_WINDOW_START_HOUR", start)
        monkeypatch.setenv("NUDGE_WINDOW_END_HOUR", end)
        assert sender.in_send_window(_ist(10)) is False

    def test_force_sends_at_night(self, sender, monkeypatch):
        out, _, metrics, sends = _run_handler(sender, monkeypatch, now=_ist(23), force=True)
        assert out["nudges_sent"] == 1 and len(sends) == 1
        assert "NudgesDeferred" not in metrics

    def test_only_boolean_true_forces(self, sender, monkeypatch):
        out, *_ = _run_handler(sender, monkeypatch, now=_ist(23), force="true")
        assert out["nudges_sent"] == 0


def _closed(status, created, **extra):
    return {"SK": f"NUDGE#{created.isoformat()}#spray", "status": status, **extra}


class TestCooldown:
    def test_done_two_days_ago_blocks(self, sender, monkeypatch):
        done = _closed("DONE", NOW - timedelta(days=3), completedAt=(NOW - timedelta(days=2)).isoformat())
        out, puts, metrics, sends = _run_handler(sender, monkeypatch, nudges=[done])
        assert out["nudges_sent"] == 0 and sends == [] and puts == []
        assert "NudgesDeferred" not in metrics

    def test_expired_eight_days_ago_allows(self, sender, monkeypatch):
        expired = _closed("EXPIRED", NOW - timedelta(days=11), expiredAt=(NOW - timedelta(days=8)).isoformat())
        out, *_ = _run_handler(sender, monkeypatch, nudges=[expired])
        assert out["nudges_sent"] == 1

    def test_expired_without_timestamp_counts_from_creation_plus_72h(self, sender, monkeypatch):
        recent = _closed("EXPIRED", NOW - timedelta(days=5))
        out, *_ = _run_handler(sender, monkeypatch, nudges=[recent])
        assert out["nudges_sent"] == 0
        old = _closed("EXPIRED", NOW - timedelta(days=11))
        out, *_ = _run_handler(sender, monkeypatch, nudges=[old])
        assert out["nudges_sent"] == 1

    def test_other_activity_does_not_block(self, sender, monkeypatch):
        other = {"SK": f"NUDGE#{(NOW - timedelta(days=2)).isoformat()}#irrigate", "status": "DONE",
                 "completedAt": (NOW - timedelta(days=1)).isoformat()}
        out, *_ = _run_handler(sender, monkeypatch, nudges=[other])
        assert out["nudges_sent"] == 1

    def test_cooldown_days_from_env(self, sender, monkeypatch):
        monkeypatch.setenv("NUDGE_COOLDOWN_DAYS", "1")
        done = _closed("DONE", NOW - timedelta(days=3), completedAt=(NOW - timedelta(days=2)).isoformat())
        out, *_ = _run_handler(sender, monkeypatch, nudges=[done])
        assert out["nudges_sent"] == 1

    def test_unreadable_close_time_blocks(self, sender, monkeypatch):
        bad = {"SK": "NUDGE#not-a-time#spray", "status": "DONE", "completedAt": "garbage"}
        out, *_ = _run_handler(sender, monkeypatch, nudges=[bad])
        assert out["nudges_sent"] == 0

    def test_force_ignores_cooldown(self, sender, monkeypatch):
        done = _closed("DONE", NOW - timedelta(days=1), completedAt=(NOW - timedelta(hours=2)).isoformat())
        out, *_ = _run_handler(sender, monkeypatch, nudges=[done], force=True)
        assert out["nudges_sent"] == 1


class TestPerFarmerNudgeIds:
    def test_two_farmers_get_distinct_ids_and_schedules(self, sender, monkeypatch):
        """Each farmer needs their own nudge_id; schedule names are global per account."""
        farmers = [
            {"phone_number": "491111", "dialect": "en"},
            {"phone_number": "492222", "dialect": "en"},
        ]
        profile = {
            "onboarding_complete": True, "consent": True, "crop": "Cotton",
            "location": "Latur", "demo_tier": "full",
        }
        puts, schedules = [], []

        def query(**kw):
            if kw.get("IndexName") == "GSI1":
                return {"Items": farmers}
            return {"Items": []}

        monkeypatch.setattr(sender, "table", types.SimpleNamespace(
            query=query,
            get_item=lambda **kw: {"Item": profile},
            put_item=lambda **kw: puts.append(kw["Item"]),
        ))
        # Wall clock stuck: both farmers share an id if the handler stamps
        # once before the loop (or reuses that single value for every farmer).
        monkeypatch.setattr(sender, "_utcnow", lambda: NOW)
        monkeypatch.setattr(sender, "emit_metric", lambda *a, **k: None)
        monkeypatch.setattr(sender, "send_whatsapp_buttons", lambda *a, **k: True)
        monkeypatch.setattr(sender.scheduler, "create_schedule",
                            lambda **kw: schedules.append(kw) or {})

        out = sender.lambda_handler(
            {"location": "Latur", "weather": {"wind_speed": 5.0}, "activity": "spray"},
            None,
        )

        assert out["nudges_sent"] == 2
        ids = [item["SK"].removeprefix("NUDGE#") for item in puts]
        assert len(ids) == 2 and ids[0] != ids[1]

        assert len(schedules) == 6
        names = [s["Name"] for s in schedules]
        assert len(set(names)) == 6

        for phone in ("491111", "492222"):
            phone_schedules = [
                s for s in schedules
                if json.loads(s["Target"]["Input"]).get("phone_number") == phone
            ]
            assert len(phone_schedules) == 3


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
