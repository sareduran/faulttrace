"""Tests for source-grounded incident prompts."""

from __future__ import annotations

import unittest
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from faulttrace.analysis import build_analysis_prompt, build_incident_query
from faulttrace.knowledge_base import KnowledgeChunk
from faulttrace.models import LogEvent


class AnalysisPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [
            LogEvent(
                timestamp=datetime(2026, 8, 6, 14, 3, 12),
                level="WARNING",
                service="database",
                message="Connection pool exhausted",
                raw_line="raw",
                line_number=5,
            ),
            LogEvent(
                timestamp=datetime(2026, 8, 6, 14, 3, 18),
                level="ERROR",
                service="payment-service",
                message="Database timeout",
                raw_line="raw",
                line_number=6,
            ),
        ]
        self.runbooks = [
            KnowledgeChunk(
                id=1,
                source="database.md",
                heading="Response",
                content="Check leaked connections.",
                score=0.8,
            )
        ]

    def test_builds_source_labelled_prompt(self) -> None:
        prompt = build_analysis_prompt(self.events, self.runbooks)
        self.assertIn("[L5]", prompt)
        self.assertIn("[L6]", prompt)
        self.assertIn("[R1]", prompt)
        self.assertIn("SOFTWARE SYSTEM", prompt)

    def test_incident_query_contains_serious_messages(self) -> None:
        query = build_incident_query(self.events)
        self.assertIn("Connection pool exhausted", query)
        self.assertIn("payment-service", query)


if __name__ == "__main__":
    unittest.main()
