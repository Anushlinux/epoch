"""CSV chat routing and debugger evidence through real simulated tools, no models."""

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from epoch_backend import debugger_bridge, hermes_bridge
from epoch_backend.app import create_app
from epoch_backend.config import Settings
from epoch_backend.csv_sandbox import SAMPLE_CSV, CsvSandbox


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "detect_installation", lambda: {"available": True})
    monkeypatch.setattr(debugger_bridge, "detect_debugger", lambda: {"available": True})
    monkeypatch.setattr(debugger_bridge, "complete", lambda *_: pytest.fail("Unexpected analysis"))
    with TestClient(create_app(Settings(data_dir=tmp_path, telemetry_enabled=False))) as http:
        yield http


def create(client, environment="csv_broken", request_id=None):
    payload = {"client_request_id": request_id or str(uuid4()), "environment": environment}
    response = client.post("/api/chats", json=payload)
    assert response.status_code in (200, 201), response.text
    return response.json()


def finish(client, chat_id, response):
    assert response.status_code == 202, response.text
    client.app.state.execution._thread.join(5)
    assert not client.app.state.execution._thread.is_alive()
    return client.get(f"/api/chats/{chat_id}/operations/{response.json()['id']}").json()


def test_environment_is_explicit_immutable_and_creation_is_read_only(client, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "execute", lambda *_: pytest.fail("Unexpected Hermes"))
    request_id = str(uuid4())
    chat = create(client, request_id=request_id)
    assert create(client, request_id=request_id)["id"] == chat["id"]
    snapshot = client.get(f"/api/chats/{chat['id']}/environment").json()
    assert snapshot["environment"] == "csv_broken"
    assert snapshot["sample_csv"] == SAMPLE_CSV
    assert snapshot["customers"] == [] and snapshot["imports"] == []
    assert not snapshot["verification"]["passed"]
    assert (
        client.post(
            "/api/chats", json={"client_request_id": request_id, "environment": "csv_healthy"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/chats", json={"client_request_id": str(uuid4()), "environment": "../../other"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/chats/{chat['id']}/environment", json={"environment": "csv_healthy"}
        ).status_code
        == 405
    )
    assert client.get("/api/tasks").json()["total"] == 0
    standard = create(client, "default")
    assert client.get(f"/api/chats/{standard['id']}/environment").json() == {
        "environment": "default",
        "simulated": True,
    }


@pytest.mark.parametrize(
    "environment, count, passed", [("csv_broken", 0, False), ("csv_healthy", 3, True)]
)
def test_csv_chat_executes_isolated_tools_and_supplies_trusted_debugger_evidence(
    client, monkeypatch, environment, count, passed
):
    from epoch_backend.csv_sandbox import CsvRegistry

    chat = create(client, environment)
    chat_id = chat["id"]
    evidence_before = client.get(f"/api/chats/{chat_id}/environment").json()["criteria"]
    requests = []

    def execute(request, on_event, cancel):
        requests.append(request)
        args = request["mcp_args"]
        assert args[-2:] == ["--environment", "csv_import"]
        sandbox = CsvSandbox(Path(args[args.index("--database") + 1]), chat_id, chat_id)
        registry = CsvRegistry(sandbox)
        names = {tool["name"] for tool in registry.discover_tools()["result"]["tools"]}
        assert names == {
            "customers.read_sample",
            "customers.import",
            "customers.list",
            "customers.get_import_status",
        }
        result = registry.invoke_tool(
            "customers.import", {"csv_text": SAMPLE_CSV, "idempotency_key": "sample-1"}
        )
        for _ in range(10):
            registry.invoke_tool("customers.list", {})
        return {"success": True, "final_response": "Import returned: " + str(result["ok"])}

    monkeypatch.setattr(hermes_bridge, "execute", execute)
    response = client.post(
        f"/api/chats/{chat_id}/messages",
        json={
            "client_request_id": str(uuid4()),
            "content": "Import the sample and preserve all three records without duplicates.",
        },
    )
    assert finish(client, chat_id, response)["status"] == "completed"
    snapshot = client.get(f"/api/chats/{chat_id}/environment").json()
    assert len(snapshot["customers"]) == count
    assert snapshot["verification"]["passed"] is passed
    assert snapshot["criteria"] == evidence_before
    analysis_inputs = []

    def analyze(request, *_):
        analysis_inputs.append(request["input"])
        checks = next(e for e in request["input"]["evidence"] if e["type"] == "evaluation.csv")
        assert checks["trusted"] is True
        return {
            "success": True,
            "output": {
                "answer": "The saved checks describe the observed result.",
                "evidence_ids": [checks["id"]],
                "hypotheses": [],
                "missing_evidence": [],
                **({"repair": None} if "repair" in request["schema"]["properties"] else {}),
            },
        }

    monkeypatch.setattr(debugger_bridge, "complete", analyze)
    result = finish(
        client,
        chat_id,
        client.post(
            f"/api/chats/{chat_id}/debugger",
            json={"client_request_id": str(uuid4()), "question": "Why did the import fail?"},
        ),
    )
    assert result["status"] == "completed"
    assert len(requests) == 1
    assert "No generic trusted" not in str(result["analysis"]["missing_evidence"])
    if not passed:
        assert "emailAddress" in str(analysis_inputs[0]["evidence"]), (
            "failure wire evidence must survive later reads"
        )
    assert client.get(f"/api/chats/{chat_id}/environment").json()["criteria"] == evidence_before
    assert client.get("/api/tasks").json()["total"] == 0
