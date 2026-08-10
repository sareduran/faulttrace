"""Tests for the SQLite vector knowledge base."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from faulttrace.knowledge_base import KnowledgeBase, chunk_content, split_markdown


class KnowledgeBaseTests(unittest.TestCase):
    def test_splits_markdown_by_heading(self) -> None:
        chunks = split_markdown("# Runbook\nIntro\n## Response\nRestart safely")
        self.assertEqual(
            [("Runbook", "Intro"), ("Response", "Restart safely")], chunks
        )

    def test_indexes_and_searches_chunks(self) -> None:
        vectors = {
            "Database\npool timeout": [1.0, 0.0],
            "CPU\nhigh processor": [0.0, 1.0],
            "connection problem": [0.9, 0.1],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "db.md").write_text("# Database\npool timeout", encoding="utf-8")
            (docs / "cpu.md").write_text("# CPU\nhigh processor", encoding="utf-8")
            knowledge_base = KnowledgeBase(root / "test.db")
            knowledge_base.index_directory(docs, vectors.__getitem__)

            results = knowledge_base.search(
                "connection problem", vectors.__getitem__, limit=1
            )

            self.assertEqual(2, knowledge_base.count())
            self.assertEqual("db.md", results[0].source)
            self.assertGreater(results[0].score, 0.9)

    def test_replaces_and_deletes_one_custom_source(self) -> None:
        vectors = {
            "Overview\nfirst version": [1.0, 0.0],
            "Overview\nsecond version": [0.0, 1.0],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_base = KnowledgeBase(Path(temp_dir) / "test.db")
            knowledge_base.index_document(
                "custom/guide.txt", "first version", vectors.__getitem__
            )
            knowledge_base.index_document(
                "custom/guide.txt", "second version", vectors.__getitem__
            )
            sources = knowledge_base.list_sources()
            self.assertEqual(1, len(sources))
            self.assertEqual(1, sources[0].chunk_count)
            self.assertEqual(1, knowledge_base.delete_source("custom/guide.txt"))
            self.assertEqual([], knowledge_base.list_sources())

    def test_splits_long_content(self) -> None:
        chunks = chunk_content("A" * 25, max_characters=10)
        self.assertEqual(["A" * 10, "A" * 10, "A" * 5], chunks)


if __name__ == "__main__":
    unittest.main()
