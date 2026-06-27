"""Per-number, per-day usage quota for expensive demo features (vision/voice).

Layered on top of the webhook's general message rate-limit, this caps the
specific costly paths (Bedrock vision, Transcribe/Polly voice) so an open
public demo number cannot run up unbounded AI cost.

Item shape (in the existing single DynamoDB table):
- PK:  f"QUOTA#{phone_number}"
- SK:  f"{feature}#{YYYY-MM-DD}"  (UTC date)
- count: running count for that feature/day
- ttl:   epoch ~2 days out (auto-cleanup)

Design note: fails OPEN (returns True) on disable, bypass, non-positive limit,
or any error — never block the demo because of a quota issue.
"""
import os
from datetime import datetime, timezone

_DEFAULT_LIMITS = {"vision": 10, "voice": 10}
_LIMIT_ENV = {"vision": "VISION_DAILY_LIMIT", "voice": "VOICE_DAILY_LIMIT"}


def _disabled() -> bool:
    return (os.environ.get("FEATURE_QUOTA_DISABLED") or "").strip().lower() in ("1", "true", "yes")


def _bypass_phones() -> set:
    raw = os.environ.get("FEATURE_QUOTA_BYPASS_PHONES") or ""
    return {p.strip() for p in raw.split(",") if p.strip()}


def daily_limit(feature: str) -> int:
    env_name = _LIMIT_ENV.get(feature)
    default = _DEFAULT_LIMITS.get(feature, 10)
    if not env_name:
        return default
    try:
        return int(os.environ.get(env_name, default))
    except (TypeError, ValueError):
        return default


def check_feature_quota(table, phone_number: str, feature: str) -> bool:
    """Atomically increment today's counter for (phone, feature); return True if
    still within the daily limit, False if the limit is now exceeded.

    Fails OPEN (True) when disabled, bypassed, limit<=0, or on any error.
    """
    if _disabled():
        return True
    if phone_number in _bypass_phones():
        return True
    limit = daily_limit(feature)
    if limit <= 0:
        return True
    try:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        ttl = int(now.timestamp()) + 2 * 24 * 3600
        resp = table.update_item(
            Key={"PK": f"QUOTA#{phone_number}", "SK": f"{feature}#{today}"},
            UpdateExpression="ADD #c :one SET #ttl = if_not_exists(#ttl, :ttl)",
            ExpressionAttributeNames={"#c": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={":one": 1, ":ttl": ttl},
            ReturnValues="UPDATED_NEW",
        )
        count = int(resp.get("Attributes", {}).get("count", 1))
        return count <= limit
    except Exception:
        return True
