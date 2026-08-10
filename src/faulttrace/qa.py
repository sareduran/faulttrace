"""Source-grounded question answering for the active software incident."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable, Sequence

from .knowledge_base import KnowledgeBase, KnowledgeChunk
from .models import LogEvent


DEFAULT_RELEVANCE_THRESHOLD = 0.48

QA_SYSTEM_PROMPT = """You are FaultTrace, an offline software incident assistant.
Answer only from the supplied LOG EVIDENCE and RUNBOOK EVIDENCE.
Do not use outside knowledge or invent facts, causes, commands, or metrics.
Factual incident claims must cite log labels such as [L4].
Operational guidance must cite runbook labels such as [R1].
If the evidence does not establish the answer, explicitly say what is missing.
Write concise technical English in Markdown.
"""


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    """The local retrieval result and whether it is safe to answer."""

    accepted: bool
    chunks: tuple[KnowledgeChunk, ...]
    best_score: float
    threshold: float


@dataclass(frozen=True, slots=True)
class CitationAudit:
    """Syntactic verification of evidence labels used by a generated answer."""

    cited_labels: tuple[str, ...]
    invalid_labels: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cited_labels) and not self.invalid_labels


def audit_answer_citations(
    answer: str,
    events: Sequence[LogEvent],
    chunks: Sequence[KnowledgeChunk],
) -> CitationAudit:
    """Check that every [L#]/[R#] citation points to supplied prompt evidence."""

    cited = tuple(dict.fromkeys(re.findall(r"\[(?:L|R)\d+\]", answer)))
    allowed = {
        f"[L{event.line_number}]"
        for event in events
        if event.level in {"WARNING", "ERROR", "CRITICAL"}
    }
    allowed.update(f"[R{index}]" for index in range(1, len(chunks) + 1))
    invalid = tuple(label for label in cited if label not in allowed)
    return CitationAudit(cited, invalid)


def retrieve_question_evidence(
    question: str,
    knowledge_base: KnowledgeBase,
    embed: Callable[[str], Sequence[float]],
    *,
    limit: int = 3,
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
) -> EvidenceDecision:
    """Retrieve local evidence and reject questions with weak semantic support."""

    normalized = question.strip()
    if not normalized:
        return EvidenceDecision(False, (), 0.0, threshold)

    chunks = tuple(knowledge_base.search(normalized, embed, limit=limit))
    best_score = chunks[0].score if chunks else 0.0
    return EvidenceDecision(best_score >= threshold, chunks, best_score, threshold)


def build_qa_prompt(
    question: str,
    events: Sequence[LogEvent],
    chunks: Sequence[KnowledgeChunk],
) -> str:
    """Build a compact prompt whose evidence labels can be verified in the UI."""

    serious_events = [
        event for event in events if event.level in {"WARNING", "ERROR", "CRITICAL"}
    ]
    log_evidence = "\n".join(
        f"[L{event.line_number}] {event.timestamp.isoformat(sep=' ')} "
        f"{event.level} {event.service}: {event.message}"
        for event in serious_events
    ) or "No WARNING, ERROR, or CRITICAL log evidence was supplied."

    runbook_evidence = "\n\n".join(
        f"[R{index}] Source: {chunk.source}, section: {chunk.heading}\n{chunk.content}"
        for index, chunk in enumerate(chunks, start=1)
    )

    return f"""Answer the user's question about the active SOFTWARE SYSTEM incident.

QUESTION
{question.strip()}

LOG EVIDENCE
{log_evidence}

RUNBOOK EVIDENCE
{runbook_evidence}

Give a direct answer first. Then, when useful, add a short **Evidence** list.
Use only [L#] and [R#] citations that appear above.
"""
