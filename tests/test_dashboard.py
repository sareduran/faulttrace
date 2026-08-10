"""Smoke tests for dashboard data transformations."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app import events_to_frame  # noqa: E402
from faulttrace import parse_log_file  # noqa: E402


class DashboardSmokeTests(unittest.TestCase):
    def test_sample_incident_becomes_dashboard_frame(self) -> None:
        events, rejected = parse_log_file(PROJECT_ROOT / "data" / "sample_incident.log")
        frame = events_to_frame(events)

        self.assertEqual([], rejected)
        self.assertEqual(10, len(frame))
        self.assertEqual(
            ["Time", "Level", "Service", "Message", "Line"], list(frame.columns)
        )
        self.assertEqual("api-gateway", frame.iloc[0]["Service"])


if __name__ == "__main__":
    unittest.main()
