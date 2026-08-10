"""Deterministic incident scoring and failure-chain helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import LogEvent


@dataclass(frozen=True, slots=True)
class IncidentScore:
    value: int
    label: str
    explanation: str


LEVEL_WEIGHTS = {
    "TRACE": 0,
    "DEBUG": 0,
    "INFO": 0,
    "WARNING": 3,
    "ERROR": 8,
    "CRITICAL": 18,
}


def calculate_incident_score(events: Sequence[LogEvent]) -> IncidentScore:
    """Calculate an explainable 0-100 operational impact score."""

    if not events:
        return IncidentScore(0, "None", "No parsed events.")

    serious = [event for event in events if event.level in {"WARNING", "ERROR", "CRITICAL"}]
    affected_services = {event.service for event in serious}
    severity_points = sum(LEVEL_WEIGHTS.get(event.level, 0) for event in serious)
    spread_points = max(0, len(affected_services) - 1) * 6
    value = min(100, severity_points + spread_points)

    if value >= 70:
        label = "Severe"
    elif value >= 45:
        label = "High"
    elif value >= 20:
        label = "Moderate"
    else:
        label = "Low"

    explanation = (
        f"{len(serious)} serious events across {len(affected_services)} services; "
        f"severity points {severity_points}, propagation points {spread_points}."
    )
    return IncidentScore(value, label, explanation)


def build_failure_chain(events: Sequence[LogEvent]) -> list[LogEvent]:
    """Return serious events in chronological order for visual propagation."""

    return [
        event
        for event in events
        if event.level in {"WARNING", "ERROR", "CRITICAL"}
    ]

