"""Tests for evidence-gated local incident question answering."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from faulttrace.knowledge_base import KnowledgeBase, KnowledgeChunk
from faulttrace.models import LogEvent
from faulttrace.qa import (
    audit_answer_claims,
    audit_answer_citations,
    build_qa_prompt,
    question_needs_log_context,
    retrieve_question_evidence,
)


class QuestionAnsweringTests(unittest.TestCase):
    def test_empty_question_is_rejected_without_embedding_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_base = KnowledgeBase(Path(temp_dir) / "qa.db")

            def fail_if_called(_: str) -> list[float]:
                raise AssertionError("Embedding must not run for empty input")

            decision = retrieve_question_evidence(
                "   ", knowledge_base, fail_if_called
            )

        self.assertFalse(decision.accepted)
        self.assertEqual((), decision.chunks)

    def test_accepts_relevant_and_rejects_unsupported_question(self) -> None:
        vectors = {
            "Overview\ndatabase connection pool recovery": [1.0, 0.0],
            "Why is the database pool exhausted?": [0.9, 0.1],
            "What is the employee vacation policy?": [0.1, 0.9],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_base = KnowledgeBase(Path(temp_dir) / "qa.db")
            knowledge_base.index_document(
                "database.md",
                "database connection pool recovery",
                vectors.__getitem__,
            )

            accepted = retrieve_question_evidence(
                "Why is the database pool exhausted?",
                knowledge_base,
                vectors.__getitem__,
                threshold=0.7,
            )
            rejected = retrieve_question_evidence(
                "What is the employee vacation policy?",
                knowledge_base,
                vectors.__getitem__,
                threshold=0.7,
            )

        self.assertTrue(accepted.accepted)
        self.assertFalse(rejected.accepted)
        self.assertEqual("database.md", accepted.chunks[0].source)

    def test_prompt_contains_verifiable_log_and_runbook_labels(self) -> None:
        event = LogEvent(
            timestamp=datetime(2026, 8, 10, 10, 0, 0),
            level="ERROR",
            service="api-gateway",
            message="Request returned HTTP 503",
            raw_line="raw",
            line_number=7,
        )
        chunk = KnowledgeChunk(
            id=1,
            source="database.md",
            heading="Recovery",
            content="Inspect pool usage before restarting.",
            score=0.8,
        )

        prompt = build_qa_prompt("What should I check?", [event], [chunk])

        self.assertIn("[L7]", prompt)
        self.assertIn("api-gateway", prompt)
        self.assertIn("[R1] Source: database.md", prompt)
        self.assertIn("What should I check?", prompt)

    def test_general_definition_prompt_excludes_incident_logs(self) -> None:
        event = LogEvent(
            timestamp=datetime(2026, 8, 10, 10, 0, 0),
            level="ERROR",
            service="api-gateway",
            message="HTTP 503",
            raw_line="raw",
            line_number=7,
        )
        chunk = KnowledgeChunk(
            1,
            "incident_response_basics.md",
            "Incident definition",
            "A software incident is an unplanned service disruption.",
            0.8,
        )

        prompt = build_qa_prompt("What is a software incident?", [event], [chunk])
        audit = audit_answer_citations(
            "A definition [R1], but not this event [L7].",
            [event],
            [chunk],
            include_log_evidence=False,
        )

        self.assertFalse(question_needs_log_context("What is a software incident?"))
        self.assertTrue(question_needs_log_context("What is causing this incident?"))
        self.assertNotIn("[L7] 2026", prompt)
        self.assertIn("cite [R#]", prompt)
        self.assertEqual(("[L7]",), audit.invalid_labels)

    def test_citation_audit_rejects_labels_not_present_in_evidence(self) -> None:
        event = LogEvent(
            timestamp=datetime(2026, 8, 10, 10, 0, 0),
            level="ERROR",
            service="api-gateway",
            message="HTTP 503",
            raw_line="raw",
            line_number=7,
        )
        chunk = KnowledgeChunk(1, "database.md", "Recovery", "Check pool", 0.8)

        valid = audit_answer_citations("Observed [L7]; follow [R1].", [event], [chunk])
        invalid = audit_answer_citations("Observed [L99]; follow [R2].", [event], [chunk])

        self.assertTrue(valid.passed)
        self.assertFalse(invalid.passed)
        self.assertEqual(("[L99]", "[R2]"), invalid.invalid_labels)

    def test_claim_audit_rejects_http_status_absent_from_logs(self) -> None:
        events = [
            LogEvent(
                timestamp=datetime(2026, 8, 10, 10, 0, 0),
                level="ERROR",
                service="api-gateway",
                message="Request returned HTTP 503",
                raw_line="raw",
                line_number=7,
            ),
            LogEvent(
                timestamp=datetime(2026, 8, 10, 10, 0, 1),
                level="ERROR",
                service="payment-service",
                message="Database timeout after 5000ms",
                raw_line="raw",
                line_number=8,
            ),
        ]

        valid = audit_answer_claims("The gateway returned HTTP 503 [L7].", events)
        invalid = audit_answer_claims(
            "The gateway returned 503 and payment returned 500.", events
        )

        self.assertTrue(valid.passed)
        self.assertFalse(invalid.passed)
        self.assertEqual(("500",), invalid.unsupported_http_statuses)


if __name__ == "__main__":
    unittest.main()
