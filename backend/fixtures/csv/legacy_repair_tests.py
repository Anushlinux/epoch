"""Actual simulated state and publication with explicitly substituted model calls."""

import json
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from epoch_backend import debugger_bridge, hermes_bridge
from epoch_backend.app import create_app
from epoch_backend.config import Settings
from epoch_backend.csv_repair import BASELINE_KEYS, CsvRepairs
from epoch_backend.csv_sandbox import SAMPLE_CSV, CsvRegistry, CsvSandbox

MAPPING = {"name_field": "name", "email_field": "email"}


def sandbox_from(request):
    args = request["mcp_args"]
    return CsvSandbox(
        Path(args[args.index("--database") + 1]), request["task_id"], request["run_id"]
    )


def fake_hermes(request, *_):
    sandbox = sandbox_from(request)
    registry = CsvRegistry(sandbox)
    registry.discover_tools()
    registry.describe_tool("customers.import")
    source = (
        request["brief"][request["brief"].index("name,email\n") :]
        if "name,email\n" in request["brief"]
        else SAMPLE_CSV
    )
    result = registry.invoke_tool(
        "customers.import",
        {
            "csv_text": source,
            "idempotency_key": "recovered"
            if Path(request["work_dir"]).name == "recovery"
            else "original",
        },
    )
    registry.invoke_tool("customers.list", {})
    baseline = dict.fromkeys(BASELINE_KEYS, "explicit-test-double")
    if _ and callable(_[0]):
        _[0]({"type": "executor.baseline", "data": baseline})
    return {
        "success": True,
        "final_response": str(result["result"]["status"]),
        "baseline": baseline,
    }


def finish(client, chat, response):
    assert response.status_code == 202, response.text
    client.app.state.execution._thread.join(10)
    assert not client.app.state.execution._thread.is_alive()
    return client.get(f"/api/chats/{chat}/operations/{response.json()['id']}").json()


def create(client, project="demo", mode="csv_broken"):
    return client.post(
        "/api/chats",
        json={"client_request_id": str(uuid4()), "project_id": project, "environment": mode},
    ).json()["id"]


def send(client, chat):
    return finish(
        client,
        chat,
        client.post(
            f"/api/chats/{chat}/messages",
            json={
                "client_request_id": str(uuid4()),
                "content": "Import the sample customers and list them.",
            },
        ),
    )


def investigate(client, chat):
    return finish(
        client,
        chat,
        client.post(
            f"/api/chats/{chat}/csv-repair",
            json={
                "client_request_id": str(uuid4()),
                "question": "Fix the import failure.",
            },
        ),
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(hermes_bridge, "detect_installation", lambda: {"available": True})
    monkeypatch.setattr(debugger_bridge, "detect_debugger", lambda: {"available": True})
    monkeypatch.setattr(hermes_bridge, "execute", fake_hermes)

    def propose(request, *_):
        assert "repair" in request["schema"]["properties"]
        failure = next(e for e in request["input"]["evidence"] if e["type"] == "tool.service_error")
        assert "emailAddress" in failure["text"]
        return {
            "success": True,
            "output": {
                "answer": "The outgoing field does not match the service contract.",
                "evidence_ids": [failure["id"]],
                "hypotheses": [],
                "missing_evidence": [],
                "repair": MAPPING,
            },
        }

    monkeypatch.setattr(debugger_bridge, "complete", propose)
    with TestClient(create_app(Settings(data_dir=tmp_path, telemetry_enabled=False))) as http:
        yield http


def test_debugger_applies_verified_mapping_then_hermes_recovers_and_later_chat_reuses(
    client, tmp_path
):
    chat = create(client)
    send(client, chat)
    before = client.get(f"/api/chats/{chat}/environment").json()
    assert not before["verification"]["passed"]
    outcome = investigate(client, chat)
    assert outcome["status"] == "completed", outcome
    repair = outcome["analysis"]["repair_result"]
    assert repair["status"] == "published", repair
    assert {c["name"] for c in repair["checks"] if c["passed"]} >= {
        "original_hermes",
        "fresh_hermes",
        "original_state",
        "invalid_atomic",
        "deduplication",
    }
    after = client.get(f"/api/chats/{chat}/environment").json()
    assert after["verification"]["passed"]
    assert after["criteria"] == before["criteria"]
    assert after["adapter_mode"] == "broken", "Do not switch to the healthy control"
    assert after["imports"][0] == before["imports"][0], "Retain the rejected receipt"
    assert len(after["imports"]) == 2
    assert after["repair"]["mapping"] == MAPPING
    sandbox = CsvSandbox(tmp_path / "chats" / chat / "sandbox.sqlite3", chat, chat)
    assert sandbox.import_customers(SAMPLE_CSV, "original") == before["imports"][0]
    assert sandbox.snapshot()["verification"]["passed"]
    stored = CsvRepairs(tmp_path)  # Reopened durable store, not in-memory state.
    assert stored.active("demo")["version"] == repair["version"]
    assert stored.active("unrelated") is None
    later = create(client)
    assert client.get(f"/api/chats/{later}/environment").json()["customers"] == []
    send(client, later)
    reused = client.get(f"/api/chats/{later}/environment").json()
    assert reused["verification"]["passed"]
    description = next(e for e in reused["events"] if e["type"] == "tool.described")
    assert description["payload"]["result"]["version"] == repair["version"]
    assert "service email" in description["payload"]["result"]["description"]
    assert all(e["type"] != "tool.service_error" for e in reused["events"])
    other = create(client, "other")
    send(client, other)
    assert not client.get(f"/api/chats/{other}/environment").json()["verification"]["passed"]
    control = create(client, mode="csv_healthy")
    assert client.get(f"/api/chats/{control}/environment").json()["repair"] is None
    rollback = client.post(
        f"/api/chats/{chat}/csv-repair/rollback", json={"expected_version": repair["version"]}
    )
    assert rollback.status_code == 200 and rollback.json()["repair"] is None
    assert (
        client.post(
            f"/api/chats/{chat}/csv-repair/rollback", json={"expected_version": repair["version"]}
        ).status_code
        == 409
    )
    assert stored.active("demo") is None
    rolled_back = create(client)
    send(client, rolled_back)
    assert not client.get(f"/api/chats/{rolled_back}/environment").json()["verification"]["passed"]
    with sqlite3.connect(stored.path) as db:
        assert (
            json.loads(db.execute("SELECT record FROM versions").fetchone()[0])["status"]
            == "published"
        )


@pytest.mark.parametrize(
    "mapping",
    [
        {"name_field": "name", "email_field": "emailAddress"},
        {"name_field": "email", "email_field": "name"},
        {"name_field": "email", "email_field": "email"},
    ],
)
def test_bad_candidate_is_retained_and_never_published(tmp_path, monkeypatch, mapping):
    sandbox = CsvSandbox(tmp_path / "sandbox.sqlite3", "task", "run")
    sandbox.initialize()
    sandbox.import_customers(SAMPLE_CSV, "original")
    repairs = CsvRepairs(tmp_path)
    failure = repairs.eligible(sandbox)
    assert failure
    monkeypatch.setattr(
        hermes_bridge, "execute", lambda *_: pytest.fail("No Hermes on bad component")
    )
    record = repairs.verify_publish(
        sandbox,
        mapping,
        failure,
        {"brief": "Import sample", "history": []},
        threading.Event(),
        lambda _: None,
    )
    assert record["status"] == "rejected"
    assert repairs.active("demo") is None
    assert sandbox.metadata().get("repair") is None
    assert sandbox.list_customers() == []
    assert repairs.eligible(sandbox) is None, "One repair attempt per observed failure"
    with sqlite3.connect(repairs.path) as db:
        saved = json.loads(db.execute("SELECT record FROM versions").fetchone()[0])
    assert saved["mapping"] == mapping and saved["checks"]


def test_fresh_verification_failure_cannot_publish(client, monkeypatch, tmp_path):
    chat = create(client)
    send(client, chat)

    def execute(request, *args):
        if "/fresh/" in request["work_dir"]:
            return {"success": True, "final_response": "Done"}  # Claim without effects.
        return fake_hermes(request, *args)

    monkeypatch.setattr(hermes_bridge, "execute", execute)
    result = investigate(client, chat)
    record = result["analysis"]["repair_result"]
    assert record["status"] == "rejected"
    assert record["checks"][-1]["name"] == "fresh_hermes"
    assert not record["checks"][-1]["passed"]
    assert CsvRepairs(tmp_path).active("demo") is None
    assert client.get(f"/api/chats/{chat}/environment").json()["customers"] == []


def test_cancel_during_verification_prevents_publication(client, monkeypatch, tmp_path):
    chat = create(client)
    send(client, chat)

    def cancel_execution(request, events, cancel):
        result = fake_hermes(request)
        cancel.set()
        return result

    monkeypatch.setattr(hermes_bridge, "execute", cancel_execution)
    result = investigate(client, chat)
    assert result["analysis"]["repair_result"]["status"] == "cancelled"
    assert CsvRepairs(tmp_path).active("demo") is None
    assert client.get(f"/api/chats/{chat}/environment").json()["customers"] == []


def test_recovery_failure_does_not_erase_published_repair_or_claim_task_success(
    client, monkeypatch
):
    chat = create(client)
    send(client, chat)

    def execute(request, *args):
        if Path(request["work_dir"]).name == "recovery":
            return {"success": False, "error": {"code": "provider_failed"}}
        return fake_hermes(request, *args)

    monkeypatch.setattr(hermes_bridge, "execute", execute)
    result = investigate(client, chat)
    assert result["analysis"]["repair_result"]["status"] == "published"
    assert not result["analysis"]["recovery"]["verification"]["passed"]
    assert "Recovery did not finish successfully" in result["analysis"]["answer"]
    assert client.get(f"/api/chats/{chat}/environment").json()["repair"] is not None


def test_changed_executor_baseline_rejects_even_when_customer_state_passes(client, monkeypatch):
    chat = create(client)
    send(client, chat)

    def changed(request, *args):
        result = fake_hermes(request, *args)
        result["baseline"]["model_configuration_sha256"] = "changed-model"
        return result

    monkeypatch.setattr(hermes_bridge, "execute", changed)
    result = investigate(client, chat)
    repair = result["analysis"]["repair_result"]
    assert repair["status"] == "rejected"
    assert repair["checks"][-1]["name"] == "original_hermes"
    assert client.get(f"/api/chats/{chat}/environment").json()["repair"] is None


def test_candidate_cannot_cite_only_an_assistant_claim(client, monkeypatch):
    chat = create(client)
    send(client, chat)

    def unsupported(request, *_):
        claim = next(e for e in request["input"]["evidence"] if e.get("role") == "assistant")
        return {
            "success": True,
            "output": {
                "answer": "Change the mapping.",
                "evidence_ids": [claim["id"]],
                "hypotheses": [],
                "missing_evidence": [],
                "repair": MAPPING,
            },
        }

    monkeypatch.setattr(debugger_bridge, "complete", unsupported)
    monkeypatch.setattr(hermes_bridge, "execute", lambda *_: pytest.fail("Unsourced repair"))
    result = investigate(client, chat)
    assert result["status"] == "failed" and result["error"]["code"] == "unsourced_repair"
    assert result["analysis"]["proposal_output"]["repair"] == MAPPING
    assert client.get(f"/api/chats/{chat}/environment").json()["repair"] is None


def test_non_sample_failure_is_out_of_scope_but_sample_formatting_does_not_block_repair(tmp_path):
    sandbox = CsvSandbox(tmp_path / "sandbox.sqlite3", "task", "run")
    sandbox.initialize()
    sandbox.import_customers("name,email\nDifferent,different@example.test\n", "different")
    repairs = CsvRepairs(tmp_path)
    assert repairs.eligible(sandbox) is None
    reformatted = SAMPLE_CSV.replace("Asha,asha@example.test", '"Asha","asha@example.test"')
    reformatted = reformatted.replace("\n", "\r\n")
    sandbox.import_customers(reformatted, "sample")
    assert repairs.eligible(sandbox)


def test_investigation_saves_proposal_without_execution_then_explicit_action_repairs(
    client, monkeypatch
):
    chat = create(client)
    send(client, chat)
    capability = client.get(f"/api/chats/{chat}/environment").json()["repair_capability"]
    assert capability["supported"] and capability["eligible"]
    request = {"client_request_id": str(uuid4()), "question": "Explain the failure."}
    monkeypatch.setattr(
        hermes_bridge, "execute", lambda *_: pytest.fail("Diagnosis cannot execute")
    )
    diagnosis = finish(client, chat, client.post(f"/api/chats/{chat}/debugger", json=request))
    assert diagnosis["action"] == "investigate"
    assert diagnosis["analysis"]["repair"] == MAPPING
    assert "repair_result" not in diagnosis["analysis"]
    assert client.get(f"/api/chats/{chat}/environment").json()["customers"] == []
    assert client.post(f"/api/chats/{chat}/csv-repair", json=request).status_code == 409
    monkeypatch.setattr(hermes_bridge, "execute", fake_hermes)
    repair_request = {"client_request_id": str(uuid4()), "question": "Apply the fix."}
    response = client.post(f"/api/chats/{chat}/csv-repair", json=repair_request)
    repaired = finish(client, chat, response)
    assert (
        repaired["action"] == "repair"
        and repaired["analysis"]["repair_result"]["status"] == "published"
    )
    monkeypatch.setattr(hermes_bridge, "execute", lambda *_: pytest.fail("Do not replay repair"))
    replay = client.post(f"/api/chats/{chat}/csv-repair", json=repair_request)
    assert replay.status_code == 200 and replay.json()["id"] == repaired["id"]
    unavailable = client.get(f"/api/chats/{chat}/environment").json()["repair_capability"]
    assert not unavailable["eligible"] and "already active" in unavailable["reason"]


def test_explicit_repair_rejects_unsupported_or_unfailed_environments_without_model(
    client, monkeypatch
):
    monkeypatch.setattr(debugger_bridge, "complete", lambda *_: pytest.fail("Not eligible"))
    for mode in ("default", "csv_healthy", "csv_broken"):
        chat = create(client, mode=mode)
        result = client.post(
            f"/api/chats/{chat}/csv-repair", json={"client_request_id": str(uuid4())}
        )
        assert result.status_code == 409
