"""Local redaction of common sensitive values in log messages."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Sequence

from .models import LogEvent


REDACTION_PATTERNS = (
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[REDACTED_IP]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\btoken\s*[=:]\s*[A-Za-z0-9._~+/=-]{8,}"), "token=[REDACTED]"),
    (
        re.compile(r"(?i)\b(password|passwd|api[_-]?key|secret)\s*[=:]\s*[^\s,;]+"),
        r"\1=[REDACTED]",
    ),
)


def redact_text(text: str) -> tuple[str, int]:
    """Mask sensitive patterns and return the number of replacements."""

    redacted = text
    count = 0
    for pattern, replacement in REDACTION_PATTERNS:
        redacted, replacements = pattern.subn(replacement, redacted)
        count += replacements
    return redacted, count


def redact_events(events: Sequence[LogEvent]) -> tuple[list[LogEvent], int]:
    """Return copies of events with redacted messages and raw lines."""

    result: list[LogEvent] = []
    total = 0
    for event in events:
        message, message_count = redact_text(event.message)
        raw_line, raw_count = redact_text(event.raw_line)
        result.append(replace(event, message=message, raw_line=raw_line))
        total += max(message_count, raw_count)
    return result, total
