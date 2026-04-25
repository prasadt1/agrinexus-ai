"""Nudge detector tests — keyword detection, message templates, all languages."""
import importlib.util
import os
import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")


@pytest.fixture()
def det(monkeypatch):
    """Import nudge detector with boto3 mocked."""
    mock_boto3 = types.ModuleType("boto3")
    mock_table = types.SimpleNamespace(
        query=lambda **kw: {"Items": []},
        update_item=lambda **kw: {},
    )
    mock_dynamo = types.SimpleNamespace(Table=lambda name: mock_table)
    mock_cw = types.SimpleNamespace(put_metric_data=lambda **kw: {})

    def _client(svc, **kw):
        if svc == "cloudwatch":
            return mock_cw
        return types.SimpleNamespace(
            get_secret_value=lambda **kw: {"SecretString": "tok"},
            delete_schedule=lambda **kw: {},
        )

    mock_boto3.resource = lambda svc, **kw: mock_dynamo
    mock_boto3.client = _client
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

    # Also stub common layer
    common_mod = types.ModuleType("common")
    common_mod.whatsapp = types.ModuleType("common.whatsapp")
    common_mod.whatsapp.send_whatsapp_message = lambda **kw: None
    common_mod.whatsapp.send_whatsapp_buttons = lambda **kw: None
    monkeypatch.setitem(sys.modules, "common", common_mod)
    monkeypatch.setitem(sys.modules, "common.whatsapp", common_mod.whatsapp)

    spec = importlib.util.spec_from_file_location(
        "nudge_detector",
        os.path.join(os.path.dirname(__file__), "..", "src", "nudge", "detector.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# detect_keyword
# ---------------------------------------------------------------------------

class TestDetectKeyword:
    def test_hindi_done(self, det):
        assert det.detect_keyword("हो गया", det.DONE_KEYWORDS["hi"]) is True

    def test_marathi_done(self, det):
        assert det.detect_keyword("झाला", det.DONE_KEYWORDS["mr"]) is True

    def test_telugu_done(self, det):
        assert det.detect_keyword("అయ్యింది", det.DONE_KEYWORDS["te"]) is True

    def test_english_done(self, det):
        assert det.detect_keyword("done", det.DONE_KEYWORDS["en"]) is True

    def test_english_done_case_insensitive(self, det):
        assert det.detect_keyword("DONE", det.DONE_KEYWORDS["en"]) is True

    def test_hindi_not_yet(self, det):
        assert det.detect_keyword("अभी नहीं", det.NOT_YET_KEYWORDS["hi"]) is True

    def test_marathi_not_yet(self, det):
        assert det.detect_keyword("अजून नाही", det.NOT_YET_KEYWORDS["mr"]) is True

    def test_telugu_not_yet(self, det):
        assert det.detect_keyword("ఇంకా లేదు", det.NOT_YET_KEYWORDS["te"]) is True

    def test_english_not_yet(self, det):
        assert det.detect_keyword("not yet", det.NOT_YET_KEYWORDS["en"]) is True

    def test_random_text_no_match(self, det):
        assert det.detect_keyword("How to grow wheat?", det.DONE_KEYWORDS["en"]) is False

    def test_partial_match_in_sentence(self, det):
        assert det.detect_keyword("I am done with spraying", det.DONE_KEYWORDS["en"]) is True


# ---------------------------------------------------------------------------
# Message templates — all 4 languages present
# ---------------------------------------------------------------------------

class TestMessageTemplates:
    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_confirmation_messages(self, det, lang):
        assert lang in det.CONFIRMATION_MESSAGES
        assert len(det.CONFIRMATION_MESSAGES[lang]) > 10

    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_not_yet_messages(self, det, lang):
        assert lang in det.NOT_YET_MESSAGES
        assert "👍" in det.NOT_YET_MESSAGES[lang]

    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_not_yet_final_messages(self, det, lang):
        assert lang in det.NOT_YET_FINAL_MESSAGES
        assert len(det.NOT_YET_FINAL_MESSAGES[lang]) > 20

    def test_confirmation_has_celebration_emoji(self, det):
        for lang, msg in det.CONFIRMATION_MESSAGES.items():
            assert "🎉" in msg, f"{lang} missing 🎉"


# ---------------------------------------------------------------------------
# DONE / NOT_YET keyword lists — completeness
# ---------------------------------------------------------------------------

class TestKeywordLists:
    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_done_keywords_all_languages(self, det, lang):
        assert lang in det.DONE_KEYWORDS
        assert len(det.DONE_KEYWORDS[lang]) >= 3

    @pytest.mark.parametrize("lang", ["hi", "mr", "te", "en"])
    def test_not_yet_keywords_all_languages(self, det, lang):
        assert lang in det.NOT_YET_KEYWORDS
        assert len(det.NOT_YET_KEYWORDS[lang]) >= 3

    def test_english_done_includes_common_words(self, det):
        en = [k.lower() for k in det.DONE_KEYWORDS["en"]]
        assert "done" in en
        assert "completed" in en
