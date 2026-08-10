"""Tests for persisted incident analysis reports."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from faulttrace.incident_repository import IncidentRepository
from faulttrace.models import LogEvent


class IncidentRepositoryTests(unittest.TestCase):
    def test_saves_and_updates_the_same_incident(self) -> None:
        event = LogEvent(
            timestamp=datetime(2026, 8, 6, 14, 3, 12),
            level="ERROR",
            service="database",
            message="Pool exhausted",
            raw_line="2026-08-06 14:03:12 ERROR database - Pool exhausted",
            line_number=1,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            repository = IncidentRepository(Path(temp_dir) / "reports.db")
            first_id = repository.save("incident.log", [event], "first analysis")
            second_id = repository.save("incident.log", [event], "updated analysis")
            reports = repository.list_recent()

            self.assertEqual(first_id, second_id)
            self.assertEqual(1, len(reports))
            self.assertEqual("updated analysis", reports[0].analysis_markdown)
            self.assertEqual(1, reports[0].event_count)


if __name__ == "__main__":
    unittest.main()
