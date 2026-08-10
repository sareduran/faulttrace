"""Small, reproducible retrieval evaluation suite for FaultTrace."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Sequence

from .knowledge_base import KnowledgeBase
from .qa import DEFAULT_RELEVANCE_THRESHOLD


EmbeddingFunction = Callable[[str], Sequence[float]]


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    name: str
    query: str
    expected_source: str
    answerable: bool = True


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    name: str
    expected_source: str
    retrieved_source: str
    retrieved_heading: str
    score: float
    latency_seconds: float
    passed: bool
    answerable: bool
    accepted: bool


DEFAULT_EVALUATION_CASES = (
    EvaluationCase(
        name="Incident definition",
        query="What is a software incident and how is it different from an alert?",
        expected_source="incident_response_basics.md",
    ),
    EvaluationCase(
        name="Database pool exhaustion",
        query=(
            "Database connections reached their maximum, payment requests time out, "
            "and the API returns HTTP 503."
        ),
        expected_source="database_connection_pool.md",
    ),
    EvaluationCase(
        name="Authentication key failure",
        query=(
            "JWT signature verification fails because the new signing key is missing, "
            "causing HTTP 401 responses."
        ),
        expected_source="authentication_failures.md",
    ),
    EvaluationCase(
        name="CPU saturation",
        query=(
            "CPU remains near 98 percent, the worker queue grows, requests return 504, "
            "and the thread pool is starved."
        ),
        expected_source="high_cpu.md",
    ),
    EvaluationCase(
        name="Unanswerable HR policy question",
        query=(
            "How many annual vacation days do employees receive and what is the "
            "company parental leave policy?"
        ),
        expected_source="REJECT",
        answerable=False,
    ),
)


def available_evaluation_cases(knowledge_base: KnowledgeBase) -> list[EvaluationCase]:
    """Return built-in cases plus optional cases for known custom sources."""

    cases = list(DEFAULT_EVALUATION_CASES)
    sources = {source.source for source in knowledge_base.list_sources()}
    queue_source = "custom/message_queue_runbook.txt"
    if queue_source in sources:
        cases.append(
            EvaluationCase(
                name="Message queue consumer failure",
                query=(
                    "Queue depth is growing, active consumers decreased, messages are "
                    "not acknowledged, and the oldest message age is increasing."
                ),
                expected_source=queue_source,
            )
        )
    return cases


def evaluate_retrieval(
    knowledge_base: KnowledgeBase,
    embed: EmbeddingFunction,
    cases: Sequence[EvaluationCase],
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
) -> list[EvaluationResult]:
    """Measure top-1 retrieval and rejection of unsupported questions."""

    results: list[EvaluationResult] = []
    for case in cases:
        started = time.perf_counter()
        matches = knowledge_base.search(case.query, embed, limit=1)
        latency = time.perf_counter() - started
        if not matches:
            passed = not case.answerable
            results.append(
                EvaluationResult(
                    name=case.name,
                    expected_source=case.expected_source,
                    retrieved_source="No result",
                    retrieved_heading="-",
                    score=0.0,
                    latency_seconds=latency,
                    passed=passed,
                    answerable=case.answerable,
                    accepted=False,
                )
            )
            continue

        match = matches[0]
        accepted = match.score >= threshold
        passed = (
            accepted and match.source == case.expected_source
            if case.answerable
            else not accepted
        )
        results.append(
            EvaluationResult(
                name=case.name,
                expected_source=case.expected_source,
                retrieved_source=match.source if accepted else "REJECT",
                retrieved_heading=match.heading,
                score=match.score,
                latency_seconds=latency,
                passed=passed,
                answerable=case.answerable,
                accepted=accepted,
            )
        )
    return results
