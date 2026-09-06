"""Exercise real state transitions and evaluator failures without an executor."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from epoch_backend.sandbox import Sandbox, SandboxError
from epoch_backend.sandbox_adapters import serialize_checklist


def make_sandbox(tmp_path, scenario="control", project_id="demo", release="1.0"):
    sandbox = Sandbox(tmp_path / "sandbox.sqlite3", str(uuid4()), str(uuid4()))
    sandbox.initialize(scenario=scenario, project_id=project_id, release=release)
    return sandbox


def complete_release(sandbox, *, channel=None, items=None, owner=False):
    meta = sandbox.metadata()
    ticket = sandbox.create_ticket(meta["ticket_title"], meta["release"], "ticket")
    checklist = sandbox.create_checklist(
        ticket["id"], meta["checklist_title"], items or meta["expected_items"], "checklist"
    )
    text = f"Release {meta['release']} is ready for QA."
    if owner:
        text += " " + meta["qa_owner"]
    message = sandbox.send_message(
        channel or meta["qa_channel"], text, [ticket["url"], checklist["url"]], "message"
    )
    return ticket, checklist, message


def test_control_persists_and_checks_actual_state(tmp_path):
    sandbox = make_sandbox(tmp_path)
    assert not sandbox.evaluate()["passed"]
    objects = complete_release(sandbox)
    result = sandbox.evaluate()
    assert result["passed"]
    assert all(check["evidence_ids"] for check in result["checks"])
    assert all(item["simulated"] and item["url"].startswith("simulated://") for item in objects)
    reopened = Sandbox(sandbox.path, sandbox.task_id, sandbox.run_id)
    assert reopened.snapshot() == sandbox.snapshot()
    reopened.initialize()
    assert reopened.evaluate()["passed"]


def test_broken_adapter_really_serializes_wrong_shape_and_preserves_partial_state(tmp_path):
    sandbox = make_sandbox(tmp_path, "broken_checklist")
    meta = sandbox.metadata()
    ticket = sandbox.create_ticket(meta["ticket_title"], meta["release"], "ticket")
    wire = serialize_checklist(
        ticket["id"], meta["checklist_title"], meta["expected_items"], legacy=True
    )
    assert isinstance(wire["items"], str)
    assert json.loads(wire["items"]) == meta["expected_items"]
    with pytest.raises(SandboxError) as error:
        sandbox.create_checklist(
            ticket["id"], meta["checklist_title"], meta["expected_items"], "list"
        )
    assert error.value.code == "adapter_contract_error"
    assert sandbox.list_tickets() == [ticket]
    assert sandbox.list_checklists() == []
    checks = sandbox.evaluate()["checks"]
    assert [check["passed"] for check in checks] == [True, False, False]


def test_wrong_destination_can_succeed_but_fails_trusted_check(tmp_path):
    sandbox = make_sandbox(tmp_path, "outdated_context")
    old = sandbox.read_runbook()
    current = sandbox.read_runbook(version="v2")
    assert old["version"] == "v1" and not old["is_current"]
    assert current["version"] == "v2" and current["is_current"]
    assert old["content"] != current["content"]
    assert old["document_id"] == current["document_id"]
    assert "#qa-demo-legacy" in old["content"]
    _, _, message = complete_release(sandbox, channel="#qa-demo-legacy")
    assert message["channel"] == "#qa-demo-legacy"
    assert [item["passed"] for item in sandbox.evaluate()["checks"]] == [True, True, False]
    assert sandbox.read_runbook(purpose="historical") == {**old, "requested_purpose": "historical"}


def test_wrong_checklist_and_incomplete_links_fail_verification(tmp_path):
    sandbox = make_sandbox(tmp_path)
    ticket, _, _ = complete_release(sandbox, items=["Unrelated checklist item"])
    assert [item["passed"] for item in sandbox.evaluate()["checks"]] == [True, False, False]
    sandbox.reset()
    meta = sandbox.metadata()
    ticket = sandbox.create_ticket(meta["ticket_title"], meta["release"], "ticket")
    sandbox.create_checklist(ticket["id"], meta["checklist_title"], meta["expected_items"], "list")
    sandbox.send_message(meta["qa_channel"], "Release 1.0 ready", [ticket["url"]], "message")
    assert [item["passed"] for item in sandbox.evaluate()["checks"]] == [True, True, False]


def test_two_different_release_objects_cannot_form_passing_link_chain(tmp_path):
    sandbox = make_sandbox(tmp_path)
    meta = sandbox.metadata()
    ticket = sandbox.create_ticket(meta["ticket_title"], meta["release"], "correct")
    other = sandbox.create_ticket("Other release", "2.0", "other")
    checklist = sandbox.create_checklist(
        other["id"], meta["checklist_title"], meta["expected_items"], "list"
    )
    sandbox.send_message(
        meta["qa_channel"], "Release 1.0", [ticket["url"], checklist["url"]], "msg"
    )
    assert [item["passed"] for item in sandbox.evaluate()["checks"]] == [True, False, False]


def test_missing_lookup_directory_exists_but_owner_is_not_supplied_by_runbook(tmp_path):
    sandbox = make_sandbox(tmp_path, "missing_lookup")
    meta = sandbox.metadata()
    directory = sandbox.snapshot()["directory"]
    assert directory[0]["name"] == meta["qa_owner"]
    assert meta["qa_owner"] not in sandbox.read_runbook()["content"]
    complete_release(sandbox)
    result = sandbox.evaluate()
    assert [item["passed"] for item in result["checks"]] == [True, True, True, False]
    sandbox.reset(scenario="missing_lookup")
    complete_release(sandbox, owner=True)
    assert sandbox.evaluate()["passed"]


def test_fixture_variations_preserve_scope_and_independent_criteria(tmp_path):
    sandbox = make_sandbox(tmp_path, project_id="payments", release="2.4")
    meta = sandbox.metadata()
    assert meta["qa_owner"] == "Morgan Chen"
    assert meta["qa_channel"] == "#qa-payments"
    assert meta["expected_items"] != [
        "Smoke tests pass",
        "Rollback plan reviewed",
        "Release notes approved",
    ]
    assert all(item["scope"] == "project:payments" for item in sandbox.snapshot()["runbooks"])
    complete_release(sandbox)
    assert sandbox.evaluate()["passed"]


def test_retries_are_atomic_and_do_not_duplicate_effects(tmp_path):
    sandbox = make_sandbox(tmp_path)
    meta = sandbox.metadata()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(
            pool.map(
                lambda _: sandbox.create_ticket(meta["ticket_title"], meta["release"], "same"),
                range(12),
            )
        )
    assert all(item == results[0] for item in results)
    assert len(sandbox.list_tickets()) == 1
    assert sum(item["type"] == "state.changed" for item in sandbox.events()) == 1
    with pytest.raises(SandboxError) as error:
        sandbox.create_ticket("Different title", meta["release"], "same")
    assert error.value.code == "idempotency_conflict"


def test_repeated_checklist_and_notification_have_single_effect(tmp_path):
    sandbox = make_sandbox(tmp_path)
    first = complete_release(sandbox)
    assert complete_release(sandbox) == first
    assert len(sandbox.list_checklists()) == 1
    assert len(sandbox.list_messages()) == 1


def test_events_have_atomic_sequences_task_run_and_cursor(tmp_path):
    sandbox = make_sandbox(tmp_path)
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(
            pool.map(
                lambda number: sandbox.record_event("test.event", {"number": number}), range(20)
            )
        )
    events = sandbox.events()
    assert [item["sequence"] for item in events] == list(range(1, 22))
    assert len({item["id"] for item in events}) == 21
    assert all(
        item["task_id"] == sandbox.task_id and item["run_id"] == sandbox.run_id for item in events
    )
    assert sandbox.events(after=19) == events[19:]


def test_reset_restores_equivalent_state_but_retains_prior_evidence(tmp_path):
    sandbox = make_sandbox(tmp_path)
    baseline = sandbox.snapshot()
    complete_release(sandbox)
    events = sandbox.events()
    sandbox.reset()
    snapshot = sandbox.snapshot()
    assert {**snapshot, "generation": 1} == baseline
    assert sandbox.events()[: len(events)] == events
    assert sandbox.events()[-1]["type"] == "sandbox.reset"
    assert not sandbox.evaluate()["passed"]
    assert all(not check["evidence_ids"] for check in sandbox.evaluate()["checks"])
    complete_release(sandbox)
    assert sandbox.evaluate()["passed"]


def test_foreign_ticket_and_links_cannot_access_another_run(tmp_path):
    sandbox = make_sandbox(tmp_path / "one")
    other = make_sandbox(tmp_path / "two")
    ticket = other.create_ticket("Other", "1.0", "ticket")
    with pytest.raises(SandboxError) as error:
        sandbox.create_checklist(ticket["id"], "Checklist", ["Item"], "list")
    assert error.value.code == "not_found"
    with pytest.raises(SandboxError) as error:
        sandbox.send_message("#qa-demo", "Ready", [ticket["url"]], "message")
    assert error.value.code == "invalid_reference"
    assert not sandbox.list_checklists() and not sandbox.list_messages()


@pytest.mark.parametrize("bad_items", [[], "[1,2]", [None], [1], [""]])
def test_invalid_items_do_not_mutate_state(tmp_path, bad_items):
    sandbox = make_sandbox(tmp_path)
    ticket = sandbox.create_ticket("Title", "1.0", "ticket")
    with pytest.raises(SandboxError) as error:
        sandbox.create_checklist(ticket["id"], "Checklist", bad_items, "list")
    assert error.value.code == "invalid_arguments"
    assert sandbox.list_checklists() == []


def test_wrong_identity_and_accidental_reinitialization_are_rejected(tmp_path):
    sandbox = make_sandbox(tmp_path)
    with pytest.raises(SandboxError, match="different task/run"):
        Sandbox(sandbox.path, str(uuid4()), sandbox.run_id).metadata()
    with pytest.raises(SandboxError) as error:
        sandbox.initialize(project_id="other")
    assert error.value.code == "setup_conflict"
    with pytest.raises(SandboxError) as error:
        Sandbox(tmp_path / "missing.sqlite3", "task", "run").metadata()
    assert error.value.code == "sandbox_not_initialized"
    assert not (tmp_path / "missing.sqlite3").exists()


def test_business_outputs_do_not_reveal_fault_selection_or_trusted_criteria(tmp_path):
    sandbox = make_sandbox(tmp_path, "broken_checklist")
    ticket = sandbox.create_ticket("Title", "1.0", "ticket")
    visible = json.dumps([ticket, sandbox.list_tickets(), sandbox.read_runbook()])
    for forbidden in (
        "broken_checklist",
        "criteria_sha256",
        "legacy serializer",
        "reference_patch",
    ):
        assert forbidden not in visible


def test_empty_and_invalid_grants_are_preserved_or_rejected(tmp_path):
    sandbox = Sandbox(tmp_path / "sandbox.sqlite3", "task", "run")
    sandbox.initialize(grants=[])
    assert sandbox.metadata()["grants"] == []
    with pytest.raises(SandboxError) as error:
        sandbox.reset(grants=["directory.lookup"])
    assert error.value.code == "invalid_grants"
    assert sandbox.metadata()["grants"] == []


def test_reset_keeps_nondefault_scenario_scope_release_and_grants(tmp_path):
    sandbox = Sandbox(tmp_path / "sandbox.sqlite3", "task", "run")
    sandbox.initialize("broken_checklist", "payments", "2.4", ["tickets.list"])
    before = sandbox.metadata()
    sandbox.reset()
    after = sandbox.metadata()
    assert {**after, "generation": before["generation"]} == before


def test_a_different_release_number_in_message_is_not_a_matching_notice(tmp_path):
    sandbox = make_sandbox(tmp_path)
    metadata = sandbox.metadata()
    ticket = sandbox.create_ticket(metadata["ticket_title"], metadata["release"], "ticket")
    checklist = sandbox.create_checklist(
        ticket["id"], metadata["checklist_title"], metadata["expected_items"], "list"
    )
    sandbox.send_message(
        metadata["qa_channel"], "Release 11.0 is ready", [ticket["url"], checklist["url"]], "msg"
    )
    assert not sandbox.evaluate()["checks"][-1]["passed"]


@pytest.mark.parametrize(
    ("notice", "expected"),
    [
        ("Please review demo release 2.4.\nTicket: see attached links.", True),
        ("Release 2.4.", True),
        ("Release 2.4. Please review the checklist.", True),
        ("Release 2.4, ready for QA.", True),
        ("Release 2.4", True),
        ("Release 12.4 is ready.", False),
        ("Release 2.40 is ready.", False),
        ("Release 2.4.1 is ready.", False),
        ("Release 2.4alpha is ready.", False),
        ("Release 2.4.alpha is ready.", False),
    ],
)
def test_release_notice_accepts_sentence_punctuation_but_not_other_versions(
    tmp_path, notice, expected
):
    sandbox = make_sandbox(tmp_path, release="2.4")
    metadata = sandbox.metadata()
    ticket = sandbox.create_ticket(metadata["ticket_title"], metadata["release"], "ticket")
    checklist = sandbox.create_checklist(
        ticket["id"], metadata["checklist_title"], metadata["expected_items"], "list"
    )
    sandbox.send_message(metadata["qa_channel"], notice, [ticket["url"], checklist["url"]], "msg")
    verification = sandbox.evaluate()
    assert verification["passed"] is expected
    assert verification["evaluator_version"] == "release-state-v2"
    assert metadata["evaluator_version"] == "release-state-v2"
