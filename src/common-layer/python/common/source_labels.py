"""
Names for the documents a knowledge-base answer cites.

A document's title comes from its metadata attribute "title", which Bedrock returns in
retrievedReferences[].metadata when the file has a "<file>.metadata.json" sidecar in the
data source bucket (scripts/kb-titles.py writes these). Without one, the file name is used.
"""
from __future__ import annotations

from typing import Any, List


def _title(ref: dict) -> str:
    meta = ref.get("metadata") or {}
    title = meta.get("title")
    if isinstance(title, str) and title.strip():
        return " ".join(title.split())
    uri = ((ref.get("location") or {}).get("s3Location") or {}).get("uri") or ""
    return uri.rstrip("/").split("/")[-1]


def source_labels(citations: Any) -> List[str]:
    """Distinct document names in citation order."""
    labels: List[str] = []
    for citation in citations or []:
        for ref in citation.get("retrievedReferences") or []:
            name = _title(ref)
            if name and name not in labels:
                labels.append(name)
    return labels


SOURCE_KEYWORDS = {"hi": "स्रोत:", "mr": "स्त्रोत:", "te": "మూలం:", "en": "Source:"}


def source_line(labels: List[str], dialect: str, max_show: int = 5) -> str:
    if not labels:
        return ""
    tail = ", ".join(labels[:max_show]) + (" …" if len(labels) > max_show else "")
    return f"{SOURCE_KEYWORDS.get(dialect, 'Source:')} {tail}"
