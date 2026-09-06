import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from epoch_backend.contracts import TaskCreate, TaskStatus
from epoch_backend.storage import RequestConflict, SchemaVersionError, SQLiteStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteStore:
    database = SQLiteStore(tmp_path / "nested" / "epoch.sqlite3")
    database.initialize()
    return database


def request(message: str = "Prepare the release") -> TaskCreate:
    return TaskCreate(client_request_id=uuid4(), message=message)


def test_restart_preserves_task_and_idempotency(store: SQLiteStore) -> None:
    incoming = request()
    task, created = store.create_task(incoming)
    assert created
    assert task.status == TaskStatus.pending
    assert task.created_at.utcoffset() is not None

    restarted = SQLiteStore(store.path)
    restarted.initialize()
    assert restarted.health()
    assert restarted.get_task(task.id) == task
    retried, created = restarted.create_task(incoming)
    assert not created
    assert retried == task
    assert restarted.list_tasks().total == 1


def test_normalized_retry_is_identical(store: SQLiteStore) -> None:
    incoming = TaskCreate(
        client_request_id=uuid4(), message="  Prepare release  ", project_id="  demo  "
    )
    task, _ = store.create_task(incoming)
    retry = TaskCreate(
        client_request_id=incoming.client_request_id, message="Prepare release", project_id="demo"
    )
    assert store.create_task(retry) == (task, False)


@pytest.mark.parametrize("changes", [{"message": "Changed request"}, {"project_id": "elsewhere"}])
def test_request_conflict_preserves_original(store: SQLiteStore, changes: dict[str, str]) -> None:
    incoming = request()
    task, _ = store.create_task(incoming)
    changed = TaskCreate.model_validate(incoming.model_dump() | changes)
    with pytest.raises(RequestConflict):
        store.create_task(changed)
    assert store.get_task(task.id) == task
    assert store.list_tasks().total == 1


def test_concurrent_retries_create_exactly_one_task(store: SQLiteStore) -> None:
    incoming = request()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: store.create_task(incoming), range(24)))
    assert sum(created for _, created in results) == 1
    assert len({task.id for task, _ in results}) == 1
    assert store.list_tasks().total == 1


def test_pagination_is_newest_first_and_missing_task_is_none(store: SQLiteStore) -> None:
    tasks = [store.create_task(request(f"Release {index}"))[0] for index in range(5)]
    page = store.list_tasks(limit=2, offset=1)
    assert page.items == [tasks[3], tasks[2]]
    assert (page.total, page.limit, page.offset) == (5, 2, 1)
    assert store.list_tasks(offset=100).items == []
    assert store.get_task(uuid4()) is None


@pytest.mark.parametrize("limit, offset", [(0, 0), (101, 0), (20, -1)])
def test_invalid_pagination_is_rejected(store: SQLiteStore, limit: int, offset: int) -> None:
    with pytest.raises(ValueError):
        store.list_tasks(limit=limit, offset=offset)


def test_sql_payload_remains_task_data(store: SQLiteStore) -> None:
    incoming = request("'); DROP TABLE tasks; --")
    task, _ = store.create_task(incoming)
    assert store.get_task(task.id).request.message == incoming.message
    assert store.health()


def test_unknown_schema_is_rejected_without_resetting_data(store: SQLiteStore) -> None:
    task, _ = store.create_task(request())
    with sqlite3.connect(store.path) as connection:
        connection.execute("PRAGMA user_version = 99")
    assert not store.health()
    with pytest.raises(SchemaVersionError, match="Unsupported database schema version"):
        store.initialize()
    with sqlite3.connect(store.path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99
        assert connection.execute("SELECT id FROM tasks").fetchone()[0] == str(task.id)


def test_unversioned_existing_database_is_not_adopted(tmp_path: Path) -> None:
    database_path = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE valuable_data (value TEXT)")
        connection.execute("INSERT INTO valuable_data VALUES ('keep me')")
    with pytest.raises(SchemaVersionError, match="unversioned"):
        SQLiteStore(database_path).initialize()
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT value FROM valuable_data").fetchone()[0] == "keep me"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0


def test_health_does_not_create_missing_database(tmp_path: Path) -> None:
    database = SQLiteStore(tmp_path / "missing" / "epoch.sqlite3")
    assert not database.health()
    assert not database.path.parent.exists()


def test_unusable_storage_directory_reports_os_error(tmp_path: Path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("a file, not a directory", encoding="utf-8")
    with pytest.raises(OSError):
        SQLiteStore(blocked / "epoch.sqlite3").initialize()


def test_corrupt_database_reports_failure(tmp_path: Path) -> None:
    database_path = tmp_path / "corrupt.sqlite3"
    database_path.write_text("This is not a SQLite database", encoding="utf-8")
    database = SQLiteStore(database_path)
    assert not database.health()
    with pytest.raises(sqlite3.DatabaseError):
        database.initialize()


def test_corrupt_task_record_becomes_storage_error(store: SQLiteStore) -> None:
    task, _ = store.create_task(request())
    with sqlite3.connect(store.path) as connection:
        connection.execute("UPDATE tasks SET record_json = ? WHERE id = ?", ("{}", str(task.id)))
    with pytest.raises(sqlite3.DatabaseError, match="stored task record is invalid"):
        store.get_task(task.id)
