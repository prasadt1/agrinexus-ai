"""The advice output filter removes pesticide products and doses from every reply."""
import glob
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))

from common import advice_filter as af  # noqa: E402
from common import district_helplines as dh  # noqa: E402

REPLAY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "try", "replays")

# Live WhatsApp replies (1-2 Oct 2026), recommendations section verbatim.
LIVE_MR = [
    "तात्काळ उपाययोजना करा: (१) निंबोळीचे पाणी (५०० ग्रॅम निंबोळी १० लिटर पाण्यात) फवारणी करा, "
    "(२) इमिडाक्लोप्रिड १७.८ एसएल (०.३ मिली/लिटर पाणी) किंवा थायामेथॉक्झाम २५ डब्ल्यूजी (०.२ ग्रॅम/लिटर पाणी) फवारणी करा, "
    "(३) पानाच्या खालच्या बाजूला चांगली फवारणी करा, (४) ७-१० दिवसांनी पुन्हा तपासणी करा.",
    "तात्काळ उपाययोजना करा: (१) निंबोळीचे पाणी (५०० ग्रॅम निंबोळी १० लिटर पाण्यात) फवारणी करा, "
    "(२) इमिडाक्लोप्रिड किंवा डायमिथोएट कीटकनाशक शिफारशीनुसार वापरा, "
    "(३) माशांचा प्रादुर्भाव जास्त असल्यास ३-४ दिवसांनी पुन्हा फवारणी करा, (४) पिकाची नियमित तपासणी करा.",
    "बाधित बोंडे ताबडतोब तोडून जमिनीत खोल गाडून टाकावे किंवा जाळून टाकावे. शेतात फेरोमोन सापळे (८-१० प्रति एकर) लावावे. "
    "प्रोफेनोफॉस २५% + सायपरमेथ्रिन ५% EC (२ मिली प्रति लिटर पाणी) किंवा क्लोरँट्रानिलिप्रोल १८.५% SC (०.३ मिली प्रति लिटर पाणी) फवारणी करावी. "
    "शेतात स्वच्छता राखावी आणि नियमित तपासणी करावी.",
    "तात्काळ उपाययोजना करा: १) प्रभावित पाने तोडून नष्ट करा, २) पिवळे चिकट सापळे लावा, "
    "३) इमिडाक्लोप्रिड १७.८% SL (१ मिली प्रति लिटर पाणी) किंवा थायामेथॉक्झाम २५% WG (०.५ ग्रॅम प्रति लिटर पाणी) यांपैकी एक फवारणी करा. "
    "पानाच्या खालच्या बाजूला चांगले फवारणी करा. १०-१२ दिवसांनी पुन्हा तपासा आणि आवश्यक असल्यास वेगळ्या गटातील कीटकनाशक वापरा.",
]


def _replay_texts():
    texts = []
    for path in sorted(glob.glob(os.path.join(REPLAY_DIR, "*.json"))):
        with open(path, encoding="utf-8") as f:
            for r in json.load(f)["results"]:
                for key in ("recommendations", "reply_text"):
                    if r.get(key):
                        texts.append(r[key])
    return list(dict.fromkeys(texts))


REPLAY_TEXTS = _replay_texts()

ACTIVE_SPELLINGS = [
    "प्रोफेनोफॉस", "इमामेक्टिन", "क्लोरपायरीफॉस", "इमिडाक्लोप्रिड", "थायामेथॉक्झाम",
    "क्लोरँट्रानिलिप्रोल", "क्लोरॅन्ट्रानिलिप्रोल", "सायपरमेथ्रिन", "डायमिथोएट", "कॉन्फिडॉर", "अॅक्टारा",
    "imidacloprid", "thiamethoxam", "profenofos", "spinosad", "quinalphos", "chlorantraniliprole",
]


@pytest.fixture(autouse=True)
def _no_cloudwatch(monkeypatch):
    calls = []
    fake = types.SimpleNamespace(put_metric_data=lambda **kw: calls.append(kw))
    monkeypatch.setattr(af, "_cloudwatch", fake)
    return calls


def _assert_clean(out):
    body = out.split("\n\n" + dh.referral_line("mr", "photo"))[0].split("\n\n" + dh.referral_line("mr", "answer"))[0]
    for line in body.split("\n"):
        assert not af.classify(line), f"chemical advice survived: {line!r}"
    for name in ACTIVE_SPELLINGS:
        assert name.lower() not in out.lower()


def test_replays_were_found():
    assert len(REPLAY_TEXTS) >= 20


@pytest.mark.parametrize("text", REPLAY_TEXTS)
def test_nothing_from_replays_survives(text):
    _assert_clean(af.filter_advice(text, "mr", "test", kind="photo"))


@pytest.mark.parametrize("text", LIVE_MR)
def test_nothing_from_live_replies_survives(text):
    _assert_clean(af.filter_advice(text, "mr", "test", kind="photo"))


def test_devanagari_numeral_neem_dose_is_removed_but_practice_steps_stay():
    out = af.filter_advice(LIVE_MR[0], "mr", "test", kind="photo")
    assert "५०० ग्रॅम" not in out and "१० लिटर" not in out
    assert "पानाच्या खालच्या बाजूला चांगली फवारणी करा" in out
    assert "७-१० दिवसांनी पुन्हा तपासणी करा" in out


def test_numbered_steps_are_renumbered_after_removal():
    out = af.filter_advice(LIVE_MR[0], "mr", "test", kind="photo")
    assert "(१) पानाच्या खालच्या बाजूला" in out
    assert "(२) ७-१० दिवसांनी" in out
    assert "(३)" not in out


def test_dropped_step_that_ended_a_sentence_does_not_leave_a_dangling_comma():
    out = af.filter_advice(LIVE_MR[3], "mr", "test", kind="photo", add_referral=False)
    assert "२) पिवळे चिकट सापळे लावा. पानाच्या खालच्या बाजूला" in out


def test_dropped_sentence_after_a_full_stop_does_not_double_it():
    text = "आठवड्यातून एकदा १० झाडांवर पांढऱ्या माशींची संख्या तपासा. नीम तेल (Azadirachtin 1500 ppm) 2.5 लिटर/हेक्टर फवारा."
    out = af.filter_advice(text, "mr", "test", add_referral=False)
    assert out == "आठवड्यातून एकदा १० झाडांवर पांढऱ्या माशींची संख्या तपासा."


def test_traps_and_field_sanitation_survive():
    out = af.filter_advice(LIVE_MR[2], "mr", "test", kind="photo")
    assert "शेतात फेरोमोन सापळे (८-१० प्रति एकर) लावावे." in out
    assert "बाधित बोंडे ताबडतोब तोडून" in out
    assert "शेतात स्वच्छता राखावी" in out


def test_formatted_message_keeps_section_labels():
    msg = (
        "*निदान (Diagnosis):* कापसाच्या बोंडावर गुलाबी इल्ली दिसत आहे.\n"
        "*तीव्रता (Severity):* उच्च\n"
        "*शिफारशी (Recommendations):* प्रोफेनोफॉस 50% EC 2 मिली प्रति लिटर पाण्यात मिसळून फवारणी करा. फेरोमोन सापळे लावा.\n"
        "*विश्वास (Confidence):* उच्च"
    )
    out = af.filter_advice(msg, "mr", "test", kind="photo")
    assert "*शिफारशी (Recommendations):* फेरोमोन सापळे लावा." in out
    assert "*निदान (Diagnosis):* कापसाच्या बोंडावर गुलाबी इल्ली दिसत आहे." in out
    assert "*विश्वास (Confidence):* उच्च" in out


def test_recommendations_that_were_all_chemical_leave_a_dash():
    msg = "*शिफारशी (Recommendations):* प्रोफेनोफॉस 50% EC 2 मिली प्रति लिटर फवारणी करा."
    out = af.filter_advice(msg, "mr", "test", kind="photo")
    assert out.startswith("*शिफारशी (Recommendations):* —")


@pytest.mark.parametrize(
    "text",
    [
        "Spray imidacloprid 17.8% SL at 0.3 ml per litre of water.",
        "Use Confidor or Actara as per label.",
        "इमिडाक्लोप्रिड 0.3 मिली प्रति लीटर पानी में मिलाकर छिड़काव करें।",
        "ఇమిడాక్లోప్రిడ్ 0.3 మి.లీ ప్రతి లీటర్ నీటిలో కలిపి పిచికారీ చేయండి.",
        "౫ మి.లీ వేప నూనె ఒక లీటర్ నీటిలో కలిపి పిచికారీ చేయండి.",
        "Mix 5 ml neem oil in 1 litre of water and spray.",
        "नीम तेल 5 मिली/लीटर का छिड़काव करें।",
        "Apply 200 ml per acre as a spray.",
        "नीम तेल (Azadirachtin 1500 ppm) 2.5 लिटर/हेक्टर + डिटर्जंट 1 ग्रॅम/लिटर पाण्यात मिसळून फवारणी करू शकता",
        "Use azadirachtin-based neem oil.",
        "Neem oil 1500 ppm is effective.",
    ],
)
def test_other_languages_and_neem_doses_are_removed(text):
    out = af.filter_advice(text, "en", "test", add_referral=False)
    assert out == "", out


@pytest.mark.parametrize(
    "text",
    [
        "Apply 50 kg urea per acre after the first irrigation.",
        "Give 10 litres of water per plant every week.",
        "Install 8-10 pheromone traps per acre.",
        "Spray neem oil on the underside of the leaves in the evening.",
        "Place yellow sticky traps at canopy height.",
        "पिवळे चिकट सापळे लावा.",
        "Check again after 7-10 days.",
        "Losses can reach 50% if not controlled.",
    ],
)
def test_non_chemical_and_fertilizer_sentences_survive(text):
    assert af.filter_advice(text, "en", "test", add_referral=False) == text


def test_referral_added_once_with_one_contact():
    out = af.filter_advice("Remove affected bolls.", "mr", "test", kind="photo")
    assert out.count(dh.referral_line("mr", "photo")) == 1
    assert out.count(dh.KISAN_CALL_CENTRE) == 1
    again = af.filter_advice(out, "mr", "test", kind="photo")
    assert again == out


def test_answer_referral_wording_is_not_about_a_photo():
    out = af.filter_advice("Irrigate every 10 days.", "en", "test", kind="answer")
    assert "automated answer" in out and "photo" not in out


def test_referral_uses_curated_district_block_when_known():
    out = af.filter_advice("Remove affected bolls.", "mr", "test", kind="photo", district="Latur")
    assert "लातूर" in out
    assert out.count(dh.KISAN_CALL_CENTRE) == 1


def test_district_footer_not_added_twice(monkeypatch):
    monkeypatch.setenv("APPEND_DISTRICT_HELPLINE", "true")
    out = af.filter_advice("Remove affected bolls.", "en", "test", district="Latur")
    out = dh.maybe_append_helpline_footer(out, "where to buy pesticide", "en", "Latur")
    assert out.count(dh.KISAN_CALL_CENTRE) == 1


def test_metric_emitted_per_kind_when_filter_fires(_no_cloudwatch):
    af.filter_advice(LIVE_MR[2], "mr", "whatsapp_photo", kind="photo")
    assert len(_no_cloudwatch) == 1
    data = _no_cloudwatch[0]["MetricData"]
    assert _no_cloudwatch[0]["Namespace"] == "AgriNexus/Advice"
    kinds = {d["Dimensions"][1]["Value"] for d in data if len(d["Dimensions"]) == 2}
    assert {"active", "dose", "formulation"} <= kinds
    assert all(d["Dimensions"][0]["Value"] == "whatsapp_photo" for d in data)


def test_no_metric_when_nothing_removed(_no_cloudwatch):
    af.filter_advice("Remove affected bolls.", "en", "whatsapp_text")
    assert _no_cloudwatch == []
