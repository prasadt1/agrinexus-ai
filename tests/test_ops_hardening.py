"""
Regression tests for Bedrock model ID, web-chat error visibility, rate-limit
sourceIp, keyword exact-match, and phone redaction.
"""
from __future__ import annotations

import base64
import importlib.util
import io
import json
import logging
import os
import sys
import types
from pathlib import Path

from typing import Optional

import pytest

REPO = Path(__file__).resolve().parents[1]
COMMON_LAYER = str(REPO / "src" / "common-layer" / "python")
if COMMON_LAYER not in sys.path:
    sys.path.insert(0, COMMON_LAYER)


# ---------------------------------------------------------------------------
# 1) Model ID — no retired foundation-model ID substring in active source
# ---------------------------------------------------------------------------

class TestNoRetiredModelLiteral:
    def test_no_claude_3_sonnet_in_active_source(self):
        """Assert no source file contains the retired model id substring."""
        offenders = []
        scan_roots = [REPO / "src", REPO / "template.yaml"]
        for root in scan_roots:
            paths = [root] if root.is_file() else root.rglob("*")
            for path in paths:
                if not path.is_file():
                    continue
                if path.suffix not in {".py", ".yaml", ".yml", ".sh", ".json"} and path.name != "template.yaml":
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if "claude-3-sonnet" in text:
                    offenders.append(str(path.relative_to(REPO)))
        assert offenders == [], f"Retired model literal still present in: {offenders}"


# ---------------------------------------------------------------------------
# Shared web-chat import helper
# ---------------------------------------------------------------------------

@pytest.fixture()
def webchat(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "test-kb")
    monkeypatch.setenv("GUARDRAIL_ID", "")
    monkeypatch.setenv("GUARDRAIL_VERSION", "1")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
    monkeypatch.setenv("ACCOUNT_ID", "123456789012")
    monkeypatch.setenv("WEB_RATE_LIMIT", "3")
    monkeypatch.setenv("WEB_RATE_LIMIT_WINDOW", "3600")
    monkeypatch.setenv("WEB_IMAGE_MAX_BYTES", "1024")
    monkeypatch.setenv("WEB_MAX_IMAGES", "1")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    store = {}

    class FakeTable:
        def get_item(self, Key):
            key = (Key["PK"], Key["SK"])
            item = store.get(key)
            return {"Item": dict(item)} if item else {}

        def put_item(self, Item):
            store[(Item["PK"], Item["SK"])] = dict(Item)

        def update_item(self, **kwargs):
            key = (kwargs["Key"]["PK"], kwargs["Key"]["SK"])
            item = store.setdefault(key, dict(kwargs["Key"]))
            # Minimal SET #count = #count + :inc support
            expr = kwargs.get("UpdateExpression", "")
            vals = kwargs.get("ExpressionAttributeValues", {})
            if "#count = #count + :inc" in expr.replace(" ", "") or "#count = #count + :inc" in expr:
                item["count"] = int(item.get("count", 0)) + int(vals[":inc"])
                item["ttl"] = item.get("ttl") or vals.get(":now", 0)
            from botocore.exceptions import ClientError
            # Honor ConditionExpression count < limit
            names = kwargs.get("ExpressionAttributeNames", {})
            if "ConditionExpression" in kwargs:
                limit = vals.get(":limit")
                now = vals.get(":now")
                count = int(item.get("count", 0))
                ttl = int(item.get("ttl", 0) or 0)
                if limit is not None and count >= limit:
                    raise ClientError(
                        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "limit"}},
                        "UpdateItem",
                    )
                if now is not None and ttl < now:
                    raise ClientError(
                        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "ttl"}},
                        "UpdateItem",
                    )
            return {"Attributes": dict(item)}

    mock_boto3 = types.ModuleType("boto3")
    mock_boto3.resource = lambda *a, **k: types.SimpleNamespace(Table=lambda name: FakeTable())
    mock_agent = types.SimpleNamespace(
        retrieve_and_generate=lambda **kw: {
            "output": {"text": "Spray neem oil at dusk."},
            "citations": [],
        }
    )
    mock_runtime = types.SimpleNamespace(
        invoke_model=lambda **kw: {
            "body": io.BytesIO(json.dumps({"content": [{"text": "Looks like cotton."}]}).encode())
        }
    )

    def _client(svc, **kw):
        if svc == "bedrock-agent-runtime":
            return mock_agent
        if svc == "bedrock-runtime":
            return mock_runtime
        return types.SimpleNamespace()

    mock_boto3.client = _client
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

    # Fresh import
    for name in list(sys.modules):
        if name == "handler" or name.endswith("web-chat.handler"):
            sys.modules.pop(name, None)

    spec = importlib.util.spec_from_file_location(
        "webchat_handler_ops",
        REPO / "src" / "web-chat" / "handler.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._rate_store = store
    mod._mock_agent = mock_agent
    mod._mock_runtime = mock_runtime
    return mod


def _chat_event(source_ip: str, message: str = "How to grow wheat?", xff: Optional[str] = None, **body_extra):
    headers = {"Content-Type": "application/json"}
    if xff is not None:
        headers["X-Forwarded-For"] = xff
    body = {"message": message, "language": "en"}
    body.update(body_extra)
    return {
        "httpMethod": "POST",
        "headers": headers,
        "requestContext": {"identity": {"sourceIp": source_ip}},
        "body": json.dumps(body),
    }


# ---------------------------------------------------------------------------
# 2) Error visibility — downstream raise surfaces as handler error
# ---------------------------------------------------------------------------

class TestWebChatErrorVisibility:
    def test_downstream_exception_is_reraised(self, webchat, monkeypatch):
        def boom(*_a, **_kw):
            raise RuntimeError("bedrock down")

        monkeypatch.setattr(webchat, "query_bedrock", boom)
        with pytest.raises(RuntimeError, match="bedrock down"):
            webchat.lambda_handler(_chat_event("1.2.3.4"), None)

    def test_does_not_return_quiet_500_body(self, webchat, monkeypatch):
        def boom(*_a, **_kw):
            raise RuntimeError("kb missing")

        monkeypatch.setattr(webchat, "query_bedrock", boom)
        try:
            result = webchat.lambda_handler(_chat_event("1.2.3.4"), None)
        except RuntimeError:
            return
        # If it returned, it must not be a swallowed 500 body success-path
        assert False, f"Expected raise, got return {result}"


# ---------------------------------------------------------------------------
# 3) Rate limiter — sourceIp, ignore spoofed X-Forwarded-For; image caps
# ---------------------------------------------------------------------------

class TestWebChatRateLimitSourceIp:
    def test_n_plus_one_with_varying_xff_still_429(self, webchat):
        limit = webchat.RATE_LIMIT
        source_ip = "203.0.113.10"
        last = None
        for i in range(limit + 1):
            event = _chat_event(
                source_ip,
                message=f"question {i}",
                xff=f"198.51.100.{i}, 203.0.113.10",
            )
            last = webchat.lambda_handler(event, None)
        assert last["statusCode"] == 429

    def test_get_client_ip_ignores_xff(self, webchat):
        event = {
            "headers": {"X-Forwarded-For": "8.8.8.8"},
            "requestContext": {"identity": {"sourceIp": "9.9.9.9"}},
        }
        assert webchat.get_client_ip(event) == "9.9.9.9"

    def test_image_count_cap(self, webchat):
        tiny = base64.b64encode(b"abc").decode()
        event = _chat_event(
            "1.1.1.1",
            message="",
            image=tiny,
            images=[tiny, tiny],
        )
        # message empty + images over cap → 400 before rate limit burn
        resp = webchat.lambda_handler(event, None)
        assert resp["statusCode"] == 400
        assert "Too many images" in resp["body"]

    def test_image_size_cap(self, webchat):
        huge = base64.b64encode(b"x" * 5000).decode()
        event = _chat_event("1.1.1.2", message="", image=huge)
        resp = webchat.lambda_handler(event, None)
        assert resp["statusCode"] == 400
        assert "too large" in resp["body"].lower()


# ---------------------------------------------------------------------------
# 4) Keyword matching — ordinary questions produce a reply path
# ---------------------------------------------------------------------------

class TestKeywordExactMatch:
    def test_after_spraying_question_not_skipped_by_webhook(self, monkeypatch):
        monkeypatch.setenv("TABLE_NAME", "t")
        monkeypatch.setenv("QUEUE_URL", "https://sqs.example.com/q")
        monkeypatch.setenv("VOICE_QUEUE_URL", "https://sqs.example.com/v")
        monkeypatch.setenv("VERIFY_TOKEN_SECRET", "s")
        monkeypatch.setenv("APP_SECRET_NAME", "s")
        monkeypatch.setenv("VERIFY_SIGNATURE", "false")

        mock_boto3 = types.ModuleType("boto3")
        mock_boto3.resource = lambda *a, **k: types.SimpleNamespace(
            Table=lambda n: types.SimpleNamespace(query=lambda **kw: {"Count": 0})
        )
        mock_boto3.client = lambda *a, **k: types.SimpleNamespace()
        monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

        # Ensure common imports resolve
        import common.whatsapp  # noqa: F401
        import common.allowlist  # noqa: F401

        # Stub whatsapp/allowlist if needed via real modules on path
        spec = importlib.util.spec_from_file_location(
            "webhook_kw",
            REPO / "src" / "webhook" / "handler.py",
        )
        mod = importlib.util.module_from_spec(spec)
        # Minimal stubs for common.whatsapp used at import
        wa = types.ModuleType("common.whatsapp")
        wa.send_whatsapp_message = lambda *a, **k: True
        wa.VOICE_RECEIVED_ACK = {"hi": "ok"}
        al = types.ModuleType("common.allowlist")
        al.is_approved_user = lambda *a, **k: True
        al.allowlist_expiry_hint = lambda *a, **k: ""
        monkeypatch.setitem(sys.modules, "common.whatsapp", wa)
        monkeypatch.setitem(sys.modules, "common.allowlist", al)
        spec.loader.exec_module(mod)

        q = "what to do after spraying?"
        assert mod.should_skip_rag(q) is False

    def test_webchat_after_spraying_produces_reply(self, webchat):
        resp = webchat.lambda_handler(
            _chat_event("5.5.5.5", message="what to do after spraying?"),
            None,
        )
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body.get("reply")
        assert "Spray" in body["reply"] or len(body["reply"]) > 0


# ---------------------------------------------------------------------------
# 5) Phone redaction — no raw number in captured logs
# ---------------------------------------------------------------------------

class TestPhoneRedaction:
    def test_redact_helper(self):
        from common.redact import redact_phone
        assert redact_phone("919876543210") == "919***"
        assert "9876543210" not in redact_phone("919876543210")

    def test_sender_logs_redacted(self, monkeypatch, capsys):
        monkeypatch.setenv("TABLE_NAME", "t")
        monkeypatch.setenv("SCHEDULER_ROLE_ARN", "arn:aws:iam::1:role/r")
        monkeypatch.setenv("REMINDER_LAMBDA_ARN", "arn:aws:lambda:us-east-1:1:function:f")

        mock_boto3 = types.ModuleType("boto3")
        from datetime import datetime
        nudge_sk = f"NUDGE#{datetime.utcnow().isoformat()}#spray"
        mock_boto3.resource = lambda *a, **k: types.SimpleNamespace(
            Table=lambda n: types.SimpleNamespace(
                query=lambda **kw: {"Items": [{"SK": nudge_sk, "status": "SENT"}]},
                put_item=lambda **kw: {},
                update_item=lambda **kw: {},
            )
        )
        mock_boto3.client = lambda *a, **k: types.SimpleNamespace(
            put_metric_data=lambda **kw: {},
            create_schedule=lambda **kw: {},
        )
        monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

        common_mod = types.ModuleType("common")
        common_mod.whatsapp = types.ModuleType("common.whatsapp")
        common_mod.whatsapp.send_whatsapp_message = lambda **kw: True
        common_mod.whatsapp.send_whatsapp_buttons = lambda **kw: True
        common_mod.whatsapp.send_whatsapp_template = lambda **kw: True
        common_mod.allowlist = types.ModuleType("common.allowlist")
        common_mod.allowlist.is_approved_user = lambda *a, **k: True
        import common.redact as redact_mod
        common_mod.redact = redact_mod
        monkeypatch.setitem(sys.modules, "common", common_mod)
        monkeypatch.setitem(sys.modules, "common.whatsapp", common_mod.whatsapp)
        monkeypatch.setitem(sys.modules, "common.allowlist", common_mod.allowlist)
        monkeypatch.setitem(sys.modules, "common.redact", redact_mod)

        spec = importlib.util.spec_from_file_location(
            "nudge_sender_redact",
            REPO / "src" / "nudge" / "sender.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        phone = "919876543210"
        assert mod.has_open_nudge(phone, "spray") is True
        out = capsys.readouterr().out
        assert phone not in out
        assert "919***" in out

    def test_whatsapp_send_success_log_omits_recipient(self, monkeypatch, capsys):
        import common.whatsapp as wa

        phone = "919876543210"

        class _Resp:
            status_code = 200

            def json(self):
                return {
                    "messaging_product": "whatsapp",
                    "contacts": [{"input": phone, "wa_id": phone}],
                    "messages": [{"id": "wamid.TEST"}],
                }

        monkeypatch.setattr(wa, "get_whatsapp_credentials", lambda: ("tok", "pnid"))
        monkeypatch.setattr(wa.requests, "post", lambda *a, **k: _Resp())

        assert wa.send_whatsapp_message(phone, "hello") is True
        assert wa.send_whatsapp_buttons(phone, "pick", [{"id": "a", "title": "A"}]) is True
        out = capsys.readouterr().out
        assert phone not in out
        assert "wamid.TEST" in out
