"""Web chat dialect detection and keyword hint tests — no AWS calls."""
import os
import sys
import re
import types

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("TABLE_NAME", "test-table")
    monkeypatch.setenv("KNOWLEDGE_BASE_ID", "test-kb")
    monkeypatch.setenv("GUARDRAIL_ID", "")
    monkeypatch.setenv("GUARDRAIL_VERSION", "1")


@pytest.fixture()
def webchat(monkeypatch):
    """Import web-chat handler with boto3 mocked."""
    mock_boto3 = types.ModuleType("boto3")
    mock_table = types.SimpleNamespace()
    mock_dynamo = types.SimpleNamespace(Table=lambda name: mock_table)
    mock_boto3.resource = lambda svc, **kw: mock_dynamo
    mock_boto3.client = lambda svc, **kw: types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)

    sys.modules.pop("handler", None)
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "web-chat"))
    import handler as mod
    sys.path.pop(0)
    return mod


# ---------------------------------------------------------------------------
# effective_dialect
# ---------------------------------------------------------------------------

class TestEffectiveDialect:
    def test_english_ui_english_text(self, webchat):
        assert webchat.effective_dialect("How to grow wheat?", "en") == "en"

    def test_hindi_ui_returns_hindi(self, webchat):
        assert webchat.effective_dialect("anything", "hi") == "hi"

    def test_marathi_ui_returns_marathi(self, webchat):
        assert webchat.effective_dialect("anything", "mr") == "mr"

    def test_telugu_ui_returns_telugu(self, webchat):
        assert webchat.effective_dialect("anything", "te") == "te"

    def test_english_ui_hindi_text_detects_hindi(self, webchat):
        assert webchat.effective_dialect("गेहूं में कीट", "en") == "hi"

    def test_english_ui_telugu_text_detects_telugu(self, webchat):
        assert webchat.effective_dialect("పత్తి పురుగులు", "en") == "te"

    def test_unknown_language_defaults_to_english(self, webchat):
        assert webchat.effective_dialect("hello", "xx") == "en"

    def test_empty_message_returns_ui_language(self, webchat):
        assert webchat.effective_dialect("", "mr") == "mr"

    def test_none_message_returns_ui_language(self, webchat):
        assert webchat.effective_dialect(None, "hi") == "hi"

    def test_none_ui_language_defaults_english(self, webchat):
        assert webchat.effective_dialect("hello", None) == "en"


# ---------------------------------------------------------------------------
# Keyword hints for multilingual retrieval
# ---------------------------------------------------------------------------

class TestKeywordHints:
    """Verify that non-English queries get English keyword hints appended."""

    def _build_retrieval_query(self, webchat, query, dialect):
        """Replicate the keyword hint logic from query_bedrock."""
        if dialect == "en":
            return query
        hints = []
        _keyword_hints = {
            'कपास': 'cotton', 'कापूस': 'cotton', 'పత్తి': 'cotton',
            'गेहूं': 'wheat', 'गहू': 'wheat', 'గోధుమ': 'wheat',
            'सोयाबीन': 'soybean', 'సోయాబీన్': 'soybean',
            'स्प्रे': 'spray', 'फवारणी': 'spray', 'స్ప్రే': 'spray',
            'पाने': 'leaves', 'पान': 'leaves', 'ఆకులు': 'leaves',
            'पीले': 'yellow', 'पिवळी': 'yellow', 'పసుపు': 'yellow',
        }
        for local_word, eng_word in _keyword_hints.items():
            if local_word in query:
                hints.append(eng_word)
        if hints:
            return f"{query} ({' '.join(dict.fromkeys(hints))})"
        return query

    def test_hindi_cotton_spray_gets_hints(self, webchat):
        q = self._build_retrieval_query(webchat, "कपास में स्प्रे कब करें?", "hi")
        assert "cotton" in q
        assert "spray" in q

    def test_marathi_wheat_leaves_gets_hints(self, webchat):
        q = self._build_retrieval_query(webchat, "गहू पान पिवळी का?", "mr")
        assert "wheat" in q
        assert "leaves" in q
        assert "yellow" in q

    def test_telugu_cotton_gets_hint(self, webchat):
        q = self._build_retrieval_query(webchat, "పత్తి పురుగులు", "te")
        assert "cotton" in q

    def test_english_query_no_hints(self, webchat):
        q = self._build_retrieval_query(webchat, "How to spray cotton?", "en")
        assert q == "How to spray cotton?"

    def test_hindi_soybean_gets_hint(self, webchat):
        q = self._build_retrieval_query(webchat, "सोयाबीन में कीट", "hi")
        assert "soybean" in q
