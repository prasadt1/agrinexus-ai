"""
re:Invent 2026 visitor path helpers.

Trigger: first message from an unknown number containing "re:invent" or "reinvent".
Caps: atomic DynamoDB counters (per-visitor/day + global/day).
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from botocore.exceptions import ClientError

_TRIGGER_RE = re.compile(r"re:?invent", re.IGNORECASE)

CAP_MSG = (
    "Thanks for trying AgriNexus AI. Today's visitor demo limit has been reached. "
    "Please come back tomorrow, or try the web demo at https://demo.agrinexus-ai.farm/"
)

DELETE_CONFIRM_MSG = (
    "Your AgriNexus demo data for this number has been deleted "
    "(profile and conversation history). Send a new message anytime to start again."
)

VISITOR_WELCOME = (
    "Welcome from re:Invent — this is a deployed AgriNexus AI demo prototype "
    "(no farmer cohort yet). Ask in English about crops, pests, weather, or soil, "
    "or pick a sample question below. Send DELETE anytime to erase your demo data. "
    "Want the full farmer onboarding instead? Choose \"Continue as farmer\"."
)

# list_reply ids (stable) — titles shown in WhatsApp
SAMPLE_QUESTIONS = [
    ("vq_whitefly", "How do I control whitefly on cotton?"),
    ("vq_yellowing", "Why are my wheat leaves yellowing?"),
    ("vq_spray", "When is it safe to spray after rain?"),
    ("vq_bollworm", "How do I manage bollworm on cotton?"),
    ("vq_irrigation", "How often should I irrigate soybean?"),
]

SAMPLE_PHOTO_ID = "vq_sample_photo"
FARMER_ONBOARD_ID = "vq_farmer_onboard"

SAMPLE_QUESTION_BY_ID = {qid: title for qid, title in SAMPLE_QUESTIONS}
SAMPLE_QUESTION_BY_TITLE = {title.lower(): title for _, title in SAMPLE_QUESTIONS}


def visitor_ttl_days() -> int:
    try:
        return max(1, int(os.environ.get("VISITOR_TTL_DAYS", "7")))
    except ValueError:
        return 7


def visitor_global_cap() -> int:
    try:
        return max(1, int(os.environ.get("VISITOR_DAILY_GLOBAL_CAP", "300")))
    except ValueError:
        return 300


def visitor_per_user_cap() -> int:
    try:
        return max(1, int(os.environ.get("VISITOR_DAILY_PER_USER_CAP", "10")))
    except ValueError:
        return 10


def matches_reinvent_trigger(text: str) -> bool:
    if not text:
        return False
    return bool(_TRIGGER_RE.search(text))


def is_visitor_profile(profile: Optional[Dict[str, Any]]) -> bool:
    if not profile:
        return False
    return str(profile.get("demo_tier") or "") == "visitor"


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ttl_epoch(days: Optional[int] = None) -> int:
    d = visitor_ttl_days() if days is None else days
    return int(time.time()) + (d * 24 * 60 * 60)


def create_visitor_profile(table, phone_number: str) -> Dict[str, Any]:
    """Create a completed visitor profile (skips farmer onboarding)."""
    item = {
        "PK": f"USER#{phone_number}",
        "SK": "PROFILE",
        "phone_number": phone_number,
        "dialect": "en",
        "demo_tier": "visitor",
        "source": "reinvent-2026",
        "onboarding_complete": True,
        "consent": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ttl": _ttl_epoch(),
    }
    table.put_item(Item=item)
    return item


def visitor_welcome_list() -> Dict[str, Any]:
    """Payload for send_whatsapp_list."""
    rows = [{"id": qid, "title": title[:24], "description": title} for qid, title in SAMPLE_QUESTIONS]
    rows.append(
        {
            "id": SAMPLE_PHOTO_ID,
            "title": "Photo diagnosis",
            "description": "Show me a photo diagnosis (sample crop image)",
        }
    )
    rows.append(
        {
            "id": FARMER_ONBOARD_ID,
            "title": "Continue as farmer",
            "description": "Start the full farmer onboarding flow",
        }
    )
    return {
        "type": "list",
        "content": VISITOR_WELCOME,
        "button_text": "Sample questions",
        "sections": [{"title": "Try AgriNexus", "rows": rows[:10]}],
    }


def resolve_sample_question(text_or_id: str) -> Optional[str]:
    """Map list id or title to the full English question text."""
    raw = (text_or_id or "").strip()
    if not raw:
        return None
    if raw == SAMPLE_PHOTO_ID or raw.lower() in ("photo diagnosis", "show me a photo diagnosis"):
        return None  # photo path handled separately
    if raw in SAMPLE_QUESTION_BY_ID:
        return SAMPLE_QUESTION_BY_ID[raw]
    if raw.lower() in SAMPLE_QUESTION_BY_TITLE:
        return SAMPLE_QUESTION_BY_TITLE[raw.lower()]
    # Partial title match from WhatsApp truncating to 24 chars
    for qid, title in SAMPLE_QUESTIONS:
        if title.startswith(raw) or raw.startswith(title[:20]):
            return title
    return None


def is_sample_photo_selection(text_or_id: str) -> bool:
    raw = (text_or_id or "").strip().lower()
    return raw in (SAMPLE_PHOTO_ID, "photo diagnosis", "show me a photo diagnosis")


def is_farmer_onboard_selection(text_or_id: str) -> bool:
    raw = (text_or_id or "").strip().lower()
    return raw in (FARMER_ONBOARD_ID, "continue as farmer")


def is_delete_command(text: str) -> bool:
    t = (text or "").strip().upper()
    return t in ("DELETE", "DELETE MY DATA")


def delete_user_conversation_data(table, phone_number: str) -> int:
    """
    Delete PROFILE, MSG#*, NUDGE#*, PENDING#*, and per-user visitor counters.
    Does not remove ALLOWLIST rows.
    Returns number of items deleted.
    """
    pk = f"USER#{phone_number}"
    deleted = 0
    start_key = None
    while True:
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": "PK = :pk",
            "ExpressionAttributeValues": {":pk": pk},
            "ProjectionExpression": "PK, SK",
        }
        if start_key:
            kwargs["ExclusiveStartKey"] = start_key
        resp = table.query(**kwargs)
        for item in resp.get("Items") or []:
            table.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})
            deleted += 1
        start_key = resp.get("LastEvaluatedKey")
        if not start_key:
            break

    # Per-user daily counters (current + recent days not required; scan by known key pattern for today)
    day = _utc_day()
    table.delete_item(
        Key={"PK": f"COUNTER#visitor#{phone_number}", "SK": f"DAY#{day}"},
    )
    return deleted


def try_consume_visitor_answer(
    table,
    phone_number: str,
    *,
    bypass: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Atomically consume one visitor answer quota.
    Returns (allowed, reason) where reason is 'user'|'global'|None.
    Allowlisted / bypass callers should pass bypass=True.
    """
    if bypass:
        return True, None

    day = _utc_day()
    ttl = _ttl_epoch(2)  # counters linger briefly past the day
    user_max = visitor_per_user_cap()
    global_max = visitor_global_cap()

    # Per-user first
    try:
        table.update_item(
            Key={"PK": f"COUNTER#visitor#{phone_number}", "SK": f"DAY#{day}"},
            UpdateExpression="ADD #c :one SET #ttl = :ttl, #kind = :kind",
            ConditionExpression="attribute_not_exists(#c) OR #c < :max",
            ExpressionAttributeNames={"#c": "count", "#ttl": "ttl", "#kind": "kind"},
            ExpressionAttributeValues={
                ":one": 1,
                ":max": user_max,
                ":ttl": ttl,
                ":kind": "visitor_user_day",
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False, "user"
        raise

    # Global
    try:
        table.update_item(
            Key={"PK": "COUNTER#visitor-answers", "SK": f"DAY#{day}"},
            UpdateExpression="ADD #c :one SET #ttl = :ttl, #kind = :kind",
            ConditionExpression="attribute_not_exists(#c) OR #c < :max",
            ExpressionAttributeNames={"#c": "count", "#ttl": "ttl", "#kind": "kind"},
            ExpressionAttributeValues={
                ":one": 1,
                ":max": global_max,
                ":ttl": ttl,
                ":kind": "visitor_global_day",
            },
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # Best-effort rollback of user counter
            try:
                table.update_item(
                    Key={"PK": f"COUNTER#visitor#{phone_number}", "SK": f"DAY#{day}"},
                    UpdateExpression="ADD #c :neg",
                    ExpressionAttributeNames={"#c": "count"},
                    ExpressionAttributeValues={":neg": -1},
                )
            except Exception:
                pass
            return False, "global"
        raise

    return True, None


def emit_visitor_metric(cloudwatch, name: str, value: float = 1.0) -> None:
    try:
        cloudwatch.put_metric_data(
            Namespace="AgriNexus/Visitor",
            MetricData=[{"MetricName": name, "Value": value, "Unit": "Count"}],
        )
    except Exception as e:
        print(f"Failed to emit visitor metric {name}: {e}")
