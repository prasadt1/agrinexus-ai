import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))

from common import district_helplines as dh


def test_wants_where_to_buy_hint_english():
    assert dh.wants_where_to_buy_hint("Where can I buy cotton seeds?") is True
    assert dh.wants_where_to_buy_hint("Best fertilizer schedule for wheat") is False


def test_wants_where_to_buy_hint_hindi():
    assert dh.wants_where_to_buy_hint("कीटनाशक कहाँ से खरीदूँ") is True
    assert dh.wants_where_to_buy_hint("गेहूं में सिंचाई कब करें") is False


def test_maybe_append_curated_district_and_keywords():
    os.environ["APPEND_DISTRICT_HELPLINE"] = "true"
    base = "General agronomy advice."
    q = "pesticide dealer in my area"
    out = dh.maybe_append_helpline_footer(base, q, "en", "Nagpur")
    assert "Nagpur" in out
    assert base in out
    assert "1800" in out


def test_maybe_append_skips_without_keywords():
    os.environ["APPEND_DISTRICT_HELPLINE"] = "true"
    base = "Irrigation tips."
    out = dh.maybe_append_helpline_footer(base, "When to irrigate wheat?", "hi", "Latur")
    assert out == base


def test_maybe_append_skips_uncurated_district():
    os.environ["APPEND_DISTRICT_HELPLINE"] = "true"
    base = "Advice."
    out = dh.maybe_append_helpline_footer(base, "where to buy seeds", "en", "Pune")
    assert out == base


def test_master_switch_off():
    os.environ["APPEND_DISTRICT_HELPLINE"] = "false"
    base = "x"
    out = dh.maybe_append_helpline_footer(base, "where to buy dealer", "en", "Jalna")
    assert out == base
