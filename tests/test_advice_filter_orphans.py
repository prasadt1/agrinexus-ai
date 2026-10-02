"""Removing a chemical step leaves no repeat instruction pointing at it and no gaps in step numbers."""
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


def test_repeat_sentence_after_removed_spray_is_dropped():
    text = (
        "Spray neem oil 5 ml per litre of water. Repeat two more times at 30-day intervals. "
        "Remove and destroy damaged bolls."
    )
    assert _f(text) == "Remove and destroy damaged bolls."


def test_repeat_paragraph_after_removed_paragraph_is_dropped():
    text = (
        "Spray neem seed kernel extract at 50 g per litre of water.\n\n"
        "Repeat two more times at 30-day intervals.\n\n"
        "Pluck 20 green bolls and cut them open to count larvae."
    )
    assert _f(text) == "Pluck 20 green bolls and cut them open to count larvae."


def test_numbered_lines_are_renumbered_across_lines():
    text = (
        "1. Remove rosette flowers.\n"
        "2. Spray 5 ml per litre of water.\n"
        "3. Repeat after 15 days.\n"
        "4. Install pheromone traps."
    )
    assert _f(text) == "1. Remove rosette flowers.\n2. Install pheromone traps."


def test_kept_line_keeps_its_place_in_the_list():
    text = (
        "1. Remove rosette flowers.\n"
        "2. Destroy crop residue. Spray 5 ml per litre of water.\n"
        "3. Install pheromone traps."
    )
    assert _f(text) == "1. Remove rosette flowers.\n2. Destroy crop residue.\n3. Install pheromone traps."


def test_second_list_restarts_at_one():
    text = (
        "1. Spray 5 ml per litre of water.\n"
        "2. Remove rosette flowers.\n"
        "\n"
        "After harvest:\n"
        "1. Shred the stalks.\n"
        "2. Let sheep graze the field."
    )
    assert _f(text) == (
        "1. Remove rosette flowers.\n"
        "\n"
        "After harvest:\n"
        "1. Shred the stalks.\n"
        "2. Let sheep graze the field."
    )


def test_marathi_spray_again_after_removed_insecticide_is_dropped():
    text = (
        "(१) प्रभावित पाने तोडून नष्ट करा, (२) इमिडाक्लोप्रिड शिफारशीनुसार वापरा, "
        "(३) प्रादुर्भाव जास्त असल्यास ३-४ दिवसांनी पुन्हा फवारणी करा, (४) पिकाची नियमित तपासणी करा."
    )
    out = _f(text, "mr")
    assert "पुन्हा फवारणी" not in out
    assert "(१) प्रभावित पाने तोडून नष्ट करा" in out
    assert "(२) पिकाची नियमित तपासणी करा" in out
    assert "(३)" not in out


def test_hindi_repeat_after_removed_dose_is_dropped():
    text = "5 मिली प्रति लीटर पानी में मिलाकर छिड़काव करें। 15 दिन बाद दोहराएं। प्रभावित पत्तियाँ हटा दें।"
    assert _f(text, "hi") == "प्रभावित पत्तियाँ हटा दें।"


def test_telugu_again_after_removed_dose_is_dropped():
    text = "లీటరు నీటికి 5 మి.లీ కలిపి పిచికారీ చేయండి. 15 రోజుల తర్వాత మళ్ళీ చేయండి. దెబ్బతిన్న ఆకులను తీసివేయండి."
    assert _f(text, "te") == "దెబ్బతిన్న ఆకులను తీసివేయండి."


def test_check_again_after_removed_step_is_kept():
    text = (
        "(१) निंबोळीचे पाणी (५०० ग्रॅम निंबोळी १० लिटर पाण्यात) फवारणी करा, "
        "(२) ७-१० दिवसांनी पुन्हा तपासणी करा."
    )
    assert _f(text, "mr") == "(१) ७-१० दिवसांनी पुन्हा तपासणी करा."
    assert _f("Spray 5 ml per litre of water. Check the field again after 7 days.") == (
        "Check the field again after 7 days."
    )


def test_repeat_after_kept_step_is_untouched():
    text = "Hand-pick the larvae. Repeat every week until none are found."
    assert _f(text) == text


def test_reply_without_removals_keeps_its_numbering():
    text = "1. Remove rosette flowers.\n3. Install pheromone traps.\nRepeat this every week."
    assert _f(text) == text


def test_against_is_not_again():
    text = "Spray 5 ml per litre of water. Resistant varieties protect against bollworm."
    assert _f(text) == "Resistant varieties protect against bollworm."


def test_orphan_drop_is_not_counted_as_chemical_advice(monkeypatch):
    calls = []
    monkeypatch.setattr(af, "_cloudwatch", types.SimpleNamespace(put_metric_data=lambda **kw: calls.append(kw)))
    af.filter_advice("Spray 5 ml per litre of water. Repeat after 15 days.", "en", "test", add_referral=False)
    kinds = {d["Value"] for c in calls for m in c["MetricData"] for d in m["Dimensions"] if d["Name"] == "Kind"}
    assert kinds == {"dose"}
