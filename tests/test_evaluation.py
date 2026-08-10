"""Tests for retrieval evaluation metrics."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from faulttrace.evaluation import EvaluationCase, evaluate_retrieval
from faulttrace.knowledge_base import KnowledgeBase


class EvaluationTests(unittest.TestCase):
    def test_marks_correct_top_one_source_as_passed(self) -> None:
        vectors = {
            "Overview\ndatabase pool timeout": [1.0, 0.0],
            "Overview\nauthentication token": [0.0, 1.0],
            "database connections exhausted": [0.9, 0.1],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_base = KnowledgeBase(Path(temp_dir) / "evaluation.db")
            knowledge_base.index_document(
                "database.md", "database pool timeout", vectors.__getitem__
            )
            knowledge_base.index_document(
                "auth.md", "authentication token", vectors.__getitem__
            )
            results = evaluate_retrieval(
                knowledge_base,
                vectors.__getitem__,
                [
                    EvaluationCase(
                        "Database", "database connections exhausted", "database.md"
                    )
                ],
            )
        self.assertEqual(1, len(results))
        self.assertTrue(results[0].passed)
        self.assertEqual("database.md", results[0].retrieved_source)

    def test_unanswerable_case_passes_when_similarity_is_below_threshold(self) -> None:
        vectors = {
            "Overview\ndatabase pool timeout": [1.0, 0.0],
            "employee vacation policy": [0.0, 1.0],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_base = KnowledgeBase(Path(temp_dir) / "evaluation.db")
            knowledge_base.index_document(
                "database.md", "database pool timeout", vectors.__getitem__
            )
            results = evaluate_retrieval(
                knowledge_base,
                vectors.__getitem__,
                [
                    EvaluationCase(
                        "Unsupported HR question",
                        "employee vacation policy",
                        "REJECT",
                        answerable=False,
                    )
                ],
                threshold=0.5,
            )

        self.assertTrue(results[0].passed)
        self.assertFalse(results[0].accepted)
        self.assertEqual("REJECT", results[0].retrieved_source)


if __name__ == "__main__":
    unittest.main()
