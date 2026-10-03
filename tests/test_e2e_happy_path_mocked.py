import json
import os
import sys
import types
import importlib.util
from pathlib import Path


def _install_common_stubs(sent_messages):
    """
    Handlers import common-layer modules (WhatsApp + allowlist + helplines) that
    depend on AWS/requests. For this unit test we stub them so imports are stable
    and we can assert the end-to-end behavior.
    """
    layer = str(Path(__file__).resolve().parents[1] / "src" / "common-layer" / "python")
    if layer not in sys.path:
        sys.path.insert(0, layer)
    for name in list(sys.modules):
        if name == "common" or name.startswith("common."):
            sys.modules.pop(name, None)
    import importlib
    redact_mod = importlib.import_module("common.redact")
    nk_mod = importlib.import_module("common.nudge_keywords")
    visitor_mod = importlib.import_module("common.visitor")
    guardrail_reply_mod = importlib.import_module("common.guardrail_reply")
    advice_mod = importlib.import_module("common.advice_filter")
    source_line_mod = importlib.import_module("common.source_line")
    source_labels_mod = importlib.import_module("common.source_labels")
    advice_mod._cloudwatch = types.SimpleNamespace(put_metric_data=lambda **kw: None)

    common_pkg = types.ModuleType("common")
    common_pkg.__path__ = []
    sys.modules["common"] = common_pkg

    whatsapp = types.ModuleType("common.whatsapp")

    def send_whatsapp_message(phone_number: str, message: str, audio_url=None):
        sent_messages.append({"to": phone_number, "text": message, "audio_url": audio_url})
        return True

    def send_whatsapp_list(*_args, **_kwargs):
        return True

    def send_whatsapp_buttons(*_args, **_kwargs):
        return True

    whatsapp.send_whatsapp_message = send_whatsapp_message
    whatsapp.send_whatsapp_list = send_whatsapp_list
    whatsapp.send_whatsapp_buttons = send_whatsapp_buttons
    whatsapp.send_whatsapp_image = lambda *_a, **_k: True
    whatsapp.VOICE_RECEIVED_ACK = {"hi": "ACK"}
    sys.modules["common.whatsapp"] = whatsapp

    allowlist = types.ModuleType("common.allowlist")
    allowlist.is_approved_user = lambda *_args, **_kwargs: True
    allowlist.allowlist_expiry_hint = lambda *_args, **_kwargs: ""
    sys.modules["common.allowlist"] = allowlist

    helplines = types.ModuleType("common.district_helplines")
    helplines.maybe_append_helpline_footer = lambda text, *_args, **_kwargs: text
    sys.modules["common.district_helplines"] = helplines

    sys.modules["common.redact"] = redact_mod
    sys.modules["common.nudge_keywords"] = nk_mod
    sys.modules["common.visitor"] = visitor_mod
    sys.modules["common.guardrail_reply"] = guardrail_reply_mod
    sys.modules["common.advice_filter"] = advice_mod
    sys.modules["common.source_line"] = source_line_mod
    sys.modules["common.source_labels"] = source_labels_mod
    common_pkg.redact = redact_mod
    common_pkg.nudge_keywords = nk_mod
    common_pkg.whatsapp = whatsapp
    common_pkg.allowlist = allowlist
    common_pkg.district_helplines = helplines
    common_pkg.visitor = visitor_mod
    common_pkg.guardrail_reply = guardrail_reply_mod

    # Processor imports these at import time; stub to keep test lightweight.
    output = types.ModuleType("output")
    output.text_to_speech = lambda *_args, **_kwargs: None
    output.truncate_for_voice = lambda s, *_args, **_kwargs: s
    output.voice_truncation_prefix = ""
    sys.modules["output"] = output

    analyzer = types.ModuleType("analyzer")
    analyzer.process_image_message = lambda *_args, **_kwargs: "image-analysis"
    sys.modules["analyzer"] = analyzer


class _FakeDynamoTable:
    def __init__(self, profile):
        self._profile = profile
        self.put_items = []

    def get_item(self, Key):
        if Key.get("SK") == "PROFILE":
            return {"Item": dict(self._profile)}
        return {}

    def put_item(self, Item):
        self.put_items.append(Item)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def query(self, **_kwargs):
        # Used for rate limiting in webhook. Keep at 0.
        return {"Count": 0}


class _FakeSqs:
    def __init__(self):
        self.sent = []

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "mid-1"}


class _FakeBedrockAgent:
    class exceptions:
        class ValidationException(Exception):
            pass

    def retrieve_and_generate(self, **_kwargs):
        return {
            "output": {"text": "यह एक परीक्षण उत्तर है।"},
            "citations": [],
            "sessionId": "s-1",
        }


def test_webhook_to_processor_happy_path_mocked(monkeypatch):
    # Arrange environment for handler imports
    os.environ["TABLE_NAME"] = "tbl"
    os.environ["QUEUE_URL"] = "https://sqs.local/q"
    os.environ["VOICE_QUEUE_URL"] = "https://sqs.local/vq"
    os.environ["VERIFY_SIGNATURE"] = "false"  # avoid secrets/HMAC

    os.environ["KNOWLEDGE_BASE_ID"] = "kb"
    os.environ["GUARDRAIL_ID"] = ""
    os.environ["GUARDRAIL_VERSION"] = "1"

    repo_root = Path(__file__).resolve().parents[1]

    sent_messages = []
    _install_common_stubs(sent_messages)

    # Import handlers after stubs are installed (use unique module names)
    webhook_path = repo_root / "src" / "webhook" / "handler.py"
    webhook_spec = importlib.util.spec_from_file_location("webhook_handler", webhook_path)
    webhook = importlib.util.module_from_spec(webhook_spec)
    assert webhook_spec and webhook_spec.loader
    webhook_spec.loader.exec_module(webhook)

    # Patch webhook AWS deps
    fake_profile = {"onboarding_complete": True, "dialect": "hi", "district": "Latur", "crop": "Cotton"}
    webhook.table = _FakeDynamoTable(fake_profile)
    webhook.sqs = _FakeSqs()

    # Create a minimal WhatsApp webhook POST payload (text message)
    wamid = "wamid.TEST123"
    phone = "1555123456789"
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"display_phone_number": "x"},
                            "messages": [
                                {
                                    "id": wamid,
                                    "from": phone,
                                    "type": "text",
                                    "text": {"body": "कपास में कीट कैसे नियंत्रित करें?"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    event = {
        "httpMethod": "POST",
        "path": "/webhook",
        "headers": {},
        "body": json.dumps(payload),
    }

    # Act 1: webhook enqueues message to SQS
    resp = webhook.lambda_handler(event, None)
    assert resp["statusCode"] == 200
    assert webhook.sqs.sent, "Expected webhook to enqueue to SQS"

    msg_body = json.loads(webhook.sqs.sent[0]["MessageBody"])
    assert msg_body["wamid"] == wamid
    assert msg_body["from"] == phone
    assert msg_body["type"] == "text"

    processor_path = repo_root / "src" / "processor" / "handler.py"
    processor_spec = importlib.util.spec_from_file_location("processor_handler", processor_path)
    processor = importlib.util.module_from_spec(processor_spec)
    assert processor_spec and processor_spec.loader
    processor_spec.loader.exec_module(processor)

    # Patch processor AWS deps
    processor.table = _FakeDynamoTable(fake_profile)
    processor.bedrock_agent = _FakeBedrockAgent()

    # Act 2: processor handles the SQS record and "sends" a WhatsApp reply (stubbed)
    sqs_event = {"Records": [{"body": json.dumps(msg_body)}]}
    processor.lambda_handler(sqs_event, None)

    # Assert: outbound message was produced
    assert sent_messages, "Expected processor to send at least one WhatsApp message"
    assert any("परीक्षण उत्तर" in (m["text"] or "") for m in sent_messages)

