"""Parse common application log formats into normalized events."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import LogEvent


LOG_PATTERN = re.compile(
    r"^\s*"
    r"(?P<timestamp>\d{4}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d:[0-5]\d(?:[.,]\d{1,6})?Z?)"
    r"\s+(?:\[)?(?P<level>TRACE|DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)(?:\])?"
    r"\s+(?:\[)?(?P<service>[A-Za-z0-9_.-]+)(?:\])?"
    r"\s*(?:-|:)?\s*(?P<message>.+?)\s*$",
    re.IGNORECASE,
)

LEVEL_ALIASES = {
    "WARN": "WARNING",
    "FATAL": "CRITICAL",
}

JSON_FIELD_ALIASES = {
    "timestamp": ("timestamp", "time", "@timestamp", "datetime"),
    "level": ("level", "severity", "log_level"),
    "service": ("service", "service_name", "logger", "component"),
    "message": ("message", "msg", "event"),
}


def _parse_timestamp(value: str) -> datetime:
    normalized = value.rstrip("Z").replace(",", ".")
    return datetime.fromisoformat(normalized)


def _first_json_value(payload: dict[str, object], field: str) -> object | None:
    for candidate in JSON_FIELD_ALIASES[field]:
        if candidate in payload:
            return payload[candidate]
    return None


def _parse_json_event(raw_line: str, line_number: int) -> LogEvent | None:
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    timestamp = _first_json_value(payload, "timestamp")
    level = _first_json_value(payload, "level")
    service = _first_json_value(payload, "service")
    message = _first_json_value(payload, "message")
    if not all(isinstance(value, str) and value.strip() for value in (timestamp, level, service, message)):
        return None

    normalized_level = str(level).upper()
    if normalized_level not in LEVEL_ALIASES and normalized_level not in {
        "TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    }:
        return None

    try:
        parsed_timestamp = _parse_timestamp(str(timestamp))
    except ValueError:
        return None

    return LogEvent(
        timestamp=parsed_timestamp,
        level=LEVEL_ALIASES.get(normalized_level, normalized_level),
        service=str(service),
        message=str(message),
        raw_line=raw_line,
        line_number=line_number,
    )


def parse_log_lines(lines: Iterable[str]) -> tuple[list[LogEvent], list[str]]:
    """Parse log lines and return normalized events plus rejected lines.

    Blank lines are ignored. Non-empty lines that do not match the supported
    format are returned so the UI can report them instead of silently losing
    input data.
    """

    events: list[LogEvent] = []
    rejected: list[str] = []

    for line_number, raw_line in enumerate(lines, start=1):
        raw_line = raw_line.rstrip("\r\n")
        if not raw_line.strip():
            continue

        json_event = _parse_json_event(raw_line, line_number) if raw_line.lstrip().startswith("{") else None
        if json_event is not None:
            events.append(json_event)
            continue

        match = LOG_PATTERN.match(raw_line)
        if match is None:
            rejected.append(raw_line)
            continue

        level = match.group("level").upper()
        try:
            parsed_timestamp = _parse_timestamp(match.group("timestamp"))
        except ValueError:
            rejected.append(raw_line)
            continue
        events.append(
            LogEvent(
                timestamp=parsed_timestamp,
                level=LEVEL_ALIASES.get(level, level),
                service=match.group("service"),
                message=match.group("message"),
                raw_line=raw_line,
                line_number=line_number,
            )
        )

    events.sort(key=lambda event: (event.timestamp, event.line_number))
    return events, rejected


def parse_log_file(path: str | Path) -> tuple[list[LogEvent], list[str]]:
    """Read and parse a UTF-8 log file."""

    log_path = Path(path)
    with log_path.open("r", encoding="utf-8-sig", errors="replace") as stream:
        return parse_log_lines(stream)
