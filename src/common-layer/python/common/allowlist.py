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

from datetime import datetime, timezone
from typing import Any, Optional


def allowlist_key(phone_number: str) -> dict:
    return {"PK": "ALLOWLIST", "SK": f"USER#{phone_number}"}


def _expired(expires_at: Any) -> bool:
    """True when expires_at is in the past or cannot be read. Naive timestamps are UTC."""
    if not isinstance(expires_at, str) or not expires_at.strip():
        return True
    try:
        when = datetime.fromisoformat(expires_at.strip().replace("Z", "+00:00"))
    except ValueError:
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when <= datetime.now(timezone.utc)


def is_approved_user(table, phone_number: str) -> bool:
    """
    Return True only if phone_number has an allowlist row that is approved and not expired.

    - `table` is a boto3 DynamoDB Table instance (dependency-injected to avoid extra clients).
    - Fails closed: no row, approved=false, a past or unreadable expires_at, or any error.
    """
    try:
        r = table.get_item(Key=allowlist_key(phone_number))
        item = r.get("Item")
        if not item:
            return False
        if not bool(item.get("approved", True)):  # a row without the flag counts as approved
            return False
        if "expires_at" in item and _expired(item["expires_at"]):
            return False
        return True
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

