"""Actual MCP stdio transport; only the three scoped registry functions are tools."""

import argparse
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, ValidationError

from epoch_backend.sandbox import Sandbox, SandboxError
from epoch_backend.tool_registry import ToolRegistry


class _FacadeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _DescribeArguments(_FacadeArguments):
    name: str


class _InvokeArguments(_DescribeArguments):
    arguments: dict[str, Any]


_FACADE_ARGUMENTS = {
    "discover_tools": _FacadeArguments,
    "describe_tool": _DescribeArguments,
    "invoke_tool": _InvokeArguments,
}


class ScopedMCP(FastMCP):
    """Enforce the facade envelope before the SDK's permissive argument conversion."""

    def __init__(self, sandbox: Sandbox, **kwargs: Any):
        self.sandbox = sandbox
        super().__init__("Epoch Sandbox", **kwargs)

    async def list_tools(self):
        tools = await super().list_tools()
        for tool in tools:
            tool.inputSchema = _FACADE_ARGUMENTS[tool.name].model_json_schema()
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]):
        model = _FACADE_ARGUMENTS.get(name)
        if model is None:
            self.sandbox.record_event(
                "mcp.invalid_call", {"facade_name": name, "code": "tool_not_found"}
            )
            return await super().call_tool(name, arguments)
        try:
            model.model_validate(arguments)
        except ValidationError:
            self.sandbox.record_event(
                "mcp.invalid_call", {"facade_name": name, "code": "invalid_arguments"}
            )
            return {
                "ok": False,
                "error": {
                    "code": "invalid_arguments",
                    "message": "Arguments must match the published MCP facade schema.",
                },
            }
        return await super().call_tool(name, arguments)


def create_server(sandbox: Sandbox) -> FastMCP:
    registry = ToolRegistry(sandbox)
    server = ScopedMCP(
        sandbox,
        instructions=(
            "Tools perform simulated business actions only in this run's project. "
            "Discover the available tools, describe each operation before invoking it, "
            "then inspect actual results. Tool success does not establish task completion."
        ),
        log_level="WARNING",
    )

    @server.tool()
    def discover_tools() -> dict[str, Any]:
        """Discover the permitted simulated business tools for this run."""
        return registry.discover_tools()

    @server.tool()
    def describe_tool(name: str) -> dict[str, Any]:
        """Read a permitted tool's input schema and usage requirements."""
        return registry.describe_tool(name)

    @server.tool()
    def invoke_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a discovered business tool using arguments matching its schema."""
        return registry.invoke_tool(name, arguments)

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Epoch scoped sandbox MCP stdio server")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--task-id", type=UUID, required=True)
    parser.add_argument("--run-id", type=UUID, required=True)
    args = parser.parse_args(argv)
    if not args.database.is_file():
        print("MCP startup failed: sandbox database must already exist.", file=sys.stderr)
        return 2
    try:
        sandbox = Sandbox(args.database, str(args.task_id), str(args.run_id))
        server = create_server(sandbox)
    except SandboxError as exc:
        print(f"MCP startup failed: {exc.code}.", file=sys.stderr)
        return 2
    except (OSError, ValueError):
        print("MCP startup failed: invalid sandbox configuration.", file=sys.stderr)
        return 2
    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
