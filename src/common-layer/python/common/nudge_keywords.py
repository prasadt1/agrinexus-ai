"""
DONE / NOT YET keyword matching for nudge replies.

Exact match on normalized short messages only — substring matching silently
drops ordinary questions that merely contain these tokens (e.g. "later" in a
longer sentence, or Marathi "केला" inside unrelated text).
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence

# DONE keywords by dialect
DONE_KEYWORDS = {
    "hi": ["हो गया", "कर दिया", "हो गया है", "कर लिया", "done", "completed"],
    "mr": ["झाला", "केला", "पूर्ण झाला", "done"],
    "te": ["అయ్యింది", "చేశాను", "పూర్తయింది", "done"],
    "en": ["done", "completed", "finished"],
}

NOT_YET_KEYWORDS = {
    "hi": ["अभी नहीं", "बाद में", "नहीं किया", "not yet", "later"],
    "mr": ["नाही झाला", "नंतर", "अजून नाही", "not yet"],
    "te": ["ఇంకా లేదు", "తర్వాత", "చేయలేదు", "not yet"],
    "en": ["not yet", "later", "not done", "not now"],
}

# Flat list used by webhook skip-RAG (all dialects)
SKIP_RAG_KEYWORDS: List[str] = []
for _dialect_map in (DONE_KEYWORDS, NOT_YET_KEYWORDS):
    for _words in _dialect_map.values():
        SKIP_RAG_KEYWORDS.extend(_words)
# Preserve order, drop duplicates
SKIP_RAG_KEYWORDS = list(dict.fromkeys(SKIP_RAG_KEYWORDS))

_MAX_WORDS = 4
_MAX_CHARS = 40


def normalize_message(text: Optional[str]) -> str:
    """Lowercase, collapse whitespace, strip common trailing punctuation."""
    if not text:
        return ""
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = t.strip(".,!?;:。…")
    return t


def _keyword_set(keywords: Iterable[str]) -> set:
    return {normalize_message(k) for k in keywords if k}


def is_exact_keyword_match(
    text: Optional[str],
    keywords: Sequence[str],
    *,
    max_words: int = _MAX_WORDS,
    max_chars: int = _MAX_CHARS,
) -> bool:
    """
    True only when the entire normalized message equals one keyword and is short.

    Longer or partial matches fall through to the normal handler.
    """
    norm = normalize_message(text)
    if not norm:
        return False
    if len(norm) > max_chars:
        return False
    if len(norm.split()) > max_words:
        return False
    return norm in _keyword_set(keywords)


def is_nudge_reply(text: Optional[str]) -> bool:
    """True if text is an exact short DONE or NOT YET reply."""
    return is_exact_keyword_match(text, SKIP_RAG_KEYWORDS)


def is_done_reply(text: Optional[str]) -> bool:
    flat: List[str] = []
    for words in DONE_KEYWORDS.values():
        flat.extend(words)
    return is_exact_keyword_match(text, flat)


def is_not_yet_reply(text: Optional[str]) -> bool:
    flat: List[str] = []
    for words in NOT_YET_KEYWORDS.values():
        flat.extend(words)
    return is_exact_keyword_match(text, flat)
