"""Tests for instant deterministic analysis."""

from __future__ import annotations

import unittest
from pathlib import Path

from faulttrace import parse_log_file
from faulttrace.knowledge_base import KnowledgeBase
from faulttrace.quick_analysis import build_quick_report, detect_cause


class QuickAnalysisTests(unittest.TestCase):
    def test_detects_each_bundled_incident_type(self) -> None:
        expected = {
            "sample_incident.log": "database_connection_pool.md",
            "sample_auth_incident.log": "authentication_failures.md",
            "sample_cpu_incident.log": "high_cpu.md",
        }
        for filename, source in expected.items():
            events, _ = parse_log_file(Path("data") / filename)
            rule, matches = detect_cause(events)
            self.assertIsNotNone(rule)
            self.assertEqual(source, rule.source)
            self.assertTrue(matches)

    def test_quick_report_contains_log_and_runbook_citations(self) -> None:
        events, _ = parse_log_file(Path("data") / "sample_incident.log")
        knowledge_base = KnowledgeBase(Path("data") / "faulttrace.db")
        chunks = knowledge_base.get_source_chunks("database_connection_pool.md")
        report = build_quick_report(events, chunks)
        self.assertIn("[L", report)
        self.assertIn("[R", report)
        self.assertIn("does not invoke the language model", report)


if __name__ == "__main__":
    unittest.main()
