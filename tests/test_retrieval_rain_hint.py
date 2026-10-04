"""A question about spraying after rain must send "rain" to the knowledge base, not only "spray".

Found 4 October 2026: "बारिश के बाद स्प्रे कब कर सकते हैं?" was answered 3 of 3 times when sent
as typed, and refused (NO_KB_ANSWER) 3 of 3 times on a Hindi profile. The Hindi path appends
English keyword hints for retrieval; "स्प्रे" had one ("spray"), "बारिश" had none, so the search
leaned toward spraying passages without the rain-timing context.

These tests call the real query_bedrock in both handlers and read what reaches Bedrock.
"""
import sys
import types

import pytest

from tests.test_advice_filter_wiring import processor  # noqa: F401  (fixture)
from tests.test_web_chat_dialect import _env, webchat  # noqa: F401  (fixtures)



@pytest.fixture(autouse=True)
def _restore_modules():
    """The borrowed fixtures stub common.* and import a module named "handler"; undo that."""
    saved = dict(sys.modules)
    yield
    for name in list(sys.modules):
        if name not in saved:
            del sys.modules[name]
    sys.modules.update(saved)


CASES = [
    ("hi", "बारिश के बाद स्प्रे कब कर सकते हैं?"),
    ("mr", "पावसानंतर फवारणी कधी करावी?"),
    ("te", "వర్షం తర్వాత స్ప్రే ఎప్పుడు చేయాలి?"),
]


def _capture():
    seen = {}

    def retrieve_and_generate(**kwargs):
        seen["text"] = kwargs["input"]["text"]
        return {"output": {"text": "ok"}, "citations": [], "sessionId": "s"}

    return seen, retrieve_and_generate


@pytest.mark.parametrize("dialect,question", CASES)
def test_processor_sends_rain_and_spray_hints(processor, dialect, question):  # noqa: F811
    seen, fn = _capture()
    processor.bedrock_agent.retrieve_and_generate = fn
    processor.query_bedrock(question, dialect)
    assert seen["text"].startswith(question)
    assert seen["text"].endswith("(rain spray)")


@pytest.mark.parametrize("dialect,question", CASES)
def test_web_chat_sends_rain_and_spray_hints(webchat, dialect, question):  # noqa: F811
    seen, fn = _capture()
    webchat.bedrock_agent = types.SimpleNamespace(retrieve_and_generate=fn)
    webchat.query_bedrock(question, dialect)
    assert seen["text"].startswith(question)
    assert seen["text"].endswith("(rain spray)")


def test_english_question_is_sent_as_typed(processor):  # noqa: F811
    seen, fn = _capture()
    processor.bedrock_agent.retrieve_and_generate = fn
    processor.query_bedrock("When can I spray after rain?", "en")
    assert seen["text"] == "When can I spray after rain?"
