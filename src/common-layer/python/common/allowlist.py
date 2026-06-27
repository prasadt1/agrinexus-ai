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
    """The public demo is intentionally OPEN — every user may use every feature.

    Cost on expensive paths (vision/voice) is capped per-number/day by
    common.quota; inbound volume is capped by the webhook message rate-limit.
    Retained as a True-returning shim so any remaining caller stays open.
    The `table`/`phone_number` params are kept for call-site compatibility.
    """
    return True


def allowlist_expiry_hint(dialect: str) -> str:
    """Short hint used in gating messages (kept intentionally brief)."""
    msg = {
        "hi": "यह सुविधा मूल्यांकन (allowlist) के लिए सक्षम है।",
        "mr": "हे फिचर मूल्यांकनासाठी (allowlist) सक्षम आहे.",
        "te": "ఈ ఫీచర్ మూల్యాంకనానికి (allowlist) అందుబాటులో ఉంది.",
        "en": "This feature is enabled for evaluators (allowlist).",
    }
    return msg.get(dialect, msg["en"])

