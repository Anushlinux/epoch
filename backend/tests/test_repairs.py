"""Repair orchestration tests use explicit LLM/runner doubles, never host exec."""

import json
import sqlite3
import threading
from uuid import uuid4

import pytest
from test_supervision import ModelHarness, ready_plan, start
from test_supervision import service as service

from epoch_backend import candidate_runner, hermes_bridge, repair_controller
from epoch_backend.candidate_runner import CandidateError
from epoch_backend.environment_store import REQUIRED_PROOFS, EnvironmentStore
from epoch_backend.operation_budget import BudgetExceeded
from epoch_backend.repair_budget import RepairBudget
from epoch_backend.repair_controller import supported_error
from epoch_backend.sandbox import Sandbox, SandboxError
from epoch_backend.tool_registry import ToolRegistry

SOURCE = (
    "def serialize_checklist(ticket_id, title, items, *, legacy=False):\n"
    '    return {"ticket_id": ticket_id, "title": title, "items": items}\n'
)
IMAGE = "sha256:" + "a" * 64


@pytest.fixture
def environments(tmp_path):
    store = EnvironmentStore(tmp_path / "environments.sqlite3")
    store.initialize()
    return store


def stage(store, project="demo", source=SOURCE, parent="builtin"):
    return store.stage(
        project,
        source,
        image_id=IMAGE,
        runner_version="docker-serializer-v1",
        parent=parent,
        diagnosis={"fixture": True},
        diff="test-only",
    )


def proofs(version):
    return [
        {
            "kind": kind,
            "passed": True,
            "artifact_sha256": version["artifact_sha256"],
            "test_double": True,
        }
        for kind in sorted(REQUIRED_PROOFS)
    ]


def test_publication_requires_every_exact_artifact_proof(environments):
    version = stage(environments)
    for invalid in (
        proofs(version)[:-1],
        [{**p, "artifact_sha256": "f" * 64} for p in proofs(version)],
        [{**p, "passed": False} for p in proofs(version)],
    ):
        with pytest.raises(CandidateError, match="Every required"):
            environments.publish(version["id"], invalid, expected_active="builtin")
    assert environments.active_id("demo") == "builtin"
    with pytest.raises(CandidateError):
        environments.manifest("demo", version["id"])


def test_persisted_publication_scope_cas_rollback_and_retry(environments):
    one, two = stage(environments), stage(environments)
    environments.publish(one["id"], proofs(one), expected_active="builtin")
    with pytest.raises(CandidateError, match="Active environment changed"):
        environments.publish(two["id"], proofs(two), expected_active="builtin")
    reopened = EnvironmentStore(environments.path)
    reopened.initialize()
    assert reopened.manifest("demo")["source"] == SOURCE
    assert reopened.active_id("other") == "builtin"
    with pytest.raises(CandidateError, match="another project"):
        reopened.manifest("other", one["id"])
    request = uuid4()
    result = reopened.rollback("demo", one["id"], request)
    assert result["version_id"] == "builtin"
    assert reopened.rollback("demo", one["id"], request) == result
    with pytest.raises(CandidateError):
        reopened.rollback("other", one["id"], request)
    assert reopened.active_id("demo") == "builtin"
    assert reopened.version(one["id"])["source"] == SOURCE


def test_rejected_and_tampered_artifacts_never_load(environments):
    version = stage(environments)
    environments.reject(version["id"], [], "regression")
    assert environments.version(version["id"])["status"] == "rejected"
    with pytest.raises(CandidateError):
        environments.manifest("demo", version["id"], staged=True)
    with sqlite3.connect(environments.path) as connection:
        value = environments.version(version["id"])
        value["source"] += "\n# changed"
        connection.execute(
            "UPDATE versions SET record=? WHERE id=?", (json.dumps(value), version["id"])
        )
    with pytest.raises(CandidateError, match="digest mismatch"):
        environments.version(version["id"])


def test_detector_uses_observed_error_not_scenario():
    assert (
        supported_error(
            [{"type": "sandbox.initialized", "payload": {"scenario": "broken_checklist"}}]
        )
        is None
    )
    event = {
        "type": "tool.error",
        "payload": {"tool_name": "checklists.create", "error": {"code": "adapter_contract_error"}},
    }
    assert supported_error([event]) == event
    assert (
        supported_error([{**event, "payload": {**event["payload"], "tool_name": "messages.send"}}])
        is None
    )


def test_repair_budget_verification_is_separate_but_overall_bounded(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("time.monotonic", lambda: clock[0])
    seen = []
    budget = RepairBudget(2, 10, threading.Event(), lambda *_: None, seen.append)
    budget.consume("debugger")
    with budget.verification_stage(lambda *_: None) as stage_budget:
        stage_budget.consume("executor")
        stage_budget.consume("executor")
        with pytest.raises(BudgetExceeded):
            stage_budget.consume("executor")
        clock[0] = 8
    assert budget.used == 1 and budget.overall_used == 3 and budget.deadline == 18
    with budget.verification_stage(lambda *_: None) as stage_budget:
        stage_budget.consume("executor")
        stage_budget.consume("executor")
    budget.consume("executor")
    assert budget.overall_used == 6
    with pytest.raises(BudgetExceeded):
        budget.reserve("verification_executor")
    clock[0] = 31
    with pytest.raises(BudgetExceeded):
        budget.overall_check()


@pytest.fixture
def fake_runner(monkeypatch):
    def run(self, source, arguments, **kwargs):
        # Declared test double: no generated Python is ever evaluated on this host.
        data = {k: v for k, v in arguments.items() if k != "legacy"}
        if source == "bad candidate":
            data["items"] = json.dumps(data["items"])
        return data

    monkeypatch.setattr(candidate_runner.CandidateRunner, "run", run)
    monkeypatch.setattr(
        repair_controller,
        "inspect_runner",
        lambda _, **kwargs: {"available": True, "image_id": IMAGE},
    )
    monkeypatch.setattr(
        repair_controller,
        "isolation_proof",
        lambda *_: {"kind": "isolation", "passed": True, "test_double": True},
    )


def proposal(request, source=SOURCE):
    event = request["input"]["observed_failure"]
    return {
        "outcome": "repair",
        "diagnosis": "Test-double diagnosis: items were stringified.",
        "evidence_ids": [event["id"]],
        "target": "checklist_serializer.py",
        "source": source,
        "uncertainty": "Explicit fixture, not actual model evidence.",
    }


def test_complete_repair_keeps_effects_and_later_discovery(service, monkeypatch, fake_runner):
    harness = ModelHarness(monkeypatch, plans=[ready_plan(), proposal], behaviors=["finish"] * 5)
    monkeypatch.setattr(
        hermes_bridge.Session, "account_verification_pause", lambda *_: None, raising=False
    )
    record = start(service, scenario="broken_checklist", repair_enabled=True)
    assert record.status == "completed", record.model_dump_json(indent=2)
    report = record.supervision.operations[0].repairs[0]
    assert report["status"] == "published" and len(report["attempts"]) == 1
    assert report["incident_ids"]
    incident = service.incidents.get_incident(report["incident_ids"][0])
    assert incident["status"] == "monitoring"
    assert any(repair["id"] == report["id"] for repair in incident["repairs"])
    assert all(p["passed"] for p in report["attempts"][0]["proofs"])
    assert len(harness.sessions) == 3  # Primary + isolated original + isolated fresh.
    before = report["state_before"]
    after = service.sandbox(record).snapshot()
    assert before["tickets"][0]["id"] == after["tickets"][0]["id"]
    assert all(len(after[k]) == 1 for k in ("tickets", "checklists", "messages"))
    assert record.supervision.operations[0].turns_used == 4  # Plan, failed pass, diagnosis, resume.
    assert record.supervision.operations[0].repair_budget["used"] == 6
    assert service.environments.manifest("demo")["source"] == SOURCE
    harness.debugger_outputs.append(ready_plan())
    later = start(service, scenario="broken_checklist")
    assert later.status == "completed" and later.environment_version == record.environment_version
    incident = service.incidents.get_incident(report["incident_ids"][0])
    assert incident["recurrence"]["after"] == {"affected": 0, "comparable": 1}
    discovery = ToolRegistry(service.sandbox(later)).discover_tools()["result"]["tools"]
    assert (
        next(t for t in discovery if t["name"] == "checklists.create")["implementation_version"]
        == record.environment_version
    )


def test_two_bad_candidates_stay_inactive(service, monkeypatch, fake_runner):
    harness = ModelHarness(
        monkeypatch,
        plans=[
            ready_plan(),
            lambda r: proposal(r, "bad candidate"),
            lambda r: proposal(r, "bad candidate"),
        ],
    )
    record = start(service, scenario="broken_checklist", repair_enabled=True)
    assert record.status == "blocked" and record.error["code"] == "repair_attempt_limit"
    report = record.supervision.operations[0].repairs[0]
    assert [a["status"] for a in report["attempts"]] == ["rejected", "rejected"]
    assert service.environments.active_id("demo") == "builtin"
    assert len(service.sandbox(record).list_tickets()) == 1
    assert service.sandbox(record).list_checklists() == []
    assert len(harness.sessions) == 1


def test_verification_failure_cannot_publish(service, monkeypatch, fake_runner):
    ModelHarness(monkeypatch, plans=[ready_plan(), proposal, proposal], behaviors=["finish"])
    monkeypatch.setattr(
        repair_controller,
        "run_verification",
        lambda kind, *a: {"kind": kind, "passed": False, "test_double": True},
    )
    record = start(service, scenario="broken_checklist", repair_enabled=True)
    assert record.status == "blocked"
    assert service.environments.active_id("demo") == "builtin"
    assert all(v["status"] == "rejected" for v in service.environments.inspect("demo")["versions"])


def test_unsourced_diagnosis_has_no_candidate(service, monkeypatch, fake_runner):
    ModelHarness(
        monkeypatch, plans=[ready_plan(), lambda r: {**proposal(r), "evidence_ids": [str(uuid4())]}]
    )
    record = start(service, scenario="broken_checklist", repair_enabled=True)
    assert record.error["code"] == "diagnosis_unsourced"
    assert service.environments.inspect("demo")["versions"] == []


def test_candidate_cannot_change_identity_or_permissions(tmp_path, fake_runner, monkeypatch):
    sandbox = Sandbox(tmp_path / "sandbox.sqlite3", "task", "run")
    sandbox.initialize()
    ticket = sandbox.create_ticket("Release demo 1.0", "1.0", "one")
    store = EnvironmentStore(tmp_path / "environment.sqlite3")
    store.initialize()
    version = stage(store)
    sandbox.select_environment(store.manifest("demo", version["id"], staged=True))
    monkeypatch.setattr(
        candidate_runner.CandidateRunner,
        "run",
        lambda *a, **k: {"ticket_id": "another", "title": "other", "items": ["x"]},
    )
    with pytest.raises(SandboxError, match="identity"):
        sandbox.create_checklist(ticket["id"], "A checklist", ["x"], "two")
    assert sandbox.list_checklists() == []
    assert "environment.select" not in [
        t["name"] for t in ToolRegistry(sandbox).discover_tools()["result"]["tools"]
    ]


def test_restart_rejects_unfinished_candidates_and_retains_published(environments):
    good = stage(environments)
    environments.publish(good["id"], proofs(good), expected_active="builtin")
    pending = stage(environments, parent=good["id"])
    repair_id = str(uuid4())
    environments.save_repair(
        {
            "id": repair_id,
            "project": "demo",
            "status": "investigating",
            "attempts": [{"status": "verifying", "candidate_id": pending["id"]}],
        }
    )
    reopened = EnvironmentStore(environments.path)
    reopened.initialize()
    reopened.recover_interrupted()
    assert reopened.active_id("demo") == good["id"]
    assert reopened.version(pending["id"])["status"] == "rejected"
    assert reopened.inspect("demo")["repairs"][0]["status"] == "interrupted"
    assert reopened.inspect("demo")["repairs"][0]["attempts"][0]["status"] == "interrupted"


@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), -1, 1801, True])
def test_pause_cannot_expand_authorized_budget(seconds):
    session = hermes_bridge.Session(
        {"allow_verification_pause": True}, lambda _: None, threading.Event()
    )
    deadline = session.deadline
    with pytest.raises(ValueError):
        session.account_verification_pause(seconds)
    assert session.deadline == deadline and session.turns_used == 0


def test_pause_requires_opt_in_and_never_resets_turns():
    session = hermes_bridge.Session({}, lambda _: None, threading.Event())
    with pytest.raises(ValueError):
        session.account_verification_pause(10)
    session.request["allow_verification_pause"] = True
    session.turns_used = 7
    session.account_verification_pause(600)
    session.account_verification_pause(600)
    session.account_verification_pause(600)
    assert session.turns_used == 7
    with pytest.raises(ValueError):
        session.account_verification_pause(1)


def test_cancelled_repair_budget_denies_every_actor():
    cancelled = threading.Event()
    budget = RepairBudget(20, 600, cancelled, lambda *_: None, lambda _: None)
    cancelled.set()
    with pytest.raises(BudgetExceeded, match="cancelled"):
        budget.consume("debugger")
    with pytest.raises(BudgetExceeded, match="cancelled"):
        with budget.verification_stage(lambda *_: None):
            pytest.fail("Cancelled verification must never start")
    assert budget.overall_used == budget.used == 0


def test_component_checks_respect_remaining_budget(environments, monkeypatch):
    from epoch_backend.repair_verification import component_proofs

    version = stage(environments)
    cancelled = threading.Event()
    budget = RepairBudget(20, 600, cancelled, lambda *_: None, lambda _: None)
    cancelled.set()
    monkeypatch.setattr(
        candidate_runner.CandidateRunner,
        "run",
        lambda *a, **k: pytest.fail("Expired/cancelled budget must veto container execution"),
    )
    with pytest.raises(BudgetExceeded):
        component_proofs(version, cancelled, budget)


def test_unresolved_container_cleanup_stops_component_sequence(environments, monkeypatch):
    from epoch_backend.repair_verification import component_proofs

    calls = []

    def failed(*args, **kwargs):
        calls.append(1)
        raise CandidateError("cleanup_unresolved", "Cleanup could not be confirmed")

    monkeypatch.setattr(candidate_runner.CandidateRunner, "run", failed)
    with pytest.raises(CandidateError, match="Cleanup"):
        component_proofs(stage(environments), threading.Event())
    assert len(calls) == 1


def test_activation_failure_blocks_further_execution(service, monkeypatch, fake_runner):
    ModelHarness(monkeypatch, plans=[ready_plan(), proposal], behaviors=["finish"] * 3)
    original_select = Sandbox.select_environment

    def fail_activation(sandbox, manifest, **kwargs):
        if (
            manifest["version_id"] != "builtin"
            and "repair-verification" not in str(sandbox.path)
            and service.environments.active_id("demo") != "builtin"
        ):
            raise OSError("test activation write failure")
        return original_select(sandbox, manifest, **kwargs)

    monkeypatch.setattr(Sandbox, "select_environment", fail_activation)
    from epoch_backend.contracts import TaskCreate
    from epoch_backend.execution_contracts import ReleaseRunRequest

    task, _ = service.tasks.create_task(
        TaskCreate(client_request_id=uuid4(), message="Prepare release 2.4", project_id="demo")
    )
    record, _ = service.start(
        task.id,
        ReleaseRunRequest(
            client_request_id=uuid4(),
            workflow="release",
            release="2.4",
            supervised=True,
            scenario="broken_checklist",
            repair_enabled=True,
        ),
    )
    service._thread.join(timeout=5)
    assert not service._thread.is_alive()
    record = service.get(record.id)
    assert record.status == "blocked" and record.error["code"] == "activation_unresolved"
    assert service.environments.active_id("demo") != "builtin"  # Verified artifact retained.
    assert service._unresolved_state
    assert service.sandbox(record).list_checklists() == []
