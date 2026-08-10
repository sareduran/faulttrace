"""Tests for deterministic incident scoring."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from faulttrace.incident_metrics import build_failure_chain, calculate_incident_score
from faulttrace.models import LogEvent


def event(index: int, level: str, service: str) -> LogEvent:
    timestamp = datetime(2026, 8, 6, 12, 0) + timedelta(seconds=index)
    return LogEvent(timestamp, level, service, "message", "raw", index)


class IncidentMetricsTests(unittest.TestCase):
    def test_score_increases_with_severity_and_service_spread(self) -> None:
        low = calculate_incident_score([event(1, "WARNING", "api")])
        high = calculate_incident_score(
            [
                event(1, "ERROR", "api"),
                event(2, "CRITICAL", "database"),
                event(3, "ERROR", "payment"),
            ]
        )

        self.assertGreater(high.value, low.value)
        self.assertEqual("High", high.label)

    def test_failure_chain_excludes_info(self) -> None:
        events = [event(1, "INFO", "api"), event(2, "ERROR", "database")]
        chain = build_failure_chain(events)
        self.assertEqual(1, len(chain))
        self.assertEqual("database", chain[0].service)


if __name__ == "__main__":
    unittest.main()
