"""
Remove source lines written by the model. A source is shown only when it comes from
retrieval metadata (document names), never from the model's prose.
"""
from __future__ import annotations

import re

_LABELS = (
    "स्रोत",
    "स्त्रोत",
    "सोर्स",
    "మూలం",
    "Source",
    "Sources",
)

_SOURCE_LINE_RE = re.compile(
    r"^[ \t]*(?:📚[ \t]*)?(?:\*{1,2}|_)?[ \t]*(?:"
    + "|".join(re.escape(l) for l in _LABELS)
    + r")[ \t]*(?:\*{1,2}|_)?[ \t]*[:：].*$",
    re.IGNORECASE | re.MULTILINE,
)


def is_source_line(line: str) -> bool:
    return bool(_SOURCE_LINE_RE.match(line or ""))


def strip_source_lines(text: str) -> str:
    if not text:
        return text
    out = _SOURCE_LINE_RE.sub("", text)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()
