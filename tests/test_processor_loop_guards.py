"""Processor loop guards: empty interactive payloads, visitor cap during crop confirmation."""
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

from tests.test_crop_override_confirmation_flow import _FakeDynamoTable, _FakeS3, _install_common_stubs

ROOT = Path(__file__).resolve().parents[1]
PHONE = "15550001111"


@pytest.fixture(autouse=True)
def _restore_modules():
    saved = dict(sys.modules)
    yield
    for name in list(sys.modules):
        if name not in saved:
            del sys.modules[name]
    sys.modules.update(saved)


def _load(sent, profile):
    os.environ["TABLE_NAME"] = "tbl"
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"
    os.environ.setdefault("KNOWLEDGE_BASE_ID", "kb")
    os.environ.setdefault("GUARDRAIL_ID", "")
    os.environ.setdefault("GUARDRAIL_VERSION", "1")
    _install_common_stubs(sent)
    analyzer = types.ModuleType("analyzer")
    analyzer.process_image_message = lambda *a, **k: {"text": "IMG"}
    analyzer.analyze_crop_image = lambda *a, **k: {"recommendations": "DIAG"}
    analyzer.diagnose_with_confirmed_crop = lambda *a, **k: "DIAG"
    analyzer.crop_mismatch_prompt = lambda *a, **k: ("?", [])
    sys.modules["analyzer"] = analyzer
    spec = importlib.util.spec_from_file_location("processor_handler_loop_guards", ROOT / "src" / "processor" / "handler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.table = _FakeDynamoTable(profile)
    mod.s3 = _FakeS3(b"img")
    return mod


def _send(mod, message, kind):
    body = {"wamid": "wamid.x", "from": PHONE, "type": kind, "message": message}
    mod.lambda_handler({"Records": [{"body": json.dumps(body)}]}, None)


FARMER = {"onboarding_complete": True, "dialect": "en", "location": "Latur", "crop": "Cotton"}


@pytest.mark.parametrize("message,kind", [
    ({"interactive": {"type": "nfm_reply", "nfm_reply": {"response_json": "{}"}}}, "interactive"),
    ({"interactive": {"type": "button_reply", "button_reply": {"title": ""}}}, "interactive"),
    ({"interactive": {}}, "interactive"),
    ({"text": {"body": "   "}}, "text"),
])
def test_empty_payload_never_reaches_bedrock_or_acks(message, kind):
    sent = []
    mod = _load(sent, FARMER)
    mod.query_bedrock = lambda *a, **k: (_ for _ in ()).throw(AssertionError("query_bedrock called"))
    _send(mod, message, kind)
    assert not any("received" in (m["text"] or "").lower() for m in sent)


def test_visitor_cap_refusal_keeps_pending_crop_confirm(monkeypatch):
    sent = []
    visitor = {"onboarding_complete": True, "dialect": "en", "user_type": "visitor", "crop": "Cotton"}
    mod = _load(sent, visitor)
    monkeypatch.setattr(mod.visitor_mod, "is_visitor_profile", lambda p: True)
    monkeypatch.setattr(mod, "is_approved_user", lambda *a, **k: False)
    monkeypatch.setattr(mod.visitor_mod, "try_consume_visitor_answer", lambda *a, **k: (False, "user"))
    monkeypatch.setattr(mod.visitor_mod, "emit_visitor_metric", lambda *a, **k: None)
    key = (f"USER#{PHONE}", mod._PENDING_CROP_CONFIRM_SK)
    mod.table._items[key] = {
        "PK": key[0], "SK": key[1], "bucket": "tmp-bucket", "key": "images/p/1.jpg",
        "profile_crop": "", "inferred_crop": "Cotton", "model_crop": "Cotton",
    }
    _send(mod, {"text": {"body": "Cotton"}}, "text")
    assert any(m["text"] == mod.visitor_mod.CAP_MSG for m in sent)
    assert key in mod.table._items
