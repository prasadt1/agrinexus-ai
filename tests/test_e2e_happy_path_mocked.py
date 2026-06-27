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
    common_pkg = types.ModuleType("common")
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
    whatsapp.VOICE_RECEIVED_ACK = {"hi": "ACK"}
    sys.modules["common.whatsapp"] = whatsapp

    allowlist = types.ModuleType("common.allowlist")
    allowlist.is_approved_user = lambda *_args, **_kwargs: True
    allowlist.allowlist_expiry_hint = lambda *_args, **_kwargs: ""
    sys.modules["common.allowlist"] = allowlist

    quota = types.ModuleType("common.quota")
    quota.check_feature_quota = lambda *_args, **_kwargs: True
    sys.modules["common.quota"] = quota

    helplines = types.ModuleType("common.district_helplines")
    helplines.maybe_append_helpline_footer = lambda text, *_args, **_kwargs: text
    sys.modules["common.district_helplines"] = helplines

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

