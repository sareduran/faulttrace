"""Tests for local sensitive-value masking."""

from __future__ import annotations

import unittest

from faulttrace.privacy import redact_text


class PrivacyTests(unittest.TestCase):
    def test_redacts_common_sensitive_values(self) -> None:
        text = (
            "user=alice@example.com ip=192.168.10.4 "
            "api_key=abcd1234secret Bearer abcdefghijk12345"
        )
        redacted, count = redact_text(text)
        self.assertNotIn("alice@example.com", redacted)
        self.assertNotIn("192.168.10.4", redacted)
        self.assertNotIn("abcd1234secret", redacted)
        self.assertNotIn("abcdefghijk12345", redacted)
        self.assertEqual(4, count)


if __name__ == "__main__":
    unittest.main()
