"""The pesticide-policy reply replaces a refused answer, so it never carries that answer's sources."""
import json

from common.advice_filter import pesticide_policy
from common.guardrail_reply import LOCALIZED_NO_ANSWER
from tests.test_ops_hardening import _chat_event, webchat  # noqa: F401
from tests.test_processor_loop_guards import FARMER, _load, _restore_modules, _send  # noqa: F401

QUESTION = "Which pesticide should I spray for whitefly?"
CITED_REFUSAL = {
    "text": LOCALIZED_NO_ANSWER["en"],
    "kb_no_answer": True,
    "citations": [{"retrievedReferences": [{"location": {"s3Location": {"uri": "s3://kb/cotton-pest-guide.pdf"}}}]}],
}


def test_whatsapp_policy_reply_has_no_source_line_but_keeps_referral():
    sent = []
    mod = _load(sent, FARMER)
    mod.query_bedrock = lambda *a, **k: dict(CITED_REFUSAL)
    _send(mod, {"text": {"body": QUESTION}}, "text")
    reply = sent[-1]["text"]
    assert reply.startswith(pesticide_policy("en"))
    assert "cotton-pest-guide" not in reply
    assert "Source:" not in reply
    assert "KVK" in reply


def test_web_chat_policy_reply_returns_no_citations(webchat, monkeypatch):
    monkeypatch.setattr(webchat, "query_bedrock", lambda *a, **k: dict(CITED_REFUSAL))
    resp = webchat.lambda_handler(_chat_event("9.9.9.9", message=QUESTION), None)
    body = json.loads(resp["body"])
    assert body["reply"].startswith(pesticide_policy("en"))
    assert body["citations"] == []
