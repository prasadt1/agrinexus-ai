"""Webhook handler pure-function tests — no live AWS calls."""
import hashlib
import hmac as hmac_mod
import importlib.util
import os
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("QUEUE_URL", "https://sqs.example.com/queue")
    monkeypatch.setenv("VOICE_QUEUE_URL", "https://sqs.example.com/voice")
    monkeypatch.setenv("VERIFY_TOKEN_SECRET", "test/verify")
    monkeypatch.setenv("APP_SECRET_NAME", "test/app")
    monkeypatch.setenv("VERIFY_SIGNATURE", "true")
    monkeypatch.setenv("RATE_LIMIT_MESSAGES", "25")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "3600")


@pytest.fixture()
def wh(monkeypatch):
    """Import webhook handler with boto3 mocked."""
    mock_boto3 = types.ModuleType("boto3")
    mock_table = types.SimpleNamespace(query=lambda **kw: {"Count": 0, "Items": []})
    mock_dynamo = types.SimpleNamespace(Table=lambda name: mock_table)
    mock_sqs = types.SimpleNamespace(send_message=lambda **kw: {})
    mock_secrets = types.SimpleNamespace(get_secret_value=lambda **kw: {"SecretString": "secret"})

    def _client(svc, **kw):
        if svc == "sqs":
            return mock_sqs
        return mock_secrets

    mock_boto3.resource = lambda svc, **kw: mock_dynamo
    mock_boto3.client = _client
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

    spec = importlib.util.spec_from_file_location(
        "webhook_handler",
        os.path.join(os.path.dirname(__file__), "..", "src", "webhook", "handler.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# should_skip_rag
# ---------------------------------------------------------------------------

class TestShouldSkipRag:
    def test_done_hindi(self, wh):
        assert wh.should_skip_rag("हो गया") is True

    def test_done_english(self, wh):
        assert wh.should_skip_rag("done") is True

    def test_done_marathi(self, wh):
        assert wh.should_skip_rag("झाला") is True

    def test_not_yet_hindi(self, wh):
        assert wh.should_skip_rag("अभी नहीं") is True

    def test_normal_question_not_skipped(self, wh):
        assert wh.should_skip_rag("How to grow wheat?") is False

    def test_empty_string(self, wh):
        assert wh.should_skip_rag("") is False

    def test_none(self, wh):
        assert wh.should_skip_rag(None) is False

    def test_case_insensitive(self, wh):
        assert wh.should_skip_rag("DONE") is True
        assert wh.should_skip_rag("Done") is True


# ---------------------------------------------------------------------------
# redact_phone
# ---------------------------------------------------------------------------

class TestRedactPhone:
    def test_normal_phone(self, wh):
        assert wh.redact_phone("491234567890") == "491***"

    def test_short_phone(self, wh):
        assert wh.redact_phone("49") == "***"

    def test_empty_phone(self, wh):
        assert wh.redact_phone("") == "***"

    def test_none_phone(self, wh):
        assert wh.redact_phone(None) == "***"

    def test_exactly_three_chars(self, wh):
        assert wh.redact_phone("491") == "491***"


# ---------------------------------------------------------------------------
# _rate_limit_globally_disabled
# ---------------------------------------------------------------------------

class TestRateLimitDisabled:
    def test_disabled_true(self, wh, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_DISABLED", "true")
        assert wh._rate_limit_globally_disabled() is True

    def test_disabled_1(self, wh, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
        assert wh._rate_limit_globally_disabled() is True

    def test_disabled_yes(self, wh, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_DISABLED", "yes")
        assert wh._rate_limit_globally_disabled() is True

    def test_not_disabled(self, wh, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_DISABLED", "false")
        assert wh._rate_limit_globally_disabled() is False

    def test_empty(self, wh, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_DISABLED", "")
        assert wh._rate_limit_globally_disabled() is False


# ---------------------------------------------------------------------------
# _rate_limit_bypass_phones / _beta_phones
# ---------------------------------------------------------------------------

class TestBypassPhones:
    def test_bypass_csv(self, wh, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_BYPASS_PHONES", "491111,+492222, 493333 ")
        result = wh._rate_limit_bypass_phones()
        assert "491111" in result
        assert "492222" in result
        assert "493333" in result

    def test_bypass_empty(self, wh, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_BYPASS_PHONES", "")
        assert wh._rate_limit_bypass_phones() == set()

    def test_beta_csv(self, wh, monkeypatch):
        monkeypatch.setenv("BETA_PHONES", "+491111,492222")
        result = wh._beta_phones()
        assert "491111" in result
        assert "492222" in result


# ---------------------------------------------------------------------------
# _select_queue_url
# ---------------------------------------------------------------------------

class TestSelectQueue:
    def test_normal_user_gets_main_queue(self, wh, monkeypatch):
        monkeypatch.setattr(wh, "QUEUE_URL_BETA", "")
        assert wh._select_queue_url("491234") == wh.QUEUE_URL

    def test_beta_user_gets_beta_queue(self, wh, monkeypatch):
        monkeypatch.setattr(wh, "QUEUE_URL_BETA", "https://sqs/beta")
        monkeypatch.setenv("BETA_PHONES", "491234")
        assert wh._select_queue_url("491234") == "https://sqs/beta"


# ---------------------------------------------------------------------------
# verify_signature
# ---------------------------------------------------------------------------

class TestVerifySignature:
    def test_valid_signature(self, wh, monkeypatch):
        secret = "mysecret"
        payload = '{"test": true}'
        expected = hmac_mod.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        monkeypatch.setattr(wh, "VERIFY_SIGNATURE", True)
        monkeypatch.setattr(wh, "get_app_secret", lambda: secret)
        assert wh.verify_signature(payload, f"sha256={expected}") is True

    def test_invalid_signature(self, wh, monkeypatch):
        monkeypatch.setattr(wh, "VERIFY_SIGNATURE", True)
        monkeypatch.setattr(wh, "get_app_secret", lambda: "mysecret")
        assert wh.verify_signature("payload", "sha256=wrong") is False

    def test_missing_signature(self, wh, monkeypatch):
        monkeypatch.setattr(wh, "VERIFY_SIGNATURE", True)
        assert wh.verify_signature("payload", "") is False

    def test_verification_disabled(self, wh, monkeypatch):
        monkeypatch.setattr(wh, "VERIFY_SIGNATURE", False)
        assert wh.verify_signature("anything", "") is True
