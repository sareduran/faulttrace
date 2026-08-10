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
Never state or infer an HTTP status code unless that exact code occurs in LOG EVIDENCE.
A timeout does not prove an HTTP 500 response. Do not convert one into a status code.
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
class IncidentAlignment:
    """Whether a domain-specific question matches the active incident logs."""

    aligned: bool
    question_domain: str | None
    incident_domain: str | None


DOMAIN_KEYWORDS = {
    "message queue": (
        "message queue", "queue", "backlog", "consumer", "acknowledg", "dead-letter"
    ),
    "authentication": (
        "authentication", "auth-service", "jwt", "token", "signing key", "401"
    ),
    "database": (
        "database", "connection pool", "db connection", "sql", "503"
    ),
    "CPU": (
        "cpu", "processor", "thread pool", "thread-pool", "saturation"
    ),
}


def _detect_domain(text: str) -> str | None:
    normalized = text.lower()
    scores = {
        domain: sum(normalized.count(keyword) for keyword in keywords)
        for domain, keywords in DOMAIN_KEYWORDS.items()
    }
    best_domain, best_score = max(scores.items(), key=lambda item: item[1])
    return best_domain if best_score > 0 else None


def assess_incident_alignment(
    question: str, events: Sequence[LogEvent]
) -> IncidentAlignment:
    """Prevent a domain-specific question from being mixed with unrelated logs."""

    if not question_needs_log_context(question):
        return IncidentAlignment(True, None, None)
    question_domain = _detect_domain(question)
    incident_text = "\n".join(
        f"{event.service} {event.message}"
        for event in events
        if event.level in {"WARNING", "ERROR", "CRITICAL"}
    )
    incident_domain = _detect_domain(incident_text)
    aligned = (
        question_domain is None
        or incident_domain is None
        or question_domain == incident_domain
    )
    return IncidentAlignment(aligned, question_domain, incident_domain)


@dataclass(frozen=True, slots=True)
class CitationAudit:
    """Syntactic verification of evidence labels used by a generated answer."""

    cited_labels: tuple[str, ...]
    invalid_labels: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cited_labels) and not self.invalid_labels


@dataclass(frozen=True, slots=True)
class ClaimAudit:
    """Deterministic checks for factual values that must exist in log evidence."""

    unsupported_http_statuses: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.unsupported_http_statuses


def audit_answer_claims(answer: str, events: Sequence[LogEvent]) -> ClaimAudit:
    """Reject HTTP status codes that do not occur in the active incident logs."""

    status_pattern = r"(?<!\d)(?:[1-5]\d{2})(?!\d)"
    claim_lines: list[str] = []
    in_evidence_section = False
    for line in answer.splitlines():
        if re.match(r"^\s*(?:#{1,6}\s*)?\*{0,2}evidence\*{0,2}\s*$", line, re.IGNORECASE):
            in_evidence_section = True
            continue
        # Runbook excerpts may mention generic status codes that are not claims
        # about the active incident. Log-labelled evidence remains auditable.
        if not in_evidence_section or re.match(r"^\s*\[L\d+\]", line):
            claim_lines.append(line)

    answer_statuses = set(re.findall(status_pattern, "\n".join(claim_lines)))
    log_text = "\n".join(event.message for event in events)
    supported_statuses = set(re.findall(status_pattern, log_text))
    unsupported = tuple(sorted(answer_statuses - supported_statuses))
    return ClaimAudit(unsupported)


def audit_answer_citations(
    answer: str,
    events: Sequence[LogEvent],
    chunks: Sequence[KnowledgeChunk],
    *,
    include_log_evidence: bool = True,
) -> CitationAudit:
    """Check that every [L#]/[R#] citation points to supplied prompt evidence."""

    cited = tuple(dict.fromkeys(re.findall(r"\[(?:(?:L|R)?\d+)\]", answer)))
    allowed = set()
    if include_log_evidence:
        allowed = {
            f"[L{event.line_number}]"
            for event in events
            if event.level in {"WARNING", "ERROR", "CRITICAL"}
        }
    allowed.update(f"[R{index}]" for index in range(1, len(chunks) + 1))
    invalid = tuple(label for label in cited if label not in allowed)
    return CitationAudit(cited, invalid)


def question_needs_log_context(question: str) -> bool:
    """Return false for definition questions that should use runbooks only."""

    normalized = " ".join(question.lower().strip().split())
    general_patterns = (
        r"^what is (?:a|an) ",
        r"^define ",
        r"^what does .+ mean\??$",
        r"^explain (?:the )?(?:concept|definition) of ",
    )
    return not any(re.search(pattern, normalized) for pattern in general_patterns)


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

    include_logs = question_needs_log_context(question)
    if include_logs:
        serious_events = [
            event
            for event in events
            if event.level in {"WARNING", "ERROR", "CRITICAL"}
        ]
        log_evidence = "\n".join(
            f"[L{event.line_number}] {event.timestamp.isoformat(sep=' ')} "
            f"{event.level} {event.service}: {event.message}"
            for event in serious_events
        ) or "No WARNING, ERROR, or CRITICAL log evidence was supplied."
        scope_instruction = (
            "This question concerns the active incident. Use [L#] for incident facts "
            "and [R#] for runbook guidance."
        )
    else:
        log_evidence = (
            "Not included because this is a general definition question. "
            "Do not use or cite any [L#] labels."
        )
        scope_instruction = (
            "This is a general definition question. Answer from RUNBOOK EVIDENCE "
            "and cite [R#]. Do not discuss the active incident or cite logs."
        )

    runbook_evidence = "\n\n".join(
        f"[R{index}] Source: {chunk.source}, section: {chunk.heading}\n{chunk.content}"
        for index, chunk in enumerate(chunks, start=1)
    )

    return f"""Answer the user's question about the active SOFTWARE SYSTEM incident.

QUESTION
{question.strip()}

QUESTION SCOPE
{scope_instruction}

LOG EVIDENCE
{log_evidence}

RUNBOOK EVIDENCE
{runbook_evidence}

Return a complete answer of at most 120 words.
Give the direct answer first and cite claims inline.
Do not reproduce raw evidence lines or copy whole runbook passages.
If an **Evidence** list is useful, include at most 3 short bullets.
Use at most 5 total citations and only [L#]/[R#] labels that appear above.
Never end with an unfinished sentence.
"""
