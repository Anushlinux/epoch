"""API/CLI contract wiring tests use explicit service doubles, never model inference."""

import argparse
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from epoch_backend import debugger_bridge, workflow_cli
from epoch_backend.app import create_app
from epoch_backend.cli import main
from epoch_backend.config import Settings
from epoch_backend.contracts import Checkpoint, SourceReference, TaskBrief
from epoch_backend.execution import ExecutionError
from epoch_backend.execution_contracts import ExecutionRecord, ReleaseRunRequest
from epoch_backend.storage import RequestConflict
from epoch_backend.supervision_contracts import SupervisionOperation, SupervisionState


def record(*, supervised=True, status="completed"):
    task_id, run_id, revision_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    request = ReleaseRunRequest(
        client_request_id=uuid4(), workflow="release", release="2.4", supervised=supervised
    )
    brief = TaskBrief(
        id=uuid4(),
        task_id=task_id,
        instructions="Test fixture release",
        created_at=now,
        checkpoints=[
            Checkpoint(
                id=uuid4(),
                description="A release ticket exists",
                scope="demo",
                verification_rule="Test fixture check",
                evaluator_version="test-v1",
                source_refs=[
                    SourceReference(
                        id=uuid4(),
                        kind="user_request",
                        locator=f"task:{task_id}",
                        attribution="explicit",
                        excerpt="Prepare release 2.4",
                    )
                ],
            )
        ],
    )
    supervision = None
    if supervised:
        operation = SupervisionOperation(
            id=revision_id,
            client_request_id=request.client_request_id,
            trigger="initial",
            user_input="Prepare release 2.4",
            request=request.model_dump(mode="json"),
            status=status,
            created_at=now,
            max_turns=20,
            timeout_seconds=600,
            brief=brief,
        )
        supervision = SupervisionState(current_revision_id=revision_id, operations=[operation])
    return ExecutionRecord(
        id=run_id,
        task_id=task_id,
        request=request,
        status=status,
        brief=brief,
        created_at=now,
        updated_at=now,
        supervision=supervision,
    )


def feedback_body(result):
    return {
        "client_request_id": str(uuid4()),
        "expected_revision_id": str(result.supervision.current_revision_id),
        "message": "Also include rollback instructions.",
    }


@pytest.mark.parametrize("path,clarification", [("feedback", False), ("clarifications", True)])
def test_feedback_routes_keep_identity_input_and_idempotent_status(
    tmp_path, monkeypatch, path, clarification
):
    app = create_app(Settings(data_dir=tmp_path, enable_hermes=False, _env_file=None))
    result = record()
    calls = []

    def submit(run_id, payload, *, clarification=False):
        calls.append((run_id, payload, clarification))
        return result, len(calls) == 1

    monkeypatch.setattr(app.state.execution, "feedback", submit)
    with TestClient(app) as client:
        body = feedback_body(result)
        first = client.post(f"/api/runs/{result.id}/{path}", json=body)
        second = client.post(f"/api/runs/{result.id}/{path}", json=body)
    assert (first.status_code, second.status_code) == (202, 200)
    assert first.json() == second.json() == result.model_dump(mode="json")
    assert len(calls) == 2 and calls[0][0] == result.id
    assert calls[0][1].model_dump(mode="json") == {
        **body,
        "max_turns": 20,
        "timeout_seconds": 600,
    }
    assert calls[0][2] is clarification


@pytest.mark.parametrize(
    "change",
    [{"max_turns": 21}, {"timeout_seconds": 601}, {"message": " "}, {"expected_revision_id": None}],
)
def test_feedback_validation_stops_invalid_requests_before_service(tmp_path, monkeypatch, change):
    app = create_app(Settings(data_dir=tmp_path, enable_hermes=False, _env_file=None))
    result = record()
    monkeypatch.setattr(
        app.state.execution,
        "feedback",
        lambda *args, **kwargs: pytest.fail("invalid request reached service"),
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/runs/{result.id}/feedback", json={**feedback_body(result), **change}
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_feedback_stale_revision_error_is_exposed_without_retry(tmp_path, monkeypatch):
    app = create_app(Settings(data_dir=tmp_path, enable_hermes=False, _env_file=None))
    result = record()

    def reject(*args, **kwargs):
        raise ExecutionError("stale_revision", "Reload the latest revision before editing.")

    monkeypatch.setattr(app.state.execution, "feedback", reject)
    with TestClient(app) as client:
        response = client.post(f"/api/runs/{result.id}/feedback", json=feedback_body(result))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_revision"


@pytest.mark.parametrize("supervised", [False, True])
def test_revisions_are_saved_operations_or_empty_for_direct_run(tmp_path, monkeypatch, supervised):
    app = create_app(Settings(data_dir=tmp_path, enable_hermes=False, _env_file=None))
    result = record(supervised=supervised)
    monkeypatch.setattr(app.state.execution, "get", lambda run_id: result)
    with TestClient(app) as client:
        response = client.get(f"/api/runs/{result.id}/revisions")
        schemas = client.get("/openapi.json").json()
    assert response.status_code == 200
    expected = (
        [op.model_dump(mode="json") for op in result.supervision.operations] if supervised else []
    )
    assert response.json() == expected
    assert (
        schemas["paths"]["/api/runs/{run_id}/revisions"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["type"]
        == "array"
    )


def test_debugger_info_is_read_only_and_does_not_infer(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EPOCH_DATA_DIR", str(tmp_path / "absent"))
    monkeypatch.setattr(
        debugger_bridge,
        "detect_debugger",
        lambda: {
            "available": True,
            "model": "gpt-5.6-luna",
            "provider": "openai-codex",
            "connectivity_verified": False,
        },
    )
    monkeypatch.setattr(debugger_bridge, "complete", lambda *args: pytest.fail("No inference"))
    assert main(["debugger-info"]) == 0
    assert json.loads(capsys.readouterr().out)["model"] == "gpt-5.6-luna"
    assert not (tmp_path / "absent").exists()


def parsed(*args):
    parser = argparse.ArgumentParser()
    workflow_cli.add_commands(parser.add_subparsers(dest="command", required=True))
    return parser.parse_args(args)


def test_run_release_defaults_preserve_direct_mode_and_requested_limits():
    args = parsed("run-release")
    assert args.max_turns == 20 and args.timeout == 600
    assert args.supervised is False and args.demo_omit_notification is False
    supervised = parsed("run-release", "--supervised", "--demo-omit-notification")
    assert supervised.supervised and supervised.demo_omit_notification


@pytest.mark.parametrize("command", ["feedback", "clarify"])
def test_cli_feedback_forwards_revision_request_id_and_message(
    tmp_path, monkeypatch, capsys, command
):
    result = record()
    request_id = uuid4()
    calls = []

    class Service:
        def __init__(self, *args):
            pass

        def initialize(self):
            pass

        def close(self):
            calls.append("closed")

        def feedback(self, run_id, payload, *, clarification=False):
            calls.append((run_id, payload, clarification))
            return result, True

        def get(self, run_id):
            return result

    monkeypatch.setattr(workflow_cli, "ExecutionService", Service)
    monkeypatch.setenv("EPOCH_DATA_DIR", str(tmp_path))
    outcome = main(
        [
            command,
            str(result.id),
            "--message",
            "Add rollback instructions.",
            "--expected-revision",
            str(result.supervision.current_revision_id),
            "--request-id",
            str(request_id),
            "--max-turns",
            "12",
            "--timeout",
            "300",
        ]
    )
    assert outcome == 0
    assert json.loads(capsys.readouterr().out)["id"] == str(result.id)
    run_id, payload, clarification = calls[0]
    assert run_id == result.id and payload.client_request_id == request_id
    assert payload.expected_revision_id == result.supervision.current_revision_id
    assert payload.message == "Add rollback instructions."
    assert payload.max_turns == 12 and payload.timeout_seconds == 300
    assert clarification is (command == "clarify")
    assert calls[-1] == "closed"


def test_cli_supervised_flags_reach_service_and_needs_input_returns_failure(
    tmp_path, monkeypatch, capsys
):
    result = record(status="needs_input")
    calls = []

    class Service:
        def __init__(self, *args):
            pass

        def initialize(self):
            pass

        def close(self):
            calls.append("closed")

        def start(self, task_id, payload):
            calls.append(payload)
            return result, True

        def get(self, run_id):
            return result

    monkeypatch.setattr(workflow_cli, "ExecutionService", Service)
    monkeypatch.setenv("EPOCH_DATA_DIR", str(tmp_path))
    assert main(["run-release", "--supervised", "--demo-omit-notification"]) == 1
    assert calls[0].supervised is True and calls[0].demo_omit_notification is True
    assert calls[0].max_turns == 20 and calls[0].timeout_seconds == 600
    assert json.loads(capsys.readouterr().out)["status"] == "needs_input"
    assert calls[-1] == "closed"


def test_cli_conflicting_request_id_is_reported_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EPOCH_DATA_DIR", str(tmp_path))

    def conflict(*args):
        raise RequestConflict("Caller details must not be echoed")

    monkeypatch.setattr(workflow_cli, "handle_command", conflict)
    assert (
        main(
            [
                "feedback",
                str(uuid4()),
                "--message",
                "Add rollback",
                "--expected-revision",
                str(uuid4()),
            ]
        )
        == 1
    )
    error = capsys.readouterr().err
    assert "request_conflict" in error
    assert "Traceback" not in error and "Caller details" not in error
