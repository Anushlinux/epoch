"""Exercise the real SDK client against a separate server over MCP stdio."""

import asyncio
import json
import subprocess
import sys
from datetime import timedelta
from uuid import uuid4

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from epoch_backend.sandbox import Sandbox


def server_args(database, task_id, run_id):
    return [
        "-m",
        "epoch_backend.mcp_server",
        "--database",
        str(database),
        "--task-id",
        task_id,
        "--run-id",
        run_id,
    ]


def unpack(result):
    assert result.isError is False
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(result.content[0].text)


def test_real_stdio_discovery_description_invocation_and_restart(tmp_path):
    task_id, run_id = str(uuid4()), str(uuid4())
    database = tmp_path / "sandbox.sqlite3"
    sandbox = Sandbox(database, task_id, run_id)
    sandbox.initialize(grants=["tickets.create", "tickets.list", "runbooks.read"])
    parameters = StdioServerParameters(
        command=sys.executable, args=server_args(database, task_id, run_id)
    )

    async def exercise():
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=15)
            ) as client:
                initialization = await client.initialize()
                assert initialization.serverInfo.name == "Epoch Sandbox"
                tools = await client.list_tools()
                assert {tool.name for tool in tools.tools} == {
                    "discover_tools",
                    "describe_tool",
                    "invoke_tool",
                }
                assert all(
                    tool.inputSchema["additionalProperties"] is False for tool in tools.tools
                )
                assert not (await client.list_resources()).resources
                assert not (await client.list_prompts()).prompts
                discovery = unpack(await client.call_tool("discover_tools", {}))
                assert {tool["name"] for tool in discovery["result"]["tools"]} == {
                    "tickets.create",
                    "tickets.list",
                    "runbooks.read",
                }
                contract = unpack(
                    await client.call_tool("describe_tool", {"name": "tickets.create"})
                )
                assert "idempotency_key" in contract["result"]["input_schema"]["required"]
                created = unpack(
                    await client.call_tool(
                        "invoke_tool",
                        {
                            "name": "tickets.create",
                            "arguments": {
                                "title": "Release 1.0",
                                "release": "1.0",
                                "idempotency_key": "mcp-ticket",
                            },
                        },
                    )
                )
                assert created["ok"] is True
                assert created["result"]["simulated"] is True
                denied = unpack(
                    await client.call_tool(
                        "invoke_tool", {"name": "messages.list", "arguments": {}}
                    )
                )
                assert denied["error"]["code"] == "access_denied"
                invalid = unpack(
                    await client.call_tool(
                        "invoke_tool",
                        {"name": "tickets.list", "arguments": {"project_id": "another-project"}},
                    )
                )
                assert invalid["error"]["code"] == "invalid_arguments"
                invalid_envelope = unpack(
                    await client.call_tool("discover_tools", {"grants": ["*"]})
                )
                assert invalid_envelope["error"]["code"] == "invalid_arguments"
                for forbidden in ("reset", "evaluate", "directory.lookup"):
                    blocked = unpack(
                        await client.call_tool("invoke_tool", {"name": forbidden, "arguments": {}})
                    )
                    assert blocked["error"]["code"] == "tool_not_found"
                unknown = await client.call_tool("reset", {})
                assert unknown.isError is True

        # A new protocol session opens the same run without silently resetting state.
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=15)
            ) as client:
                await client.initialize()
                retained = unpack(
                    await client.call_tool("invoke_tool", {"name": "tickets.list", "arguments": {}})
                )
                assert len(retained["result"]) == 1

    asyncio.run(exercise())
    events = sandbox.events()
    assert any(event["type"] == "tool.called" for event in events)
    assert any(event["type"] == "tool.error" for event in events)
    assert all(event["run_id"] == run_id and event["task_id"] == task_id for event in events)


def test_real_stdio_updates_existing_objects_after_host_sourced_revision(tmp_path):
    task_id, run_id = str(uuid4()), str(uuid4())
    database = tmp_path / "revision.sqlite3"
    sandbox = Sandbox(database, task_id, run_id)
    metadata = sandbox.initialize()
    ticket = sandbox.create_ticket(metadata["ticket_title"], metadata["release"], "ticket")
    checklist = sandbox.create_checklist(
        ticket["id"], metadata["checklist_title"], metadata["expected_items"], "checklist"
    )
    message = sandbox.send_message(
        metadata["qa_channel"],
        "Release 1.0 is ready.",
        [ticket["url"], checklist["url"]],
        "message",
    )
    revised = sandbox.revise_requirements(
        "feedback-1",
        ["Security review approved"],
        ["Deployment at 10:00 UTC"],
        [{"kind": "user_feedback", "source_id": "feedback-1"}],
    )
    assert not sandbox.evaluate()["passed"]
    parameters = StdioServerParameters(
        command=sys.executable, args=server_args(database, task_id, run_id)
    )

    async def exercise():
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=15)
            ) as client:
                await client.initialize()
                discovered = unpack(await client.call_tool("discover_tools", {}))
                names = {tool["name"] for tool in discovered["result"]["tools"]}
                assert "checklists.update" in names and "messages.update" in names
                assert len(names) == 9
                for name, arguments in (
                    (
                        "checklists.update",
                        {
                            "checklist_id": checklist["id"],
                            "items": revised["expected_items"],
                            "idempotency_key": "checklist-edit",
                        },
                    ),
                    (
                        "messages.update",
                        {
                            "message_id": message["id"],
                            "text": "Release 1.0 is ready. Deployment at 10:00 UTC",
                            "idempotency_key": "message-edit",
                        },
                    ),
                ):
                    contract = unpack(await client.call_tool("describe_tool", {"name": name}))
                    assert contract["result"]["input_schema"]["additionalProperties"] is False
                    result = unpack(
                        await client.call_tool(
                            "invoke_tool", {"name": name, "arguments": arguments}
                        )
                    )
                    assert result["ok"] is True
                    retried = unpack(
                        await client.call_tool(
                            "invoke_tool", {"name": name, "arguments": arguments}
                        )
                    )
                    assert retried == result
                forbidden = unpack(
                    await client.call_tool(
                        "invoke_tool", {"name": "requirements.revise", "arguments": {}}
                    )
                )
                assert forbidden["error"]["code"] == "tool_not_found"

    asyncio.run(exercise())
    assert sandbox.evaluate()["passed"]
    assert sandbox.list_tickets() == [ticket]
    assert [item["id"] for item in sandbox.list_checklists()] == [checklist["id"]]
    assert [item["id"] for item in sandbox.list_messages()] == [message["id"]]
    updates = [
        event
        for event in sandbox.events()
        if event["type"] == "state.changed" and event["payload"]["operation"].endswith(".update")
    ]
    assert len(updates) == 2


def test_missing_database_is_not_created_and_stdout_stays_protocol_only(tmp_path):
    database = tmp_path / "missing.sqlite3"
    result = subprocess.run(
        [sys.executable, *server_args(database, str(uuid4()), str(uuid4()))],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "must already exist" in result.stderr
    assert not database.exists()


def test_wrong_run_identity_is_rejected_without_resetting_database(tmp_path):
    task_id, run_id = str(uuid4()), str(uuid4())
    database = tmp_path / "sandbox.sqlite3"
    sandbox = Sandbox(database, task_id, run_id)
    sandbox.initialize()
    before = sandbox.metadata()
    result = subprocess.run(
        [sys.executable, *server_args(database, task_id, str(uuid4()))],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "sandbox_identity_mismatch" in result.stderr
    assert sandbox.metadata() == before
