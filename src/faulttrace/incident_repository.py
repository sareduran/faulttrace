"""SQLite persistence for generated incident reports."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from .models import LogEvent


@dataclass(frozen=True, slots=True)
class SavedIncident:
    id: int
    source_name: str
    created_at: str
    event_count: int
    started_at: str
    ended_at: str
    analysis_markdown: str


class IncidentRepository:
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
                    CREATE TABLE IF NOT EXISTS incident_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        signature TEXT NOT NULL UNIQUE,
                        source_name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        event_count INTEGER NOT NULL,
                        started_at TEXT NOT NULL,
                        ended_at TEXT NOT NULL,
                        analysis_markdown TEXT NOT NULL
                    )
                    """
                )

    @staticmethod
    def _signature(source_name: str, events: Sequence[LogEvent]) -> str:
        payload = "\n".join(event.raw_line for event in events)
        return hashlib.sha256(f"{source_name}\n{payload}".encode("utf-8")).hexdigest()

    def save(
        self, source_name: str, events: Sequence[LogEvent], analysis_markdown: str
    ) -> int:
        if not events:
            raise ValueError("Cannot save an incident without log events.")
        self.initialize()
        signature = self._signature(source_name, events)
        created_at = datetime.now(UTC).isoformat(timespec="seconds")

        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO incident_reports (
                        signature, source_name, created_at, event_count,
                        started_at, ended_at, analysis_markdown
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(signature) DO UPDATE SET
                        created_at = excluded.created_at,
                        analysis_markdown = excluded.analysis_markdown
                    """,
                    (
                        signature,
                        source_name,
                        created_at,
                        len(events),
                        events[0].timestamp.isoformat(sep=" "),
                        events[-1].timestamp.isoformat(sep=" "),
                        analysis_markdown,
                    ),
                )
                row = connection.execute(
                    "SELECT id FROM incident_reports WHERE signature = ?", (signature,)
                ).fetchone()
        return int(row["id"])

    def list_recent(self, limit: int = 10) -> list[SavedIncident]:
        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, source_name, created_at, event_count,
                       started_at, ended_at, analysis_markdown
                FROM incident_reports
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [SavedIncident(**dict(row)) for row in rows]

