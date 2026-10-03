"""PII redaction helpers for logs.

Logs are kept 90 days. Visitor records expire after 7 days and are erased on DELETE.
So log lines carry no message text, no full phone number and no raw WhatsApp message ID.
"""
import hashlib
import os
import re


def redact_phone(phone: str) -> str:
    """Redact phone number for logging (show only first 3 digits)."""
    if not phone or len(phone) < 3:
        return "***"
    return f"{phone[:3]}***"


def text_for_log(text, limit: int = 50) -> str:
    """How message or reply text appears in a log line: its length only.

    For a debugging session with a test number, set LOG_TEXT_PREVIEW=true on the function
    to log the first `limit` characters again. The template does not set it, so the next
    `sam deploy` switches it off.
    """
    text = text if isinstance(text, str) else ("" if text is None else str(text))
    if os.environ.get("LOG_TEXT_PREVIEW", "").strip().lower() == "true":
        return f"{text[:limit]!r} ({len(text)} characters)"
    return f"{len(text)} characters"


def message_ref(wamid) -> str:
    """Short one-way reference to a WhatsApp message ID, for log lines.

    A wamid is base64 with the other party's full phone number inside it in plain digits,
    so logging one logs the number. The same wamid always gives the same reference, which
    is enough to follow one message from the webhook to the processor.
    """
    if not wamid:
        return "msg-none"
    return "msg-" + hashlib.sha256(str(wamid).encode("utf-8")).hexdigest()[:12]


def scrub_numbers(text) -> str:
    """Mask every run of 7 or more digits in third-party text before it is logged.

    Used for the error body Meta returns when a send fails, in case it echoes the
    recipient's number. Error codes are shorter and stay readable.
    """
    text = text if isinstance(text, str) else ("" if text is None else str(text))
    return re.sub(r"\d{7,}", lambda m: m.group()[:3] + "***", text)
