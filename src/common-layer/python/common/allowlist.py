"""
Simple DynamoDB-backed allowlist for gating expensive WhatsApp features.

Item shape (in the existing single DynamoDB table):
- PK: "ALLOWLIST"
- SK: f"USER#{phone_number}"
- approved: true
- approved_at: ISO timestamp (optional)
- expires_at: ISO timestamp (optional)
"""

from __future__ import annotations

from typing import Optional


def allowlist_key(phone_number: str) -> dict:
    return {"PK": "ALLOWLIST", "SK": f"USER#{phone_number}"}


def is_approved_user(table, phone_number: str) -> bool:
    """
    Return True if phone_number exists in allowlist.

    - `table` is a boto3 DynamoDB Table instance (dependency-injected to avoid extra clients).
    - Fails closed on unexpected errors (safer for cost control).
    """
    try:
        r = table.get_item(Key=allowlist_key(phone_number))
        item = r.get("Item") or {}
        return bool(item.get("approved", True))  # presence implies approved unless explicitly false
    except Exception:
        return False


def allowlist_expiry_hint(dialect: str) -> str:
    """Short hint used in gating messages (kept intentionally brief)."""
    msg = {
        "hi": "यह सुविधा मूल्यांकन (allowlist) के लिए सक्षम है।",
        "mr": "हे फिचर मूल्यांकनासाठी (allowlist) सक्षम आहे.",
        "te": "ఈ ఫీచర్ మూల్యాంకనానికి (allowlist) అందుబాటులో ఉంది.",
        "en": "This feature is enabled for evaluators (allowlist).",
    }
    return msg.get(dialect, msg["en"])

