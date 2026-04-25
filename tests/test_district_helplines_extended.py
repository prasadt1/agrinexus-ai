"""Extended district helplines tests — helpline data, keyword detection, footer append."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common-layer", "python"))
from common.district_helplines import (
    HELPLINES,
    wants_where_to_buy_hint,
    maybe_append_helpline_footer,
)


# ---------------------------------------------------------------------------
# HELPLINES data
# ---------------------------------------------------------------------------

class TestHelplineData:
    def test_three_districts(self):
        assert len(HELPLINES) == 3

    @pytest.mark.parametrize("district", ["Latur", "Nagpur", "Jalna"])
    def test_all_districts_present(self, district):
        assert district in HELPLINES

    @pytest.mark.parametrize("district", ["Latur", "Nagpur", "Jalna"])
    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_all_languages_per_district(self, district, lang):
        assert lang in HELPLINES[district]

    @pytest.mark.parametrize("district", ["Latur", "Nagpur", "Jalna"])
    def test_contains_kisan_call_centre(self, district):
        en = HELPLINES[district]["en"]
        assert "1800-180-1551" in en

    def test_hindi_has_phone_emoji(self):
        assert "📞" in HELPLINES["Latur"]["hi"]


# ---------------------------------------------------------------------------
# wants_where_to_buy_hint
# ---------------------------------------------------------------------------

class TestWantsWhereToBuy:
    def test_english_buy(self):
        assert wants_where_to_buy_hint("Where can I buy pesticide?") is True

    def test_english_purchase(self):
        assert wants_where_to_buy_hint("How to purchase seeds?") is True

    def test_english_dealer(self):
        assert wants_where_to_buy_hint("Find a dealer near me") is True

    def test_hindi_kharid(self):
        assert wants_where_to_buy_hint("कीटनाशक कहाँ खरीदें?") is True

    def test_hindi_vikreta(self):
        assert wants_where_to_buy_hint("विक्रेता कहां है?") is True

    def test_normal_question_no_hint(self):
        assert wants_where_to_buy_hint("How to control aphids?") is False

    def test_empty_string(self):
        assert wants_where_to_buy_hint("") is False


# ---------------------------------------------------------------------------
# maybe_append_helpline_footer
# ---------------------------------------------------------------------------

class TestAppendHelplineFooter:
    def test_disabled_by_default(self):
        result = maybe_append_helpline_footer("Answer text", "Where to buy?", "en", "Latur")
        assert result == "Answer text"  # No footer when env var is false

    def test_enabled_appends_footer(self, monkeypatch):
        monkeypatch.setenv("APPEND_DISTRICT_HELPLINE", "true")
        result = maybe_append_helpline_footer("Answer text", "Where to buy?", "en", "Latur")
        assert "1800-180-1551" in result
        assert "Answer text" in result

    def test_enabled_but_no_buy_keyword(self, monkeypatch):
        monkeypatch.setenv("APPEND_DISTRICT_HELPLINE", "true")
        result = maybe_append_helpline_footer("Answer text", "How to control pests?", "en", "Latur")
        assert result == "Answer text"

    def test_enabled_but_unknown_district(self, monkeypatch):
        monkeypatch.setenv("APPEND_DISTRICT_HELPLINE", "true")
        result = maybe_append_helpline_footer("Answer text", "Where to buy?", "en", "Mumbai")
        assert result == "Answer text"

    def test_hindi_footer(self, monkeypatch):
        monkeypatch.setenv("APPEND_DISTRICT_HELPLINE", "true")
        result = maybe_append_helpline_footer("जवाब", "कीटनाशक कहाँ खरीदें?", "hi", "Nagpur")
        assert "कृषि सहायता" in result
