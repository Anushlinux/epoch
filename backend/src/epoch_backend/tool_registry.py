"""Permission-scoped business tools shared by the local harness and MCP server.

This registry exposes business operations only. Sandbox setup, trusted evaluation,
and environment changes belong to the host and never appear in tool discovery.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, ValidationError

from epoch_backend.sandbox import Sandbox, SandboxError

TOOL_INTERFACE_VERSION = "epoch-tools-v1"
TOOL_VERSION = "sandbox-v1"
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
IdempotencyKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class NoArguments(Arguments):
    pass


class CreateTicket(Arguments):
    title: Title
    release: ShortText
    idempotency_key: IdempotencyKey


class CreateChecklist(Arguments):
    ticket_id: Title
    title: Title
    items: list[Text] = Field(min_length=1, max_length=50)
    idempotency_key: IdempotencyKey


class SendMessage(Arguments):
    channel: ShortText
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]
    links: list[Text] = Field(min_length=1, max_length=20)
    idempotency_key: IdempotencyKey


class ReadRunbook(Arguments):
    purpose: Literal["current", "historical"] = "current"
    version: Literal["v1", "v2"] | None = None


class SimulatedObject(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    id: str
    project_id: str
    simulated: Literal[True]
    url: Annotated[str, StringConstraints(pattern=r"^simulated://")]


class TicketResult(SimulatedObject):
    title: str
    release: str


class ChecklistResult(SimulatedObject):
    ticket_id: str
    title: str
    items: list[str]


class MessageResult(SimulatedObject):
    channel: str
    text: str
    links: list[str]


class RunbookResult(SimulatedObject):
    document_id: str
    version: str
    is_current: bool
    content: str
    scope: str
    selection_rule_version: str
    requested_purpose: str


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    arguments: type[Arguments]
    operation: str
    read_only: bool


_TOOLS = (
    ToolDefinition(
        "tickets.create",
        "Create a simulated release ticket in the current project. Reuse its idempotency "
        "key only when retrying identical content.",
        CreateTicket,
        "create_ticket",
        False,
    ),
    ToolDefinition(
        "tickets.list",
        "List simulated tickets in the current run and project.",
        NoArguments,
        "list_tickets",
        True,
    ),
    ToolDefinition(
        "checklists.create",
        "Create a simulated checklist linked to a ticket in the current run. Supply "
        "the ticket's id, checklist title, checklist items and a stable idempotency key.",
        CreateChecklist,
        "create_checklist",
        False,
    ),
    ToolDefinition(
        "checklists.list",
        "List simulated checklists in the current run and project.",
        NoArguments,
        "list_checklists",
        True,
    ),
    ToolDefinition(
        "messages.send",
        "Send a simulated message to the supplied channel with links to existing "
        "objects in the current run. Reuse an idempotency key only for identical retries.",
        SendMessage,
        "send_message",
        False,
    ),
    ToolDefinition(
        "messages.list",
        "List simulated messages in the current run and project.",
        NoArguments,
        "list_messages",
        True,
    ),
    ToolDefinition(
        "runbooks.read",
        "Read a simulated project runbook. For current work use purpose=current; "
        "a version can be requested explicitly. Inspect the returned document version "
        "and current/historical status before using its guidance.",
        ReadRunbook,
        "read_runbook",
        True,
    ),
)
_TOOL_BY_NAME = {tool.name: tool for tool in _TOOLS}
_OUTPUTS = {
    "tickets.create": TypeAdapter(TicketResult),
    "tickets.list": TypeAdapter(list[TicketResult]),
    "checklists.create": TypeAdapter(ChecklistResult),
    "checklists.list": TypeAdapter(list[ChecklistResult]),
    "messages.send": TypeAdapter(MessageResult),
    "messages.list": TypeAdapter(list[MessageResult]),
    "runbooks.read": TypeAdapter(RunbookResult),
}


def _safe_arguments(value: Any) -> Any:
    """Keep arbitrary invalid tool input from writing obvious credentials to traces."""
    if isinstance(value, dict):
        return {
            str(key): "[redacted]"
            if any(
                token in str(key).lower()
                for token in ("secret", "password", "token", "api_key", "authorization")
            )
            else _safe_arguments(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_arguments(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return "[non-JSON value]"


class ToolRegistry:
    """A fixed facade over permission-filtered operations in one initialized sandbox."""

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        # Assert initialization and identity before exposing any capability.
        sandbox.metadata()

    def _visible(self, tool: ToolDefinition) -> bool:
        return tool.name in self.sandbox.metadata()["grants"]

    def _error(self, code: str, message: str, **event: Any) -> dict[str, Any]:
        error = {"code": code, "message": message}
        self.sandbox.record_event("tool.error", {**event, "error": error})
        return {"ok": False, "error": error}

    @staticmethod
    def _summary(tool: ToolDefinition) -> dict[str, Any]:
        return {
            "name": tool.name,
            "description": tool.description,
            "version": TOOL_VERSION,
            "simulated": True,
            "read_only": tool.read_only,
            "required_permission": tool.name,
        }

    def discover_tools(self) -> dict[str, Any]:
        metadata = self.sandbox.metadata()
        tools = [self._summary(tool) for tool in _TOOLS if self._visible(tool)]
        result = {
            "interface_version": TOOL_INTERFACE_VERSION,
            "project_id": metadata["project_id"],
            "simulated": True,
            "tools": tools,
        }
        self.sandbox.record_event("tool.discovery", {"result": result})
        return {"ok": True, "result": result}

    def describe_tool(self, name: str) -> dict[str, Any]:
        tool = _TOOL_BY_NAME.get(name) if isinstance(name, str) else None
        if tool is None:
            return self._error(
                "tool_not_found", "The requested tool is not available.", tool_name=name
            )
        if not self._visible(tool):
            return self._error(
                "access_denied", "This run is not permitted to use this tool.", tool_name=name
            )
        result = {
            **self._summary(tool),
            "input_schema": tool.arguments.model_json_schema(),
            "output_schema": _OUTPUTS[name].json_schema(),
        }
        self.sandbox.record_event("tool.described", {"tool_name": name, "result": result})
        return {"ok": True, "result": result}

    def invoke_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        call_id = str(uuid4())
        correlation = {"call_id": call_id, "tool_name": name, "tool_version": TOOL_VERSION}
        self.sandbox.record_event(
            "tool.called", {**correlation, "arguments": _safe_arguments(arguments)}
        )
        tool = _TOOL_BY_NAME.get(name) if isinstance(name, str) else None
        if tool is None:
            return self._error(
                "tool_not_found", "The requested tool is not available.", **correlation
            )
        if not self._visible(tool):
            return self._error(
                "access_denied", "This run is not permitted to use this tool.", **correlation
            )
        try:
            validated = tool.arguments.model_validate(arguments)
        except ValidationError as exc:
            # Locations and error categories explain the failure without echoing secret input.
            problems = "; ".join(
                f"{'.'.join(str(part) for part in error['loc']) or 'arguments'}: {error['type']}"
                for error in exc.errors(include_input=False, include_url=False)
            )
            return self._error("invalid_arguments", problems, **correlation)

        operation: Callable[..., Any] = getattr(self.sandbox, tool.operation)
        try:
            result = operation(**validated.model_dump())
        except SandboxError as exc:
            return self._error(exc.code, exc.message, **correlation)
        except Exception:
            # Preserve a missing-result observation without disclosing process internals.
            return self._error(
                "tool_execution_failed", "The tool did not produce a valid result.", **correlation
            )
        try:
            _OUTPUTS[name].validate_python(result, strict=True)
        except ValidationError:
            return self._error(
                "invalid_tool_result",
                "The tool result did not match its output schema.",
                **correlation,
            )
        self.sandbox.record_event("tool.result", {**correlation, "result": result})
        if name == "runbooks.read":
            self.sandbox.record_event(
                "context.supplied",
                {**correlation, "source": result, "requested": validated.model_dump()},
            )
        return {"ok": True, "result": result}


def facade_identity() -> dict[str, Any]:
    """Stable public contracts for the host's executor baseline fingerprint."""
    return {
        "interface_version": TOOL_INTERFACE_VERSION,
        "facade": ["discover_tools", "describe_tool", "invoke_tool"],
        "tools": [
            {
                **ToolRegistry._summary(tool),
                "input_schema": tool.arguments.model_json_schema(),
                "output_schema": _OUTPUTS[tool.name].json_schema(),
            }
            for tool in _TOOLS
        ],
    }
