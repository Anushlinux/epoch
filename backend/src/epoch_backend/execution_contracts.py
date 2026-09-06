"""Direct execution and opt-in Phase 4 supervision records."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from epoch_backend.contracts import Contract, TaskBrief
from epoch_backend.supervision_contracts import OperationStatus, SupervisionState

Scenario = Literal["control", "broken_checklist", "missing_lookup", "outdated_context"]


class StoredReleaseRunRequest(Contract):
    """Keep previously accepted Phase 3 limits readable in historical records."""

    client_request_id: UUID
    workflow: Literal["release"]
    release: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    scenario: Scenario = "control"
    max_turns: int = Field(default=20, ge=1, le=30)
    timeout_seconds: int = Field(default=600, ge=10, le=600)
    supervised: bool = False
    demo_omit_notification: bool = False


class ReleaseRunRequest(StoredReleaseRunRequest):
    max_turns: int = Field(default=20, ge=1, le=20, strict=True)
    timeout_seconds: int = Field(default=600, ge=10, le=600, strict=True)

    @model_validator(mode="after")
    def require_supervised_demo(self):
        if self.demo_omit_notification and not self.supervised:
            raise ValueError("The omission demonstration requires supervised execution")
        return self


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
    request: StoredReleaseRunRequest
    status: OperationStatus
    brief: TaskBrief
    created_at: AwareDatetime
    updated_at: AwareDatetime
    final_response: str | None = None
    executor_success: bool | None = None
    baseline: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] | None = None
    missing_evidence: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    supervision: SupervisionState | None = None


class RuntimeInfo(Contract):
    phase: Literal[4] = 4
    execution_enabled: bool
    hermes_available: bool
    active_run_id: UUID | None = None
    workflow: Literal["release"] = "release"
    simulation_only: Literal[True] = True
    automatic_supervision: Literal[True] = True
    automatic_repair: Literal[False] = False
    installation: dict[str, Any] = Field(default_factory=dict)
    debugger: dict[str, Any] = Field(default_factory=dict)
    supervision_enabled: bool = False
    max_agent_turns: Literal[20] = 20
    max_operation_seconds: Literal[600] = 600
