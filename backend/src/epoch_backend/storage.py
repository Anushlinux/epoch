"""Durable task intake; no executor or repair behavior lives in this store."""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from epoch_backend.contracts import Task, TaskCreate, TaskList, TaskStatus

SCHEMA_VERSION = 1


class RequestConflict(Exception):
    """A client request ID was already used with different task input."""


class SchemaVersionError(sqlite3.DatabaseError):
    """This application cannot safely open the database schema."""


class SQLiteStore:
    """Open one short-lived connection per operation, safe across worker threads."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        """Create a fresh schema or validate an existing one without resetting data."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version == 0:
                    existing = connection.execute(
                        "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
                    ).fetchone()
                    if existing is not None:
                        raise SchemaVersionError("Refusing an unversioned, nonempty database.")
                    connection.execute(
                        "CREATE TABLE tasks ("
                        "sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "id TEXT NOT NULL UNIQUE, "
                        "client_request_id TEXT NOT NULL UNIQUE, "
                        "record_json TEXT NOT NULL)"
                    )
                    connection.execute("PRAGMA user_version = 1")
                elif version != SCHEMA_VERSION:
                    raise SchemaVersionError(f"Unsupported database schema version: {version}.")
                connection.execute(
                    "SELECT sequence, id, client_request_id, record_json FROM tasks LIMIT 0"
                )
            connection.execute("PRAGMA journal_mode = WAL")

    def health(self) -> bool:
        """Check the initialized schema without creating a missing database."""
        try:
            if not self.path.is_file():
                return False
            with closing(self._connect()) as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version != SCHEMA_VERSION:
                    return False
                connection.execute(
                    "SELECT sequence, id, client_request_id, record_json FROM tasks LIMIT 1"
                ).fetchone()
            return True
        except (sqlite3.Error, OSError):
            return False

    @staticmethod
    def _decode(record_json: str) -> Task:
        try:
            return Task.model_validate_json(record_json)
        except ValueError as error:
            raise sqlite3.DatabaseError("A stored task record is invalid.") from error

    def create_task(self, request: TaskCreate) -> tuple[Task, bool]:
        """Atomically return the existing task or create one pending intake record."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT record_json FROM tasks WHERE client_request_id = ?",
                (str(request.client_request_id),),
            ).fetchone()
            if row is not None:
                task = self._decode(row["record_json"])
                if task.request != request:
                    raise RequestConflict("Client request ID already belongs to different input.")
                return task, False

            now = datetime.now(UTC)
            task = Task(
                id=uuid4(),
                request=request,
                status=TaskStatus.pending,
                created_at=now,
                updated_at=now,
            )
            connection.execute(
                "INSERT INTO tasks (id, client_request_id, record_json) VALUES (?, ?, ?)",
                (str(task.id), str(request.client_request_id), task.model_dump_json()),
            )
            return task, True

    def get_task(self, task_id: UUID) -> Task | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT record_json FROM tasks WHERE id = ?", (str(task_id),)
            ).fetchone()
            return self._decode(row["record_json"]) if row is not None else None

    def list_tasks(self, limit: int = 20, offset: int = 0) -> TaskList:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset must be nonnegative")
        with closing(self._connect()) as connection, connection:
            # The count and page must describe the same snapshot during concurrent intake.
            connection.execute("BEGIN")
            total = connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            rows = connection.execute(
                "SELECT record_json FROM tasks ORDER BY sequence DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return TaskList(
                items=[self._decode(row["record_json"]) for row in rows],
                total=total,
                limit=limit,
                offset=offset,
            )

    def set_task_status(self, task_id: UUID, status: TaskStatus) -> Task:
        """Persist execution state without changing the original intake request."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT record_json FROM tasks WHERE id = ?", (str(task_id),)
            ).fetchone()
            if row is None:
                raise KeyError(task_id)
            task = self._decode(row["record_json"])
            task.status = status
            task.updated_at = datetime.now(UTC)
            connection.execute(
                "UPDATE tasks SET record_json = ? WHERE id = ?",
                (task.model_dump_json(), str(task_id)),
            )
            return task
