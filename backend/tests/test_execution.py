"""Orchestration tests use explicit doubles; actual Hermes has separate acceptance evidence."""

import threading
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from epoch_backend import debugger_bridge, hermes_bridge
from epoch_backend.app import create_app
from epoch_backend.config import Settings
from epoch_backend.execution import ExecutionError
from epoch_backend.sandbox import Sandbox
from epoch_backend.tool_registry import ToolRegistry


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "detect_installation", lambda: {"available": True})
    monkeypatch.setattr(debugger_bridge, "detect_debugger", lambda: {"available": False})
    return Settings(data_dir=tmp_path, enable_hermes=True, _env_file=None)


def request_data(**changes):
    return {"client_request_id": str(uuid4()), "workflow": "release", "release": "2.4", **changes}


def task(client):
    response = client.post(
        "/api/tasks",
        json={
            "client_request_id": str(uuid4()),
            "message": "Prepare the demo release",
            "project_id": "demo",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def wait_for_run(client, run_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200, response.text
        record = response.json()
        if record["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return record
        time.sleep(0.01)
    pytest.fail("Test-double execution did not finish")


def perform_release(request, on_event, cancel_event):
    args = request["mcp_args"]
    path = args[args.index("--database") + 1]
    sandbox = Sandbox(path, request["task_id"], request["run_id"])
    metadata = sandbox.metadata()
    registry = ToolRegistry(sandbox)
    registry.discover_tools()
    ticket = registry.invoke_tool(
        "tickets.create",
        {
            "title": f"Release demo {metadata['release']}",
            "release": metadata["release"],
            "idempotency_key": "ticket",
        },
    )["result"]
    checklist = registry.invoke_tool(
        "checklists.create",
        {
            "ticket_id": ticket["id"],
            "title": f"Release checklist {metadata['release']}",
            "items": metadata["expected_items"],
            "idempotency_key": "checklist",
        },
    )
    if checklist["ok"]:
        registry.invoke_tool(
            "messages.send",
            {
                "channel": metadata["qa_channel"],
                "text": f"Release {metadata['release']} ready for QA",
                "links": [ticket["url"], checklist["result"]["url"]],
                "idempotency_key": "message",
            },
        )
    on_event({"type": "executor.message", "data": {"content": "Test double finished."}})
    return {
        "success": True,
        "final_response": "Test double finished.",
        "baseline": {},
        "missing_evidence": ["Test double: no actual Hermes invocation."],
    }


def test_only_explicit_workflow_submission_starts_execution(configured, monkeypatch):
    called = []
    monkeypatch.setattr(hermes_bridge, "execute", lambda *args: called.append(args))
    with TestClient(create_app(configured)) as client:
        task_id = task(client)
        assert client.get(f"/api/tasks/{task_id}").json()["status"] == "pending"
        assert client.get(f"/api/tasks/{task_id}/runs").json() == []
        assert not called
        body = request_data()
        del body["workflow"]
        assert client.post(f"/api/tasks/{task_id}/runs", json=body).status_code == 422
        assert not called


def test_verified_run_persists_status_state_and_trace(configured, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "execute", perform_release)
    with TestClient(create_app(configured)) as client:
        task_id, body = task(client), request_data()
        response = client.post(f"/api/tasks/{task_id}/runs", json=body)
        assert response.status_code == 202, response.text
        run_id = response.json()["id"]
        record = wait_for_run(client, run_id)
        assert record["status"] == "completed", record
        assert record["verification"]["passed"]
        assert client.get(f"/api/tasks/{task_id}").json()["status"] == "completed"
        retry = client.post(f"/api/tasks/{task_id}/runs", json=body)
        assert retry.status_code == 200
        assert retry.json()["id"] == run_id
        conflict = client.post(f"/api/tasks/{task_id}/runs", json={**body, "release": "3.0"})
        assert conflict.status_code == 409
        events = client.get(f"/api/runs/{run_id}/trace").json()
        assert events and all(e["run_id"] == run_id and e["task_id"] == task_id for e in events)
        sequence = events[0]["sequence"]
        remainder = client.get(f"/api/runs/{run_id}/trace?after={sequence}").json()
        assert all(e["sequence"] > sequence for e in remainder)
        state = client.get(f"/api/runs/{run_id}/state").json()
    with TestClient(create_app(configured)) as restarted:
        assert restarted.get(f"/api/runs/{run_id}").json() == record
        assert restarted.get(f"/api/runs/{run_id}/state").json() == state


def test_executor_success_cannot_override_missing_outcomes(configured, monkeypatch):
    monkeypatch.setattr(
        hermes_bridge,
        "execute",
        lambda *args: {"success": True, "final_response": "Everything succeeded!", "baseline": {}},
    )
    with TestClient(create_app(configured)) as client:
        task_id = task(client)
        response = client.post(f"/api/tasks/{task_id}/runs", json=request_data())
        record = wait_for_run(client, response.json()["id"])
        assert record["executor_success"] is True
        assert record["verification"]["passed"] is False
        assert record["status"] == "failed"


def test_unavailable_hermes_does_not_start_a_fake_run(configured, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "detect_installation", lambda: {"available": False})
    with TestClient(create_app(configured)) as client:
        task_id = task(client)
        response = client.post(f"/api/tasks/{task_id}/runs", json=request_data())
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "hermes_unavailable"
        assert client.get(f"/api/tasks/{task_id}/runs").json() == []


def test_single_active_run_can_be_cancelled(configured, monkeypatch):
    entered = threading.Event()

    def wait_until_cancelled(request, on_event, cancel_event):
        entered.set()
        assert cancel_event.wait(5)
        return {"success": False, "final_response": "Cancelled test double."}

    monkeypatch.setattr(hermes_bridge, "execute", wait_until_cancelled)
    with TestClient(create_app(configured)) as client:
        task_id = task(client)
        response = client.post(f"/api/tasks/{task_id}/runs", json=request_data())
        assert entered.wait(2)
        run_id = response.json()["id"]
        assert client.post(f"/api/tasks/{task_id}/runs", json=request_data()).status_code == 409
        assert client.post(f"/api/runs/{run_id}/cancel").status_code == 202
        assert wait_for_run(client, run_id)["status"] == "cancelled"


def test_sse_replays_from_cursor_and_closes_for_finished_run(configured, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "execute", perform_release)
    with TestClient(create_app(configured)) as client:
        response = client.post(f"/api/tasks/{task(client)}/runs", json=request_data())
        run_id = response.json()["id"]
        wait_for_run(client, run_id)
        response = client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "1"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        ids = [int(line[4:]) for line in response.text.splitlines() if line.startswith("id: ")]
        assert ids and ids == sorted(set(ids)) and min(ids) > 1
        bad = client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "invalid"})
        assert bad.status_code == 422


def test_server_lease_prevents_competing_recovery(configured):
    with TestClient(create_app(configured)):
        with pytest.raises(ExecutionError, match="Another Epoch server"):
            with TestClient(create_app(configured)):
                pass
