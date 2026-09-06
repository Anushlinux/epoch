"""Actual API/storage integration with an explicit executor double; no model calls."""

from uuid import uuid4

from fastapi.testclient import TestClient
from test_execution import configured as configured
from test_execution import perform_release, request_data, task, wait_for_run

from epoch_backend import hermes_bridge
from epoch_backend.app import create_app


def test_failed_run_projects_incident_and_restart_retains_identity(configured, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "execute", perform_release)
    with TestClient(create_app(configured)) as client:
        task_id = task(client)
        started = client.post(
            f"/api/tasks/{task_id}/runs", json=request_data(scenario="broken_checklist")
        )
        assert started.status_code == 202, started.text
        run_id = started.json()["id"]
        record = wait_for_run(client, run_id)
        assert record["status"] == "failed"
        listing = client.get("/api/incidents?project_id=demo")
        assert listing.status_code == 200, listing.text
        incident = next(item for item in listing.json()["items"] if run_id in item["run_ids"])
        detail = client.get(f"/api/incidents/{incident['id']}").json()
        assert any(item["trusted"] for item in detail["evidence"])
        assert not detail["analyses"]
    with TestClient(create_app(configured)) as client:
        restored = client.get(f"/api/incidents/{incident['id']}")
        assert restored.status_code == 200, restored.text
        assert {item["id"] for item in restored.json()["evidence"]} == {
            item["id"] for item in detail["evidence"]
        }


def test_projection_failure_cannot_change_trusted_task_result(configured, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "execute", perform_release)
    app = create_app(configured)
    with TestClient(app) as client:

        def unavailable(*_args, **_kwargs):
            raise OSError("explicit projection failure")

        monkeypatch.setattr(app.state.execution.incidents, "refresh_run", unavailable)
        monkeypatch.setattr(app.state.execution.telemetry, "project_events", unavailable)
        task_id = task(client)
        started = client.post(f"/api/tasks/{task_id}/runs", json=request_data())
        record = wait_for_run(client, started.json()["id"])
        assert record["status"] == "completed"
        assert record["verification"]["passed"] is True
        assert app.state.execution.observation_warnings


def test_external_import_is_idempotent_and_never_starts_execution(configured, monkeypatch):
    calls = []
    monkeypatch.setattr(hermes_bridge, "execute", lambda *_args: calls.append(True))
    with TestClient(create_app(configured)) as client:
        payload = {
            "client_request_id": str(uuid4()),
            "records": [
                {
                    "source_type": "support",
                    "source_id": "support-42",
                    "timestamp": "2026-09-06T12:00:00Z",
                    "project_id": "demo",
                    "text": "Customer reports a missing release checklist.",
                }
            ],
        }
        first = client.post("/api/evidence/import", json=payload)
        assert first.status_code in {200, 201}, first.text
        assert client.post("/api/evidence/import", json=payload).json() == first.json()
        evidence_id = first.json()["evidence_ids"][0]
        assert client.get(f"/api/evidence/{evidence_id}").json()["trusted"] is False
        payload["records"][0]["text"] = "Changed report under the same identity"
        assert client.post("/api/evidence/import", json=payload).status_code == 409
        assert not calls
