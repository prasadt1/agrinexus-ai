"""Every farmer-facing advice path runs through the advice output filter."""
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

from tests import test_crop_override_confirmation_flow as flow

REPO = Path(__file__).resolve().parents[1]

CHEM = (
    "Remove affected bolls. Spray profenofos 50% EC at 2 ml per litre of water. "
    "Install pheromone traps."
)


def _assert_filtered(text, kind):
    assert "profenofos" not in text and "2 ml" not in text and "50% EC" not in text
    assert "Remove affected bolls." in text and "Install pheromone traps." in text
    wording = "automated reading of your photo" if kind == "photo" else "automated answer"
    assert wording in text
    assert "contact your nearest KVK" in text


@pytest.fixture()
def processor(monkeypatch):
    for k, v in {
        "TABLE_NAME": "tbl",
        "TEMP_AUDIO_BUCKET": "tmp-bucket",
        "KNOWLEDGE_BASE_ID": "kb",
        "GUARDRAIL_ID": "",
        "GUARDRAIL_VERSION": "1",
    }.items():
        monkeypatch.setenv(k, v)
    sent, buttons = [], []
    flow._install_common_stubs(sent)
    analyzer = types.ModuleType("analyzer")
    analyzer.process_image_message = lambda *_a, **_k: CHEM
    analyzer.analyze_crop_image = lambda *_a, **_k: {"recommendations": CHEM}
    analyzer.diagnose_with_confirmed_crop = lambda *_a, **_k: CHEM
    sys.modules["analyzer"] = analyzer

    spec = importlib.util.spec_from_file_location("processor_handler_advice_wiring", REPO / "src" / "processor" / "handler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    profile = {"onboarding_complete": True, "dialect": "en", "district": "Pune", "crop": "Cotton", "location": "Pune"}
    mod.table = flow._FakeDynamoTable(profile)
    mod.s3 = flow._FakeS3(b"img")
    mod._send_whatsapp_buttons = lambda phone, body, btns: buttons.append(body) or True
    mod.bedrock_agent = types.SimpleNamespace(
        exceptions=types.SimpleNamespace(ValidationException=Exception),
        retrieve_and_generate=lambda **_k: {"output": {"text": CHEM}, "citations": [], "sessionId": "s"},
    )
    mod._sent, mod._buttons, mod._analyzer, mod._profile = sent, buttons, analyzer, profile
    return mod


def _run(mod, mtype, message, **extra):
    body = {"wamid": "wamid.x", "from": "1555123000000", "type": mtype, "message": message, **extra}
    mod.lambda_handler({"Records": [{"body": json.dumps(body)}]}, None)


def _last_reply(mod):
    return [m["text"] for m in mod._sent if m["text"]][-1]


def test_whatsapp_text_answer_is_filtered(processor):
    _run(processor, "text", {"text": {"body": "Which spray for bollworm?"}})
    _assert_filtered(_last_reply(processor), "answer")


MR_REFUSAL = (
    "मला या विषयाची माहिती माझ्या ज्ञानकोशात नाही. कृपया तुमच्या जवळच्या कृषी विज्ञान केंद्र (KVK) "
    "किंवा कृषी विस्तार अधिकाऱ्यांशी संपर्क साधा."
)


def test_whatsapp_marathi_refusal_gets_no_source_line_or_second_referral(processor):
    processor._profile["dialect"] = "mr"
    processor.bedrock_agent.retrieve_and_generate = lambda **_k: {
        "output": {"text": MR_REFUSAL}, "citations": [], "sessionId": "s"
    }
    _run(processor, "text", {"text": {"body": "कापसावरील पांढऱ्या माशीसाठी कोणते कीटकनाशक फवारावे?"}})
    reply = _last_reply(processor)
    assert reply.strip() == MR_REFUSAL


def test_web_chat_marathi_refusal_gets_no_referral(webchat):
    webchat.query_bedrock = lambda *_a, **_k: {"text": MR_REFUSAL, "citations": []}
    reply = _post(webchat, {"message": "कापसावरील पांढऱ्या माशीसाठी कोणते कीटकनाशक फवारावे?", "language": "mr"})
    assert reply.strip() == MR_REFUSAL


def test_whatsapp_voice_answer_is_filtered_before_speech(processor):
    spoken = []
    processor.text_to_speech = lambda text, *_a, **_k: spoken.append(text) or None
    _run(processor, "text", {"text": {"body": "Which spray for bollworm?"}, "_source": "voice"})
    _assert_filtered(_last_reply(processor), "answer")
    assert spoken and "profenofos" not in spoken[0] and "2 ml" not in spoken[0]


def test_whatsapp_photo_answer_is_filtered(processor):
    _run(processor, "image", {"image": {"id": "m"}})
    _assert_filtered(_last_reply(processor), "photo")


def test_assumed_crop_photo_answer_is_filtered(processor):
    processor._analyzer.process_image_message = lambda *_a, **_k: {
        "text": CHEM,
        "pending_crop_confirm": {"bucket": "b", "key": "k", "assumed": True},
    }
    _run(processor, "image", {"image": {"id": "m"}})
    _assert_filtered(_last_reply(processor), "photo")


def test_crop_question_is_filtered_without_a_referral(processor):
    processor._analyzer.process_image_message = lambda *_a, **_k: {
        "text": "Larvae seen; spray profenofos 2 ml per litre. Which crop is this?",
        "pending_crop_confirm": {"bucket": "b", "key": "k"},
        "buttons": ["Cotton", "Sugarcane"],
    }
    _run(processor, "image", {"image": {"id": "m"}})
    body = processor._buttons[-1]
    assert "profenofos" not in body and "KVK" not in body


def test_confirmed_crop_rerun_and_visitor_sample_are_filtered(processor):
    _assert_filtered(processor._diagnose_image_with_confirmed_crop(b"img", "en", "Cotton", district="Pune"), "photo")


def test_last_image_override_is_filtered(processor):
    processor._get_last_image_pointer = lambda _n: {"bucket": "b", "key": "k"}
    processor._delete_last_image_pointer = lambda _n: None
    processor._get_pending_crop_confirm = lambda _n: None
    _run(processor, "text", {"text": {"body": "Cotton"}})
    _assert_filtered(_last_reply(processor), "photo")


def _kb_prompt(kwargs):
    cfg = kwargs["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"]
    return cfg["generationConfiguration"]["promptTemplate"]["textPromptTemplate"]


def test_whatsapp_knowledge_base_prompt_forbids_products(processor):
    seen = {}

    def _rag(**kwargs):
        seen.update(kwargs)
        return {"output": {"text": "ok"}, "citations": [], "sessionId": "s"}

    processor.bedrock_agent.retrieve_and_generate = _rag
    processor.query_bedrock("Which spray for whitefly?", "mr")
    prompt = _kb_prompt(seen)
    assert "Never name a pesticide" in prompt and "even if the Context contains one" in prompt
    assert "local KVK" in prompt


@pytest.fixture()
def webchat(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "t")
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "kb")
    monkeypatch.setenv("GUARDRAIL_ID", "")
    mock_boto3 = types.ModuleType("boto3")
    mock_boto3.resource = lambda *_a, **_k: types.SimpleNamespace(Table=lambda _n: types.SimpleNamespace())
    mock_boto3.client = lambda *_a, **_k: types.SimpleNamespace(put_metric_data=lambda **_k: None)
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)
    layer = str(REPO / "src" / "common-layer" / "python")
    for name in list(sys.modules):
        if name == "common" or name.startswith("common."):
            sys.modules.pop(name, None)
    sys.path.insert(0, layer)
    spec = importlib.util.spec_from_file_location("webchat_advice_wiring", REPO / "src" / "web-chat" / "handler.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path.remove(layer)
    allowed = {"allowed": True, "remaining": 4, "reset_at": 0, "current_count": 1}
    mod._peek_rate_limit = lambda _i: allowed
    mod.check_rate_limit = lambda _i: allowed
    return mod


def _post(mod, body):
    resp = mod.lambda_handler({"httpMethod": "POST", "body": json.dumps(body), "requestContext": {}}, None)
    return json.loads(resp["body"])["reply"]


def test_web_chat_text_answer_is_filtered(webchat):
    webchat.query_bedrock = lambda *_a, **_k: {"text": CHEM, "citations": []}
    _assert_filtered(_post(webchat, {"message": "Which spray for bollworm?", "language": "en"}), "answer")


def test_web_chat_prompts_forbid_products(webchat):
    seen = {}

    def _rag(**kwargs):
        seen.update(kwargs)
        return {"output": {"text": "ok"}, "citations": []}

    webchat.bedrock_agent = types.SimpleNamespace(retrieve_and_generate=_rag)
    webchat.query_bedrock("Which spray for whitefly?", "en")
    assert "Never name a pesticide" in _kb_prompt(seen)

    def _invoke(**kwargs):
        seen["vision"] = json.loads(kwargs["body"])["messages"][0]["content"][1]["text"]
        return {"body": types.SimpleNamespace(read=lambda: json.dumps({"content": [{"text": "ok"}]}).encode())}

    webchat.bedrock_runtime = types.SimpleNamespace(invoke_model=_invoke)
    webchat._decode_image_payload = lambda _raw: ("image/jpeg", "x", b"x")
    webchat.analyze_image("x", "mr")
    assert "Never name a pesticide" in seen["vision"] and "local KVK" in seen["vision"]


WHITEFLY_MR = "कापसावरील पांढऱ्या माशीसाठी कोणते कीटकनाशक फवारावे?"


def _retrieval_text(seen):
    return seen["input"]["text"]


def test_whatsapp_marathi_whitefly_question_gets_english_retrieval_hints(processor):
    seen = {}

    def _rag(**kwargs):
        seen.update(kwargs)
        return {"output": {"text": "ok"}, "citations": [], "sessionId": "s"}

    processor.bedrock_agent.retrieve_and_generate = _rag
    processor.query_bedrock(WHITEFLY_MR, "mr")
    q = _retrieval_text(seen)
    for hint in ("cotton", "whitefly", "spray"):
        assert hint in q
    assert "pesticide" not in q and "pest management" not in q


def test_web_chat_marathi_whitefly_question_gets_english_retrieval_hints(webchat):
    seen = {}

    def _rag(**kwargs):
        seen.update(kwargs)
        return {"output": {"text": "ok"}, "citations": []}

    webchat.bedrock_agent = types.SimpleNamespace(retrieve_and_generate=_rag)
    webchat.query_bedrock(WHITEFLY_MR, "mr")
    q = _retrieval_text(seen)
    for hint in ("cotton", "whitefly", "spray"):
        assert hint in q
    assert "pest management" not in q


def test_web_chat_photo_answer_is_filtered(webchat):
    webchat.analyze_image = lambda *_a, **_k: CHEM
    webchat._decode_image_payload = lambda _raw: ("image/jpeg", "x", b"x")
    webchat.collect_images = lambda _b: ["data:image/jpeg;base64,eA=="]
    _assert_filtered(_post(webchat, {"message": "", "language": "en", "image": "x"}), "photo")
