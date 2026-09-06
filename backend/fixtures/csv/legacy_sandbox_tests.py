"""Real local CSV adapter/service effects, isolated from models and release tools."""

import asyncio
import json
import sys
from datetime import timedelta
from uuid import uuid4

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from epoch_backend.csv_sandbox import SAMPLE_CSV, CsvRegistry, CsvSandbox
from epoch_backend.sandbox import Sandbox, SandboxError


def environment(tmp_path, mode="broken"):
    value = CsvSandbox(tmp_path / f"{mode}.sqlite3", str(uuid4()), str(uuid4()))
    value.initialize(adapter_mode=mode)
    return value


def test_broken_adapter_generates_wrong_wire_and_service_atomically_rejects(tmp_path):
    sandbox = environment(tmp_path)
    original = sandbox.metadata()
    result = sandbox.import_customers(SAMPLE_CSV, "sample-import")
    assert result["status"] == "rejected"
    assert result["error"]["code"] == "missing_email"
    assert result["created_count"] == result["customer_count_after"] == 0
    snapshot = sandbox.snapshot()
    assert snapshot["customers"] == []
    assert snapshot["verification"]["passed"] is False
    assert snapshot["verification"]["checks"][2]["passed"] is True
    failure = next(e for e in sandbox.events() if e["type"] == "tool.service_error")
    assert failure["payload"]["outgoing_customers"][0] == {
        "name": "Asha",
        "emailAddress": "asha@example.test",
    }
    assert failure["payload"]["expected_fields"] == ["name", "email"]
    assert len(json.dumps(failure["payload"])) < 4000
    assert any(
        e["type"] == "criteria.recorded" and e["payload"]["trusted"] for e in sandbox.events()
    )
    assert original == sandbox.metadata()
    assert sandbox.get_import_status(result["id"]) == result
    assert sandbox.import_customers(SAMPLE_CSV, "sample-import") == result
    assert len(sandbox.snapshot()["imports"]) == 1


def test_healthy_control_persists_three_and_exact_retry_deduplicates(tmp_path):
    sandbox = environment(tmp_path, "healthy")
    result = sandbox.import_customers(SAMPLE_CSV, "original")
    assert result["status"] == "completed" and result["created_count"] == 3
    first = sandbox.snapshot()
    assert first["verification"]["passed"] is True
    assert sandbox.import_customers(SAMPLE_CSV, "original") == result
    second = sandbox.import_customers(SAMPLE_CSV, "different-key-same-customers")
    assert second["created_count"] == 0 and second["customer_count_after"] == 3
    assert sandbox.list_customers() == first["customers"]
    with pytest.raises(SandboxError, match="different CSV content"):
        sandbox.import_customers(SAMPLE_CSV + "Extra,extra@example.test\n", "original")
    restarted = CsvSandbox(sandbox.path, sandbox.task_id, sandbox.run_id)
    restarted.initialize(adapter_mode="healthy")
    assert restarted.list_customers() == first["customers"]
    assert restarted.get_import_status(result["id"]) == result
    assert restarted.metadata()["criteria"] == first["criteria"]
    with pytest.raises(SandboxError, match="cannot change"):
        restarted.initialize(adapter_mode="broken")
    with pytest.raises(SandboxError, match="another task/run"):
        CsvSandbox(sandbox.path, str(uuid4()), str(uuid4())).metadata()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "x" * 12001,
        "email,name\na@example.test,Asha\n",
        "name,email,email\nA,a@b.test,a@b.test\n",
        "name,email\nAsha\n",
        "name,email\n,asha@example.test\n",
        "name,email\nAsha,\n",
        "name,email\nAsha,invalid\n",
        "name,email\nAsha,asha@example.test,extra\n",
        "name,email\n",
        "name,email\n\n",
        'name,email\n"Asha,asha@example.test\n',
        "name,email\n" + "Asha,asha@example.test\n" * 51,
    ],
)
def test_invalid_csv_never_leaves_partial_customers(tmp_path, text):
    sandbox = environment(tmp_path, "healthy")
    try:
        result = sandbox.import_customers(text, "invalid")
    except SandboxError as error:
        assert error.code == "invalid_csv"
    else:
        assert result["status"] == "rejected" and result["error"]["code"] == "invalid_csv"
    assert sandbox.list_customers() == []


def test_mixed_valid_and_invalid_rows_are_atomic_and_casefold_deduplicates(tmp_path):
    sandbox = environment(tmp_path, "healthy")
    rejected = sandbox.import_customers("name,email\nAsha,asha@example.test\nRavi,\n", "bad")
    assert rejected["created_count"] == 0 and sandbox.list_customers() == []
    accepted = sandbox.import_customers(
        "name,email\nAsha,asha@example.test\nAsha,ASHA@example.test\n", "duplicates"
    )
    assert accepted["created_count"] == 1
    assert sandbox.list_customers()[0]["email"] == "asha@example.test"


def test_registry_has_only_customer_tools_and_no_mode_or_criteria_edits(tmp_path):
    sandbox = environment(tmp_path)
    registry = CsvRegistry(sandbox)
    names = {item["name"] for item in registry.discover_tools()["result"]["tools"]}
    assert names == {
        "customers.read_sample",
        "customers.import",
        "customers.list",
        "customers.get_import_status",
    }
    assert "broken" not in json.dumps(registry.discover_tools())
    assert "adapter_mode" not in json.dumps(registry.invoke_tool("customers.read_sample", {}))
    for name in ("tickets.create", "repair", "criteria.update", "environment.select"):
        assert registry.invoke_tool(name, {})["error"]["code"] == "tool_not_found"
    assert (
        registry.invoke_tool(
            "customers.import",
            {
                "csv_text": SAMPLE_CSV,
                "idempotency_key": "x",
                "adapter_mode": "healthy",
            },
        )["error"]["code"]
        == "invalid_arguments"
    )
    assert registry.invoke_tool("customers.list", {"project_id": "other"})["ok"] is False
    assert (
        registry.invoke_tool("customers.get_import_status", {"import_id": str(uuid4())})["error"][
            "code"
        ]
        == "import_not_found"
    )
    assert sandbox.metadata()["adapter_mode"] == "broken"


def test_unrelated_release_database_is_rejected_and_snapshot_is_bounded(tmp_path):
    release = Sandbox(tmp_path / "release.sqlite3", str(uuid4()), str(uuid4()))
    release.initialize()
    with pytest.raises(SandboxError, match="not a CSV"):
        CsvSandbox(release.path, release.task_id, release.run_id).initialize()
    sandbox = environment(tmp_path)
    for index in range(22):
        sandbox.import_customers(SAMPLE_CSV, str(index))
    snapshot = sandbox.snapshot()
    assert len(snapshot["imports"]) == 20 and snapshot["imports_total"] == 22
    assert len(snapshot["events"]) == 30 and snapshot["events_total"] > 30
    assert snapshot["sample_csv"] == SAMPLE_CSV
    after = snapshot["events"][-1]["sequence"]
    assert sandbox.events(after=after) == []


def test_real_csv_stdio_discovery_import_and_restart(tmp_path):
    sandbox = environment(tmp_path)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "epoch_backend.mcp_server",
            "--database",
            str(sandbox.path),
            "--task-id",
            sandbox.task_id,
            "--run-id",
            sandbox.run_id,
            "--environment",
            "csv_import",
        ],
    )

    def unpack(result):
        assert result.isError is False
        return result.structuredContent or json.loads(result.content[0].text)

    async def exercise():
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=15)
            ) as client:
                await client.initialize()
                assert {tool.name for tool in (await client.list_tools()).tools} == {
                    "discover_tools",
                    "describe_tool",
                    "invoke_tool",
                }
                discovery = unpack(await client.call_tool("discover_tools", {}))
                assert all(t["name"].startswith("customers.") for t in discovery["result"]["tools"])
                contract = unpack(
                    await client.call_tool("describe_tool", {"name": "customers.import"})
                )
                assert contract["result"]["input_schema"]["additionalProperties"] is False
                source = unpack(
                    await client.call_tool(
                        "invoke_tool", {"name": "customers.read_sample", "arguments": {}}
                    )
                )
                imported = unpack(
                    await client.call_tool(
                        "invoke_tool",
                        {
                            "name": "customers.import",
                            "arguments": {
                                "csv_text": source["result"]["csv_text"],
                                "idempotency_key": "stdio-import",
                            },
                        },
                    )
                )
                assert imported["result"]["status"] == "rejected"
                assert imported["result"]["error"]["code"] == "missing_email"
                listed = unpack(
                    await client.call_tool(
                        "invoke_tool", {"name": "customers.list", "arguments": {}}
                    )
                )
                assert listed["result"] == []
                return imported["result"]

    first = asyncio.run(exercise())
    assert asyncio.run(exercise()) == first
    assert sandbox.snapshot()["imports_total"] == 1
