"""Central redaction helpers for logs, APIs, and audit events."""

from __future__ import annotations

import hashlib
import re
from typing import Any

SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,\"']+"),
    re.compile(r"(?i)((?:api[_-]?key|token|password|secret|webhook)\s*[:=]\s*)[^\s,\"']+"),
    re.compile(r"\b(?:sk|ghp|xox[baprs])-[-A-Za-z0-9_]{8,}\b"),
)


def stable_scope_hash(value: str) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest()[:16] if value else None


def redact_text(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(lambda match: (match.group(1) if match.lastindex else "") + "[REDACTED]", result)
    return result


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if any(marker in key.lower() for marker in ("password", "secret", "token", "authorization", "api_key", "webhook")):
                result[key] = "[REDACTED]" if item else item
            else:
                result[key] = redact(item)
        return result
    return value
