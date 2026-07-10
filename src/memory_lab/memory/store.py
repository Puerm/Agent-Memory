"""SQLite persistence for structured cards and deliberately-naive raw traces."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..schemas import MemoryCard


class MemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_cards (
                    memory_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    project_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS naive_records (
                    record_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def put_card(self, card: MemoryCard) -> None:
        payload = card.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_cards(memory_id, payload, project_id, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                  payload=excluded.payload,
                  project_id=excluded.project_id,
                  status=excluded.status,
                  created_at=excluded.created_at
                """,
                (card.memory_id, payload, card.project_id, card.status, card.created_at.isoformat()),
            )

    def get_card(self, memory_id: str) -> MemoryCard | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM memory_cards WHERE memory_id = ?", (memory_id,)
            ).fetchone()
        return MemoryCard.model_validate_json(row["payload"]) if row else None

    def list_cards(self) -> list[MemoryCard]:
        with self._connect() as connection:
            rows = connection.execute("SELECT payload FROM memory_cards ORDER BY created_at").fetchall()
        return [MemoryCard.model_validate_json(row["payload"]) for row in rows]

    def active_cards(self) -> list[MemoryCard]:
        return [card for card in self.list_cards() if card.status == "active"]

    def next_memory_id(self) -> str:
        count = len(self.list_cards()) + 1
        return f"mem-{count:03d}"

    def put_naive_record(self, record_id: str, project_id: str | None, content: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO naive_records(record_id, project_id, content, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET content=excluded.content
                """,
                (record_id, project_id, content, datetime.now(timezone.utc).isoformat()),
            )

    def list_naive_records(self) -> list[dict[str, str | None]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_id, project_id, content FROM naive_records ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM memory_cards")
            connection.execute("DELETE FROM naive_records")
