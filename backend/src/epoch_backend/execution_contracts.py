"""Actual Phase 3 execution records; automatic planning belongs to Phase 4."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints

from epoch_backend.contracts import Contract, TaskBrief

Scenario = Literal["control", "broken_checklist", "missing_lookup", "outdated_context"]


class ReleaseRunRequest(Contract):
    client_request_id: UUID
    workflow: Literal["release"]
    release: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    scenario: Scenario = "control"
    max_turns: int = Field(default=16, ge=1, le=30)
    timeout_seconds: int = Field(default=180, ge=10, le=300)


class RunEvent(Contract):
    id: UUID
    task_id: UUID
    run_id: UUID
    sequence: int = Field(gt=0)
    type: str
    payload: dict[str, Any]
    emitted_at: AwareDatetime


class ExecutionRecord(Contract):
    schema_version: Literal[1] = 1
    id: UUID
    task_id: UUID
    request: ReleaseRunRequest
    status: Literal["running", "verifying", "completed", "failed", "cancelled", "interrupted"]
    brief: TaskBrief
    created_at: AwareDatetime
    updated_at: AwareDatetime
    final_response: str | None = None
    executor_success: bool | None = None
    baseline: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] | None = None
    missing_evidence: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None


class RuntimeInfo(Contract):
    phase: Literal[3] = 3
    execution_enabled: bool
    hermes_available: bool
    active_run_id: UUID | None = None
    workflow: Literal["release"] = "release"
    simulation_only: Literal[True] = True
    automatic_supervision: Literal[False] = False
    automatic_repair: Literal[False] = False
    installation: dict[str, Any] = Field(default_factory=dict)
