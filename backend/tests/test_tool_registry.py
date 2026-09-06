"""Behavioral checks at the only business capability boundary exposed to Hermes."""

import json
from uuid import uuid4

import pytest

from epoch_backend.sandbox import Sandbox
from epoch_backend.tool_registry import ToolRegistry, facade_identity


@pytest.fixture
def sandbox(tmp_path):
    result = Sandbox(tmp_path / "sandbox.sqlite3", str(uuid4()), str(uuid4()))
    result.initialize()
    return result


def ticket_arguments(**overrides):
    return {
        "title": "Release 1.0",
        "release": "1.0",
        "idempotency_key": "ticket-1",
        **overrides,
    }


def test_discovery_and_descriptions_expose_only_granted_business_operations(tmp_path):
    sandbox = Sandbox(tmp_path / "scoped.sqlite3", str(uuid4()), str(uuid4()))
    sandbox.initialize(grants=["tickets.list", "runbooks.read"])
    registry = ToolRegistry(sandbox)
    discovery = registry.discover_tools()
    assert discovery["ok"] is True
    assert {tool["name"] for tool in discovery["result"]["tools"]} == {
        "tickets.list",
        "runbooks.read",
    }
    assert registry.describe_tool("tickets.create")["error"]["code"] == "access_denied"
    description = registry.describe_tool("runbooks.read")["result"]
    assert description["input_schema"]["additionalProperties"] is False
    assert description["simulated"] is True
    assert registry.invoke_tool("tickets.create", ticket_arguments())["error"]["code"] == (
        "access_denied"
    )
    assert sandbox.list_tickets() == []


@pytest.mark.parametrize(
    "forbidden",
    [
        "reset",
        "evaluate",
        "sandbox.metadata",
        "directory.lookup",
        "grants.update",
        "revise_requirements",
        "requirements.revise",
    ],
)
def test_administration_trusted_answers_and_missing_lookup_are_not_tools(sandbox, forbidden):
    registry = ToolRegistry(sandbox)
    before = sandbox.metadata()
    assert registry.describe_tool(forbidden)["error"]["code"] == "tool_not_found"
    assert registry.invoke_tool(forbidden, {})["error"]["code"] == "tool_not_found"
    assert sandbox.metadata() == before
    assert forbidden not in {item["name"] for item in registry.discover_tools()["result"]["tools"]}


@pytest.mark.parametrize(
    "extra", [{"project_id": "other"}, {"grants": ["*"]}, {"scenario": "control"}, {"reset": True}]
)
def test_arguments_cannot_override_project_permissions_or_fixture(sandbox, extra):
    result = ToolRegistry(sandbox).invoke_tool("tickets.create", ticket_arguments(**extra))
    assert result["error"]["code"] == "invalid_arguments"
    assert sandbox.list_tickets() == []


@pytest.mark.parametrize(
    "arguments",
    [ticket_arguments(title="  "), ticket_arguments(release=123), {"title": "only title"}, []],
)
def test_invalid_calls_are_recorded_without_business_effects(sandbox, arguments):
    result = ToolRegistry(sandbox).invoke_tool("tickets.create", arguments)
    assert result["error"]["code"] == "invalid_arguments"
    calls = [event for event in sandbox.events() if event["type"] == "tool.called"]
    errors = [event for event in sandbox.events() if event["type"] == "tool.error"]
    assert len(calls) == len(errors) == 1
    assert calls[0]["payload"]["call_id"] == errors[0]["payload"]["call_id"]
    assert calls[0]["task_id"] == sandbox.metadata()["task_id"]
    assert calls[0]["run_id"] == sandbox.metadata()["run_id"]
    assert sandbox.list_tickets() == []


def test_successful_call_is_persistent_idempotent_and_traced(sandbox):
    registry = ToolRegistry(sandbox)
    first = registry.invoke_tool("tickets.create", ticket_arguments())
    second = registry.invoke_tool("tickets.create", ticket_arguments())
    assert first["ok"] is True
    assert first == second
    assert len(sandbox.list_tickets()) == 1
    results = [event for event in sandbox.events() if event["type"] == "tool.result"]
    assert results[-1]["payload"]["result"] == first["result"]
    assert first["result"]["simulated"] is True


def test_unexpected_adapter_error_records_missing_result_without_host_details(sandbox, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("secret host path and internal credentials")

    monkeypatch.setattr(sandbox, "create_ticket", fail)
    result = ToolRegistry(sandbox).invoke_tool("tickets.create", ticket_arguments())
    assert result["error"]["code"] == "tool_execution_failed"
    assert "credentials" not in json.dumps(sandbox.events())
    assert sandbox.list_tickets() == []


def test_adapter_cannot_return_an_unsimulated_or_fabricated_success(sandbox, monkeypatch):
    monkeypatch.setattr(sandbox, "create_ticket", lambda **kwargs: {"url": "https://made-up.test"})
    result = ToolRegistry(sandbox).invoke_tool("tickets.create", ticket_arguments())
    assert result["error"]["code"] == "invalid_tool_result"
    assert not any(event["type"] == "tool.result" for event in sandbox.events())
    assert sandbox.list_tickets() == []


def test_obvious_credentials_in_invalid_arguments_are_redacted(sandbox):
    result = ToolRegistry(sandbox).invoke_tool(
        "tickets.create", ticket_arguments(api_key="do-not-store-this-value")
    )
    assert result["error"]["code"] == "invalid_arguments"
    assert "do-not-store-this-value" not in json.dumps(sandbox.events())
    assert "[redacted]" in json.dumps(sandbox.events())


def test_context_retains_document_and_selector_provenance(tmp_path):
    sandbox = Sandbox(tmp_path / "historical.sqlite3", str(uuid4()), str(uuid4()))
    sandbox.initialize(scenario="outdated_context")
    registry = ToolRegistry(sandbox)
    result = registry.invoke_tool("runbooks.read", {})
    assert result["ok"] is True
    assert result["result"]["is_current"] is False
    assert result["result"]["version"] == "v1"
    context = [event for event in sandbox.events() if event["type"] == "context.supplied"][-1]
    assert context["payload"]["source"] == result["result"]
    assert context["payload"]["source"]["selection_rule_version"]
    assert registry.invoke_tool("runbooks.read", {"version": "v2"})["result"]["is_current"] is True


def test_discovery_and_tool_contracts_do_not_reveal_control_or_failure_setup(tmp_path):
    discoveries = []
    contracts = []
    for scenario in ("control", "broken_checklist", "missing_lookup", "outdated_context"):
        sandbox = Sandbox(tmp_path / f"{scenario}.sqlite3", str(uuid4()), str(uuid4()))
        sandbox.initialize(scenario=scenario)
        registry = ToolRegistry(sandbox)
        discoveries.append(registry.discover_tools())
        contracts.append(registry.describe_tool("checklists.create"))
    assert all(discovery == discoveries[0] for discovery in discoveries)
    assert all(contract == contracts[0] for contract in contracts)
    public = json.dumps([discoveries, contracts, facade_identity()])
    for private in ("expected_items", "qa_channel", "broken_checklist", "missing_lookup"):
        assert private not in public


def test_foreign_ticket_reference_cannot_create_a_checklist(sandbox, tmp_path):
    other = Sandbox(tmp_path / "other.sqlite3", str(uuid4()), str(uuid4()))
    other.initialize(project_id="other")
    foreign = other.create_ticket(**ticket_arguments())
    result = ToolRegistry(sandbox).invoke_tool(
        "checklists.create",
        {
            "ticket_id": foreign["id"],
            "title": "Checklist",
            "items": ["Smoke test"],
            "idempotency_key": "foreign-checklist",
        },
    )
    assert result["ok"] is False
    assert sandbox.list_checklists() == []
