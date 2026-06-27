"""Resolve reminder/expiry cadence from an optional per-cohort rules dict.
Defaults preserve the engine's historical behavior so a payload without
`rules` behaves exactly as before (backward-compatible contract)."""
from typing import Optional, Dict, Any, List, Tuple

DEFAULT_REMINDERS: List[int] = [24, 48]
DEFAULT_EXPIRY_HOURS: int = 72

def resolve_cadence(rules: Optional[Dict[str, Any]]) -> Tuple[List[int], int]:
    rules = rules or {}
    reminders = rules.get("reminderIntervals")
    if not isinstance(reminders, list) or len(reminders) == 0:
        reminders = DEFAULT_REMINDERS
    expiry = rules.get("expiryHours")
    if isinstance(expiry, bool) or not isinstance(expiry, (int, float)):
        expiry = DEFAULT_EXPIRY_HOURS
    return reminders, int(expiry)
