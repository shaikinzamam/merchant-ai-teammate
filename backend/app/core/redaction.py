"""PII / secret redaction shared by logging and the audit trail."""
from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "account_number", "bank_account", "phone", "mobile", "otp", "pin", "password",
        "pan", "aadhaar", "api_key", "token", "secret", "authorization", "x-api-key",
        "x-operator-key",
    }
)
_LONG_DIGITS = re.compile(r"\b\d{9,}\b")
MASK = "[REDACTED]"


def redact_text(value: str) -> str:
    return _LONG_DIGITS.sub(MASK, value)


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: (MASK if str(k).lower() in SENSITIVE_KEYS else redact(v)) for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj
