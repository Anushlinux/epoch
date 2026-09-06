"""Durable run records, independent of the existing task schema."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from epoch_backend.execution_contracts import ExecutionRecord


class ExecutionStore:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise sqlite3.DatabaseError("Unsupported execution database schema.")
            if (
                version == 0
                and connection.execute(
                    "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
                ).fetchone()
            ):
                raise sqlite3.DatabaseError("Refusing an unversioned nonempty execution database.")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS executions ("
                "id TEXT PRIMARY KEY, task_id TEXT NOT NULL, request_id TEXT NOT NULL, "
                "record_json TEXT NOT NULL, UNIQUE(task_id, request_id))"
            )
            connection.execute("PRAGMA user_version = 1")

    def insert(self, record: ExecutionRecord):
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO executions VALUES (?, ?, ?, ?)",
                (
                    str(record.id),
                    str(record.task_id),
                    str(record.request.client_request_id),
                    record.model_dump_json(),
                ),
            )

    def save(self, record: ExecutionRecord):
        record.updated_at = datetime.now(UTC)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE executions SET record_json = ? WHERE id = ?",
                (record.model_dump_json(), str(record.id)),
            )

    def get(self, run_id: UUID) -> ExecutionRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT record_json FROM executions WHERE id = ?", (str(run_id),)
            ).fetchone()
            return ExecutionRecord.model_validate_json(row[0]) if row else None

    def find_request(self, task_id: UUID, request_id: UUID) -> ExecutionRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT record_json FROM executions WHERE task_id = ? AND request_id = ?",
                (str(task_id), str(request_id)),
            ).fetchone()
            return ExecutionRecord.model_validate_json(row[0]) if row else None

    def list(self, task_id: UUID | None = None) -> list[ExecutionRecord]:
        with closing(self._connect()) as connection:
            if task_id is None:
                rows = connection.execute("SELECT record_json FROM executions ORDER BY rowid DESC")
            else:
                rows = connection.execute(
                    "SELECT record_json FROM executions WHERE task_id = ? ORDER BY rowid DESC",
                    (str(task_id),),
                )
            return [ExecutionRecord.model_validate_json(row[0]) for row in rows]
