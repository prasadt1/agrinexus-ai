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
