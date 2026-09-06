"""Additive user criteria and ordinary in-place business updates retain evidence."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256

import pytest

from epoch_backend.sandbox import TOOL_NAMES, Sandbox, SandboxError
from epoch_backend.tool_registry import ToolRegistry
from epoch_backend.trusted_checks import criteria_from_metadata


@pytest.fixture
def sandbox(tmp_path):
    result = Sandbox(tmp_path / "sandbox.sqlite3", "task", "run")
    result.initialize()
    return result


def complete_release(sandbox):
    metadata = sandbox.metadata()
    ticket = sandbox.create_ticket(metadata["ticket_title"], metadata["release"], "ticket")
    checklist = sandbox.create_checklist(
        ticket["id"], metadata["checklist_title"], metadata["expected_items"], "checklist"
    )
    message = sandbox.send_message(
        metadata["qa_channel"],
        f"Release {metadata['release']} is ready.",
        [ticket["url"], checklist["url"]],
        "message",
    )
    return ticket, checklist, message


def revise(sandbox, revision_id="revision-1", **overrides):
    return sandbox.revise_requirements(
        revision_id=revision_id,
        additional_items=["Security review approved"],
        required_message_phrases=["Deployment starts at 10:00 UTC"],
        source_refs=[{"kind": "user_feedback", "source_id": "feedback-1"}],
        **overrides,
    )


def write_metadata(sandbox, metadata):
    with sqlite3.connect(sandbox.path) as connection:
        connection.execute(
            "UPDATE sandbox_metadata SET record_json=? WHERE id=1", (json.dumps(metadata),)
        )


def test_revision_is_durable_additive_and_retains_original_outcomes(sandbox):
    original = sandbox.metadata()
    original_state = sandbox.snapshot()
    complete_release(sandbox)
    passed = sandbox.evaluate()
    assert passed["passed"]
    before = sandbox.snapshot()
    revised = revise(sandbox)
    assert sandbox.snapshot() == before
    assert revised["expected_items"] == original["expected_items"] + ["Security review approved"]
    for key in ("qa_channel", "ticket_title", "checklist_title", "project_id", "release", "grants"):
        assert revised[key] == original[key]
    assert revised["criteria_sha256"] != original["criteria_sha256"]
    assert revised["requirements_revisions"][0]["before_criteria"] == criteria_from_metadata(
        original
    )
    assert revised["requirements_revisions"][0]["after_sha256"] == revised["criteria_sha256"]
    assert Sandbox(sandbox.path, "task", "run").metadata() == revised
    retained = next(event for event in sandbox.events() if event["id"] == passed["evidence_id"])
    assert retained["payload"]["passed"] is True
    assert retained["payload"]["criteria_sha256"] == original["criteria_sha256"]
    assert not sandbox.evaluate()["passed"]
    assert sandbox.read_runbook()["content"] == original_state["runbooks"][1]["content"]


def test_updates_satisfy_revision_without_duplicating_or_relinking_objects(sandbox):
    ticket, checklist, message = complete_release(sandbox)
    original = sandbox.metadata()
    revised = revise(sandbox)
    checklist_update = sandbox.update_checklist(
        checklist["id"], revised["expected_items"], "edit-1"
    )
    message_update = sandbox.update_message(
        message["id"], message["text"] + " Deployment starts at 10:00 UTC", "edit-2"
    )
    assert sandbox.evaluate()["passed"]
    assert sandbox.list_tickets() == [ticket]
    assert sandbox.list_checklists() == [checklist_update]
    assert sandbox.list_messages() == [message_update]
    assert {**checklist_update, "items": checklist["items"]} == checklist
    assert {**message_update, "text": message["text"]} == message
    events = [
        event
        for event in sandbox.events()
        if event["payload"].get("operation", "").endswith(".update")
    ]
    assert len(events) == 2
    assert events[0]["payload"]["before"] == checklist
    assert events[0]["payload"]["after"] == checklist_update
    assert events[1]["payload"]["before"] == message
    assert (
        sandbox.metadata()["requirements_revisions"][0]["before_sha256"]
        == original["criteria_sha256"]
    )


def test_same_revision_retry_retains_original_result_and_changed_input_conflicts(sandbox):
    first = revise(sandbox)
    second = revise(sandbox, "revision-2")
    event_count = len(sandbox.events())
    assert revise(sandbox) == first
    assert sandbox.metadata() == second
    assert len(sandbox.events()) == event_count
    with pytest.raises(SandboxError) as error:
        sandbox.revise_requirements("revision-1", [], [], [{"source_id": "different"}])
    assert error.value.code == "revision_conflict"
    assert sandbox.metadata() == second


def test_concurrent_revision_retries_have_one_atomic_receipt(sandbox):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: revise(sandbox), range(8)))
    assert all(result == results[0] for result in results)
    assert len(sandbox.metadata()["requirements_revisions"]) == 1
    assert (
        len([event for event in sandbox.events() if event["type"] == "requirements.revised"]) == 1
    )


def test_revision_failure_rolls_back_metadata_receipt_and_event(sandbox, monkeypatch):
    before = sandbox.metadata()
    original_event = sandbox._event

    def fail(*args, **kwargs):
        raise RuntimeError("disk failure")

    monkeypatch.setattr(sandbox, "_event", fail)
    with pytest.raises(RuntimeError):
        revise(sandbox)
    assert sandbox.metadata() == before
    monkeypatch.setattr(sandbox, "_event", original_event)
    assert len(revise(sandbox)["requirements_revisions"]) == 1


@pytest.mark.parametrize(
    "items,phrases,sources",
    [
        ("replace old items", [], [{"id": "feedback"}]),
        ([""], [], [{"id": "feedback"}]),
        (["x" * 501], [], [{"id": "feedback"}]),
        ([], [1], [{"id": "feedback"}]),
        ([], [], []),
        ([], [], [{}]),
        ([], [], [{"id": "x" * 4001}]),
        ([], [], [{"id": float("nan")}]),
        ([f"item-{index}" for index in range(50)], [], [{"id": "feedback"}]),
        ([], [f"phrase-{index}" for index in range(21)], [{"id": "feedback"}]),
    ],
)
def test_invalid_or_oversize_revision_cannot_change_criteria(sandbox, items, phrases, sources):
    original = sandbox.metadata()
    with pytest.raises(SandboxError) as error:
        sandbox.revise_requirements("invalid", items, phrases, sources)
    assert error.value.code == "invalid_arguments"
    assert sandbox.metadata() == original


def test_duplicate_requirements_are_normalized_and_cannot_remove_originals(sandbox):
    original = sandbox.metadata()
    revised = sandbox.revise_requirements(
        "add",
        [original["expected_items"][0], " Added ", "Added"],
        ["Exact", "Exact"],
        [{"id": "source"}],
    )
    assert revised["expected_items"] == [*original["expected_items"], "Added"]
    assert revised["required_message_phrases"] == ["Exact"]
    empty = sandbox.revise_requirements("empty", [], [], [{"id": "new-source"}])
    assert empty["expected_items"] == revised["expected_items"]
    assert empty["required_message_phrases"] == ["Exact"]
    assert empty["criteria_sha256"] == revised["criteria_sha256"]


def test_all_phrases_must_be_exact_in_one_correctly_linked_message(sandbox):
    ticket, checklist, message = complete_release(sandbox)
    sandbox.revise_requirements(
        "phrases", [], ["Review approved", "Deploy tomorrow"], [{"id": "source"}]
    )
    sandbox.update_message(message["id"], "Release 1.0. Review approved", "split-1")
    second = sandbox.send_message(
        "#qa-demo", "Release 1.0. Deploy tomorrow", [ticket["url"], checklist["url"]], "split-2"
    )
    assert not sandbox.evaluate()["passed"]
    sandbox.update_message(second["id"], "Release 1.0. review approved. Deploy tomorrow", "case")
    assert not sandbox.evaluate()["passed"]
    sandbox.update_message(second["id"], "Release 1.0. Review approved. Deploy tomorrow", "exact")
    result = sandbox.evaluate()
    assert result["passed"]
    assert result["checks"][-1]["id"] == "qa_message_content"
    assert result["checks"][-1]["details"]["matching_object_ids"] == [second["id"]]


def test_required_content_cannot_pass_in_wrong_channel_or_unlinked_notice(sandbox):
    ticket, checklist, _ = complete_release(sandbox)
    sandbox.revise_requirements("phrases", [], ["Review approved"], [{"id": "source"}])
    sandbox.send_message(
        "#other", "Release 1.0. Review approved", [ticket["url"], checklist["url"]], "wrong-channel"
    )
    sandbox.send_message("#qa-demo", "Release 1.0. Review approved", [ticket["url"]], "wrong-links")
    assert not sandbox.evaluate()["passed"]


@pytest.mark.parametrize("kind", ["checklist", "message"])
def test_updates_retry_once_conflict_on_changed_content_and_retain_history(sandbox, kind):
    _, checklist, message = complete_release(sandbox)
    operation = sandbox.update_checklist if kind == "checklist" else sandbox.update_message
    identifier = checklist["id"] if kind == "checklist" else message["id"]
    first_content = ["First"] if kind == "checklist" else "First"
    second_content = ["Second"] if kind == "checklist" else "Second"
    first = operation(identifier, first_content, "revision")
    event_count = len(sandbox.events())
    assert operation(identifier, first_content, "revision") == first
    assert len(sandbox.events()) == event_count
    with pytest.raises(SandboxError) as error:
        operation(identifier, second_content, "revision")
    assert error.value.code == "idempotency_conflict"
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: operation(identifier, second_content, "next"), range(6)))
    assert all(result == results[0] for result in results)
    assert len(sandbox.events()) == event_count + 1
    assert operation(identifier, first_content, "revision") == first
    assert len(sandbox.events()) == event_count + 1


def test_updates_reject_foreign_ids_and_broken_adapter_without_effects(sandbox, tmp_path):
    other = Sandbox(tmp_path / "other.sqlite3", "task-2", "run-2")
    other.initialize()
    _, checklist, message = complete_release(other)
    before = sandbox.snapshot()
    for operation, identifier, value in (
        (sandbox.update_checklist, checklist["id"], ["New item"]),
        (sandbox.update_message, message["id"], "New text"),
    ):
        with pytest.raises(SandboxError) as error:
            operation(identifier, value, "foreign")
        assert error.value.code == "not_found"
    assert sandbox.snapshot() == before
    # Existing state can predate a defective adapter: update must use its real serializer too.
    write_metadata(other, {**other.metadata(), "scenario": "broken_checklist"})
    before = other.snapshot()
    with pytest.raises(SandboxError) as error:
        other.update_checklist(checklist["id"], ["New item"], "broken")
    assert error.value.code == "adapter_contract_error"
    assert other.snapshot() == before


def test_historical_metadata_and_grants_are_preserved_on_reopen(sandbox):
    complete_release(sandbox)
    old = sandbox.metadata()
    old["grants"] = sorted(name for name in TOOL_NAMES if not name.endswith(".update"))
    old["evaluator_version"] = "release-state-v2"
    old["environment_version"] = "sandbox-v1"
    old.pop("required_message_phrases")
    old.pop("requirements_revisions")
    criteria = criteria_from_metadata(old)
    old["criteria_sha256"] = sha256(
        json.dumps(criteria, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    write_metadata(sandbox, old)
    reopened = Sandbox(sandbox.path, sandbox.task_id, sandbox.run_id)
    assert reopened.initialize() == old
    assert reopened.evaluate()["evaluator_version"] == "release-state-v2"
    assert reopened.metadata() == old
    registry = ToolRegistry(reopened)
    names = {tool["name"] for tool in registry.discover_tools()["result"]["tools"]}
    assert "checklists.update" not in names and "messages.update" not in names
    for name, arguments in (
        (
            "checklists.update",
            {
                "checklist_id": sandbox.list_checklists()[0]["id"],
                "items": ["New"],
                "idempotency_key": "new",
            },
        ),
        (
            "messages.update",
            {
                "message_id": sandbox.list_messages()[0]["id"],
                "text": "New",
                "idempotency_key": "new",
            },
        ),
    ):
        assert registry.invoke_tool(name, arguments)["error"]["code"] == "access_denied"
    revised = revise(reopened)
    assert revised["evaluator_version"] == "release-state-v3"
    assert revised["grants"] == old["grants"]
    assert revised["requirements_revisions"][0]["before_criteria"] == criteria


def test_update_permissions_are_enforced_even_on_direct_business_calls(sandbox):
    _, checklist, message = complete_release(sandbox)
    sandbox.update_message(message["id"], "New", "retry")
    original = sandbox.metadata()
    write_metadata(
        sandbox,
        {**original, "grants": [name for name in TOOL_NAMES if not name.endswith(".update")]},
    )
    for operation, identifier, value in (
        (sandbox.update_checklist, checklist["id"], ["New"]),
        (sandbox.update_message, message["id"], "New"),
    ):
        with pytest.raises(SandboxError) as error:
            operation(identifier, value, "retry")
        assert error.value.code == "access_denied"


def test_updates_cannot_override_scope_links_identity_or_criteria_through_registry(sandbox):
    _, checklist, message = complete_release(sandbox)
    registry = ToolRegistry(sandbox)
    for name, args, invalid_fields in (
        (
            "checklists.update",
            {"checklist_id": checklist["id"], "items": ["Item"], "idempotency_key": "edit"},
            {"ticket_id": "foreign", "title": "Changed", "expected_items": ["Weakened"]},
        ),
        (
            "messages.update",
            {"message_id": message["id"], "text": "Updated", "idempotency_key": "edit"},
            {"channel": "#other", "links": [], "id": "new"},
        ),
    ):
        for key, value in invalid_fields.items():
            response = registry.invoke_tool(name, {**args, key: value})
            assert response["error"]["code"] == "invalid_arguments"
    assert sandbox.list_checklists() == [checklist]
    assert sandbox.list_messages() == [message]
