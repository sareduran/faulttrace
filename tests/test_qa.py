"""Tests for evidence-gated local incident question answering."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from faulttrace.knowledge_base import KnowledgeBase, KnowledgeChunk
from faulttrace.models import LogEvent
from faulttrace.qa import (
    assess_incident_alignment,
    attach_missing_source_context,
    audit_answer_claims,
    audit_answer_citations,
    build_qa_prompt,
    question_needs_log_context,
    normalize_citation_format,
    retrieve_question_evidence,
)


class QuestionAnsweringTests(unittest.TestCase):
    def test_normalizes_parenthesized_citation_labels(self) -> None:
        answer = "Consumer stopped (L13); follow the runbook (R1)."

        normalized = normalize_citation_format(answer)

        self.assertEqual(
            "Consumer stopped [L13]; follow the runbook [R1].", normalized
        )

    def test_attaches_retrieved_runbook_when_model_omits_r_label(self) -> None:
        event = LogEvent(
            timestamp=datetime(2026, 8, 10, 10, 0, 0),
            level="ERROR",
            service="queue-consumer",
            message="Consumer loop stopped",
            raw_line="raw",
            line_number=13,
        )
        chunk = KnowledgeChunk(
            1,
            "custom/message_queue_runbook.txt",
            "Immediate response",
            "Inspect consumer health logs.",
            0.7,
        )
        answer = "The consumer stopped [L13]. Check consumer health logs."

        grounded = attach_missing_source_context(
            answer, [event], [chunk], include_log_evidence=True
        )
        audit = audit_answer_citations(grounded, [event], [chunk])

        self.assertIn(
            "[R1] custom/message_queue_runbook.txt — Immediate response", grounded
        )
        self.assertTrue(audit.passed)

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
        self.assertIn("at least one [L#]", prompt)
        self.assertIn("at least one [R#]", prompt)
        self.assertIn("at most 120 words", prompt)
        self.assertIn("Never end with an unfinished sentence", prompt)

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
        self.assertIn("at least one [R#] citation", prompt)
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
        numeric = audit_answer_citations("Unsupported source [1].", [event], [chunk])

        self.assertTrue(valid.passed)
        self.assertFalse(invalid.passed)
        self.assertEqual(("[L99]", "[R2]"), invalid.invalid_labels)
        self.assertFalse(numeric.passed)
        self.assertEqual(("[1]",), numeric.invalid_labels)

        missing_runbook = audit_answer_citations(
            "Observed [L7].", [event], [chunk]
        )
        self.assertFalse(missing_runbook.passed)
        self.assertEqual(("[R#]",), missing_runbook.missing_required_types)

    def test_incident_alignment_rejects_queue_question_for_auth_logs(self) -> None:
        auth_event = LogEvent(
            timestamp=datetime(2026, 8, 10, 10, 0, 0),
            level="ERROR",
            service="auth-service",
            message="JWT signing key not found; token validation failed",
            raw_line="raw",
            line_number=3,
        )
        queue_event = LogEvent(
            timestamp=datetime(2026, 8, 10, 10, 0, 0),
            level="ERROR",
            service="queue-consumer",
            message="Consumer stopped acknowledging messages; backlog growing",
            raw_line="raw",
            line_number=4,
        )
        question = "Why is the message queue backlog growing?"

        mismatch = assess_incident_alignment(question, [auth_event])
        match = assess_incident_alignment(question, [queue_event])

        self.assertFalse(mismatch.aligned)
        self.assertEqual("message queue", mismatch.question_domain)
        self.assertEqual("authentication", mismatch.incident_domain)
        self.assertTrue(match.aligned)

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

    def test_claim_audit_ignores_generic_status_in_runbook_excerpt(self) -> None:
        event = LogEvent(
            timestamp=datetime(2026, 8, 10, 10, 0, 0),
            level="ERROR",
            service="api-gateway",
            message="GET /account returned 401",
            raw_line="raw",
            line_number=4,
        )
        answer = """Users receive HTTP 401 because signing-key validation failed.

**Evidence**
[L4] GET /account returned 401
[R1] Authentication incidents commonly produce HTTP 401 or 403 responses.
"""

        audit = audit_answer_claims(answer, [event])

        self.assertTrue(audit.passed)
        self.assertEqual((), audit.unsupported_http_statuses)


if __name__ == "__main__":
    unittest.main()
