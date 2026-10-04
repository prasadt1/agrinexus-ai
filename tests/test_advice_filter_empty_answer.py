"""A pesticide-product answer the filter empties out becomes the policy reply, not a bare refusal.

Live voice reply of 4 Oct 2026 to "सफेद मक्खी के लिए कौन सी दवा छिड़कें?": after the filter removed
every chemical step, the farmer got only "मैं कीटनाशक के नाम या मात्रा नहीं बता सकता।" plus a
source line and the footer.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))

from common import advice_filter as af  # noqa: E402

PRODUCT_Q = {
    "hi": "सफेद मक्खी के लिए कौन सी दवा छिड़कें?",
    "mr": "पांढऱ्या माशीसाठी कोणते कीटकनाशक फवारावे?",
    "te": "తెల్లదోమకు ఏ పురుగుమందు స్ప్రే చేయాలి?",
    "en": "Which pesticide should I spray for whitefly?",
}
EMPTIED = {
    "hi": "मैं कीटनाशक के नाम या मात्रा नहीं बता सकता। इमिडाक्लोप्रिड 0.5 मिली प्रति लीटर छिड़कें। यह तब करें जब 8 वयस्क प्रति पत्ती दिखें।",
    "mr": "मी कीटकनाशकांची नावे सांगू शकत नाही. इमिडाक्लोप्रिड 0.5 मिली प्रति लिटर फवारा.",
    "te": "నేను పురుగుమందుల పేర్లు చెప్పలేను. ఇమిడాక్లోప్రిడ్ 0.5 మి.లీ. లీటరుకు పిచికారీ చేయండి.",
    "en": "I can't give pesticide names or doses. Spray imidacloprid 17.8 SL at 0.5 ml per litre. Do this when you see 8 adults per leaf.",
}


@pytest.fixture(autouse=True)
def _no_cloudwatch(monkeypatch):
    monkeypatch.setattr(af, "_cloudwatch", types.SimpleNamespace(put_metric_data=lambda **kw: None))


@pytest.mark.parametrize("dialect", ["hi", "mr", "te", "en"])
def test_emptied_product_answer_becomes_the_policy_reply_without_a_source(dialect):
    out = af.filter_advice(EMPTIED[dialect], dialect, "whatsapp_voice", kind="answer", district="Latur",
                           question=PRODUCT_Q[dialect], source_line="Source: niphm-cotton-advisory-2022.pdf")
    assert out.startswith(af.pesticide_policy(dialect))
    assert "niphm" not in out
    assert "KVK" in out


def test_live_hindi_reply_offers_a_photo_diagnosis():
    out = af.filter_advice(EMPTIED["hi"], "hi", "whatsapp_voice", kind="answer", question=PRODUCT_Q["hi"])
    assert "फोटो भेजें" in out and "इमिडाक्लोप्रिड" not in out


def test_answer_with_advice_left_is_unchanged():
    text = "मैं कीटनाशक के नाम या मात्रा नहीं बता सकता। पीले चिपचिपे ट्रैप लगाएं। इमिडाक्लोप्रिड 0.5 मिली प्रति लीटर छिड़कें।"
    out = af.filter_advice(text, "hi", "whatsapp_text", kind="answer", question=PRODUCT_Q["hi"], source_line="स्रोत: x.pdf")
    assert out.startswith("मैं कीटनाशक के नाम या मात्रा नहीं बता सकता। पीले चिपचिपे ट्रैप लगाएं।")
    assert "स्रोत: x.pdf" in out
    assert "फोटो भेजें" not in out


def test_a_bare_refusal_with_nothing_removed_also_gets_the_policy_reply():
    out = af.filter_advice("I cannot recommend specific pesticide names or doses.", "en", "web_text",
                           kind="answer", question=PRODUCT_Q["en"])
    assert out.startswith(af.pesticide_policy("en"))


def test_not_a_product_question_is_not_replaced():
    out = af.filter_advice("Spray imidacloprid 0.5 ml per litre. Check leaves weekly.", "en", "whatsapp_text",
                           kind="answer", question="How do I control whitefly on cotton?")
    assert out.startswith("Check leaves weekly.")
    assert af.pesticide_policy("en") not in out


def test_photo_answers_are_not_replaced():
    out = af.filter_advice("I can't name pesticides.", "en", "whatsapp_photo", kind="photo", question=PRODUCT_Q["en"])
    assert af.pesticide_policy("en") not in out


@pytest.mark.parametrize("sentence,decline", [
    ("I can't give pesticide names or quantities.", True),
    ("I cannot recommend specific pesticide names or doses.", True),
    ("मैं कीटनाशक दवाओं या उनकी मात्रा के बारे में सलाह नहीं दे सकता।", True),
    ("मी कीटकनाशकांची नावे सांगू शकत नाही.", True),
    ("నేను పురుగుమందుల పేర్లు చెప్పలేను.", True),
    ("Do not spray when it is windy.", False),
    ("पीले चिपचिपे ट्रैप लगाएं।", False),
])
def test_decline_sentences_are_recognised(sentence, decline):
    assert af._is_decline(sentence) is decline
