"""Core data models used by the FaultTrace pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class LogEvent:
    """A normalized event parsed from one log line."""

    timestamp: datetime
    level: str
    service: str
    message: str
    raw_line: str
    line_number: int

