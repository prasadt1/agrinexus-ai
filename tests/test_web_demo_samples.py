"""The web demo offers the same English sample questions as the WhatsApp visitor list."""
import re
from pathlib import Path

from common import visitor

PAGE = Path(__file__).resolve().parents[1] / "docs" / "web-demo" / "live-2026-04-13b.html"


def _english_samples() -> list:
    html = PAGE.read_text(encoding="utf-8")
    block = re.search(r"const SAMPLE_QUESTIONS = \{\s*en: \[(.*?)\]", html, re.S).group(1)
    return re.findall(r'"([^"]+)"', block)


def test_english_samples_match_the_whatsapp_list_in_order():
    assert _english_samples() == [q for _id, _title, q in visitor.SAMPLE_QUESTIONS]


def test_page_states_the_per_browser_limit():
    html = PAGE.read_text(encoding="utf-8")
    assert "20 questions remaining this hour" in html
    assert "5 questions" not in html


def test_landing_page_states_the_same_limit():
    html = (PAGE.parents[1] / "try" / "index.html").read_text(encoding="utf-8")
    assert "Text only, 20 questions an hour." in html
