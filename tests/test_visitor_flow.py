"""The re:Invent visitor path, driven through the processor's lambda_handler.

The landing page (docs/try/) sends a visitor to WhatsApp with "Hi from re:Invent" typed in.
These tests walk what happens next, message by message, against a fake table and fake AWS
clients: welcome, sample question, own question, photo, daily limit, DELETE, start again.
"""
from __future__ import annotations

import ast
import base64
import importlib.util
import json
import re
import sys
import time
import types
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from tests import test_crop_override_confirmation_flow as flow

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PHONE = "4915112345678"
DAY = 24 * 60 * 60
ANSWER = "Hang yellow sticky traps and check the underside of the leaves every morning."


def _wamid(n: int, phone: str = PHONE) -> str:
    """A message ID shaped like WhatsApp's: base64 with the sender's number inside it."""
    serial = b"%020d" % n
    raw = (
        b"\x1c\x18" + bytes([len(phone)]) + phone.encode()
        + b"\x15\x02\x00\x12\x18" + bytes([len(serial)]) + serial + b"\x00"
    )
    return "wamid." + base64.b64encode(raw).decode()


class FakeTable:
    """The single DynamoDB table: enough of get/put/delete/query/update for the processor."""

    def __init__(self):
        self.items: dict[tuple[str, str], dict] = {}

    def get_item(self, Key, **_k):
        item = self.items.get((Key["PK"], Key["SK"]))
        return {"Item": dict(item)} if item else {}

    conditional_check_failed = None  # set to the boto3 exception class when the webhook is in play

    def put_item(self, Item, ConditionExpression=None, **_k):
        key = (Item["PK"], Item["SK"])
        if ConditionExpression and key in self.items and self.conditional_check_failed:
            raise self.conditional_check_failed(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}}, "PutItem"
            )
        self.items[key] = dict(Item)
        return {}

    def delete_item(self, Key, **_k):
        self.items.pop((Key["PK"], Key["SK"]), None)
        return {}

    def query(self, **kw):
        pk = kw["ExpressionAttributeValues"][":pk"]
        if kw.get("Select") == "COUNT":  # the webhook's hourly rate-limit count
            return {"Count": 0}
        return {"Items": [dict(v) for (p, _s), v in sorted(self.items.items()) if p == pk]}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, ConditionExpression=None, **_k):
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        key = (Key["PK"], Key["SK"])
        item = dict(self.items.get(key) or Key)
        if ConditionExpression and ":max" in values and item.get("count", 0) >= values[":max"]:
            raise ClientError({"Error": {"Code": "ConditionalCheckFailedException", "Message": "cap"}}, "UpdateItem")
        for name, value in re.findall(r"ADD\s+(#\w+)\s+(:\w+)", UpdateExpression):
            item[names[name]] = item.get(names[name], 0) + values[value]
        for name, value in re.findall(r"(#?\w+)\s*=\s*(:\w+)", UpdateExpression):
            item[names.get(name, name)] = values[value]
        self.items[key] = item
        return {}

    def rows(self, phone=PHONE):
        return {sk: item for (pk, sk), item in self.items.items() if pk == f"USER#{phone}"}

    def holding(self, phone=PHONE):
        """Every row whose key or content mentions the number."""
        return [key for key, item in self.items.items() if phone in json.dumps([key, item], default=str)]


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {"visitor-samples/crop-leaf.jpg": b"sample"}

    def get_object(self, Bucket, Key):
        return {"Body": types.SimpleNamespace(read=lambda: self.objects[Key])}

    def list_objects_v2(self, Bucket, Prefix, **_k):
        return {"Contents": [{"Key": k} for k in sorted(self.objects) if k.startswith(Prefix)]}

    def delete_objects(self, Bucket, Delete):
        for obj in Delete["Objects"]:
            self.objects.pop(obj["Key"], None)
        return {}


class Bot:
    """The processor with fake AWS around it, plus what it sent and asked."""

    def __init__(self, mod, sent):
        self.mod, self.sent = mod, sent
        self.table: FakeTable = mod.table
        self.s3: FakeS3 = mod.s3
        self.lists: list[dict] = []
        self.buttons: list[dict] = []
        self.bedrock_calls: list[dict] = []
        self.metrics: list[str] = []
        self._n = 0

    def texts(self):
        return [m["text"] for m in self.sent if m["text"]]

    def _deliver(self, kind, message, phone):
        self._n += 1
        body = {"wamid": f"wamid.test{self._n}", "from": phone, "type": kind, "message": message}
        self.mod.lambda_handler({"Records": [{"body": json.dumps(body)}]}, None)

    def text(self, body, phone=PHONE):
        self._deliver("text", {"from": phone, "type": "text", "text": {"body": body}}, phone)

    def pick(self, row_id, title="", phone=PHONE):
        reply = {"type": "list_reply", "list_reply": {"id": row_id, "title": title}}
        self._deliver("interactive", {"from": phone, "type": "interactive", "interactive": reply}, phone)

    def tap(self, title, phone=PHONE):
        reply = {"type": "button_reply", "button_reply": {"id": "btn_0", "title": title}}
        self._deliver("interactive", {"from": phone, "type": "interactive", "interactive": reply}, phone)

    def photo(self, phone=PHONE):
        self._deliver("image", {"from": phone, "type": "image", "image": {"id": "media-1"}}, phone)


@pytest.fixture(autouse=True)
def _restore_modules():
    saved_modules, saved_path = dict(sys.modules), list(sys.path)
    yield
    for name in list(sys.modules):
        if name not in saved_modules:
            del sys.modules[name]
    sys.modules.update(saved_modules)
    sys.path[:] = saved_path


@pytest.fixture
def bot(monkeypatch):
    for key, value in {
        "TABLE_NAME": "tbl",
        "TEMP_AUDIO_BUCKET": "tmp-bucket",
        "KNOWLEDGE_BASE_ID": "kb",
        "GUARDRAIL_ID": "",
        "GUARDRAIL_VERSION": "1",
        "AWS_DEFAULT_REGION": "us-east-1",
        "VISITOR_TTL_DAYS": "7",
        "VISITOR_DAILY_PER_USER_CAP": "10",
        "VISITOR_DAILY_GLOBAL_CAP": "300",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LOG_TEXT_PREVIEW", raising=False)
    monkeypatch.delenv("LAST_IMAGE_OVERRIDE_ENABLED", raising=False)
    # Lambda runs in UTC. save_message() takes its expiry from datetime.utcnow().timestamp(),
    # which is the real epoch only when the local zone is UTC.
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()

    sent: list[dict] = []
    flow._install_common_stubs(sent)
    s3 = FakeS3()

    analyzer = types.ModuleType("analyzer")

    def process_image_message(message, profile):
        key = f"images/{profile['phone_number']}/1790000000.jpg"
        s3.objects[key] = b"jpg"
        return {"text": "PHOTO ADVICE", "s3": {"bucket": "tmp-bucket", "key": key}}

    analyzer.process_image_message = process_image_message
    analyzer.diagnose_with_confirmed_crop = lambda *a, **k: "SAMPLE PHOTO ADVICE"
    analyzer.analyze_crop_image = lambda *a, **k: {"recommendations": "ADVICE"}
    sys.modules["analyzer"] = analyzer

    processor_dir = str(SRC / "processor")
    if processor_dir not in sys.path:
        sys.path.insert(0, processor_dir)
    spec = importlib.util.spec_from_file_location("processor_handler_visitor_flow", SRC / "processor" / "handler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.table = FakeTable()
    mod.s3 = s3
    out = Bot(mod, sent)
    mod.cloudwatch = types.SimpleNamespace(
        put_metric_data=lambda **kw: out.metrics.append(kw["MetricData"][0]["MetricName"])
    )
    mod.is_approved_user = lambda *_a, **_k: False  # a visitor is never on the allowlist

    def retrieve_and_generate(**kwargs):
        out.bedrock_calls.append(kwargs)
        return {"output": {"text": ANSWER}, "citations": [], "sessionId": "bedrock-issued-session"}

    mod.bedrock_agent = types.SimpleNamespace(
        exceptions=types.SimpleNamespace(ValidationException=type("ValidationException", (Exception,), {})),
        retrieve_and_generate=retrieve_and_generate,
    )
    mod.send_whatsapp_list = lambda phone, content, button_text, sections: out.lists.append(
        {"to": phone, "content": content, "button_text": button_text, "sections": sections}
    ) or True
    mod._send_whatsapp_buttons = lambda phone, body, buttons: out.buttons.append(
        {"to": phone, "content": body, "buttons": buttons}
    ) or True
    yield out
    monkeypatch.undo()
    time.tzset()


# ---------------------------------------------------------------------------
# First message
# ---------------------------------------------------------------------------

class TestFirstMessage:
    def test_hi_from_reinvent_gets_the_welcome_list(self, bot):
        """The message the landing page types for the visitor.

        This used to raise UnboundLocalError: a local import of send_whatsapp_list further
        down lambda_handler made the name local to the whole function.
        """
        bot.text("Hi from re:Invent")

        assert len(bot.lists) == 1
        welcome = bot.lists[0]
        assert welcome["to"] == PHONE
        assert welcome["content"] == bot.mod.visitor_mod.VISITOR_WELCOME
        assert bot.metrics == ["visitor_started"]
        assert bot.bedrock_calls == []  # the welcome costs no model call
        assert bot.texts() == []        # and no second message

    def test_welcome_creates_a_visitor_profile_that_expires_in_7_days(self, bot):
        bot.text("Hi from re:Invent")
        profile = bot.table.rows()["PROFILE"]
        assert profile["demo_tier"] == "visitor"
        assert profile["dialect"] == "en"
        assert profile["onboarding_complete"] is True
        assert profile["consent"] is False
        assert abs(profile["ttl"] - (time.time() + 7 * DAY)) < 60

    @pytest.mark.parametrize("first", ["Hi from re:Invent", "hello from reinvent", "RE:INVENT booth"])
    def test_trigger_variants(self, bot, first):
        bot.text(first)
        assert len(bot.lists) == 1 and bot.table.rows()["PROFILE"]["demo_tier"] == "visitor"

    def test_welcome_offers_six_rows_and_no_way_into_farmer_onboarding(self, bot):
        bot.text("Hi from re:Invent")
        rows = bot.lists[0]["sections"][0]["rows"]
        assert [r["id"] for r in rows] == [
            "vq_whitefly", "vq_yellowing", "vq_spray", "vq_bollworm", "vq_irrigation", "vq_sample_photo",
        ]
        shown = json.dumps(bot.lists[0]).lower()
        assert "farmer onboarding" not in shown and "continue as farmer" not in shown

    def test_welcome_fits_whatsapp_list_limits(self, bot):
        bot.text("Hi from re:Invent")
        welcome = bot.lists[0]
        assert len(welcome["content"]) <= 1024
        assert len(welcome["button_text"]) <= 20
        rows = [r for s in welcome["sections"] for r in s["rows"]]
        assert len(rows) <= 10
        for section in welcome["sections"]:
            assert len(section["title"]) <= 24
        for row in rows:
            assert 0 < len(row["title"]) <= 24, row
            assert 0 < len(row["description"]) <= 72, row
            assert len(row["id"]) <= 200
            for field in ("title", "description"):
                assert row[field] == row[field].strip(), row  # no stray space at either end
        assert len({r["id"] for r in rows}) == len(rows)
        assert len({r["title"] for r in rows}) == len(rows)

    def test_row_titles_are_whole_words_and_descriptions_are_the_questions(self, bot):
        bot.text("Hi from re:Invent")
        rows = bot.lists[0]["sections"][0]["rows"]
        assert [(r["title"], r["description"]) for r in rows] == [
            ("Whitefly on cotton", "How do I control whitefly on cotton?"),
            ("Yellow wheat leaves", "Why are my wheat leaves yellowing?"),
            ("Spraying after rain", "When is it safe to spray after rain?"),
            ("Bollworm on cotton", "How do I manage bollworm on cotton?"),
            ("Irrigating soybean", "How often should I irrigate soybean?"),
            ("Photo diagnosis", "Show me a photo diagnosis (sample crop image)"),
        ]

    def test_the_same_greeting_again_shows_the_welcome_again(self, bot):
        """Pressing the landing page button a second time sends "Hi from re:Invent" again."""
        bot.text("Hi from re:Invent")
        expiry = bot.table.rows()["PROFILE"]["ttl"]
        bot.text("Hi from re:Invent")

        assert len(bot.lists) == 2 and bot.lists[1] == bot.lists[0]
        assert bot.bedrock_calls == []                      # no knowledge base search for a greeting
        assert bot.texts() == []                            # and no "farming questions only" reply
        assert not [k for k in bot.table.items if k[0].startswith("COUNTER#")]  # none of the day's answers used
        assert bot.table.rows()["PROFILE"]["ttl"] == expiry  # the 7 days are not restarted
        assert bot.metrics == ["visitor_started"]           # still one visitor

    def test_a_longer_question_that_mentions_reinvent_is_answered(self, bot):
        bot.text("Hi from re:Invent")
        question = "At re:Invent I heard about whitefly traps for cotton. Do they work?"
        bot.text(question)
        assert len(bot.lists) == 1
        assert [c["input"]["text"] for c in bot.bedrock_calls] == [question]

    def test_a_number_with_a_farmer_profile_keeps_it(self, bot):
        """Open decision: someone who signed up as a farmer earlier does not get the visitor welcome."""
        farmer = {
            "PK": f"USER#{PHONE}", "SK": "PROFILE", "phone_number": PHONE, "dialect": "en",
            "onboarding_complete": True, "demo_tier": "public", "location": "Latur", "crop": "Cotton",
        }
        bot.table.put_item(Item=farmer)
        bot.text("Hi from re:Invent")
        assert bot.lists == []
        assert bot.table.rows()["PROFILE"] == farmer
        assert len(bot.bedrock_calls) == 1

    def test_welcome_wording(self, bot):
        welcome = bot.mod.visitor_mod.VISITOR_WELCOME
        assert "—" not in welcome and "–" not in welcome  # no dashes used as punctuation
        assert "demo prototype" in welcome and "no farmer cohort yet" in welcome
        assert "crop photo" in welcome
        assert "Send DELETE anytime to erase your demo data." in welcome


# ---------------------------------------------------------------------------
# Questions and photos
# ---------------------------------------------------------------------------

class TestQuestions:
    def test_sample_question_from_the_list_is_answered(self, bot):
        bot.text("Hi from re:Invent")
        bot.pick("vq_whitefly", "Whitefly on cotton")

        assert len(bot.bedrock_calls) == 1
        assert bot.bedrock_calls[0]["input"]["text"] == "How do I control whitefly on cotton?"
        assert bot.texts()[0] == "✓ Question received. Preparing answer..."
        assert ANSWER in bot.texts()[-1]
        assert bot.metrics == ["visitor_started", "visitor_question_answered"]

    @pytest.mark.parametrize("row_id,question", [
        ("vq_whitefly", "How do I control whitefly on cotton?"),
        ("vq_yellowing", "Why are my wheat leaves yellowing?"),
        ("vq_spray", "When is it safe to spray after rain?"),
        ("vq_bollworm", "How do I manage bollworm on cotton?"),
        ("vq_irrigation", "How often should I irrigate soybean?"),
    ])
    def test_every_list_row_sends_its_full_question_to_the_model(self, bot, row_id, question):
        bot.text("Hi from re:Invent")
        bot.pick(row_id)
        assert [c["input"]["text"] for c in bot.bedrock_calls] == [question]

    def test_a_typed_row_title_counts_as_that_sample_question(self, bot):
        bot.text("Hi from re:Invent")
        bot.text("whitefly on cotton")
        assert bot.bedrock_calls[0]["input"]["text"] == "How do I control whitefly on cotton?"

    @pytest.mark.parametrize("own", ["How", "Why", "W", "When is it", "How do I grow maize?"])
    def test_a_visitors_own_words_are_not_swapped_for_a_sample_question(self, bot, own):
        bot.text("Hi from re:Invent")
        bot.text(own)
        assert bot.bedrock_calls[0]["input"]["text"] == own

    def test_own_question_is_answered_in_one_bedrock_call_without_the_number(self, bot, capsys):
        bot.text("Hi from re:Invent")
        capsys.readouterr()
        bot.text("Why are my soybean leaves turning yellow?")

        assert len(bot.bedrock_calls) == 1
        call = bot.bedrock_calls[0]
        assert "sessionId" not in call
        assert PHONE not in json.dumps(call, default=str)
        logs = capsys.readouterr().out
        assert PHONE not in logs and PHONE[:10] not in logs and PHONE[3:] not in logs
        assert "soybean" not in logs and ANSWER not in logs

    def test_conversation_rows_expire_in_7_days(self, bot):
        bot.text("Hi from re:Invent")
        bot.text("Why are my soybean leaves turning yellow?")
        messages = [item for sk, item in bot.table.rows().items() if sk.startswith("MSG#")]
        assert len(messages) == 1
        assert ANSWER in messages[0]["response"]
        assert abs(messages[0]["ttl"] - (time.time() + 7 * DAY)) < 60

    def test_typing_continue_as_farmer_is_just_a_question_now(self, bot):
        bot.text("Hi from re:Invent")
        bot.text("Continue as farmer")
        assert bot.table.rows()["PROFILE"]["demo_tier"] == "visitor"
        assert len(bot.lists) == 1       # no farmer language list
        assert len(bot.bedrock_calls) == 1

    def test_uploaded_photo_is_analyzed_and_stored_under_the_number(self, bot):
        bot.text("Hi from re:Invent")
        bot.photo()
        ack, reply = bot.texts()
        assert ack == "✓ Photo received. Analyzing..."
        assert reply.startswith("PHOTO ADVICE") and "KVK" in reply  # advice, then the referral line
        assert f"images/{PHONE}/1790000000.jpg" in bot.s3.objects
        assert "visitor_photo_answered" in bot.metrics

    def test_sample_photo_option_runs_the_photo_path(self, bot):
        bot.text("Hi from re:Invent")
        bot.pick("vq_sample_photo", "Photo diagnosis")
        assert bot.texts()[-1].startswith("SAMPLE PHOTO ADVICE")
        assert "visitor_photo_answered" in bot.metrics

    def test_eleventh_answer_of_the_day_is_refused_without_a_model_call(self, bot, monkeypatch):
        bot.text("Hi from re:Invent")
        for n in range(10):
            bot.text(f"Question {n} about cotton?")
        assert len(bot.bedrock_calls) == 10
        bot.text("One more question about cotton?")
        assert len(bot.bedrock_calls) == 10
        assert bot.texts()[-1] == bot.mod.visitor_mod.CAP_MSG
        assert "visitor_cap_hit_user" in bot.metrics

    def test_help_does_not_count_against_the_limit(self, bot):
        bot.text("Hi from re:Invent")
        bot.text("HELP")
        assert bot.bedrock_calls == []
        counters = [k for k in bot.table.items if k[0].startswith("COUNTER#")]
        assert counters == []


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

class TestDelete:
    def _used_demo(self, bot):
        bot.text("Hi from re:Invent")
        bot.text("Why are my soybean leaves turning yellow?")
        bot.photo()

    def test_delete_leaves_no_row_and_no_photo_with_the_number(self, bot):
        self._used_demo(bot)
        assert bot.table.holding() and any(PHONE in k for k in bot.s3.objects)

        bot.text("DELETE")

        assert bot.table.holding() == []
        assert not any(PHONE in k for k in bot.s3.objects)
        assert "visitor-samples/crop-leaf.jpg" in bot.s3.objects  # the shared sample stays
        assert bot.table.items.get(("COUNTER#visitor-answers", time.strftime("DAY#%Y-%m-%d", time.gmtime())))
        assert "visitor_delete" in bot.metrics

    def test_delete_also_removes_counters_from_the_two_days_before(self, bot):
        self._used_demo(bot)
        for days_back in (1, 2):
            day = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days_back * DAY))
            bot.table.put_item(Item={"PK": f"COUNTER#visitor#{PHONE}", "SK": f"DAY#{day}", "count": 3})
        bot.text("DELETE")
        assert bot.table.holding() == []

    def test_visitor_is_told_how_to_start_again(self, bot):
        self._used_demo(bot)
        bot.text("DELETE")
        confirm = bot.texts()[-1]
        assert confirm == bot.mod.visitor_mod.VISITOR_DELETE_CONFIRM_MSG
        assert "has been deleted" in confirm and confirm.endswith("To start again, send: Hi from re:Invent")
        assert "voice" not in confirm.lower()  # visitors cannot send voice notes

    @pytest.mark.parametrize("command", ["DELETE", "delete", " Delete ", "DELETE MY DATA"])
    def test_delete_spellings(self, bot, command):
        bot.text("Hi from re:Invent")
        bot.text(command)
        assert bot.table.holding() == []

    def test_start_again_after_delete(self, bot):
        self._used_demo(bot)
        bot.text("DELETE")
        bot.text("Hi from re:Invent")
        assert len(bot.lists) == 2
        assert bot.table.rows()["PROFILE"]["demo_tier"] == "visitor"

    def test_farmer_keeps_the_general_confirmation(self, bot):
        bot.table.put_item(Item={
            "PK": f"USER#{PHONE}", "SK": "PROFILE", "phone_number": PHONE, "dialect": "en",
            "onboarding_complete": True, "demo_tier": "public", "location": "Latur", "crop": "Cotton",
        })
        bot.text("DELETE")
        assert bot.texts()[-1] == bot.mod.visitor_mod.DELETE_CONFIRM_MSG
        assert bot.table.holding() == []

    def test_delete_from_a_number_with_no_data_still_answers(self, bot):
        bot.text("DELETE")
        assert bot.texts() == [bot.mod.visitor_mod.DELETE_CONFIRM_MSG]
        assert bot.table.holding() == []


# ---------------------------------------------------------------------------
# Webhook and processor together: what is left in the table after DELETE
# ---------------------------------------------------------------------------

class TestWholePipelineAfterDelete:
    """Incoming messages pass the webhook first; it writes its own rows before the processor runs."""

    @pytest.fixture
    def pipeline(self, bot, monkeypatch):
        monkeypatch.setenv("QUEUE_URL", "https://sqs.local/live")
        monkeypatch.setenv("QUEUE_URL_BETA", "")
        monkeypatch.setenv("VERIFY_SIGNATURE", "false")
        monkeypatch.setenv("BETA_PHONES", "")
        monkeypatch.setenv("VOICE_QUEUE_URL", "https://sqs.local/voice")
        sys.modules["common.whatsapp"].VOICE_RECEIVED_ACK = {"en": "ack", "hi": "ack"}
        spec = importlib.util.spec_from_file_location("webhook_handler_visitor_flow", SRC / "webhook" / "handler.py")
        wh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wh)

        bot.table.conditional_check_failed = wh.dynamodb.meta.client.exceptions.ConditionalCheckFailedException
        wh.table = bot.table
        wh.is_approved_user = lambda *_a, **_k: False
        wh.send_whatsapp_message = lambda phone, text, *a, **k: bot.sent.append(
            {"to": phone, "text": text, "audio_url": None}
        ) or True
        queued: list[str] = []
        wh.sqs = types.SimpleNamespace(send_message=lambda **kw: queued.append(kw["MessageBody"]) or {})
        counter = {"n": 0}

        def send(message: dict, n: int | None = None) -> None:
            """Deliver one WhatsApp message through the webhook, then run what it queued."""
            if n is None:
                counter["n"] += 1
                n = counter["n"]
            message = {"id": _wamid(n), "from": PHONE, "timestamp": "1790000000", **message}
            payload = {"entry": [{"changes": [{"value": {"messages": [message], "metadata": {}}}]}]}
            event = {"httpMethod": "POST", "path": "/webhook", "headers": {}, "body": json.dumps(payload)}
            assert wh.lambda_handler(event, None)["statusCode"] == 200
            while queued:
                bot.mod.lambda_handler({"Records": [{"body": queued.pop(0)}]}, None)

        return send

    def test_nothing_in_the_table_holds_the_number_after_delete(self, bot, pipeline):
        pipeline({"type": "text", "text": {"body": "Hi from re:Invent"}})
        pipeline({"type": "text", "text": {"body": "Why are my soybean leaves turning yellow?"}})
        pipeline({"type": "image", "image": {"id": "media-1"}})
        pipeline({"type": "audio", "audio": {"id": "media-2"}})   # refused: voice is off for visitors
        pipeline({"type": "text", "text": {"body": "done"}})      # a nudge keyword, handled by the detector
        assert len(bot.lists) == 1 and len(bot.bedrock_calls) == 1
        assert any("Voice is not enabled in the public demo" in t for t in bot.texts())
        assert bot.table.holding()

        pipeline({"type": "text", "text": {"body": "DELETE"}})

        assert bot.texts()[-1] == bot.mod.visitor_mod.VISITOR_DELETE_CONFIRM_MSG
        assert not any(PHONE in k for k in bot.s3.objects)
        assert bot.table.holding() == []
        # What is left: dedup rows keyed by a hash, and the day's global counter.
        left = sorted({pk.split("#")[0] for pk, _sk in bot.table.items})
        assert left == ["COUNTER", "WAMID"]
        encoded = base64.b64encode(PHONE.encode()).decode().rstrip("=")[:-2]
        for key, item in bot.table.items.items():
            blob = json.dumps([key, item], default=str)
            assert "wamid." not in blob and encoded not in blob

    def test_a_message_delivered_twice_is_processed_once(self, bot, pipeline):
        pipeline({"type": "text", "text": {"body": "Hi from re:Invent"}})
        question = {"type": "text", "text": {"body": "Why are my soybean leaves turning yellow?"}}
        pipeline(dict(question), n=50)
        pipeline(dict(question), n=50)  # Meta delivers the same message ID again
        assert len(bot.bedrock_calls) == 1
        pipeline(dict(question), n=51)  # the same words as a new message are a new question
        assert len(bot.bedrock_calls) == 2


# ---------------------------------------------------------------------------
# A first message without the phrase starts the farmer sign-up
# ---------------------------------------------------------------------------

class TestUnfinishedFarmerSignUp:
    def test_a_first_message_without_the_phrase_starts_sign_up_with_an_expiry(self, bot):
        bot.text("Hello")
        assert len(bot.lists) == 1 and bot.lists[0]["button_text"] == "Select Language"
        profile = bot.table.rows()["PROFILE"]
        assert profile["onboarding_complete"] is False
        assert abs(profile["ttl"] - (time.time() + 7 * DAY)) < 60

    def test_a_language_tap_as_first_message_also_gets_the_expiry(self, bot):
        bot.pick("en", "English")
        profile = bot.table.rows()["PROFILE"]
        assert profile["onboarding_state"] == "location"
        assert abs(profile["ttl"] - (time.time() + 7 * DAY)) < 60

    def test_the_expiry_stays_while_the_sign_up_is_in_progress(self, bot):
        bot.text("Hello")
        bot.pick("en", "English")
        bot.tap("Latur")
        profile = bot.table.rows()["PROFILE"]
        assert profile["onboarding_state"] == "crop"
        assert "ttl" in profile

    def test_a_finished_sign_up_has_no_expiry(self, bot):
        bot.text("Hello")
        bot.pick("en", "English")
        bot.tap("Latur")
        bot.tap("Cotton")
        bot.tap("Yes ✅")
        profile = bot.table.rows()["PROFILE"]
        assert profile["onboarding_complete"] is True
        assert profile["demo_tier"] == "public"
        assert "ttl" not in profile

    def test_after_delete_a_plain_message_starts_sign_up_that_expires(self, bot):
        bot.text("Hi from re:Invent")
        bot.text("DELETE")
        bot.text("thanks")
        profile = bot.table.rows()["PROFILE"]
        assert profile.get("demo_tier") == "public" and profile["onboarding_complete"] is False
        assert abs(profile["ttl"] - (time.time() + 7 * DAY)) < 60


# ---------------------------------------------------------------------------
# The bug class behind the broken welcome
# ---------------------------------------------------------------------------

def _own_nodes(fn):
    stack = list(ast.iter_child_nodes(fn))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _reads_before_local_import(source: str) -> list[str]:
    found = []
    for fn in ast.walk(ast.parse(source)):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        imported: dict[str, int] = {}
        for node in _own_nodes(fn):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = (alias.asname or alias.name).split(".")[0]
                    imported[name] = min(imported.get(name, node.lineno), node.lineno)
        for node in _own_nodes(fn):
            if (
                isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and node.id in imported and node.lineno < imported[node.id]
            ):
                found.append(f"{fn.name}(): {node.id} read on line {node.lineno}, imported on line {imported[node.id]}")
    return found


def test_the_scan_finds_the_original_bug():
    source = (
        "from wa import send_list\n"
        "def handler(kind):\n"
        "    if kind == 'visitor':\n"
        "        send_list('welcome')\n"
        "    else:\n"
        "        from wa import send_list\n"
        "        send_list('language')\n"
    )
    assert _reads_before_local_import(source) == ["handler(): send_list read on line 4, imported on line 6"]


def test_no_function_reads_a_name_before_importing_it_locally():
    """An import inside a function makes the name local to all of it, earlier lines included."""
    problems = []
    for py in sorted(SRC.rglob("*.py")):
        for problem in _reads_before_local_import(py.read_text(encoding="utf-8")):
            problems.append(f"{py.relative_to(ROOT)}: {problem}")
    assert problems == []
