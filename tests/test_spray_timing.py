"""Spray-timing questions: classified apart from pesticide-product questions and answered from weather."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from common import advice_filter, spray_timing
from common.advice_filter import is_pesticide_question, spray_question_kind, spray_timing_day


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

TIMING = [
    # (question, day)
    ("क्या कल लाटूर में स्प्रे करने का सही समय है?", "tomorrow"),   # the live question of 4 Oct 2026
    ("Is tomorrow a good time to spray in Latur?", "tomorrow"),
    ("Can I spray today?", "today"),
    ("Can I spray now?", "today"),
    ("Is it a good time to spray?", "today"),
    ("क्या आज स्प्रे कर सकते हैं?", "today"),
    ("क्या स्प्रे करने का सही समय है?", "today"),
    ("अभी छिड़काव करें?", "today"),
    ("उद्या फवारणी करू का?", "tomorrow"),
    ("आज फवारणी करू का?", "today"),
    ("ఈరోజు స్ప్రే చేయవచ్చా?", "today"),
    ("రేపు పిచికారీ చేయవచ్చా?", "tomorrow"),
    # general timing questions: agronomy for the knowledge base, no day
    ("When is it safe to spray after rain?", None),
    ("कपास में स्प्रे करने का सबसे अच्छा समय कब है?", None),
    ("When should I spray tomorrow?", "tomorrow"),
]

PRODUCT = [
    "Which pesticide should I spray for whitefly on cotton, and how much?",
    "Which spray for bollworm?",
    "Which spray tomorrow for whitefly?",            # names a product need and a day: product wins
    "Should I spray neem oil?",
    "How much pesticide per litre?",
    "सफेद मक्खी के लिए कौन सी दवा छिड़कें?",
    "कपास के लिए क्या विशेष प्रबंधन करना चाहिए कीटनाशक का?",
    "बोंडअळीसाठी कोणते कीटकनाशक फवारावे?",
    "తెల్లదోమకు ఏ పురుగుమందు స్ప్రే చేయాలి?",
]

NOT_SPRAY = [
    "How do I control whitefly on cotton?",
    "Why are my wheat leaves yellowing?",
    "When does soybean need irrigation?",
    "कपास में सफेद मक्खी का नियंत्रण कैसे करें?",
]


@pytest.mark.parametrize("question,day", TIMING)
def test_timing_questions_are_timing_and_not_pesticide(question, day):
    assert spray_question_kind(question) == "timing"
    assert is_pesticide_question(question) is False
    assert spray_timing_day(question) == day


@pytest.mark.parametrize("question", PRODUCT)
def test_product_questions_keep_the_pesticide_policy(question):
    assert spray_question_kind(question) == "product"
    assert is_pesticide_question(question) is True


@pytest.mark.parametrize("question", NOT_SPRAY)
def test_other_questions_are_neither(question):
    assert spray_question_kind(question) is None
    assert is_pesticide_question(question) is False


# ---------------------------------------------------------------------------
# Weather lookups (fetch injected; no network)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(spray_timing, "_api_key_cache", "k")


def _current(wind_mps, rain=None):
    data = {"wind": {"speed": wind_mps}, "main": {"temp": 29}}
    if rain is not None:
        data["rain"] = {"1h": rain}
    return lambda url, params: data


def test_current_conditions_favorable_when_calm_and_dry():
    c = spray_timing.current_conditions("Latur", fetch=_current(1.0))
    assert c == {"wind_kmh": 3.6, "rain_mm": 0, "favorable": True}


def test_current_conditions_unfavorable_in_wind_or_rain():
    assert spray_timing.current_conditions("Latur", fetch=_current(4.0))["favorable"] is False   # 14.4 km/h
    wet = spray_timing.current_conditions("Latur", fetch=_current(1.0, rain=0.8))
    assert wet["favorable"] is False and wet["rain_mm"] == 0.8


def test_current_conditions_fail_closed():
    assert spray_timing.current_conditions("Latur", fetch=lambda u, p: None) is None
    assert spray_timing.current_conditions("Latur", fetch=lambda u, p: {"wind": {}}) is None
    assert spray_timing.current_conditions("Pune", fetch=_current(1.0)) is None  # no coordinates


def test_current_conditions_need_a_key(monkeypatch):
    monkeypatch.setattr(spray_timing, "_api_key_cache", None)
    monkeypatch.delenv("WEATHER_API_KEY_SECRET", raising=False)
    assert spray_timing.current_conditions("Latur", fetch=_current(1.0)) is None


NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)  # 17:30 IST on 4 October


def _slot(ist_hour, day=5, wind_mps=1.0, rain3h=0.0, pop=0.0):
    # IST = UTC+5:30, so an IST hour H on 5 Oct is H-5:30 UTC
    dt = datetime(2026, 10, day, ist_hour, 30, tzinfo=timezone.utc).timestamp() - 6 * 3600
    item = {"dt": int(dt), "wind": {"speed": wind_mps}, "pop": pop}
    if rain3h:
        item["rain"] = {"3h": rain3h}
    return item


def test_tomorrow_slots_are_the_early_morning_of_the_next_ist_day():
    items = [_slot(2), _slot(5), _slot(8), _slot(11), _slot(14), _slot(5, day=6)]
    picked = spray_timing.tomorrow_morning_slots(items, now_utc=NOW)
    hours = sorted(datetime.fromtimestamp(i["dt"], tz=spray_timing.IST).hour for i in picked)
    assert hours == [5, 8]


def test_tomorrow_conditions_take_the_worst_slot():
    fetch = lambda u, p: {"list": [_slot(5, wind_mps=1.0), _slot(8, wind_mps=3.0, pop=0.2)]}
    c = spray_timing.tomorrow_conditions("Latur", fetch=fetch, now_utc=NOW)
    assert c["wind_kmh"] == 10.8 and c["favorable"] is False and c["rain_probability"] == 0.2


def test_tomorrow_conditions_rain_probability_blocks():
    fetch = lambda u, p: {"list": [_slot(5, pop=0.6), _slot(8)]}
    c = spray_timing.tomorrow_conditions("Latur", fetch=fetch, now_utc=NOW)
    assert c["favorable"] is False and c["rain_probability"] == 0.6


def test_tomorrow_conditions_favorable_when_calm_dry_and_unlikely_to_rain():
    fetch = lambda u, p: {"list": [_slot(5, pop=0.1), _slot(8, wind_mps=2.0, pop=0.3)]}
    c = spray_timing.tomorrow_conditions("Latur", fetch=fetch, now_utc=NOW)
    assert c["favorable"] is True and c["wind_kmh"] == 7.2


def test_tomorrow_conditions_fail_closed_without_slots():
    assert spray_timing.tomorrow_conditions("Latur", fetch=lambda u, p: {"list": [_slot(14)]}, now_utc=NOW) is None
    assert spray_timing.tomorrow_conditions("Latur", fetch=lambda u, p: None, now_utc=NOW) is None


# ---------------------------------------------------------------------------
# Fixed replies
# ---------------------------------------------------------------------------

OK = {"wind_kmh": 4.0, "rain_mm": 0, "favorable": True}
WINDY = {"wind_kmh": 14.4, "rain_mm": 0, "favorable": False}
WET = {"wind_kmh": 4.0, "rain_mm": 1.2, "favorable": False}
TOK = {"wind_kmh": 6.0, "rain_mm": 0, "rain_probability": 0.1, "favorable": True}
TRAIN = {"wind_kmh": 6.0, "rain_mm": 0, "rain_probability": 0.6, "favorable": False}
TWIND = {"wind_kmh": 12.0, "rain_mm": 0, "rain_probability": 0.0, "favorable": False}


@pytest.mark.parametrize("dialect", ["hi", "mr", "te", "en"])
def test_reply_names_the_district_and_the_rule_in_every_language(dialect):
    for day, cond in [("today", OK), ("today", WINDY), ("today", WET), ("tomorrow", TOK), ("tomorrow", TRAIN),
                      ("tomorrow", TWIND), ("today", None), ("tomorrow", None)]:
        text = spray_timing.spray_timing_reply("Latur", dialect, day, cond)
        assert text.startswith("Latur:")
        rainy = cond is not None and (cond["rain_mm"] > 0 or cond.get("rain_probability", 0) > 0.3)
        if cond is not None and not rainy:
            assert "km/h" in text   # wind figure shown whenever wind decides the answer
        assert text.endswith(spray_timing._TEXT[dialect]["caveat"])


def test_reply_branches_english():
    r = lambda day, c: spray_timing.spray_timing_reply("Latur", "en", day, c)
    assert "favorable for spraying now. Wind 4.0 km/h" in r("today", OK)
    assert "not favorable" in r("today", WINDY) and "14.4 km/h" in r("today", WINDY)
    assert "raining now, do not spray" in r("today", WET)
    assert "tomorrow morning is likely to be favorable" in r("tomorrow", TOK)
    assert "rain is likely tomorrow morning (60% chance)" in r("tomorrow", TRAIN)
    assert "wind tomorrow morning is likely to be strong (about 12.0 km/h)" in r("tomorrow", TWIND)
    assert "not available right now" in r("today", None)


def test_reply_hindi_matches_the_nudge_wording():
    text = spray_timing.spray_timing_reply("Latur", "hi", "today", OK)
    assert "स्प्रे के लिए मौसम अनुकूल है। हवा 4.0 km/h" in text


def test_reply_never_names_a_pesticide_and_passes_the_advice_filter_unchanged():
    advice_filter._cloudwatch = MagicMock()
    for dialect in ("hi", "mr", "te", "en"):
        for day, cond in [("today", OK), ("today", WINDY), ("today", WET), ("tomorrow", TOK), ("tomorrow", TRAIN), ("today", None)]:
            body = spray_timing.spray_timing_reply("Latur", dialect, day, cond)
            out = advice_filter.filter_advice(body, dialect, "whatsapp_text", kind="answer", district="Latur",
                                              question="can I spray today")
            assert out.startswith(body)              # nothing removed
            assert "KVK" in out                      # standard footer still appended


def test_answer_spray_timing_never_raises(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("network")
    monkeypatch.setattr(spray_timing, "current_conditions", boom)
    text = spray_timing.answer_spray_timing("Latur", "en", "today")
    assert "not available right now" in text


def test_district_known():
    assert spray_timing.district_known("Latur") and spray_timing.district_known("Jalna")
    assert not spray_timing.district_known("Pune") and not spray_timing.district_known(None)
