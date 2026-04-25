"""Tests for is_rag_refusal_response — no generic source footer on KB refusals."""

import os
import sys
from pathlib import Path
import importlib.util

import pytest

_ROOT = Path(__file__).resolve().parents[1]

# handler.py reads these at import time
os.environ.setdefault("TABLE_NAME", "test-table")
os.environ.setdefault("KNOWLEDGE_BASE_ID", "test-kb")
os.environ.setdefault("GUARDRAIL_ID", "")
os.environ.setdefault("GUARDRAIL_VERSION", "DRAFT")

def _load_processor_handler():
    """
    Load src/processor/handler.py in isolation without polluting global sys.path.
    This avoids breaking other tests that import their own `handler` modules.
    """
    original_sys_path = list(sys.path)
    try:
        # Lambda layout: handler imports `output` and `analyzer` from the processor folder
        sys.path.insert(0, str(_ROOT / "src" / "processor"))
        # Handler also imports `common.whatsapp` from the common layer package root.
        sys.path.insert(0, str(_ROOT / "src" / "common-layer" / "python"))

        handler_path = _ROOT / "src" / "processor" / "handler.py"
        spec = importlib.util.spec_from_file_location("processor_handler", handler_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        return mod
    finally:
        sys.path[:] = original_sys_path


processor_handler = _load_processor_handler()

is_rag_refusal_response = processor_handler.is_rag_refusal_response
strip_llm_xml_citation_tags = processor_handler.strip_llm_xml_citation_tags


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", True),
        ("   ", True),
        (
            "I don't have information about this in my knowledge base. Please contact KVK.",
            True,
        ),
        (
            "मेरे पास इस बारे में जानकारी नहीं है कि सोयाबीन में कौन सा पेस्टिसाइड लगे।",
            True,
        ),
        (
            "मेरे पास इस बारे में जानकारी नहीं है। हालांकि संदर्भ में बुवाई की जानकारी है।",
            True,
        ),
        (
            "दिए गए संदर्भ में पेस्टिसाइड के उपयोग के बारे में कोई विशिष्ट जानकारी नहीं दी गई है।",
            True,
        ),
        (
            "दिए गए संदर्भ में जानकारी नहीं दी गई है। कृपया केवीके से संपर्क करें।",
            True,
        ),
        ("ज्ञानकोषात या विषयाविषयी माहिती नाही.", True),
        ("माझ्याकडे या विषयाविषयी माहिती नाही.", True),
        (
            "सोयाबीन में बुवाई अप्रैल में करें। बीज दर 60–80 किग्रा प्रति हेक्टेयर।",
            False,
        ),
        (
            "गेहूं में तना मोड़क कीट के लिए इमिडाक्लोप्रिड का उपयोग किया जाता है (स्थानीय लेबल देखें)।",
            False,
        ),
    ],
)
def test_is_rag_refusal_response(text, expected):
    assert is_rag_refusal_response(text) is expected


def test_strip_llm_xml_citation_tags_removes_source_element():
    raw = (
        "सोयाबीन में कीट नियंत्रण के लिए जैविक कीटनाशक उपयोग करें।\n\n"
        "<source>2</source>\n\n"
        "स्रोत: FAO/ICAR कृषि मार्गदर्शिका"
    )
    out = strip_llm_xml_citation_tags(raw)
    assert "<source>" not in out and "</source>" not in out
    assert "जैविक कीटनाशक" in out
    assert "स्रोत:" in out


def test_strip_llm_xml_citation_tags_case_insensitive():
    raw = "जवाब।\n<SOURCE> 12 </Source>\nअंत"
    out = strip_llm_xml_citation_tags(raw)
    assert "<" not in out
    assert "जवाब" in out and "अंत" in out
