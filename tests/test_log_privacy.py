"""What the landing page promises about visitor data, pinned to the code.

docs/try/index.html tells a re:Invent visitor that records expire after 7 days, that
DELETE erases them, and that the technical logs hold no message text and no phone number.
Logs are kept 90 days, so anything a log line carries outlives both promises.
"""
from __future__ import annotations

import ast
import base64
import importlib
import importlib.util
import io
import json
import logging
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LAYER = str(SRC / "common-layer" / "python")
PROCESSOR = str(SRC / "processor")

PHONE = "4915112345678"
QUESTION = "My cotton leaves are curling near the well, what should I do?"
REPLY = "Check the underside of the leaves for whitefly and ask your local agriculture office."


def _wamid(phone: str = PHONE, msg_hex: str = "3EB0C5A4E1F2A9B7C6D5") -> str:
    """A message ID shaped like WhatsApp's: base64 with the phone number inside it."""
    raw = (
        b"\x1c\x18" + bytes([len(phone)]) + phone.encode()
        + b"\x15\x02\x00\x12\x18" + bytes([len(msg_hex)]) + msg_hex.encode() + b"\x00"
    )
    return "wamid." + base64.b64encode(raw).decode()


def _assert_no_personal_data(out: str, *texts: str, phone: str = PHONE, wamid: str | None = None) -> None:
    """The log text holds no number (plain or base64), no message ID and none of the texts."""
    assert phone not in out
    assert phone[3:] not in out
    for text in texts:
        assert text not in out
        assert text[:20] not in out
    if wamid:
        assert wamid not in out
        assert wamid.split(".", 1)[1] not in out
    for token in re.findall(r"[A-Za-z0-9+/]{16,}={0,2}", out):
        try:
            decoded = base64.b64decode(token + "=" * (-len(token) % 4))
        except Exception:
            continue
        assert phone.encode() not in decoded, f"{token} decodes to the phone number"


@pytest.fixture(autouse=True)
def _real_common_modules(monkeypatch):
    """Other test files leave stubbed `common.*` modules behind; these tests need the real ones."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("LOG_TEXT_PREVIEW", raising=False)
    saved_modules = dict(sys.modules)
    saved_path = list(sys.path)
    for name in list(sys.modules):
        if name == "common" or name.startswith("common."):
            del sys.modules[name]
    for p in (PROCESSOR, LAYER):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    yield
    for name in list(sys.modules):
        if name not in saved_modules:
            del sys.modules[name]
    sys.modules.update(saved_modules)
    sys.path[:] = saved_path


# ---------------------------------------------------------------------------
# The helpers
# ---------------------------------------------------------------------------

class TestRedactHelpers:
    def test_a_message_id_really_contains_the_number(self):
        payload = _wamid().split(".", 1)[1]
        assert PHONE.encode() in base64.b64decode(payload)

    def test_text_for_log_gives_the_length_only(self):
        from common.redact import text_for_log

        assert text_for_log(QUESTION) == f"{len(QUESTION)} characters"
        assert text_for_log("") == "0 characters"
        assert text_for_log(None) == "0 characters"
        assert text_for_log(12345) == "5 characters"

    @pytest.mark.parametrize("value", ["false", "0", "", "yes", "1"])
    def test_only_the_word_true_switches_the_preview_on(self, monkeypatch, value):
        from common.redact import text_for_log

        monkeypatch.setenv("LOG_TEXT_PREVIEW", value)
        assert text_for_log(QUESTION) == f"{len(QUESTION)} characters"

    def test_preview_for_a_debugging_session(self, monkeypatch):
        from common.redact import text_for_log

        monkeypatch.setenv("LOG_TEXT_PREVIEW", "true")
        out = text_for_log(QUESTION, limit=10)
        assert QUESTION[:10] in out and QUESTION[:11] not in out
        assert f"{len(QUESTION)} characters" in out

    def test_template_never_switches_the_preview_on(self):
        assert "LOG_TEXT_PREVIEW" not in (ROOT / "template.yaml").read_text(encoding="utf-8")

    def test_message_ref_is_stable_and_one_way(self):
        from common.redact import message_ref

        wamid = _wamid()
        ref = message_ref(wamid)
        assert ref == message_ref(wamid)
        assert re.fullmatch(r"msg-[0-9a-f]{12}", ref)
        assert ref != message_ref(_wamid(msg_hex="3EB0C5A4E1F2A9B7C6D6"))
        _assert_no_personal_data(ref, wamid=wamid)

    def test_message_ref_without_an_id(self):
        from common.redact import message_ref

        assert message_ref(None) == "msg-none"
        assert message_ref("") == "msg-none"

    def test_scrub_numbers_masks_long_digit_runs_only(self):
        from common.redact import scrub_numbers

        assert scrub_numbers(f"to {PHONE} failed (#131030)") == "to 491*** failed (#131030)"
        assert scrub_numbers("code 100, 6 digits 123456 stay") == "code 100, 6 digits 123456 stay"
        assert scrub_numbers(None) == ""


# ---------------------------------------------------------------------------
# Outgoing messages (common/whatsapp.py)
# ---------------------------------------------------------------------------

class _SendResponse:
    status_code = 200
    text = "{}"

    def __init__(self, wamid):
        self._wamid = wamid

    def json(self):
        return {
            "messaging_product": "whatsapp",
            "contacts": [{"input": PHONE, "wa_id": PHONE}],
            "messages": [{"id": self._wamid}],
        }


class TestOutgoingMessageLogs:
    @pytest.fixture
    def wa(self, monkeypatch):
        import common.whatsapp as wa

        self.wamid = _wamid(msg_hex="3EB0AAAA1111BBBB2222")
        monkeypatch.setattr(wa, "get_whatsapp_credentials", lambda: ("tok", "pnid"))
        monkeypatch.setattr(wa.requests, "post", lambda *a, **k: _SendResponse(self.wamid))
        return wa

    def _check(self, capsys, wa, *texts):
        out = capsys.readouterr().out
        _assert_no_personal_data(out, *texts, wamid=self.wamid)
        assert "491***" in out
        from common.redact import message_ref
        assert message_ref(self.wamid) in out
        return out

    def test_text_message(self, wa, capsys):
        assert wa.send_whatsapp_message(PHONE, REPLY) is True
        out = self._check(capsys, wa, REPLY)
        assert f"{len(REPLY)} characters" in out

    def test_voice_message_does_not_log_the_audio_url(self, wa, capsys):
        url = f"https://bucket.s3.amazonaws.com/voice-output/{PHONE}/1790000000.mp3?X-Amz-Signature=abc"
        assert wa.send_whatsapp_message(PHONE, "", audio_url=url) is True
        out = self._check(capsys, wa)
        assert "voice-output" not in out and "X-Amz-Signature" not in out

    def test_image_does_not_log_the_presigned_link(self, wa, capsys):
        url = "https://bucket.s3.amazonaws.com/visitor-samples/crop-leaf.jpg?X-Amz-Signature=abc"
        assert wa.send_whatsapp_image(PHONE, url, "Sample crop photo.") is True
        out = self._check(capsys, wa)
        assert "visitor-samples" not in out and "X-Amz-Signature" not in out

    def test_buttons(self, wa, capsys):
        assert wa.send_whatsapp_buttons(PHONE, REPLY, [{"id": "a", "title": "A"}]) is True
        self._check(capsys, wa, REPLY)

    def test_list(self, wa, capsys):
        sections = [{"title": "Try", "rows": [{"id": "q1", "title": "Whitefly"}]}]
        assert wa.send_whatsapp_list(PHONE, REPLY, "Sample questions", sections) is True
        self._check(capsys, wa, REPLY)

    def test_template(self, wa, capsys):
        assert wa.send_whatsapp_template(PHONE, "weather_nudge", "en") is True
        self._check(capsys, wa)

    def test_failed_send_masks_a_number_in_metas_error_text(self, wa, capsys, monkeypatch):
        class _Refused:
            status_code = 400
            text = json.dumps({"error": {
                "message": f"(#131030) Recipient phone number {PHONE} not in allowed list",
                "code": 131030, "fbtrace_id": "AbC123",
            }})

        monkeypatch.setattr(wa.requests, "post", lambda *a, **k: _Refused())
        assert wa.send_whatsapp_message(PHONE, REPLY) is False
        assert wa.send_whatsapp_buttons(PHONE, REPLY, [{"id": "a", "title": "A"}]) is False
        assert wa.send_whatsapp_list(PHONE, REPLY, "Pick", [{"title": "T", "rows": []}]) is False
        assert wa.send_whatsapp_template(PHONE, "weather_nudge", "en") is False
        assert wa.send_whatsapp_image(PHONE, "https://example.test/a.jpg", "c") is False
        out = capsys.readouterr().out
        _assert_no_personal_data(out, REPLY)
        assert out.count("131030") == 10  # the error code stays readable, twice per body
        assert "not in allowed list" in out


# ---------------------------------------------------------------------------
# Incoming messages (webhook)
# ---------------------------------------------------------------------------

class _WebhookTable:
    def __init__(self, wh):
        self.items = {}
        self._exc = wh.dynamodb.meta.client.exceptions.ConditionalCheckFailedException

    def put_item(self, Item, ConditionExpression=None):
        key = (Item["PK"], Item["SK"])
        if ConditionExpression and key in self.items:
            raise self._exc({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
        self.items[key] = Item
        return {}

    def delete_item(self, Key, **_k):
        self.items.pop((Key["PK"], Key["SK"]), None)
        return {}

    def query(self, **_k):
        return {"Count": 0, "Items": []}

    def get_item(self, **_k):
        return {}


class _Sqs:
    def __init__(self):
        self.sent = []

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "m"}


class TestWebhookLogsAndDedupRow:
    @pytest.fixture
    def webhook(self, monkeypatch):
        monkeypatch.setenv("QUEUE_URL", "https://sqs.local/live")
        monkeypatch.setenv("QUEUE_URL_BETA", "")
        monkeypatch.setenv("TABLE_NAME", "tbl")
        monkeypatch.setenv("VERIFY_SIGNATURE", "false")
        monkeypatch.setenv("BETA_PHONES", "")
        monkeypatch.setenv("VOICE_QUEUE_URL", "https://sqs.local/voice")
        from src.webhook import handler as wh

        importlib.reload(wh)
        monkeypatch.setattr(wh, "check_rate_limit", lambda *_a, **_k: True)
        monkeypatch.setattr(wh, "send_whatsapp_message", lambda *_a, **_k: None)
        self.table, self.sqs = _WebhookTable(wh), _Sqs()
        monkeypatch.setattr(wh, "table", self.table)
        monkeypatch.setattr(wh, "sqs", self.sqs)
        return wh

    @staticmethod
    def _event(wamid, body=QUESTION):
        message = {"id": wamid, "from": PHONE, "type": "text", "text": {"body": body}}
        payload = {"entry": [{"changes": [{"value": {"messages": [message]}}]}]}
        return {"httpMethod": "POST", "path": "/webhook", "headers": {}, "body": json.dumps(payload)}

    def test_log_lines_hold_no_number_no_message_id_no_text(self, webhook, caplog):
        from common.redact import message_ref

        wamid = _wamid()
        with caplog.at_level(logging.INFO):
            assert webhook.lambda_handler(self._event(wamid), None)["statusCode"] == 200
            # Meta delivers the same message again: the duplicate path logs too.
            assert webhook.lambda_handler(self._event(wamid), None)["statusCode"] == 200
        assert len(self.sqs.sent) == 1
        _assert_no_personal_data(caplog.text, QUESTION, wamid=wamid)
        assert message_ref(wamid) in caplog.text
        assert "491***" in caplog.text

    def test_rate_limited_message_is_logged_without_its_id(self, webhook, caplog, monkeypatch):
        monkeypatch.setattr(webhook, "check_rate_limit", lambda *_a, **_k: False)
        monkeypatch.setattr(webhook, "get_user_dialect", lambda *_a, **_k: "en")
        wamid = _wamid()
        with caplog.at_level(logging.INFO):
            webhook.lambda_handler(self._event(wamid), None)
        assert self.sqs.sent == []
        _assert_no_personal_data(caplog.text, QUESTION, wamid=wamid)

    def test_dedup_row_holds_no_number(self, webhook):
        wamid = _wamid()
        webhook.lambda_handler(self._event(wamid), None)
        dedup = [item for (pk, sk), item in self.table.items.items() if sk == "DEDUP"]
        assert len(dedup) == 1
        row = dedup[0]
        assert re.fullmatch(r"WAMID#[0-9a-f]{64}", row["PK"])
        assert set(row) == {"PK", "SK", "processed_at", "ttl"}
        _assert_no_personal_data(json.dumps(row), wamid=wamid)

    def test_dedup_row_expires_after_a_day(self, webhook):
        import time

        webhook.lambda_handler(self._event(_wamid()), None)
        row = next(item for (pk, sk), item in self.table.items.items() if sk == "DEDUP")
        assert abs(row["ttl"] - (time.time() + 24 * 3600)) < 60

    def test_message_row_for_the_detector_expires_within_the_visitor_promise(self, webhook):
        import time

        webhook.lambda_handler(self._event(_wamid()), None)
        row = next(item for (pk, sk), item in self.table.items.items() if sk.startswith("MSG#"))
        assert row["PK"] == f"USER#{PHONE}"  # under the user's key, so DELETE removes it
        assert row["ttl"] - time.time() <= 7 * 24 * 3600 + 60


# ---------------------------------------------------------------------------
# Reply detector, voice, speech output, photo analysis
# ---------------------------------------------------------------------------

def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestWorkerLogs:
    def test_detector_logs_the_length_of_an_incoming_text(self, monkeypatch, capsys):
        monkeypatch.setenv("TABLE_NAME", "tbl")
        det = _load("nudge_detector_log_privacy", SRC / "nudge" / "detector.py")
        monkeypatch.setattr(det, "get_active_nudges", lambda phone: [])
        det._handle_reply(f"USER#{PHONE}", PHONE, "MSG#2026-10-03T05:00:00", QUESTION)
        out = capsys.readouterr().out
        _assert_no_personal_data(out, QUESTION)
        assert f"{len(QUESTION)} characters" in out

    def test_voice_transcript_is_not_logged(self, monkeypatch, capsys):
        monkeypatch.setenv("TABLE_NAME", "tbl")
        monkeypatch.setenv("TEMP_AUDIO_BUCKET", "tmp-bucket")
        monkeypatch.setenv("QUEUE_URL", "https://sqs.local/live")
        voice = _load("voice_processor_log_privacy", SRC / "voice" / "processor.py")

        transcript = {
            "results": {
                "transcripts": [{"transcript": QUESTION}],
                "items": [{"alternatives": [{"confidence": "0.93", "content": "cotton"}]}],
            }
        }

        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(voice.urllib.request, "urlopen", lambda req: _Resp(json.dumps(transcript).encode()))
        monkeypatch.setattr(voice, "s3", types.SimpleNamespace(delete_object=lambda **k: {}))
        monkeypatch.setattr(voice, "transcribe", types.SimpleNamespace(delete_transcription_job=lambda **k: {}))
        job = {"TranscriptionJob": {"Transcript": {"TranscriptFileUri": "https://transcribe.local/t.json"}}}
        result = voice._finalize_transcription(job, "job-1", f"voice/{PHONE}/1.ogg")
        assert result["success"] and result["text"] == QUESTION

        sent = []
        monkeypatch.setattr(voice, "table", types.SimpleNamespace(get_item=lambda **k: {"Item": {"dialect": "en"}}))
        monkeypatch.setattr(voice, "process_voice_note", lambda message, profile: result)
        monkeypatch.setattr(voice, "sqs", types.SimpleNamespace(send_message=lambda **k: sent.append(k)))
        wamid = _wamid()
        body = {"wamid": wamid, "from": PHONE, "message": {"timestamp": "1790000000", "audio": {"id": "a1"}}}
        voice.lambda_handler({"Records": [{"body": json.dumps(body)}]}, None)
        assert len(sent) == 1 and QUESTION in sent[0]["MessageBody"]

        out = capsys.readouterr().out
        _assert_no_personal_data(out, QUESTION, wamid=wamid)
        assert f"{len(QUESTION)} characters" in out

    def test_speech_output_logs_neither_the_text_nor_the_number(self, monkeypatch, capsys):
        monkeypatch.setenv("TEMP_AUDIO_BUCKET", "tmp-bucket")
        out_mod = _load("processor_output_log_privacy", SRC / "processor" / "output.py")
        monkeypatch.setattr(out_mod, "TEMP_BUCKET", "tmp-bucket", raising=False)
        monkeypatch.setattr(out_mod, "polly", types.SimpleNamespace(
            synthesize_speech=lambda **k: {"AudioStream": io.BytesIO(b"mp3")}
        ))
        url = f"https://tmp-bucket.s3.amazonaws.com/voice-output/{PHONE}/1.mp3?X-Amz-Signature=abc"
        monkeypatch.setattr(out_mod, "s3", types.SimpleNamespace(
            put_object=lambda **k: {}, generate_presigned_url=lambda *a, **k: url,
        ))
        assert out_mod.text_to_speech(REPLY, "en", PHONE) == url
        out = capsys.readouterr().out
        _assert_no_personal_data(out, REPLY)
        assert "X-Amz-Signature" not in out
        assert "voice-output/491***/" in out

    def test_photo_analysis_logs_neither_the_advice_nor_the_number(self, monkeypatch, capsys):
        monkeypatch.setenv("TEMP_AUDIO_BUCKET", "tmp-bucket")
        monkeypatch.setenv("VISION_RELEVANCE_GATE_ENABLED", "false")
        monkeypatch.setenv("VISION_QUALITY_GATE_ENABLED", "false")
        from src.processor import analyzer as a

        importlib.reload(a)
        monkeypatch.setattr(a, "TEMP_BUCKET", "tmp-bucket", raising=False)
        monkeypatch.setattr(a, "download_whatsapp_image", lambda _mid: b"\xff\xd8fakejpg")
        keys = []
        monkeypatch.setattr(a, "s3", types.SimpleNamespace(put_object=lambda **k: keys.append(k["Key"]) or {}))
        advice = "Remove the two pink-striped caterpillars by hand and burn the damaged bolls today."
        vision = {
            "recommendations": advice,
            "diagnosis": "Two pink-striped caterpillars feeding inside a boll.",
            "severity": "high",
            "confidence_text": "high - pest and crop clear",
            "photo_kind": "crop",
            "inferred_crop": "cotton",
            "crop_confidence": "high",
            "is_real_crop_photo": True,
            "visible_problem": True,
        }
        monkeypatch.setattr(a, "analyze_crop_image", lambda *_a, **_k: vision)
        out = a.process_image_message(
            {"image": {"id": "m"}, "from": PHONE},
            {"dialect": "en", "crop": "Cotton", "district": "Latur", "phone_number": PHONE},
        )
        assert out.get("text")
        assert keys and keys[0].startswith(f"images/{PHONE}/")  # the stored key itself is unchanged
        logs = capsys.readouterr().out
        _assert_no_personal_data(logs, advice, out["text"])
        assert "images/491***/" in logs
        assert "Vision analysis complete" in logs  # the diagnostic line is still written


# ---------------------------------------------------------------------------
# Guard for log lines added later
# ---------------------------------------------------------------------------

LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
SAFE_WRAPPERS = {"redact_phone", "text_for_log", "message_ref", "len", "bool", "type", "_sent_message_ids"}
SENSITIVE_NAMES = {
    "wamid", "phone", "phone_number", "from_number", "to_number",
    "text", "early_text", "message", "message_text", "body", "body_text", "payload",
    "transcript", "transcript_text", "query", "question", "reply", "reply_text", "response_text",
    "final_msg", "audio_url", "s3_key", "event", "record", "session_id", "rag_session",
}
SENSITIVE_KEYS = {"text", "body", "from", "wamid", "message", "transcript", "phone_number", "response"}


def _is_log_call(node: ast.Call) -> bool:
    f = node.func
    if isinstance(f, ast.Name) and f.id == "print":
        return True
    return (
        isinstance(f, ast.Attribute) and f.attr in LOG_METHODS
        and isinstance(f.value, ast.Name) and f.value.id in {"logger", "logging", "log"}
    )


def _sensitive_uses(expr: ast.AST) -> list[str]:
    """Sensitive names or keys an expression reads outside redact_phone/text_for_log/message_ref.

    `event.get('path')` and `record['eventName']` read one harmless field and pass;
    `event`, `text[:50]`, `result['text']` and `body.get('from')` do not.
    """
    found: list[str] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in SAFE_WRAPPERS:
                return
            if (
                isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                if node.args[0].value in SENSITIVE_KEYS:
                    found.append(f".get({node.args[0].value!r})")
                    return
                if isinstance(node.func.value, ast.Name):
                    return  # one named, harmless field of a dict
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if node.slice.value in SENSITIVE_KEYS:
                found.append(f"[{node.slice.value!r}]")
                return
            if isinstance(node.value, ast.Name):
                return  # one named, harmless field of a dict
        if isinstance(node, ast.Name) and node.id in SENSITIVE_NAMES:
            found.append(node.id)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(expr)
    return found


def _log_line_violations() -> list[str]:
    violations = []
    for py in sorted(SRC.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _is_log_call(node)):
                continue
            for arg in list(node.args) + [k.value for k in node.keywords]:
                if isinstance(arg, ast.JoinedStr):
                    parts = [v.value for v in arg.values if isinstance(v, ast.FormattedValue)]
                elif isinstance(arg, ast.Constant):
                    parts = []
                else:
                    parts = [arg]
                for part in parts:
                    for use in _sensitive_uses(part):
                        violations.append(f"{py.relative_to(ROOT)}:{node.lineno} logs {use}")
    return violations


def test_guard_recognizes_a_leaking_log_line():
    leaks = [
        'print(f"Sending to {phone_number}: {message[:50]}")',
        'logger.info(f"Message - wamid: {wamid}")',
        "print(f\"Queued: {result['text']}\")",
        'print("Checking keywords in: " + text)',
        'print(f"Body: {body.get(\'text\')}")',
    ]
    for line in leaks:
        call = ast.parse(line).body[0].value
        args = call.args[0]
        parts = [v.value for v in args.values if isinstance(v, ast.FormattedValue)] if isinstance(args, ast.JoinedStr) else [args]
        assert any(_sensitive_uses(p) for p in parts), line
    safe = ast.parse(
        'print(f"To {redact_phone(phone_number)}: {text_for_log(message)} {message_ref(wamid)} {len(text)}")'
    ).body[0].value.args[0]
    assert not any(_sensitive_uses(v.value) for v in safe.values if isinstance(v, ast.FormattedValue))


def test_no_log_line_interpolates_a_number_a_message_id_or_message_text():
    assert _log_line_violations() == []
