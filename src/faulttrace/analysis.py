"""Grounded prompt construction for local incident analysis."""

from __future__ import annotations

from typing import Sequence

from .knowledge_base import KnowledgeChunk
from .models import LogEvent


SYSTEM_PROMPT = """You are a software site reliability engineer reviewing a production incident.
Use only the LOG EVIDENCE and RUNBOOK EVIDENCE supplied by the user.
Never interpret the event as a legal, criminal, medical, or physical incident.
Do not invent metrics, causes, services, actions, or events.
Treat a root cause as probable unless the evidence proves it conclusively.
Every factual claim about the incident must cite one or more log line labels such as [L5].
Runbook guidance must cite its source label such as [R1].
The service name after each log label is authoritative. Never attribute that event to a different service.
In chronological lists, cite the exact log line for every listed event.
If evidence is insufficient, say so explicitly.
Write concise technical English in Markdown.
"""


def build_incident_query(events: Sequence[LogEvent]) -> str:
    """Create the semantic-search query from serious incident events."""

    serious = [
        f"{event.service}: {event.message}"
        for event in events
        if event.level in {"WARNING", "ERROR", "CRITICAL"}
    ]
    return "\n".join(serious)


def build_analysis_prompt(
    events: Sequence[LogEvent], runbook_chunks: Sequence[KnowledgeChunk]
) -> str:
    """Build a compact, source-labelled RAG prompt."""

    log_evidence = "\n".join(
        f"[L{event.line_number}] {event.timestamp.isoformat(sep=' ')} "
        f"{event.level} {event.service}: {event.message}"
        for event in events
        if event.level in {"WARNING", "ERROR", "CRITICAL"}
    )
    runbook_evidence = "\n\n".join(
        f"[R{index}] Source: {chunk.source}, section: {chunk.heading}\n{chunk.content}"
        for index, chunk in enumerate(runbook_chunks, start=1)
    )

    return f"""Analyze this SOFTWARE SYSTEM incident.

LOG EVIDENCE
{log_evidence}

RUNBOOK EVIDENCE
{runbook_evidence}

Return exactly these sections:
## Executive summary
Two sentences maximum.

## Probable root cause
State one probable root cause and cite the strongest log evidence.

## Impact and propagation
Explain the affected services in chronological order. Preserve the exact service name from each log line and cite that line.

## Recommended actions
Give 3-5 concrete actions grounded in the runbook evidence, with runbook citations.

## Confidence
Write High, Medium, or Low and explain the main uncertainty in one sentence.
"""
