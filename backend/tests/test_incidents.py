"""Focused incident boundaries with an explicit no-network debugger double."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from epoch_backend.incident_api import incident_router
from epoch_backend.incidents import IncidentError, IncidentService


@pytest.fixture
def service(tmp_path):
    value = IncidentService(tmp_path)
    value.initialize()
    return value


def evidence(**updates):
    return {
        "source_type": "trace",
        "source_id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "project_id": "demo",
        "workflow": "release",
        "tool": "checklists.create",
        "error_code": "adapter_contract_error",
        "text": "Release checklist creation failed",
        "run_id": str(uuid4()),
        **updates,
    }


def native(service, error=True, status="failed", version="builtin"):
    event = {
        "id": str(uuid4()),
        "sequence": 1,
        "type": "tool.error" if error else "state.changed",
        "emitted_at": datetime.now(UTC).isoformat(),
        "payload": {
            "tool_name": "checklists.create",
            **(
                {
                    "error": {
                        "code": "adapter_contract_error",
                        "message": "Release checklist creation failed",
                    }
                }
                if error
                else {}
            ),
        },
    }
    record = {
        "id": str(uuid4()),
        "task_id": str(uuid4()),
        "request": {"workflow": "release"},
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "environment_version": version,
        "verification": {
            "passed": not error,
            "evaluator_version": "release-state-v3",
            "checks": [{"id": "checklist"}],
            "missing_evidence": [],
        },
    }
    sandbox = SimpleNamespace(
        metadata=lambda: {"project_id": "demo"}, events=lambda after=0: [event] if after < 1 else []
    )
    service.refresh_run(record, sandbox)
    return record, sandbox, event


def test_duplicate_projection_restart_and_imported_native_hint(service):
    record, sandbox, event = native(service)
    service.refresh_run(record, sandbox)
    assert service.list_incidents()["total"] == 1
    assert service.list_incidents()["items"][0]["evidence_count"] == 1
    imported = service.ingest_evidence([evidence(native_event_id=event["id"], project_id="forged")])
    assert imported["deduplicated"] == 1
    assert service.get_evidence(imported["evidence_ids"][0])["trusted"] is True
    restarted = IncidentService(service.path.parent)
    restarted.initialize()
    restarted.refresh_run(record, sandbox)
    assert restarted.list_incidents()["items"][0]["evidence_count"] == 1


def test_native_arrival_preserves_authority(service):
    event_id = str(uuid4())
    imported = service.ingest_evidence([evidence(native_event_id=event_id)])
    with service._connect() as db:
        service._put(
            db, evidence(source_type="epoch", source_id=event_id, native_event_id=event_id), True
        )
    alias = service.get_evidence(imported["evidence_ids"][0])
    assert not alias["trusted"] and alias["duplicate_of"]
    assert service.get_evidence(alias["duplicate_of"])["trusted"]


def test_version_grouping_external_relevance_and_scope(service):
    native(service)
    native(service, version="new-version")
    service.ingest_evidence([evidence(project_id="other")])
    assert service.list_incidents()["total"] == 2
    request = {
        "client_request_id": str(uuid4()),
        "records": [
            {
                "source_type": "slack",
                "source_id": "message-1",
                "timestamp": datetime.now(UTC).isoformat(),
                "project_id": "demo",
                "text": "Release checklist creation is broken",
            }
        ],
    }
    receipt = service.import_records(request)
    assert receipt["imported"] == 1 and len(receipt["incident_ids"]) == 1
    assert service.import_records(request) == receipt
    request["records"][0]["text"] = "changed"
    with pytest.raises(IncidentError, match="different input"):
        service.import_records(request)
    detail = service.get_incident(receipt["incident_ids"][0])
    assert len(detail["run_ids"]) == 2
    assert detail["recurrence"]["before"] == {"affected": 2, "comparable": 2}
    assert detail["recurrence"]["after"] == {"affected": 0, "comparable": 0}
    assert any(not e["trusted"] for e in detail["evidence"])


def test_intermediate_checks_dont_open_incident(service):
    native(service, error=False, status="running")
    assert service.list_incidents()["total"] == 0


def test_analysis_single_call_saved_failure_and_restart(service, monkeypatch):
    native(service)
    identity = service.list_incidents()["items"][0]["id"]
    calls = []

    def complete(request, on_event, cancelled):
        calls.append(request)
        return {
            "success": True,
            "output": {
                "answer": "Unsupported citation",
                "evidence_ids": [str(uuid4())],
                "hypotheses": [],
                "missing_evidence": [],
            },
        }

    monkeypatch.setattr("epoch_backend.incidents.debugger_bridge.complete", complete)
    payload = {"client_request_id": str(uuid4())}
    result = service.analyze(identity, payload)
    assert result["status"] == "failed"
    assert service.analyze(identity, payload) == result
    assert len(calls) == 1 and calls[0]["timeout_seconds"] == 60
    with service._connect() as db:
        db.execute(
            "UPDATE requests SET record=? WHERE id=?",
            (json.dumps({**result, "status": "running"}), payload["client_request_id"]),
        )
    service.initialize()
    assert service.analyze(identity, payload)["status"] == "interrupted"
    assert len(calls) == 1


def test_api_detail_and_question_validation(service):
    native(service)
    app = FastAPI()
    app.include_router(incident_router(service))
    with TestClient(app) as client:
        identity = client.get("/api/incidents").json()["items"][0]["id"]
        assert client.get(f"/api/incidents/{identity}").json()["evidence"][0]["trusted"]
        assert (
            client.post(
                f"/api/incidents/{identity}/questions", json={"client_request_id": str(uuid4())}
            ).status_code
            == 422
        )
        assert client.get(f"/api/incidents/{uuid4()}").status_code == 404
        assert (
            client.post(
                "/api/evidence/import",
                json={"client_request_id": str(uuid4()), "records": [{"source_type": "epoch"}]},
            ).status_code
            == 422
        )


def test_recurrence_excludes_rollback_and_keeps_recovery_separate(service):
    record, sandbox, event = native(service)
    published = datetime.now(UTC).isoformat()
    report = {
        "id": str(uuid4()),
        "trigger": event,
        "run_id": record["id"],
        "created_at": event["emitted_at"],
        "finished_at": published,
        "status": "published",
        "version_id": "repaired",
        "editable_target": "checklist_serializer.py",
        "attempts": [{"proofs": [{"kind": "original_replay"}, {"kind": "fresh_release"}]}],
    }
    record.update(
        status="completed",
        environment_version="repaired",
        supervision={"operations": [{"repairs": [report]}]},
    )
    record["verification"]["passed"] = True
    service.refresh_run(record, sandbox)
    native(service, error=False, status="completed", version="repaired")
    native(service, error=False, status="completed", version="builtin")
    identity = service.list_incidents()["items"][0]["id"]
    counts = service.get_incident(identity)["recurrence"]
    # The test's state.changed event alone does not establish actual tool use.
    assert counts == {
        "before": {"affected": 1, "comparable": 1},
        "after": {"affected": 0, "comparable": 0},
        "recovered_runs": 1,
        "verification_runs": 2,
        "excluded_runs": 2,
    }


def test_explicit_context_trigger_survives_restart_and_does_not_rewrite_event(service):
    record, sandbox, event = native(service, error=False, status="running")
    trigger = {**event, "repair_target": "runbook_selector.py"}
    service.refresh_run(record, sandbox, trigger=trigger)
    report = {
        "id": str(uuid4()),
        "trigger": trigger,
        "status": "published",
        "version_id": "fixed",
        "run_id": record["id"],
        "created_at": event["emitted_at"],
        "finished_at": datetime.now(UTC).isoformat(),
    }
    record.update(
        status="completed",
        environment_version="fixed",
        supervision={"operations": [{"repairs": [report]}]},
    )
    service.refresh_run(record, sandbox)
    detail = service.get_incident(service.list_incidents()["items"][0]["id"])
    assert detail["status"] == "monitoring"
    assert len([item for item in detail["evidence"] if item["error_code"]]) == 1
    assert any(
        e["native_event_id"] == event["id"] and not e["error_code"] for e in detail["evidence"]
    )
    restarted = IncidentService(service.path.parent)
    restarted.initialize()
    restarted.refresh_run(record, sandbox)
    assert restarted.list_incidents()["total"] == 1


def test_analysis_reserves_external_reports_with_many_native_events(service, monkeypatch):
    record, sandbox, event = native(service)
    with service._connect() as db:
        for index in range(30):
            service._put(
                db,
                evidence(
                    source_type="epoch",
                    source_id=f"progress-{index}",
                    run_id=record["id"],
                    error_code=None,
                    text=f"Native progress event {index}",
                ),
                True,
            )
    report = {
        "source_type": "support",
        "source_id": "customer-report",
        "project_id": "demo",
        "timestamp": datetime.now(UTC).isoformat(),
        "run_id": record["id"],
        "text": "Release checklist broken for customer Orion",
    }
    receipt = service.import_records({"client_request_id": str(uuid4()), "records": [report]})
    supplied = []

    def complete(request, on_event, cancelled):
        supplied.extend(request["input"]["evidence"])
        return {
            "success": True,
            "output": {
                "answer": "The attached customer report names Orion.",
                "evidence_ids": receipt["evidence_ids"],
                "hypotheses": [],
                "missing_evidence": [],
            },
        }

    monkeypatch.setattr("epoch_backend.incidents.debugger_bridge.complete", complete)
    identity = service.list_incidents()["items"][0]["id"]
    answer = service.analyze(
        identity,
        {"client_request_id": str(uuid4()), "question": "Which customer reported the issue?"},
    )
    assert answer["status"] == "completed"
    assert len(supplied) == 24
    assert any(
        item["id"] == receipt["evidence_ids"][0] and not item["trusted"] for item in supplied
    )
    assert any(item["error_code"] for item in supplied)
    assert any("external report" in item["reason"] for item in answer["selection_reasons"])


def test_cli_import_requires_retained_request_id_before_dispatch(tmp_path, monkeypatch, capsys):
    from epoch_backend.incident_cli import handle_incident_command

    source = tmp_path / "records.json"
    source.write_text("[]")
    args = SimpleNamespace(command="import-evidence", file=source, request_id=None)
    settings = SimpleNamespace(host="127.0.0.1", port=8000)
    calls = []

    def unavailable(request, timeout):
        from urllib.error import URLError

        calls.append(request)
        raise URLError("offline test double")

    monkeypatch.setattr("epoch_backend.incident_cli.urlopen", unavailable)
    with pytest.raises(ValueError, match="Supply --request-id"):
        handle_incident_command(args, settings)
    assert not calls
    args.request_id = str(uuid4())
    assert handle_incident_command(args, settings) == 1
    assert args.request_id in capsys.readouterr().err
    assert len(calls) == 1
