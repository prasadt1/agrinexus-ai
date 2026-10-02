"""Model-written source lines are removed; real ones come only from retrieval metadata."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "common-layer" / "python"))

from common.source_line import strip_source_lines  # noqa: E402

BODY = "पिवळे चिकट सापळे लावा."


@pytest.mark.parametrize(
    "line",
    [
        "स्त्रोत: FAO/ICAR शेती मार्गदर्शक",
        "**स्त्रोत:** ICAR-Central Institute for Cotton Research, Nagpur कापूस कीट व्यवस्थापन मार्गदर्शक तत्त्वे",
        "**स्रोत:** ICAR-Central Institute for Cotton Research, Nagpur (Cotton Pest Management Guidelines)",
        "स्रोत: कपास के नाशीजीवों के लिए सलाह (ICAR-NBAIR)",
        "📚 स्त्रोत: FAO/ICAR शेती मार्गदर्शक",
        "మూలం: ICAR మార్గదర్శకం",
        "Source: ICAR-CICR",
        "Sources : 3, 4, 5",
        "*Source:* FAO",
        "सोर्स: ICAR",
    ],
)
def test_model_written_source_line_removed(line):
    assert strip_source_lines(f"{BODY}\n\n{line}") == BODY


def test_body_mentioning_source_mid_sentence_is_kept():
    text = "Water source: use the canal after 10 am."
    assert strip_source_lines(text) == text


def test_referral_footer_untouched():
    text = f"{BODY}\n\nस्त्रोत: ICAR\n\nहे स्वयंचलित उत्तर आहे.\n📞 किसान कॉल सेंटर: 1800-180-1551"
    assert strip_source_lines(text) == f"{BODY}\n\nहे स्वयंचलित उत्तर आहे.\n📞 किसान कॉल सेंटर: 1800-180-1551"
