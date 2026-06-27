"""Resolve reminder/expiry cadence from an optional per-cohort rules dict.
Defaults preserve the engine's historical behavior so a payload without
`rules` behaves exactly as before (backward-compatible contract)."""
from typing import Optional, Dict, Any, List, Tuple

DEFAULT_REMINDERS: List[int] = [24, 48]
DEFAULT_EXPIRY_HOURS: int = 72


def _is_positive_number(value: Any) -> bool:
    """A valid cadence hour: a real number (not bool) strictly greater than zero."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def resolve_cadence(rules: Optional[Dict[str, Any]]) -> Tuple[List[int], int]:
    rules = rules or {}
    reminders = rules.get("reminderIntervals")
    if (isinstance(reminders, list) and len(reminders) > 0
            and all(_is_positive_number(v) for v in reminders)):
        reminders = [int(v) for v in reminders]
    else:
        reminders = list(DEFAULT_REMINDERS)
    expiry = rules.get("expiryHours")
    if not _is_positive_number(expiry):
        expiry = DEFAULT_EXPIRY_HOURS
    return reminders, int(expiry)
