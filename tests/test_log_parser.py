"""Tests for normalization of supported log formats."""

from __future__ import annotations

import unittest
from datetime import datetime

from faulttrace.log_parser import parse_log_lines


class ParseLogLinesTests(unittest.TestCase):
    def test_parses_and_normalizes_levels(self) -> None:
        events, rejected = parse_log_lines(
            [
                "2026-08-06 14:03:18 ERROR payment-service - timeout\n",
                "2026-08-06T14:03:12.250Z [WARN] [database] pool nearly full\n",
                "2026-08-06 14:04:02 FATAL api-gateway: unavailable\n",
            ]
        )

        self.assertEqual([], rejected)
        self.assertEqual(["WARNING", "ERROR", "CRITICAL"], [e.level for e in events])
        self.assertEqual("database", events[0].service)
        self.assertEqual(datetime(2026, 8, 6, 14, 3, 12, 250000), events[0].timestamp)

    def test_returns_non_empty_unparsed_lines(self) -> None:
        events, rejected = parse_log_lines(["not a supported log line", "\n"])

        self.assertEqual([], events)
        self.assertEqual(["not a supported log line"], rejected)

    def test_empty_input_returns_no_events_and_no_rejections(self) -> None:
        events, rejected = parse_log_lines([])

        self.assertEqual([], events)
        self.assertEqual([], rejected)

    def test_malformed_json_and_broken_log_are_reported_not_crashed(self) -> None:
        events, rejected = parse_log_lines(
            [
                '{"timestamp":"not-closed"',
                "2026-99-99 21:00:00 ERROR service impossible timestamp",
                "totally broken line",
            ]
        )

        self.assertEqual([], events)
        self.assertEqual(3, len(rejected))

    def test_parses_jsonl_with_common_field_aliases(self) -> None:
        events, rejected = parse_log_lines(
            [
                '{"@timestamp":"2026-08-07T10:15:20Z","severity":"ERROR",'
                '"service_name":"checkout","msg":"request failed"}',
                '{"time":"2026-08-07 10:15:21","level":"WARN",'
                '"logger":"database","message":"pool nearly full"}',
            ]
        )
        self.assertEqual([], rejected)
        self.assertEqual(["ERROR", "WARNING"], [event.level for event in events])
        self.assertEqual("checkout", events[0].service)


if __name__ == "__main__":
    unittest.main()
