"""Tests for user knowledge-document ingestion."""

from __future__ import annotations

import unittest

from faulttrace.document_ingestion import extract_document_text, safe_source_name


class DocumentIngestionTests(unittest.TestCase):
    def test_extracts_utf8_text_document(self) -> None:
        text = extract_document_text("runbook.txt", "Çözüm adımları".encode("utf-8"))
        self.assertEqual("Çözüm adımları", text)

    def test_normalizes_uploaded_filename(self) -> None:
        self.assertEqual("custom/runbook.md", safe_source_name("../runbook.md"))

    def test_rejects_unsupported_document_type(self) -> None:
        with self.assertRaises(ValueError):
            extract_document_text("notes.exe", b"not allowed")


if __name__ == "__main__":
    unittest.main()
