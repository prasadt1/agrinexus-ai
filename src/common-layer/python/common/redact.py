"""PII redaction helpers for logs."""


def redact_phone(phone: str) -> str:
    """Redact phone number for logging (show only first 3 digits)."""
    if not phone or len(phone) < 3:
        return "***"
    return f"{phone[:3]}***"
