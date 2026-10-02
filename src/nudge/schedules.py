"""EventBridge Scheduler names for a nudge's reminders and expiry."""
from typing import List


def _safe(nudge_id: str) -> str:
    # Schedule names allow only letters, digits, '-', '_' and '.'
    return nudge_id.replace(':', '-').replace('#', '-')


def reminder_schedule_name(nudge_id: str, hours_offset: int) -> str:
    return f'reminder-{_safe(nudge_id)}-{hours_offset}h'


def expiry_schedule_name(nudge_id: str) -> str:
    return f'expiry-{_safe(nudge_id)}'


def nudge_schedule_names(nudge_id: str) -> List[str]:
    return [
        reminder_schedule_name(nudge_id, 24),
        reminder_schedule_name(nudge_id, 48),
        expiry_schedule_name(nudge_id),
    ]


def delete_nudge_schedules(scheduler, nudge_id: str) -> None:
    """Delete every schedule for the nudge. Missing schedules are expected and ignored."""
    for name in nudge_schedule_names(nudge_id):
        try:
            scheduler.delete_schedule(Name=name)
            print(f"Deleted schedule: {name}")
        except Exception as e:
            print(f"Schedule not deleted ({name}): {e}")
