"""SQLite-backed local vector knowledge base."""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


EmbeddingFunction = Callable[[str], Sequence[float]]


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    id: int
    source: str
    heading: str
    content: str
    score: float


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    source: str
    chunk_count: int


def chunk_content(text: str, max_characters: int = 1400) -> list[str]:
    """Split long content on paragraph boundaries for predictable local inference."""

    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_characters:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                paragraph[index : index + max_characters]
                for index in range(0, len(paragraph), max_characters)
            )
            continue
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > max_characters:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def prepare_document_chunks(text: str) -> list[tuple[str, str]]:
    """Create uniquely labelled, size-limited chunks from one document."""

    prepared: list[tuple[str, str]] = []
    label_counts: dict[str, int] = {}
    for heading, content in split_markdown(text):
        parts = chunk_content(content)
        for part_index, part in enumerate(parts, start=1):
            base_label = heading if len(parts) == 1 else f"{heading} (part {part_index})"
            label_counts[base_label] = label_counts.get(base_label, 0) + 1
            occurrence = label_counts[base_label]
            label = base_label if occurrence == 1 else f"{base_label} ({occurrence})"
            prepared.append((label, part))
    return prepared


def split_markdown(text: str) -> list[tuple[str, str]]:
    """Split a small Markdown runbook into heading-based chunks."""

    chunks: list[tuple[str, str]] = []
    heading = "Overview"
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            chunks.append((heading, content))

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            buffer.clear()
            heading = line.lstrip("#").strip()
        else:
            buffer.append(line)
    flush()
    return chunks


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Embedding vectors must have the same non-zero length.")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


class KnowledgeBase:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_chunks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        heading TEXT NOT NULL,
                        content TEXT NOT NULL,
                        embedding_json TEXT NOT NULL,
                        UNIQUE(source, heading)
                    )
                    """
                )

    def index_directory(
        self, directory: str | Path, embed: EmbeddingFunction
    ) -> int:
        """Replace the index with Markdown chunks from a directory."""

        directory = Path(directory)
        indexed = 0
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("DELETE FROM knowledge_chunks")
                for path in sorted(directory.glob("*.md")):
                    text = path.read_text(encoding="utf-8")
                    for heading, content in prepare_document_chunks(text):
                        embedding = list(embed(f"{heading}\n{content}"))
                        connection.execute(
                            """
                            INSERT INTO knowledge_chunks
                                (source, heading, content, embedding_json)
                            VALUES (?, ?, ?, ?)
                            """,
                            (path.name, heading, content, json.dumps(embedding)),
                        )
                        indexed += 1
        return indexed

    def index_document(
        self, source: str, text: str, embed: EmbeddingFunction
    ) -> int:
        """Insert or replace one user document in the local vector index."""

        chunks = prepare_document_chunks(text)
        if not chunks:
            raise ValueError("Document does not contain extractable text.")
        embedded = [
            (heading, content, json.dumps(list(embed(f"{heading}\n{content}"))))
            for heading, content in chunks
        ]
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("DELETE FROM knowledge_chunks WHERE source = ?", (source,))
                connection.executemany(
                    """
                    INSERT INTO knowledge_chunks
                        (source, heading, content, embedding_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (source, heading, content, embedding_json)
                        for heading, content, embedding_json in embedded
                    ],
                )
        return len(chunks)

    def search(
        self, query: str, embed: EmbeddingFunction, limit: int = 3
    ) -> list[KnowledgeChunk]:
        """Return the most semantically similar locally stored chunks."""

        query_vector = list(embed(query))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT id, source, heading, content, embedding_json FROM knowledge_chunks"
            ).fetchall()

        results = [
            KnowledgeChunk(
                id=row["id"],
                source=row["source"],
                heading=row["heading"],
                content=row["content"],
                score=cosine_similarity(query_vector, json.loads(row["embedding_json"])),
            )
            for row in rows
        ]
        return sorted(results, key=lambda chunk: chunk.score, reverse=True)[:limit]

    def count(self) -> int:
        self.initialize()
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()
        return int(row[0])

    def get_source_chunks(self, source: str) -> list[KnowledgeChunk]:
        """Return all chunks for one known local source without model inference."""

        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, source, heading, content
                FROM knowledge_chunks
                WHERE source = ?
                ORDER BY id
                """,
                (source,),
            ).fetchall()
        return [
            KnowledgeChunk(
                id=row["id"],
                source=row["source"],
                heading=row["heading"],
                content=row["content"],
                score=1.0,
            )
            for row in rows
        ]

    def list_sources(self) -> list[KnowledgeSource]:
        """List indexed sources and their chunk counts."""

        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT source, COUNT(*) AS chunk_count
                FROM knowledge_chunks
                GROUP BY source
                ORDER BY source
                """
            ).fetchall()
        return [KnowledgeSource(**dict(row)) for row in rows]

    def delete_source(self, source: str) -> int:
        """Delete all chunks for one source and return the removed row count."""

        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM knowledge_chunks WHERE source = ?", (source,)
                )
        return int(cursor.rowcount)
