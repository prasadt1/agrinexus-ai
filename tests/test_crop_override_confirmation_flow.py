import json
import os
import sys
import types
import importlib.util
from pathlib import Path


class _FakeDynamoTable:
    def __init__(self, profile):
        self._items = {}
        self._profile = dict(profile)
        self.put_items = []

    def get_item(self, Key):
        pk = Key.get("PK")
        sk = Key.get("SK")
        if pk and sk and sk == "PROFILE":
            return {"Item": dict(self._profile)}
        if pk and sk and (pk, sk) in self._items:
            return {"Item": dict(self._items[(pk, sk)])}
        return {}

    def put_item(self, Item, **_kwargs):
        self.put_items.append(Item)
        pk = Item.get("PK")
        sk = Item.get("SK")
        if pk and sk:
            self._items[(pk, sk)] = dict(Item)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def delete_item(self, Key, **_kwargs):
        pk = Key.get("PK")
        sk = Key.get("SK")
        self._items.pop((pk, sk), None)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


def _install_common_stubs(sent_messages):
    common_pkg = types.ModuleType("common")
    sys.modules["common"] = common_pkg

    whatsapp = types.ModuleType("common.whatsapp")

    def send_whatsapp_message(phone_number: str, message: str, audio_url=None):
        sent_messages.append({"to": phone_number, "text": message, "audio_url": audio_url})
        return True

    def send_whatsapp_buttons(*_args, **_kwargs):
        return True

    def send_whatsapp_list(*_args, **_kwargs):
        return True

    whatsapp.send_whatsapp_message = send_whatsapp_message
    whatsapp.send_whatsapp_buttons = send_whatsapp_buttons
    whatsapp.send_whatsapp_list = send_whatsapp_list
    sys.modules["common.whatsapp"] = whatsapp

    allowlist = types.ModuleType("common.allowlist")
    allowlist.is_approved_user = lambda *_args, **_kwargs: True
    allowlist.allowlist_expiry_hint = lambda *_args, **_kwargs: ""
    sys.modules["common.allowlist"] = allowlist

    helplines = types.ModuleType("common.district_helplines")
    helplines.maybe_append_helpline_footer = lambda text, *_args, **_kwargs: text
    sys.modules["common.district_helplines"] = helplines

    output = types.ModuleType("output")
    output.text_to_speech = lambda *_args, **_kwargs: None
    output.truncate_for_voice = lambda s, *_args, **_kwargs: s
    output.voice_truncation_prefix = ""
    sys.modules["output"] = output


class _FakeS3:
    def __init__(self, body_bytes: bytes):
        self._bytes = body_bytes
        self.get_calls = []

    def get_object(self, Bucket, Key):
        self.get_calls.append({"Bucket": Bucket, "Key": Key})

        class _Body:
            def __init__(self, b):
                self._b = b

            def read(self):
                return self._b

        return {"Body": _Body(self._bytes)}


def test_crop_confirm_then_reprocess_on_yes(monkeypatch):
    os.environ["TABLE_NAME"] = "tbl"
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"
    os.environ.setdefault("KNOWLEDGE_BASE_ID", "kb")
    os.environ.setdefault("GUARDRAIL_ID", "")
    os.environ.setdefault("GUARDRAIL_VERSION", "1")

    repo_root = Path(__file__).resolve().parents[1]

    sent = []
    _install_common_stubs(sent)

    # Stub analyzer with "needs confirm" on first image, and a final analysis on reprocess.
    analyzer = types.ModuleType("analyzer")

    def process_image_message(_message, _profile):
        return {
            "text": "CONFIRM_CROP",
            "pending_crop_confirm": {
                "bucket": "tmp-bucket",
                "key": "images/phone/ts.jpg",
                "profile_crop": "Wheat",
                "inferred_crop": "Cotton",
            },
        }

    def analyze_crop_image(_image_bytes, _dialect, crop="cotton", district=None):
        assert crop == "Cotton"
        return {
            "recommendations": "FINAL_COTTON_ANALYSIS",
            "diagnosis": "ok",
            "severity": "low",
            "confidence": "high",
        }

    analyzer.process_image_message = process_image_message
    analyzer.analyze_crop_image = analyze_crop_image
    sys.modules["analyzer"] = analyzer

    handler_path = repo_root / "src" / "processor" / "handler.py"
    spec = importlib.util.spec_from_file_location("processor_handler_crop_confirm", handler_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    fake_profile = {
        "onboarding_complete": True,
        "dialect": "en",
        "district": "Latur",
        "crop": "Wheat",
        "location": "Latur",
    }
    mod.table = _FakeDynamoTable(fake_profile)
    mod.s3 = _FakeS3(b"img-bytes")

    # 1) image message triggers confirmation
    phone = "1555123000000"
    msg_body = {
        "wamid": "wamid.1",
        "from": phone,
        "type": "image",
        "message": {"image": {"id": "mid"}},
    }
    mod.lambda_handler({"Records": [{"body": json.dumps(msg_body)}]}, None)
    assert any(m["text"] == "CONFIRM_CROP" for m in sent)

    # 2) user replies YES -> should reprocess from S3 with inferred crop
    sent.clear()
    msg_body2 = {
        "wamid": "wamid.2",
        "from": phone,
        "type": "text",
        "message": {"text": {"body": "YES"}},
    }
    mod.lambda_handler({"Records": [{"body": json.dumps(msg_body2)}]}, None)

    assert any("FINAL_COTTON_ANALYSIS" in (m["text"] or "") for m in sent)


def test_crop_confirm_hindi_yes_phrase_reprocesses(monkeypatch):
    os.environ["TABLE_NAME"] = "tbl"
    os.environ["TEMP_AUDIO_BUCKET"] = "tmp-bucket"
    os.environ.setdefault("KNOWLEDGE_BASE_ID", "kb")
    os.environ.setdefault("GUARDRAIL_ID", "")
    os.environ.setdefault("GUARDRAIL_VERSION", "1")

    repo_root = Path(__file__).resolve().parents[1]

    sent = []
    _install_common_stubs(sent)

    analyzer = types.ModuleType("analyzer")

    def process_image_message(_message, _profile):
        return {
            "text": "CONFIRM_CROP",
            "pending_crop_confirm": {
                "bucket": "tmp-bucket",
                "key": "images/phone/ts.jpg",
                "profile_crop": "Wheat",
                "inferred_crop": "Cotton",
            },
        }

    def analyze_crop_image(_image_bytes, _dialect, crop="cotton", district=None):
        assert crop == "Cotton"
        return {"recommendations": "FINAL_COTTON_ANALYSIS", "diagnosis": "ok", "severity": "low", "confidence": "high"}

    analyzer.process_image_message = process_image_message
    analyzer.analyze_crop_image = analyze_crop_image
    sys.modules["analyzer"] = analyzer

    handler_path = repo_root / "src" / "processor" / "handler.py"
    spec = importlib.util.spec_from_file_location("processor_handler_crop_confirm_hi", handler_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    fake_profile = {"onboarding_complete": True, "dialect": "hi", "district": "Latur", "crop": "Wheat", "location": "Latur"}
    mod.table = _FakeDynamoTable(fake_profile)
    mod.s3 = _FakeS3(b"img-bytes")

    phone = "1555123000000"
    msg_body = {"wamid": "wamid.1", "from": phone, "type": "image", "message": {"image": {"id": "mid"}}}
    mod.lambda_handler({"Records": [{"body": json.dumps(msg_body)}]}, None)
    assert any(m["text"] == "CONFIRM_CROP" for m in sent)

    sent.clear()
    # Hindi phrase, not exact token.
    msg_body2 = {"wamid": "wamid.2", "from": phone, "type": "text", "message": {"text": {"body": "हाँ वही है"}}}
    mod.lambda_handler({"Records": [{"body": json.dumps(msg_body2)}]}, None)
    assert any("FINAL_COTTON_ANALYSIS" in (m["text"] or "") for m in sent)

