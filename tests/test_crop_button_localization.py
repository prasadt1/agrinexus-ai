import importlib
import sys
import os


def _parse_crop_word(text: str):
    # Import handler with its module-level relative imports resolved
    sys.path.insert(0, "src/processor")
    os.environ.setdefault("TABLE_NAME", "t")
    os.environ.setdefault("KNOWLEDGE_BASE_ID", "kb")
    os.environ.setdefault("GUARDRAIL_ID", "")
    os.environ.setdefault("GUARDRAIL_VERSION", "1")
    handler = importlib.import_module("handler")
    return handler._parse_crop_word(text)


def test_parse_crop_word_localized_variants():
    assert _parse_crop_word("कपास") == "Cotton"
    assert _parse_crop_word("गेहूं") == "Wheat"
    assert _parse_crop_word("सोयाबीन") == "Soybean"
    assert _parse_crop_word("मक्का") == "Maize"

    assert _parse_crop_word("कापूस") == "Cotton"
    assert _parse_crop_word("गहू") == "Wheat"
    assert _parse_crop_word("मका") == "Maize"

    assert _parse_crop_word("పత్తి") == "Cotton"
    assert _parse_crop_word("గోధుమ") == "Wheat"
    assert _parse_crop_word("సోయాబీన్") == "Soybean"
    assert _parse_crop_word("మొక్కజొన్న") == "Maize"

    assert _parse_crop_word("Cotton") == "Cotton"
    assert _parse_crop_word("wheat") == "Wheat"

