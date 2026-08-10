"""Instant, deterministic incident analysis for CPU-only workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .knowledge_base import KnowledgeChunk
from .models import LogEvent


@dataclass(frozen=True, slots=True)
class CauseRule:
    label: str
    source: str
    keywords: tuple[str, ...]


CAUSE_RULES = (
    CauseRule(
        "Database connection pool exhaustion",
        "database_connection_pool.md",
        ("connection pool exhausted", "active=50", "database connection timeout"),
    ),
    CauseRule(
        "Authentication signing-key synchronization failure",
        "authentication_failures.md",
        ("jwt signature", "signing key", "returned 401", "token validation"),
    ),
    CauseRule(
        "CPU saturation and thread-pool starvation",
        "high_cpu.md",
        ("cpu utilization", "thread-pool-starvation", "returned 504", "worker queue"),
    ),
)


def detect_cause(events: Sequence[LogEvent]) -> tuple[CauseRule | None, list[LogEvent]]:
    """Select the rule with the most direct matching log evidence."""

    best_rule: CauseRule | None = None
    best_matches: list[LogEvent] = []
    for rule in CAUSE_RULES:
        matches = [
            event
            for event in events
            if any(keyword in event.message.lower() for keyword in rule.keywords)
        ]
        if len(matches) > len(best_matches):
            best_rule = rule
            best_matches = matches
    return best_rule, best_matches


def build_quick_report(
    events: Sequence[LogEvent], runbooks: Sequence[KnowledgeChunk]
) -> str:
    """Create a source-labelled report without invoking an LLM."""

    rule, cause_events = detect_cause(events)
    serious = [
        event for event in events if event.level in {"WARNING", "ERROR", "CRITICAL"}
    ]
    if rule is None:
        cause_label = "Insufficient evidence for a known root-cause pattern"
        cause_citations = "No matching rule"
        confidence = "Low"
    else:
        cause_label = rule.label
        cause_citations = " ".join(f"[L{event.line_number}]" for event in cause_events[:3])
        confidence = "High" if len(cause_events) >= 2 else "Medium"

    first_seen: dict[str, LogEvent] = {}
    for event in serious:
        first_seen.setdefault(event.service, event)
    propagation = "\n".join(
        f"- **{event.timestamp.strftime('%H:%M:%S')} — {service}:** "
        f"{event.message} [L{event.line_number}]"
        for service, event in first_seen.items()
    )

    selected_actions = [
        chunk
        for chunk in runbooks
        if chunk.heading.lower() in {"immediate response", "prevention"}
    ]
    if not selected_actions:
        selected_actions = list(runbooks[:2])
    actions = "\n".join(
        f"- **{chunk.heading}:** {chunk.content} [R{index}]"
        for index, chunk in enumerate(selected_actions, start=1)
    ) or "- No matching local runbook guidance was found."

    return f"""## Executive summary
FaultTrace detected **{cause_label}** as the probable software incident pattern {cause_citations}.

## Probable root cause
{cause_label}. This conclusion is rule-based and derived directly from matching log evidence: {cause_citations}.

## Impact and propagation
{propagation}

## Recommended actions
{actions}

## Confidence
**{confidence}.** The quick report uses deterministic patterns and does not invoke the language model.
"""

