import importlib.util
import os
import sys
from pathlib import Path


def _parse_crop_word(text: str):
    root = Path(__file__).resolve().parents[1]
    original_sys_path = list(sys.path)
    try:
        # Resolve processor handler's sibling imports.
        sys.path.insert(0, str(root / "src" / "processor"))
        sys.path.insert(0, str(root / "src" / "common-layer" / "python"))

        os.environ.setdefault("TABLE_NAME", "t")
        os.environ.setdefault("KNOWLEDGE_BASE_ID", "kb")
        os.environ.setdefault("GUARDRAIL_ID", "")
        os.environ.setdefault("GUARDRAIL_VERSION", "1")

        handler_path = root / "src" / "processor" / "handler.py"
        spec = importlib.util.spec_from_file_location("processor_handler_for_crop", handler_path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        return mod._parse_crop_word(text)
    finally:
        sys.path[:] = original_sys_path



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

