"""Removing a step never changes a number that is not a list number, and leaves no "do this" pointing at it.

Live reply of 4 Oct 2026 (voice, Hindi, "सफेद मक्खी के लिए कौन सी दवा छिड़कें?"): the filter removed a
spray sentence, renumbered "45)" in "(NPK 13:0:45)" as if it were list item 45, and printed
"13:0:1"; it also left "यह तब करें जब..." ("do this when...") pointing at the removed sentence.
"""
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))

from common import advice_filter as af  # noqa: E402


@pytest.fixture(autouse=True)
def _no_cloudwatch(monkeypatch):
    monkeypatch.setattr(af, "_cloudwatch", types.SimpleNamespace(put_metric_data=lambda **kw: None))


def _f(text, dialect="en"):
    return af.filter_advice(text, dialect, "test", add_referral=False)


LIVE_MODEL_TEXT = (
    "मैं किसी कीटनाशक या दवा का नाम नहीं बता सकता। "
    "जब 8 वयस्क सफेद मक्खी प्रति पत्ती दिखें, तब नीम तेल 5 मिली प्रति लीटर का छिड़काव करें। "
    "यह तब करें जब 8 वयस्क सफेद मक्खी प्रति पत्ती दिखें। "
    "बोल बनने के समय पोटैशियम नाइट्रेट खाद (NPK 13:0:45) 2% की दर से छिड़काव करने से फूल गिरना कम होता है और बोल अच्छे बनते हैं।"
)


def test_live_reply_keeps_the_fertilizer_grade_and_drops_the_dangling_sentence():
    out = _f(LIVE_MODEL_TEXT, "hi")
    assert "(NPK 13:0:45)" in out and "13:0:1" not in out
    assert "यह तब करें" not in out
    assert "5 मिली" not in out
    assert out.startswith("मैं किसी कीटनाशक या दवा का नाम नहीं बता सकता। बोल बनने के समय")


@pytest.mark.parametrize("ratio", ["(NPK 19:19:19)", "(NPK 13:0:45)", "(12:61:0)", "(at 10:30)"])
def test_ratios_and_times_before_a_bracket_are_not_renumbered(ratio):
    out = _f(f"Spray profenofos 2 ml per litre. Apply water soluble fertilizer {ratio} at flowering.")
    assert ratio in out


@pytest.mark.parametrize("dialect,text,kept", [
    ("en", "Spray profenofos 2 ml per litre. Check the crop again (about 45) days after sowing.", "(about 45) days"),
    ("hi", "प्रोफेनोफॉस 2 मिली प्रति लीटर छिड़कें। बुवाई के बाद (लगभग 45) दिन पर निगरानी करें।", "(लगभग 45) दिन"),
])
def test_a_number_closing_an_open_bracket_is_not_renumbered(dialect, text, kept):
    assert kept in _f(text, dialect)


def test_bracketed_number_survives_inside_a_real_numbered_list():
    text = ("1) Remove affected bolls. 2) Spray profenofos 2 ml per litre. 3) Install pheromone traps. "
            "4) Sow early, (about 45) days before the usual date.")
    out = _f(text)
    assert out == ("1) Remove affected bolls. 2) Install pheromone traps. "
                   "3) Sow early, (about 45) days before the usual date.")


def test_real_numbered_lists_still_renumber():
    out = _f("1. Check leaves.\n2. Spray profenofos 2 ml per litre.\n3. Hang traps.\n4. Weed bunds.")
    assert out == "1. Check leaves.\n2. Hang traps.\n3. Weed bunds."


def test_no_double_full_stop_where_a_middle_step_was_removed():
    out = _f("1) Remove affected bolls. 2) Spray profenofos 2 ml per litre. 3) Install pheromone traps.")
    assert ".." not in out
    out = _f("Remove affected bolls. Spray profenofos 2 ml per litre. Install pheromone traps.")
    assert out == "Remove affected bolls. Install pheromone traps."


@pytest.mark.parametrize("dialect,text", [
    ("en", "Spray profenofos 2 ml per litre. Do this when you see 8 adults per leaf. Check leaves weekly."),
    ("en", "Spray profenofos 2 ml per litre. Only do this in the evening. Check leaves weekly."),
    ("hi", "प्रोफेनोफॉस 2 मिली प्रति लीटर छिड़कें। यह तब करें जब 8 वयस्क प्रति पत्ती दिखें। हर हफ्ते पत्तियाँ जाँचें।"),
    ("hi", "प्रोफेनोफॉस 2 मिली प्रति लीटर छिड़कें। इसका छिड़काव शाम को करें। हर हफ्ते पत्तियाँ जाँचें।"),
    ("mr", "प्रोफेनोफॉस 2 मिली प्रति लिटर फवारा. हे तेव्हा करा जेव्हा 8 प्रौढ प्रति पान दिसतात. दर आठवड्याला पाने तपासा."),
    ("te", "ప్రొఫెనోఫాస్ 2 మి.లీ. లీటరుకు పిచికారీ చేయండి. దీనిని సాయంత్రం చేయండి. ప్రతి వారం ఆకులను తనిఖీ చేయండి."),
])
def test_a_sentence_pointing_back_at_a_removed_step_is_dropped(dialect, text):
    out = _f(text, dialect)
    last = text.rsplit(". ", 1)[-1].rsplit("। ", 1)[-1]
    assert out.strip() == last.strip()


@pytest.mark.parametrize("dialect,text,kept", [
    ("en", "Spray profenofos 2 ml per litre. This pest hides under the leaves.", "This pest hides under the leaves."),
    ("hi", "प्रोफेनोफॉस 2 मिली प्रति लीटर छिड़कें। यह कीट पत्तियों के नीचे रहता है।", "यह कीट पत्तियों के नीचे रहता है।"),
    # a back-reference with nothing removed before it is left alone
    ("en", "Hang yellow sticky traps. Do this when you first see adults.", "Do this when you first see adults."),
])
def test_sentences_that_stand_alone_are_kept(dialect, text, kept):
    assert kept in _f(text, dialect)
