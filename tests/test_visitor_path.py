"""
Unit tests for re:Invent visitor path: trigger, caps, DELETE, nudge exclusion.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

REPO = Path(__file__).resolve().parents[1]
COMMON = str(REPO / "src" / "common-layer" / "python")
if COMMON not in sys.path:
    sys.path.insert(0, COMMON)

from common import visitor as visitor_mod  # noqa: E402


class TestVisitorTrigger:
    def test_matches_reinvent_variants(self):
        assert visitor_mod.matches_reinvent_trigger("Hi from re:Invent")
        assert visitor_mod.matches_reinvent_trigger("hello reinvent booth")
        assert visitor_mod.matches_reinvent_trigger("RE:INVENT")
        assert not visitor_mod.matches_reinvent_trigger("Hi")
        assert not visitor_mod.matches_reinvent_trigger("inventory check")


class TestVisitorCaps:
    def test_per_user_cap_blocks(self, monkeypatch):
        monkeypatch.setenv("VISITOR_DAILY_PER_USER_CAP", "2")
        monkeypatch.setenv("VISITOR_DAILY_GLOBAL_CAP", "300")
        table = MagicMock()
        # first call user ok, second user fails
        table.update_item.side_effect = [
            {},  # user ok
            {},  # global ok
            ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}},
                "UpdateItem",
            ),
        ]
        ok1, r1 = visitor_mod.try_consume_visitor_answer(table, "15551234567", bypass=False)
        assert ok1 and r1 is None
        ok2, r2 = visitor_mod.try_consume_visitor_answer(table, "15551234567", bypass=False)
        assert not ok2 and r2 == "user"

    def test_global_cap_blocks_and_rolls_back_user(self, monkeypatch):
        monkeypatch.setenv("VISITOR_DAILY_PER_USER_CAP", "10")
        monkeypatch.setenv("VISITOR_DAILY_GLOBAL_CAP", "1")
        table = MagicMock()
        table.update_item.side_effect = [
            {},  # user ok
            ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}},
                "UpdateItem",
            ),
            {},  # rollback
        ]
        ok, reason = visitor_mod.try_consume_visitor_answer(table, "15551234567", bypass=False)
        assert not ok and reason == "global"
        assert table.update_item.call_count == 3

    def test_allowlisted_bypass(self):
        table = MagicMock()
        ok, reason = visitor_mod.try_consume_visitor_answer(table, "15551234567", bypass=True)
        assert ok and reason is None
        table.update_item.assert_not_called()


class TestDelete:
    def test_is_delete_command(self):
        assert visitor_mod.is_delete_command("DELETE")
        assert visitor_mod.is_delete_command("delete my data")
        assert not visitor_mod.is_delete_command("please delete later")

    def test_delete_user_conversation_data(self):
        table = MagicMock()
        table.query.return_value = {
            "Items": [
                {"PK": "USER#1", "SK": "PROFILE"},
                {"PK": "USER#1", "SK": "MSG#1"},
            ]
        }
        n = visitor_mod.delete_user_conversation_data(table, "1")
        assert n == 2
        assert table.delete_item.call_count >= 2

    def test_delete_user_media_objects(self):
        s3 = MagicMock()
        s3.list_objects_v2.side_effect = [
            {
                "Contents": [
                    {"Key": "images/15551234567/a.jpg"},
                    {"Key": "images/15551234567/b.jpg"},
                ]
            },
            {"Contents": [{"Key": "voice/15551234567/c.ogg"}]},
        ]
        n = visitor_mod.delete_user_media_objects(s3, "bucket", "15551234567")
        assert n == 3
        assert s3.delete_objects.call_count == 2
        assert s3.list_objects_v2.call_args_list[0][1]["Prefix"] == "images/15551234567/"
        assert s3.list_objects_v2.call_args_list[1][1]["Prefix"] == "voice/15551234567/"


class TestVisitorMetrics:
    def test_emit_visitor_metric_namespace(self):
        cw = MagicMock()
        visitor_mod.emit_visitor_metric(cw, "visitor_started", 1.0)
        cw.put_metric_data.assert_called_once()
        kwargs = cw.put_metric_data.call_args[1]
        assert kwargs["Namespace"] == "AgriNexus/Visitor"
        assert kwargs["MetricData"][0]["MetricName"] == "visitor_started"

    def test_processor_wires_expected_metric_names(self):
        """Processor must emit each required Visitor counter on the live paths."""
        src = (REPO / "src" / "processor" / "handler.py").read_text(encoding="utf-8")
        for name in (
            "visitor_started",
            "visitor_question_answered",
            "visitor_photo_answered",
            "visitor_cap_hit_user",
            "visitor_cap_hit_global",
            "visitor_delete",
        ):
            assert f'"{name}"' in src or f"'{name}'" in src, f"missing emit for {name}"

    def test_cap_hit_and_delete_metrics_fire_via_processor_helpers(self, monkeypatch):
        monkeypatch.setenv("TABLE_NAME", "t")
        monkeypatch.setenv("KNOWLEDGE_BASE_ID", "kb")
        monkeypatch.setenv("GUARDRAIL_ID", "")
        monkeypatch.setenv("GUARDRAIL_VERSION", "1")
        monkeypatch.setenv("TEMP_AUDIO_BUCKET", "media-bucket")
        monkeypatch.setenv("VISITOR_DAILY_PER_USER_CAP", "1")
        monkeypatch.setenv("VISITOR_DAILY_GLOBAL_CAP", "300")

        import importlib.util
        import types

        emitted: list[str] = []
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = lambda **kw: emitted.append(
            kw["MetricData"][0]["MetricName"]
        )
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {"Contents": []}
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_table.update_item.side_effect = [
            {},  # user ok
            {},  # global ok
            ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}},
                "UpdateItem",
            ),
        ]

        output_mod = types.ModuleType("output")
        output_mod.text_to_speech = lambda *a, **k: None
        output_mod.truncate_for_voice = lambda t, *a, **k: t
        output_mod.voice_truncation_prefix = lambda *a, **k: ""
        monkeypatch.setitem(sys.modules, "output", output_mod)
        analyzer_mod = types.ModuleType("analyzer")
        analyzer_mod.analyze_crop_image = lambda *a, **k: {"recommendations": "ok"}
        analyzer_mod.process_image_message = lambda *a, **k: {"text": "ok"}
        monkeypatch.setitem(sys.modules, "analyzer", analyzer_mod)

        wa = types.ModuleType("common.whatsapp")
        wa.send_whatsapp_message = MagicMock(return_value=True)
        wa.send_whatsapp_list = MagicMock(return_value=True)
        wa.send_whatsapp_buttons = MagicMock(return_value=True)
        monkeypatch.setitem(sys.modules, "common.whatsapp", wa)

        original_path = list(sys.path)
        try:
            sys.path.insert(0, str(REPO / "src" / "processor"))
            sys.path.insert(0, COMMON)
            spec = importlib.util.spec_from_file_location(
                "processor_handler_visitor_metrics",
                REPO / "src" / "processor" / "handler.py",
            )
            mod = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(mod)
        finally:
            sys.path[:] = original_path

        mod.table = mock_table
        mod.cloudwatch = mock_cw
        mod.s3 = mock_s3

        profile = {"demo_tier": "visitor", "dialect": "en", "onboarding_complete": True}
        assert mod._consume_visitor_or_refuse("15550001111", profile, approved=False) is True
        assert mod._consume_visitor_or_refuse("15550001111", profile, approved=False) is False
        assert "visitor_cap_hit_user" in emitted

        mod._handle_delete_command("15550001111")
        assert "visitor_delete" in emitted
        mock_s3.list_objects_v2.assert_called()


class TestNudgeExclusion:
    def test_visitor_profile_detected(self):
        assert visitor_mod.is_visitor_profile({"demo_tier": "visitor"})
        assert not visitor_mod.is_visitor_profile({"demo_tier": "public"})
        assert not visitor_mod.is_visitor_profile(None)

    def test_sender_skips_visitor_tier(self, monkeypatch, capsys):
        monkeypatch.setenv("TABLE_NAME", "t")
        monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:aws:iam::1:role/r")
        monkeypatch.setenv("REMINDER_LAMBDA_ARN", "arn:aws:lambda:us-east-1:1:function:f")

        import types
        import importlib.util

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {
                    "phone_number": "15551230000",
                    "dialect": "en",
                    "GSI1PK": "LOCATION#Latur",
                }
            ]
        }
        mock_table.get_item.return_value = {
            "Item": {
                "demo_tier": "visitor",
                "onboarding_complete": True,
                "consent": True,
                "crop": "Cotton",
                "location": "Latur",
            }
        }

        mock_boto3 = types.ModuleType("boto3")
        mock_boto3.resource = lambda *a, **k: types.SimpleNamespace(Table=lambda n: mock_table)
        mock_boto3.client = lambda *a, **k: MagicMock()
        monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

        common_mod = types.ModuleType("common")
        common_mod.whatsapp = types.ModuleType("common.whatsapp")
        common_mod.whatsapp.send_whatsapp_message = lambda *a, **k: True
        common_mod.whatsapp.send_whatsapp_buttons = lambda *a, **k: True
        common_mod.whatsapp.send_whatsapp_template = lambda *a, **k: True
        common_mod.allowlist = types.ModuleType("common.allowlist")
        common_mod.allowlist.is_approved_user = lambda *a, **k: True
        common_mod.redact = types.ModuleType("common.redact")
        common_mod.redact.redact_phone = lambda p: "155***"
        monkeypatch.setitem(sys.modules, "common", common_mod)
        monkeypatch.setitem(sys.modules, "common.whatsapp", common_mod.whatsapp)
        monkeypatch.setitem(sys.modules, "common.allowlist", common_mod.allowlist)
        monkeypatch.setitem(sys.modules, "common.redact", common_mod.redact)

        nc = types.ModuleType("nudge_copy")
        nc.NUDGE_BUTTONS = {"en": ["Done", "Not yet"], "hi": ["हो गया", "अभी नहीं"]}
        nc.build_nudge_message = lambda *a, **k: "nudge text"
        monkeypatch.setitem(sys.modules, "nudge_copy", nc)
        bl = types.ModuleType("bedrock_liner")
        bl.invoke_nudge_focus_line = lambda *a, **k: None
        monkeypatch.setitem(sys.modules, "bedrock_liner", bl)

        spec = importlib.util.spec_from_file_location(
            "nudge_sender_visitor",
            REPO / "src" / "nudge" / "sender.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.table = mock_table

        result = mod.lambda_handler(
            {"location": "Latur", "weather": {"wind_speed": 1.0}, "activity": "spray"},
            None,
        )
        assert result["nudges_sent"] == 0
        assert result["nudges_skipped"] >= 1
        out = capsys.readouterr().out
        assert "visitor tier" in out
        mock_table.put_item.assert_not_called()
