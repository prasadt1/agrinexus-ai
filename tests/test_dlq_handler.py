"""DLQ handler tests — dialect-aware error messages, no live AWS calls."""
import json
import os
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("ACCESS_TOKEN_SECRET", "test/token")
    monkeypatch.setenv("PHONE_NUMBER_ID_SECRET", "test/phone-id")


@pytest.fixture()
def dlq_module(monkeypatch):
    """Import DLQ handler with boto3 fully mocked."""
    import importlib.util

    # Stub boto3 before import
    mock_boto3 = types.ModuleType("boto3")
    mock_table = types.SimpleNamespace(get_item=lambda **kw: {"Item": {}})
    mock_dynamo = types.SimpleNamespace(Table=lambda name: mock_table)
    mock_secrets = types.SimpleNamespace(get_secret_value=lambda **kw: {"SecretString": "tok"})
    mock_boto3.resource = lambda svc, **kw: mock_dynamo
    mock_boto3.client = lambda svc, **kw: mock_secrets
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

    spec = importlib.util.spec_from_file_location(
        "dlq_handler",
        os.path.join(os.path.dirname(__file__), "..", "src", "dlq", "handler.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# ERROR_MESSAGES coverage
# ---------------------------------------------------------------------------

class TestErrorMessages:
    def test_all_four_languages_present(self, dlq_module):
        msgs = dlq_module.ERROR_MESSAGES
        assert set(msgs.keys()) == {"hi", "mr", "te", "en"}

    def test_hindi_message_is_devanagari(self, dlq_module):
        assert "माफ" in dlq_module.ERROR_MESSAGES["hi"]

    def test_english_message_readable(self, dlq_module):
        assert "system error" in dlq_module.ERROR_MESSAGES["en"].lower()

    def test_marathi_message_is_devanagari(self, dlq_module):
        assert "माफ" in dlq_module.ERROR_MESSAGES["mr"]

    def test_telugu_message_is_telugu_script(self, dlq_module):
        assert "క్షమించండి" in dlq_module.ERROR_MESSAGES["te"]


# ---------------------------------------------------------------------------
# get_user_dialect
# ---------------------------------------------------------------------------

class TestGetUserDialect:
    def test_returns_dialect_from_profile(self, dlq_module, monkeypatch):
        mock_table = types.SimpleNamespace(
            get_item=lambda **kw: {"Item": {"dialect": "mr"}}
        )
        monkeypatch.setattr(dlq_module, "table", mock_table)
        assert dlq_module.get_user_dialect("491234") == "mr"

    def test_defaults_to_hindi_when_no_profile(self, dlq_module, monkeypatch):
        mock_table = types.SimpleNamespace(get_item=lambda **kw: {})
        monkeypatch.setattr(dlq_module, "table", mock_table)
        assert dlq_module.get_user_dialect("491234") == "hi"

    def test_defaults_to_hindi_on_exception(self, dlq_module, monkeypatch):
        def _raise(**kw):
            raise RuntimeError("boom")
        mock_table = types.SimpleNamespace(get_item=_raise)
        monkeypatch.setattr(dlq_module, "table", mock_table)
        assert dlq_module.get_user_dialect("491234") == "hi"


# ---------------------------------------------------------------------------
# lambda_handler
# ---------------------------------------------------------------------------

class TestLambdaHandler:
    def test_processes_single_record(self, dlq_module, monkeypatch):
        sent = []
        monkeypatch.setattr(dlq_module, "get_user_dialect", lambda ph: "en")
        monkeypatch.setattr(dlq_module, "send_error_message", lambda ph, d: sent.append((ph, d)))

        event = {"Records": [{"body": json.dumps({"from": "491234"})}]}
        result = dlq_module.lambda_handler(event, None)
        assert result["statusCode"] == 200
        assert sent == [("491234", "en")]

    def test_skips_record_without_from(self, dlq_module, monkeypatch):
        sent = []
        monkeypatch.setattr(dlq_module, "send_error_message", lambda ph, d: sent.append((ph, d)))

        event = {"Records": [{"body": json.dumps({"text": "hello"})}]}
        dlq_module.lambda_handler(event, None)
        assert sent == []

    def test_processes_multiple_records(self, dlq_module, monkeypatch):
        sent = []
        monkeypatch.setattr(dlq_module, "get_user_dialect", lambda ph: "hi")
        monkeypatch.setattr(dlq_module, "send_error_message", lambda ph, d: sent.append(ph))

        event = {"Records": [
            {"body": json.dumps({"from": "111"})},
            {"body": json.dumps({"from": "222"})},
        ]}
        dlq_module.lambda_handler(event, None)
        assert sent == ["111", "222"]
