"""Concurrency/recovery regressions; all executor calls here are explicit doubles."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from epoch_backend import debugger_bridge, hermes_bridge
from epoch_backend.config import Settings
from epoch_backend.contracts import TaskCreate, TaskStatus
from epoch_backend.execution import ExecutionError, ExecutionService, release_brief
from epoch_backend.execution_api import execution_router
from epoch_backend.execution_contracts import ExecutionRecord, ReleaseRunRequest
from epoch_backend.sandbox import Sandbox
from epoch_backend.storage import SQLiteStore


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "detect_installation", lambda: {"available": True})
    monkeypatch.setattr(debugger_bridge, "detect_debugger", lambda: {"available": False})
    settings = Settings(data_dir=tmp_path, enable_hermes=True, _env_file=None)
    tasks = SQLiteStore(settings.database_path)
    tasks.initialize()
    execution = ExecutionService(settings, tasks)
    execution.initialize()
    try:
        yield execution
    finally:
        execution.close()


def add_task(service):
    return service.tasks.create_task(
        TaskCreate(client_request_id=uuid4(), message="Prepare the release", project_id="demo")
    )[0]


def run_request():
    return ReleaseRunRequest(client_request_id=uuid4(), workflow="release", release="1.0")


def finish(service, run_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        record = service.get(run_id)
        if record.status in {"completed", "failed", "cancelled", "interrupted"}:
            return record
        time.sleep(0.01)
    pytest.fail("Executor double failed to reach a terminal state")


def test_concurrent_identical_admissions_execute_once(service, monkeypatch):
    calls = []
    release = threading.Event()
    started = threading.Event()

    def execute(request, on_event, cancelled):
        calls.append(request["run_id"])
        started.set()
        assert release.wait(5)
        return {"success": False, "final_response": "Test double has no business effects."}

    monkeypatch.setattr(hermes_bridge, "execute", execute)
    task, request = add_task(service), run_request()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: service.start(task.id, request), range(16)))
        assert sum(created for _, created in results) == 1
        assert len({record.id for record, _ in results}) == 1
        assert len(service.store.list(task.id)) == 1
        assert started.wait(2)
        assert calls == [str(results[0][0].id)]
    finally:
        release.set()
    finish(service, results[0][0].id)


def test_concurrent_different_requests_admit_only_one(service, monkeypatch):
    release = threading.Event()

    def execute(request, on_event, cancelled):
        assert release.wait(5)
        return {"success": False, "final_response": "Test double complete."}

    monkeypatch.setattr(hermes_bridge, "execute", execute)
    task = add_task(service)

    def start(_):
        try:
            return service.start(task.id, run_request())[0]
        except ExecutionError as error:
            return error.code

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(start, range(16)))
        assert sum(isinstance(value, ExecutionRecord) for value in results) == 1
        assert results.count("executor_busy") == 15
        assert len(service.store.list(task.id)) == 1
    finally:
        release.set()
    finish(service, service.store.list(task.id)[0].id)


def seed_interrupted_record(service, *, with_sandbox):
    task = add_task(service)
    run_id = uuid4()
    sandbox = Sandbox(
        service.settings.data_dir / "runs" / str(run_id) / "sandbox.sqlite3", task.id, run_id
    )
    # Obtain real metadata from another database for the missing-evidence variant.
    if not with_sandbox:
        sandbox = Sandbox(service.settings.data_dir / "fixture.sqlite3", task.id, run_id)
    metadata = sandbox.initialize()
    ticket = sandbox.create_ticket(metadata["ticket_title"], metadata["release"], "partial-ticket")
    now = datetime.now(UTC)
    record = ExecutionRecord(
        id=run_id,
        task_id=task.id,
        request=run_request(),
        status="running",
        brief=release_brief(task, run_id, metadata),
        created_at=now,
        updated_at=now,
    )
    service.store.insert(record)
    service.tasks.set_task_status(task.id, TaskStatus.running)
    return record, ticket


def test_restart_marks_stale_run_interrupted_without_replaying_partial_effects(service):
    record, ticket = seed_interrupted_record(service, with_sandbox=True)
    service.close()
    restarted = ExecutionService(service.settings, service.tasks)
    restarted.initialize()
    try:
        recovered = restarted.get(record.id)
        assert recovered.status == "interrupted"
        assert recovered.error["code"] == "server_restarted"
        assert restarted.tasks.get_task(record.task_id).status == TaskStatus.blocked
        assert restarted.sandbox(record).list_tickets() == [ticket]
        assert any(
            event["type"] == "run.interrupted" for event in restarted.sandbox(record).events()
        )
        assert restarted.active_run_id is None
    finally:
        restarted.close()


def test_restart_survives_missing_sandbox_and_reports_missing_evidence(service):
    record, _ = seed_interrupted_record(service, with_sandbox=False)
    service.close()
    restarted = ExecutionService(service.settings, service.tasks)
    try:
        restarted.initialize()
        recovered = restarted.get(record.id)
        assert recovered.status == "interrupted"
        assert recovered.missing_evidence
        assert restarted.tasks.get_task(record.task_id).status == TaskStatus.blocked
        assert restarted.active_run_id is None
    finally:
        restarted.close()


def test_missing_lookup_brief_discloses_extra_trusted_owner_requirement(service):
    task = add_task(service)
    run_id = uuid4()
    sandbox = Sandbox(service.settings.data_dir / "lookup.sqlite3", task.id, run_id)
    metadata = sandbox.initialize(scenario="missing_lookup")
    brief = release_brief(task, run_id, metadata)
    assert "QA owner" in brief.instructions
    assert any("owner" in item.description.lower() for item in brief.checkpoints)
    assert metadata["qa_owner"] not in brief.instructions


def test_sse_waits_for_final_event_when_publication_is_delayed(service, monkeypatch):
    final_event_pending = threading.Event()
    allow_final_event = threading.Event()
    original_record_event = Sandbox.record_event

    def delay_final_event(sandbox, event_type, payload):
        if event_type == "run.finished":
            final_event_pending.set()
            assert allow_final_event.wait(5)
        return original_record_event(sandbox, event_type, payload)

    monkeypatch.setattr(Sandbox, "record_event", delay_final_event)
    monkeypatch.setattr(
        hermes_bridge, "execute", lambda *args: {"success": False, "final_response": "Test double"}
    )
    task = add_task(service)
    run, _ = service.start(task.id, run_request())
    assert final_event_pending.wait(2)
    app = FastAPI()
    app.include_router(execution_router(service))
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        response = pool.submit(client.get, f"/api/runs/{run.id}/events")
        try:
            with pytest.raises(TimeoutError):
                response.result(timeout=0.3)
        finally:
            allow_final_event.set()
        streamed = response.result(timeout=5)
    assert streamed.status_code == 200
    assert "event: run.finished\n" in streamed.text
    assert finish(service, run.id).status == "failed"


def test_failed_final_event_persistence_blocks_further_execution(service, monkeypatch):
    original_record_event = Sandbox.record_event
    executor_calls = []

    def fail_final_event(sandbox, event_type, payload):
        if event_type == "run.finished":
            raise OSError("Injected event-storage failure")
        return original_record_event(sandbox, event_type, payload)

    def execute(request, on_event, cancelled):
        executor_calls.append(request["run_id"])
        return {"success": False, "final_response": "Controlled executor double."}

    monkeypatch.setattr(Sandbox, "record_event", fail_final_event)
    monkeypatch.setattr(hermes_bridge, "execute", execute)
    task = add_task(service)
    run, _ = service.start(task.id, run_request())
    record = finish(service, run.id)
    assert record.status == "failed"
    assert record.error["code"] == "finalization_failed"
    assert record.missing_evidence
    assert not any(event["type"] == "run.finished" for event in service.sandbox(record).events())
    assert service.runtime_info().execution_enabled is False
    with pytest.raises(ExecutionError) as error:
        service.start(task.id, run_request())
    assert error.value.code == "execution_state_unresolved"
    assert error.value.status == 503
    assert executor_calls == [str(run.id)]
    assert len(service.store.list(task.id)) == 1


@pytest.mark.parametrize("stage", ["task_status", "initial_event", "thread_start"])
def test_failed_admission_becomes_terminal_and_retry_never_starts_a_worker(
    service, monkeypatch, stage
):
    executor_calls = []
    monkeypatch.setattr(hermes_bridge, "execute", lambda *args: executor_calls.append(args))
    task, request = add_task(service), run_request()
    original_status = service.tasks.set_task_status
    original_event = Sandbox.record_event

    def fail_running_status(task_id, status):
        if status == TaskStatus.running:
            raise OSError("Injected admission status failure")
        return original_status(task_id, status)

    def fail_initial_event(sandbox, event_type, payload):
        if event_type == "brief.created":
            raise OSError("Injected admission event failure")
        return original_event(sandbox, event_type, payload)

    def fail_thread_start(worker):
        raise RuntimeError("Injected worker startup failure")

    with monkeypatch.context() as patch:
        if stage == "task_status":
            patch.setattr(service.tasks, "set_task_status", fail_running_status)
        elif stage == "initial_event":
            patch.setattr(Sandbox, "record_event", fail_initial_event)
        else:
            patch.setattr(threading.Thread, "start", fail_thread_start)
        with pytest.raises(ExecutionError) as error:
            service.start(task.id, request)
    assert error.value.code == "execution_admission_failed"
    assert error.value.status == 503
    record = service.store.list(task.id)[0]
    assert record.status == "failed"
    assert record.error["code"] == "execution_admission_failed"
    assert service.tasks.get_task(task.id).status == TaskStatus.failed
    assert service.active_run_id is None
    assert service._thread is None
    assert service.runtime_info().execution_enabled is True
    retry, created = service.start(task.id, request)
    assert created is False and retry.id == record.id and retry.status == "failed"
    assert executor_calls == []
    assert len(service.store.list(task.id)) == 1
    assert service.sandbox(record).snapshot()["tickets"] == []
    assert service.sandbox(record).events()[-1]["type"] == "run.finished"
    app = FastAPI()
    app.include_router(execution_router(service))
    with TestClient(app) as client:
        stream = client.get(f"/api/runs/{record.id}/events")
    assert stream.status_code == 200 and "event: run.finished\n" in stream.text


def test_unconfirmed_admission_cleanup_blocks_further_execution(service, monkeypatch):
    task, request = add_task(service), run_request()
    original_event = Sandbox.record_event

    def fail_admission_and_final_event(sandbox, event_type, payload):
        if event_type in {"brief.created", "run.finished"}:
            raise OSError("Injected persistent event-storage failure")
        return original_event(sandbox, event_type, payload)

    monkeypatch.setattr(Sandbox, "record_event", fail_admission_and_final_event)
    with pytest.raises(ExecutionError) as error:
        service.start(task.id, request)
    assert error.value.code == "execution_admission_failed"
    record = service.store.list(task.id)[0]
    assert record.status == "failed"
    assert any("finalized consistently" in gap for gap in record.missing_evidence)
    assert service.active_run_id == record.id
    assert service._thread is None
    assert service.runtime_info().execution_enabled is False
    with pytest.raises(ExecutionError) as blocked:
        service.start(task.id, run_request())
    assert blocked.value.code == "execution_state_unresolved"
    assert blocked.value.status == 503
    assert len(service.store.list(task.id)) == 1
