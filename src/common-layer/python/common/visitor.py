"""
re:Invent 2026 visitor path helpers.

Trigger: first message from an unknown number containing "re:invent" or "reinvent".
Caps: atomic DynamoDB counters (per-visitor/day + global/day).
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from botocore.exceptions import ClientError

_TRIGGER_RE = re.compile(r"re:?invent", re.IGNORECASE)

CAP_MSG = (
    "Thanks for trying AgriNexus AI. Today's visitor demo limit has been reached. "
    "Please come back tomorrow, or try the web demo at https://demo.agrinexus-ai.farm/"
)

DELETE_CONFIRM_MSG = (
    "Your AgriNexus demo data for this number has been deleted "
    "(profile, conversation history, and any photos or voice notes we stored). "
    "Send a new message anytime to start again."
)

# A visitor who sends any other first message would start farmer onboarding, so say how to come back.
VISITOR_DELETE_CONFIRM_MSG = (
    "Your AgriNexus demo data for this number has been deleted "
    "(profile, conversation history, and any photos we stored). "
    "To start again, send: Hi from re:Invent"
)

# The landing page (docs/try/) promises visitors a 7-day expiry and no proactive messages.
# The welcome therefore offers no way into farmer onboarding, which keeps rows for 90 days.
VISITOR_WELCOME = (
    "Welcome from re:Invent. This is a deployed AgriNexus AI demo prototype "
    "(no farmer cohort yet). Ask in English about crops, pests, weather, or soil, "
    "or pick a sample question below. You can also send a crop photo. "
    "Send DELETE anytime to erase your demo data."
)

# (list_reply id, row title, full question). WhatsApp shows the title in the list and in the
# visitor's chat bubble and allows 24 characters, so each row has its own short title instead
# of a question cut off mid-word. The description under it carries the full question (72 max).
SAMPLE_QUESTIONS = [
    ("vq_whitefly", "Whitefly on cotton", "How do I control whitefly on cotton?"),
    ("vq_yellowing", "Yellow wheat leaves", "Why are my wheat leaves yellowing?"),
    ("vq_spray", "Spraying after rain", "When is it safe to spray after rain?"),
    ("vq_bollworm", "Bollworm on cotton", "How do I manage bollworm on cotton?"),
    ("vq_irrigation", "Irrigating soybean", "How often should I irrigate soybean?"),
]

SAMPLE_PHOTO_ID = "vq_sample_photo"

SAMPLE_QUESTION_BY_ID = {qid: question for qid, _title, question in SAMPLE_QUESTIONS}
# Typed instead of tapped: the row title or the full question, in any letter case.
SAMPLE_QUESTION_BY_TEXT = {
    text.lower(): question
    for _qid, title, question in SAMPLE_QUESTIONS
    for text in (title, question)
}


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


# The landing page types "Hi from re:Invent" (17 characters). A visitor who presses its button
# a second time sends that greeting again; a real question that mentions re:Invent is longer.
GREETING_MAX_CHARS = 40


def is_visitor_greeting(text: str) -> bool:
    """The trigger phrase sent as a short greeting, not inside a longer question."""
    stripped = (text or "").strip()
    return len(stripped) <= GREETING_MAX_CHARS and matches_reinvent_trigger(stripped)


def is_visitor_profile(profile: Optional[Dict[str, Any]]) -> bool:
    if not profile:
        return False
    return str(profile.get("demo_tier") or "") == "visitor"


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ttl_epoch(days: Optional[int] = None) -> int:
    d = visitor_ttl_days() if days is None else days
    return int(time.time()) + (d * 24 * 60 * 60)


def unfinished_signup_expiry() -> int:
    """Epoch expiry for a farmer sign-up that is not finished: the visitor expiry (default 7 days).

    Anyone can message the public number. Without this, a number that sent one message and
    never finished the sign-up stayed in the table for good.
    """
    return _ttl_epoch()


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
    rows = [{"id": qid, "title": title, "description": question} for qid, title, question in SAMPLE_QUESTIONS]
    rows.append(
        {
            "id": SAMPLE_PHOTO_ID,
            "title": "Photo diagnosis",
            "description": "Show me a photo diagnosis (sample crop image)",
        }
    )
    return {
        "type": "list",
        "content": VISITOR_WELCOME,
        "button_text": "Sample questions",
        "sections": [{"title": "Try AgriNexus", "rows": rows[:10]}],
    }


def resolve_sample_question(text_or_id: str) -> Optional[str]:
    """Map a list id, a row title or a full sample question to the full English question.

    Exact matches only. A prefix match used to turn a visitor's own message such as "How"
    or "Why" into a sample question.
    """
    raw = (text_or_id or "").strip()
    if not raw:
        return None
    if raw in SAMPLE_QUESTION_BY_ID:
        return SAMPLE_QUESTION_BY_ID[raw]
    return SAMPLE_QUESTION_BY_TEXT.get(raw.lower())


def is_sample_photo_selection(text_or_id: str) -> bool:
    raw = (text_or_id or "").strip().lower()
    return raw in (SAMPLE_PHOTO_ID, "photo diagnosis", "show me a photo diagnosis")


def is_delete_command(text: str) -> bool:
    t = (text or "").strip().upper()
    return t in ("DELETE", "DELETE MY DATA")


def delete_user_conversation_data(table, phone_number: str) -> int:
    """
    Delete every row keyed by this number: PROFILE, MSG#*, NUDGE#*, PENDING#*, and the
    per-user visitor counters. (WAMID# dedup rows are keyed by a hash and hold no number.)
    Does not remove ALLOWLIST rows.
    Returns number of USER# items deleted.
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

    # Per-user daily counters live 2 days past their last update, so up to three can exist.
    today = datetime.now(timezone.utc)
    for days_back in range(3):
        day = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
        table.delete_item(
            Key={"PK": f"COUNTER#visitor#{phone_number}", "SK": f"DAY#{day}"},
        )
    return deleted


def delete_user_media_objects(s3_client, bucket: str, phone_number: str) -> int:
    """
    Delete S3 objects under images/{phone}/, voice/{phone}/ and voice-output/{phone}/.
    Returns number of objects deleted. No-op if bucket or phone is empty.
    """
    if not bucket or not phone_number:
        return 0
    phone = str(phone_number).lstrip("+")
    deleted = 0
    for prefix in (f"images/{phone}/", f"voice/{phone}/", f"voice-output/{phone}/"):
        continuation = None
        while True:
            kwargs: Dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
            if continuation:
                kwargs["ContinuationToken"] = continuation
            resp = s3_client.list_objects_v2(**kwargs)
            keys = [{"Key": obj["Key"]} for obj in (resp.get("Contents") or []) if obj.get("Key")]
            if keys:
                # delete_objects accepts up to 1000 keys
                for i in range(0, len(keys), 1000):
                    chunk = keys[i : i + 1000]
                    s3_client.delete_objects(Bucket=bucket, Delete={"Objects": chunk, "Quiet": True})
                    deleted += len(chunk)
            if not resp.get("IsTruncated"):
                break
            continuation = resp.get("NextContinuationToken")
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
