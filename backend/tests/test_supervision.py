"""Supervisor integration tests use explicit model doubles over real sandbox state."""

import copy
import json
from uuid import UUID, uuid4

import pytest

from epoch_backend import debugger_bridge, hermes_bridge, supervisor
from epoch_backend.config import Settings
from epoch_backend.contracts import TaskCreate
from epoch_backend.execution import ExecutionError, ExecutionService
from epoch_backend.execution_contracts import ReleaseRunRequest
from epoch_backend.sandbox import Sandbox
from epoch_backend.storage import RequestConflict, SQLiteStore
from epoch_backend.supervision_contracts import FeedbackRequest
from epoch_backend.tool_registry import ToolRegistry


def ready_plan(**changes):
    return {
        "outcome": "ready",
        "summary": "Prepare the requested release.",
        "instructions": "Create the release ticket and checklist, then notify QA.",
        "checkpoints": [
            {"kind": kind, "description": description, "source_quote": ""}
            for kind, description in (
                ("release_ticket", "Create the release ticket."),
                ("release_checklist", "Attach the complete checklist."),
                ("qa_notification", "Notify QA with both links."),
            )
        ],
        "additional_checklist_items": [],
        "required_message_phrases": [],
        "classification": "omitted_requirement",
        "questions": [],
        **changes,
    }


def decision(action="continue", instruction="Send the missing QA notice using existing objects."):
    return {
        "action": action,
        "reason": "The trusted QA checkpoint is unmet.",
        "instruction": instruction,
        "questions": [],
    }


class ModelHarness:
    """Visible test-only provider results; no installed model is invoked."""

    def __init__(self, monkeypatch, plans=None, behaviors=None):
        self.debugger_outputs = list(plans or [ready_plan()])
        self.behaviors = list(behaviors or ["finish"])
        self.debugger_requests = []
        self.sessions = []
        self.instructions = []
        self.after_pass = None
        monkeypatch.setattr(hermes_bridge, "detect_installation", lambda: {"available": True})
        monkeypatch.setattr(debugger_bridge, "detect_debugger", lambda: {"available": True})
        monkeypatch.setattr(debugger_bridge, "complete", self.complete)
        harness = self

        class FakeSession:
            def __init__(self, request, on_event, cancelled, before_model_request):
                self.request = request
                self.on_event = on_event
                self.cancelled = cancelled
                self.before_model_request = before_model_request
                self.passes = 0
                harness.sessions.append(self)

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return None

            def run(self, instruction, max_turns, timeout_seconds):
                assert 1 <= max_turns <= 20 and 1 <= timeout_seconds <= 600
                self.before_model_request()
                self.passes += 1
                harness.instructions.append(instruction)
                behavior = harness.behaviors.pop(0)
                args = self.request["mcp_args"]
                sandbox = Sandbox(
                    args[args.index("--database") + 1],
                    self.request["task_id"],
                    self.request["run_id"],
                )
                if behavior not in {"nothing", "drift"}:
                    harness.perform(sandbox, self.on_event, omit=behavior == "omit")
                if behavior == "cancel":
                    self.cancelled.set()
                if harness.after_pass:
                    harness.after_pass()
                baseline = {key: "test-double-stable-identity" for key in supervisor.BASELINE_KEYS}
                baseline.update(
                    implementation_unchanged=True,
                    user_settings_unchanged=True,
                    system_prompt_unchanged=True,
                    system_prompt_static_unchanged=True,
                    discovery_unchanged=True,
                )
                if behavior == "missing_baseline":
                    baseline = {}
                if behavior == "drift":
                    baseline["system_prompt_sha256"] = "changed-prompt"
                return {
                    "success": True,
                    "final_response": "Explicit test double result.",
                    "baseline": baseline,
                    "missing_evidence": [],
                    "turns_used": 1,
                    "session_turns_used": self.passes,
                    "history_retained": True,
                    "api_calls": 1,
                    "segment": self.passes,
                }

        monkeypatch.setattr(hermes_bridge, "Session", FakeSession)

    def complete(self, request, on_event, cancelled):
        assert not cancelled.is_set()
        assert 1 <= request["timeout_seconds"] <= 600
        self.debugger_requests.append(copy.deepcopy(request))
        assert self.debugger_outputs, "Unexpected debugger inference"
        response = self.debugger_outputs.pop(0)
        if callable(response):
            response = response(request)
        on_event({"type": "debugger.completed", "data": {"model": "gpt-5.6-luna"}})
        return {
            "success": True,
            "output": response,
            "model": "gpt-5.6-luna",
            "provider": "test-double",
            "usage": {"total_tokens": 10},
            "baseline": {"response_model": "gpt-5.6-luna"},
            "missing_evidence": [],
            "error": None,
        }

    @staticmethod
    def perform(sandbox, on_event, *, omit):
        metadata = sandbox.metadata()
        registry = ToolRegistry(sandbox)

        def invoke(name, args):
            result = registry.invoke_tool(name, args)
            on_event(
                {
                    "type": "executor.tool_completed",
                    "data": {
                        "name": name,
                        "arguments": args,
                        "result": result,
                    },
                }
            )
            return result

        tickets = sandbox.list_tickets()
        ticket = (
            tickets[0]
            if tickets
            else invoke(
                "tickets.create",
                {
                    "title": metadata["ticket_title"],
                    "release": metadata["release"],
                    "idempotency_key": "create-ticket",
                },
            )["result"]
        )
        checklists = sandbox.list_checklists()
        if checklists:
            checklist_result = invoke(
                "checklists.update",
                {
                    "checklist_id": checklists[0]["id"],
                    "items": metadata["expected_items"],
                    "idempotency_key": "update-checklist-" + metadata["criteria_sha256"],
                },
            )
        else:
            checklist_result = invoke(
                "checklists.create",
                {
                    "ticket_id": ticket["id"],
                    "title": metadata["checklist_title"],
                    "items": metadata["expected_items"],
                    "idempotency_key": "create-checklist",
                },
            )
        if not checklist_result["ok"] or omit:
            return
        checklist = checklist_result["result"]
        text = f"Release {metadata['release']} is ready. " + " ".join(
            metadata.get("required_message_phrases", [])
        )
        messages = sandbox.list_messages()
        if messages:
            invoke(
                "messages.update",
                {
                    "message_id": messages[0]["id"],
                    "text": text,
                    "idempotency_key": "update-message-" + metadata["criteria_sha256"],
                },
            )
        else:
            invoke(
                "messages.send",
                {
                    "channel": metadata["qa_channel"],
                    "text": text,
                    "links": [ticket["url"], checklist["url"]],
                    "idempotency_key": "create-message",
                },
            )


@pytest.fixture
def service(tmp_path):
    settings = Settings(data_dir=tmp_path, enable_hermes=True, _env_file=None)
    tasks = SQLiteStore(settings.database_path)
    tasks.initialize()
    execution = ExecutionService(settings, tasks)
    execution.initialize()
    try:
        yield execution
    finally:
        execution.close()


def start(service, message="Prepare the demo release", **changes):
    task, _ = service.tasks.create_task(
        TaskCreate(client_request_id=uuid4(), message=message, project_id="demo")
    )
    request = ReleaseRunRequest(
        client_request_id=uuid4(), workflow="release", release="2.4", supervised=True, **changes
    )
    record, created = service.start(task.id, request)
    assert created
    return finish(service, record.id)


def finish(service, run_id):
    service._thread.join(timeout=5)
    assert not service._thread.is_alive(), "The test-double operation did not finish"
    assert service.active_run_id is None
    return service.get(run_id)


def feedback(service, record, message, **changes):
    request = FeedbackRequest(
        client_request_id=uuid4(),
        expected_revision_id=record.supervision.current_revision_id,
        message=message,
        **changes,
    )
    revised, created = service.feedback(record.id, request)
    assert created
    return finish(service, revised.id), request


def test_omission_gets_a_targeted_continuation_in_the_same_session(service, monkeypatch):
    def review(request):
        payload = request["input"]
        assert payload["trusted_verification"]["passed"] is False
        ticket = payload["existing_objects"]["tickets"][0]
        checklist = payload["existing_objects"]["checklists"][0]
        assert payload["existing_objects"]["messages"] == []
        return decision(
            instruction=f"Notify QA using ticket {ticket['id']} and checklist {checklist['id']}."
        )

    harness = ModelHarness(monkeypatch, [ready_plan(), review], ["omit", "finish"])
    record = start(service, demo_omit_notification=True)
    assert record.status == "completed", record.error
    operation = record.supervision.operations[0]
    assert len(harness.sessions) == 1 and harness.sessions[0].passes == 2
    assert len(operation.interventions) == 1
    assert len(operation.interventions[0].checkpoint_refs) == 1
    assert "Notify QA using ticket" in harness.instructions[1]
    assert record.verification["passed"]
    assert operation.turns_used == 4
    assert operation.debugger_turns == operation.executor_turns == 2
    state = service.sandbox(record).snapshot()
    assert [len(state[kind]) for kind in ("tickets", "checklists", "messages")] == [1, 1, 1]
    assert all(checkpoint.status == "verified" for checkpoint in record.brief.checkpoints)
    events = service.sandbox(record).events()
    assert any(event["type"] == "supervisor.intervention" for event in events)
    assert any(event["type"] == "checkpoint.updated" for event in events)


@pytest.mark.parametrize(
    "invalid", ["missing_checkpoint", "invented_quote", "unquoted_value", "questions"]
)
def test_invalid_sourced_plan_cannot_start_executor_or_change_criteria(
    service, monkeypatch, invalid
):
    plan = ready_plan()
    if invalid == "missing_checkpoint":
        plan["checkpoints"].pop()
    elif invalid == "invented_quote":
        plan["additional_checklist_items"] = [
            {"value": "Invented requirement", "source_quote": "Invented requirement"}
        ]
    elif invalid == "unquoted_value":
        plan["required_message_phrases"] = [{"value": "Invented", "source_quote": "demo release"}]
    else:
        plan["questions"] = ["Which release?"]
    harness = ModelHarness(monkeypatch, [plan])
    record = start(service)
    assert record.status == "needs_input"
    assert record.error["code"] == "plan_rejected"
    assert harness.sessions == []
    assert record.supervision.operations[0].turns_used == 1
    sandbox = service.sandbox(record)
    assert sandbox.metadata().get("requirements_revisions", []) == []
    assert sandbox.list_tickets() == []


def test_feedback_adds_sourced_requirements_without_duplicates_or_history_loss(
    service, monkeypatch
):
    harness = ModelHarness(monkeypatch, [ready_plan()], ["finish"])
    record = start(service)
    assert record.status == "completed", record.error
    prior = record.supervision.operations[0].model_dump(mode="json")
    before = service.sandbox(record).snapshot()
    phrase = "Deployment starts at 10:00 UTC"
    item = "Security review approved"
    message = f"Add checklist item '{item}' and include '{phrase}' in the QA message."
    harness.debugger_outputs.append(
        ready_plan(
            additional_checklist_items=[{"value": item, "source_quote": item}],
            required_message_phrases=[{"value": phrase, "source_quote": phrase}],
            classification="new_preference",
        )
    )
    harness.behaviors.append("finish")
    revised, request = feedback(service, record, message)
    assert revised.status == "completed", revised.error
    assert revised.supervision.operations[0].model_dump(mode="json") == prior
    operation = revised.supervision.operations[1]
    assert operation.previous_revision_id == record.supervision.current_revision_id
    assert operation.intent_revision.feedback == message
    assert operation.intent_revision.reason == "new_preference"
    assert operation.intent_revision.retained_evidence_refs == [
        UUID(record.verification["evidence_id"])
    ]
    assert all(ref.kind == "user_feedback" for ref in operation.intent_revision.source_refs)
    assert (
        operation.criteria_after["criteria_sha256"] != operation.criteria_before["criteria_sha256"]
    )
    after = service.sandbox(revised).snapshot()
    for kind in ("tickets", "checklists", "messages"):
        assert len(after[kind]) == 1
        assert [row["id"] for row in after[kind]] == [row["id"] for row in before[kind]]
    assert item in after["checklists"][0]["items"]
    assert phrase in after["messages"][0]["text"]
    assert set(before["checklists"][0]["items"]) <= set(after["checklists"][0]["items"])
    assert after["tickets"] == before["tickets"]
    assert len(harness.sessions) == 2
    assert len(harness.debugger_requests) == 2
    retried, created = service.feedback(record.id, request)
    assert not created
    assert len(retried.supervision.operations) == 2
    assert len(harness.debugger_requests) == 2
    with pytest.raises(RequestConflict):
        service.feedback(record.id, request.model_copy(update={"message": "Different feedback"}))
    with pytest.raises(ExecutionError) as stale:
        service.feedback(record.id, request.model_copy(update={"client_request_id": uuid4()}))
    assert stale.value.code == "stale_revision"


def test_environment_contract_failure_is_blocked_without_any_repair(service, monkeypatch):
    harness = ModelHarness(monkeypatch, [ready_plan(), decision("environment_defect")], ["finish"])
    record = start(service, scenario="broken_checklist")
    assert record.status == "blocked", record.error
    assert record.error["code"] == "environment_defect"
    assert len(harness.sessions) == 1 and harness.sessions[0].passes == 1
    sandbox = service.sandbox(record)
    assert len(sandbox.list_tickets()) == 1
    assert sandbox.list_checklists() == sandbox.list_messages() == []
    assert sandbox.metadata()["scenario"] == "broken_checklist"
    assert any(event["type"] == "tool.error" for event in sandbox.events())
    assert record.supervision.operations[0].interventions == []


def test_three_turn_total_stops_before_a_second_executor_pass(service, monkeypatch):
    harness = ModelHarness(monkeypatch, [ready_plan(), decision()], ["omit", "finish"])
    record = start(service, max_turns=3)
    assert record.status == "blocked", record.error
    assert record.error["code"] == "turn_limit"
    operation = record.supervision.operations[0]
    assert operation.turns_used == 3
    assert operation.debugger_turns == 2 and operation.executor_turns == 1
    assert len(harness.sessions) == 1 and harness.sessions[0].passes == 1
    assert service.sandbox(record).list_messages() == []


def test_cancelled_result_cannot_be_reported_complete_even_when_state_passes(service, monkeypatch):
    ModelHarness(monkeypatch, [ready_plan()], ["cancel"])
    record = start(service)
    assert record.status == "cancelled"
    assert service.sandbox(record).evaluate()["passed"]
    assert record.supervision.operations[0].status == "cancelled"


def test_missing_executor_baseline_cannot_claim_completion(service, monkeypatch):
    ModelHarness(monkeypatch, [ready_plan()], ["missing_baseline"])
    record = start(service)
    assert record.status == "blocked"
    assert record.error
    assert service.sandbox(record).evaluate()["passed"]


def test_prompt_drift_between_passes_blocks_execution_instead_of_asking_for_intent(
    service, monkeypatch
):
    ModelHarness(monkeypatch, [ready_plan(), decision()], ["omit", "drift"])
    record = start(service)
    assert record.status == "blocked"
    assert record.error
    assert record.supervision.operations[0].questions == []


def test_restart_marks_the_active_operation_interrupted_and_preserves_state(service, monkeypatch):
    harness = ModelHarness(monkeypatch)
    record = start(service)
    sandbox = service.sandbox(record)
    before = sandbox.snapshot()
    record.status = "running"
    record.supervision.operations[-1].status = "running"
    service.store.save(record)
    service.close()
    restarted = ExecutionService(service.settings, service.tasks)
    restarted.initialize()
    try:
        recovered = restarted.get(record.id)
        assert recovered.status == "interrupted"
        assert recovered.supervision.operations[-1].status == "interrupted"
        assert recovered.supervision.operations[-1].missing_evidence
        assert restarted.sandbox(recovered).snapshot() == before
        assert any(event["type"] == "run.interrupted" for event in sandbox.events())
        assert len(harness.debugger_requests) == 1 and len(harness.sessions) == 1
    finally:
        restarted.close()


def test_needs_input_can_be_explicitly_clarified_without_rewriting_earlier_input(
    service, monkeypatch
):
    plan = ready_plan(outcome="needs_input", questions=["What should the QA message say?"])
    harness = ModelHarness(monkeypatch, [plan], [])
    initial = start(service, message="Prepare release with an extra QA note.")
    assert initial.status == "needs_input"
    prior = initial.supervision.operations[0].model_dump(mode="json")
    assert harness.sessions == []
    phrase = "Deployment starts at 10:00 UTC"
    harness.debugger_outputs.append(
        ready_plan(required_message_phrases=[{"value": phrase, "source_quote": phrase}])
    )
    harness.behaviors = ["finish"]
    request = FeedbackRequest(
        client_request_id=uuid4(),
        expected_revision_id=initial.supervision.current_revision_id,
        message=f"The extra note must say '{phrase}'.",
    )
    record, created = service.feedback(initial.id, request, clarification=True)
    assert created
    record = finish(service, record.id)
    assert record.status == "completed", record.error
    assert record.supervision.operations[0].model_dump(mode="json") == prior
    assert record.supervision.operations[-1].trigger == "clarification"
    assert phrase in service.sandbox(record).list_messages()[0]["text"]


def test_serialized_history_contains_visible_evidence_and_original_intent(service, monkeypatch):
    ModelHarness(monkeypatch)
    record = start(service)
    encoded = json.loads(record.model_dump_json())
    assert encoded["supervision"]["operations"][0]["user_input"] == "Prepare the demo release"
    assert encoded["supervision"]["operations"][0]["debugger_calls"][0]["model"] == "gpt-5.6-luna"
    assert encoded["supervision"]["operations"][0]["executor_passes"][0]["history_retained"]
    assert all(checkpoint["source_refs"] for checkpoint in encoded["brief"]["checkpoints"])


def test_late_executor_result_cannot_complete_after_the_shared_deadline(service, monkeypatch):
    from epoch_backend.operation_budget import OperationBudget

    budgets = []

    def tracked_budget(*args):
        budget = OperationBudget(*args)
        budgets.append(budget)
        return budget

    monkeypatch.setattr(supervisor, "OperationBudget", tracked_budget)
    harness = ModelHarness(monkeypatch)
    harness.after_pass = lambda: setattr(budgets[0], "deadline", 0)
    record = start(service)
    assert record.status == "blocked"
    assert record.error["code"] == "time_limit"
    assert service.sandbox(record).evaluate()["passed"]
    assert record.supervision.operations[0].turns_used == 2


def test_blocked_checkpoint_state_matches_the_saved_operation_brief(service, monkeypatch):
    ModelHarness(monkeypatch, [ready_plan(), decision("environment_defect")], ["finish"])
    record = start(service, scenario="broken_checklist")
    assert record.status == "blocked"
    assert record.supervision.operations[0].brief.model_dump() == record.brief.model_dump()
    assert any(checkpoint.status == "blocked" for checkpoint in record.brief.checkpoints)


def test_second_feedback_retains_prior_additive_requirement_sources(service, monkeypatch):
    harness = ModelHarness(monkeypatch)
    initial = start(service)
    item, phrase = "Security review approved", "Deployment starts at 10:00 UTC"
    harness.debugger_outputs.append(
        ready_plan(
            additional_checklist_items=[{"value": item, "source_quote": item}],
            required_message_phrases=[{"value": phrase, "source_quote": phrase}],
            classification="new_preference",
        )
    )
    harness.behaviors.append("finish")
    added, _ = feedback(service, initial, f"Add '{item}' and include '{phrase}' in the QA notice.")
    assert added.status == "completed", added.error
    source_revision = added.supervision.current_revision_id
    before = service.sandbox(added).snapshot()
    earlier_operations = [
        operation.model_dump(mode="json") for operation in added.supervision.operations
    ]
    prior_criteria = service.sandbox(added).metadata()["criteria_sha256"]
    # The next model plan proposes no new additions and does not repeat the quotes.
    harness.debugger_outputs.append(ready_plan(classification="evaluation_mistake"))
    harness.behaviors.append("finish")
    checked, _ = feedback(service, added, "Verify the existing result and retain all requirements.")
    assert checked.status == "completed", checked.error
    assert checked.supervision.operations[-1].plan.additional_checklist_items == []
    assert checked.supervision.operations[-1].plan.required_message_phrases == []
    for kind, quote in (("release_checklist", item), ("qa_message_content", phrase)):
        checkpoint = next(
            item for item in checked.brief.checkpoints if item.verification_rule == kind
        )
        assert any(
            ref.excerpt == quote and ref.locator == f"intent:{source_revision}"
            for ref in checkpoint.source_refs
        )
        assert checkpoint.status == "verified"
    assert service.sandbox(checked).metadata()["criteria_sha256"] == prior_criteria
    assert service.sandbox(checked).snapshot() == before
    assert [
        operation.model_dump(mode="json") for operation in checked.supervision.operations[:2]
    ] == earlier_operations
    assert len(checked.supervision.operations) == 3


def test_initial_questions_are_given_to_the_clarification_debugger(service, monkeypatch):
    question = "What exact phrase should the QA notice include?"
    initial_message = "Prepare a release with an additional QA notice phrase."
    harness = ModelHarness(monkeypatch, [ready_plan(outcome="needs_input", questions=[question])])
    initial = start(service, message=initial_message)
    assert initial.status == "needs_input"
    phrase = "Deployment starts at 10:00 UTC"

    def clarification_plan(request):
        payload = request["input"]
        assert payload["original_request"] == initial_message
        assert payload["trigger"] == "clarification"
        assert payload["current_input"] == phrase
        initial_context = next(
            revision for revision in payload["user_revisions"] if revision["kind"] == "initial"
        )
        assert initial_context == {
            "kind": "initial",
            "message": initial_message,
            "questions": [question],
        }
        return ready_plan(required_message_phrases=[{"value": phrase, "source_quote": phrase}])

    harness.debugger_outputs.append(clarification_plan)
    record, created = service.feedback(
        initial.id,
        FeedbackRequest(
            client_request_id=uuid4(),
            expected_revision_id=initial.supervision.current_revision_id,
            message=phrase,
        ),
        clarification=True,
    )
    assert created
    record = finish(service, record.id)
    assert record.status == "completed", record.error
    assert record.supervision.operations[0].questions == [question]
    assert phrase in service.sandbox(record).list_messages()[0]["text"]


def test_finalization_failure_marks_current_operation_failed_and_blocks_new_work(
    service, monkeypatch
):
    harness = ModelHarness(monkeypatch)
    original_event = Sandbox.record_event

    def fail_final_event(sandbox, event_type, payload):
        if event_type == "run.finished":
            raise OSError("Test-only failure publishing the final event")
        return original_event(sandbox, event_type, payload)

    monkeypatch.setattr(Sandbox, "record_event", fail_final_event)
    task, _ = service.tasks.create_task(
        TaskCreate(client_request_id=uuid4(), message="Prepare the demo release", project_id="demo")
    )
    record, created = service.start(
        task.id,
        ReleaseRunRequest(
            client_request_id=uuid4(), workflow="release", release="2.4", supervised=True
        ),
    )
    assert created
    service._thread.join(timeout=5)
    assert not service._thread.is_alive()
    saved = service.get(record.id)
    assert saved.status == "failed"
    assert saved.error["code"] == "finalization_failed"
    operation = saved.supervision.operations[-1]
    assert operation.status == "failed"
    assert operation.error == saved.error
    assert operation.finished_at is not None
    assert "Final status or event persistence failed." in operation.missing_evidence
    assert saved.verification["passed"]
    assert service._unresolved_state is True
    assert service.active_run_id == saved.id
    assert service.runtime_info().supervision_enabled is False
    with pytest.raises(ExecutionError) as blocked:
        service.feedback(
            saved.id,
            FeedbackRequest(
                client_request_id=uuid4(),
                expected_revision_id=saved.supervision.current_revision_id,
                message="Try again",
            ),
        )
    assert blocked.value.code == "execution_state_unresolved"
    assert len(harness.sessions) == 1 and len(harness.debugger_requests) == 1
