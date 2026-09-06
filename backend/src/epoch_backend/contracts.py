"""Versioned records. Future-phase records describe data, not execution authority."""

from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(Contract):
    client_request_id: UUID
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16_000)
    ]
    project_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ] = "demo"


class TaskStatus(StrEnum):
    pending = "pending"
    planning = "planning"
    awaiting_clarification = "awaiting_clarification"
    running = "running"
    verifying = "verifying"
    repairing = "repairing"
    completed = "completed"
    blocked = "blocked"
    failed = "failed"
    cancelled = "cancelled"


class Task(Contract):
    schema_version: Literal[1] = 1
    id: UUID
    request: TaskCreate
    status: TaskStatus = TaskStatus.pending
    created_at: AwareDatetime
    updated_at: AwareDatetime


class TaskList(Contract):
    items: list[Task]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    phase: Literal[1] = 1
    storage: Literal["ok"] = "ok"
    execution_enabled: Literal[False] = False


class ErrorDetail(Contract):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorEnvelope(Contract):
    error: ErrorDetail


class SourceReference(Contract):
    id: UUID
    kind: Literal["user_request", "user_feedback", "document", "tool_contract"]
    locator: NonBlank
    version: str | None = None
    attribution: Literal["explicit", "inferred"]
    excerpt: str | None = None


class Evidence(Contract):
    schema_version: Literal[1] = 1
    id: UUID
    task_id: UUID
    run_id: UUID | None = None
    category: Literal[
        "local_component", "simulation", "hermes", "tracing_integration", "live_provider"
    ]
    kind: Literal["tool_call", "tool_result", "state_observation", "artifact", "check"]
    uri: NonBlank
    sha256: Digest
    captured_at: AwareDatetime
    summary: NonBlank


class Checkpoint(Contract):
    id: UUID
    description: NonBlank
    source_refs: list[SourceReference] = Field(min_length=1)
    depends_on: list[UUID] = Field(default_factory=list)
    scope: NonBlank
    verification_rule: NonBlank
    evaluator_version: NonBlank
    status: Literal["pending", "verified", "failed", "blocked"] = "pending"
    evidence_refs: list[UUID] = Field(default_factory=list)
    uncertainty: str | None = None

    @model_validator(mode="after")
    def require_evidence_for_verified(self) -> "Checkpoint":
        if self.status == "verified" and not self.evidence_refs:
            raise ValueError("A verified checkpoint requires evidence references")
        if self.id in self.depends_on:
            raise ValueError("A checkpoint cannot depend on itself")
        return self


class TaskBrief(Contract):
    schema_version: Literal[1] = 1
    id: UUID
    task_id: UUID
    intent_revision_id: UUID | None = None
    instructions: NonBlank
    checkpoints: list[Checkpoint] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    clarification_requests: list[str] = Field(default_factory=list)
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_dependencies(self) -> "TaskBrief":
        checkpoint_ids = {checkpoint.id for checkpoint in self.checkpoints}
        if len(checkpoint_ids) != len(self.checkpoints):
            raise ValueError("Checkpoint IDs must be unique within a brief")
        remaining = {item.id: set(item.depends_on) for item in self.checkpoints}
        if any(not deps <= checkpoint_ids for deps in remaining.values()):
            raise ValueError("Checkpoint dependencies must belong to the same brief")
        while remaining:
            ready = {item_id for item_id, deps in remaining.items() if not deps}
            if not ready:
                raise ValueError("Checkpoint dependencies must not contain a cycle")
            remaining = {
                item_id: deps - ready for item_id, deps in remaining.items() if item_id not in ready
            }
        return self


class Clarification(Contract):
    id: UUID
    task_id: UUID
    question: NonBlank
    source_refs: list[SourceReference] = Field(min_length=1)
    response: NonBlank | None = None
    created_at: AwareDatetime
    answered_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def require_answer_pair(self) -> "Clarification":
        if (self.response is None) != (self.answered_at is None):
            raise ValueError("A clarification response and answered_at must be supplied together")
        return self


class UserFeedback(Contract):
    id: UUID
    task_id: UUID
    message: NonBlank
    run_id: UUID | None = None
    classification: Literal[
        "omitted_requirement", "evaluation_mistake", "new_preference", "unclassified"
    ] = "unclassified"
    created_at: AwareDatetime


class IntentRevision(Contract):
    id: UUID
    task_id: UUID
    previous_revision_id: UUID | None = None
    feedback_id: UUID | None = None
    feedback: NonBlank
    reason: Literal["omitted_requirement", "evaluation_mistake", "new_preference"]
    source_refs: list[SourceReference] = Field(min_length=1)
    retained_evidence_refs: list[UUID] = Field(default_factory=list)
    created_at: AwareDatetime


class SupervisorIntervention(Contract):
    id: UUID
    task_id: UUID
    run_id: UUID
    checkpoint_refs: list[UUID] = Field(min_length=1)
    instruction: NonBlank
    reason: NonBlank
    evidence_refs: list[UUID] = Field(default_factory=list)
    created_at: AwareDatetime


class PermissionScope(Contract):
    project_id: NonBlank
    readable_paths: list[str] = Field(default_factory=list)
    writable_paths: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(default_factory=list)
    service_grants: list[str] = Field(default_factory=list)


class ToolVersion(Contract):
    name: NonBlank
    version: NonBlank
    artifact_sha256: Digest


class ToolContract(Contract):
    tool: ToolVersion
    description: NonBlank
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permissions: PermissionScope
    side_effects: list[str] = Field(default_factory=list)
    retry_behavior: NonBlank
    idempotency_key_supported: bool = False


class ToolInvocation(Contract):
    id: UUID
    task_id: UUID
    run_id: UUID
    tool: ToolVersion
    environment_version_id: UUID
    permissions: PermissionScope
    arguments: dict[str, Any]
    idempotency_key: str | None = None
    status: Literal["started", "succeeded", "failed", "uncertain"]
    result: dict[str, Any] | None = None
    error: ErrorDetail | None = None
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    evidence_refs: list[UUID] = Field(default_factory=list)


class ContextInput(Contract):
    id: UUID
    task_id: UUID
    run_id: UUID
    content: str
    sources: list[SourceReference]
    selection_rule_version: NonBlank
    scope: PermissionScope
    captured_at: AwareDatetime


class ExecutorBaseline(Contract):
    implementation_sha256: Digest
    system_prompt_sha256: Digest
    model_configuration_sha256: Digest
    discovery_interface_sha256: Digest
    evaluator_sha256: Digest
    permission_grants_sha256: Digest


class Run(Contract):
    schema_version: Literal[1] = 1
    id: UUID
    task_id: UUID
    brief_id: UUID
    intent_revision_id: UUID | None = None
    environment_version_id: UUID
    executor_baseline: ExecutorBaseline
    visible_tools: list[ToolVersion]
    context_refs: list[UUID] = Field(default_factory=list)
    invocation_refs: list[UUID] = Field(default_factory=list)
    evidence_refs: list[UUID] = Field(default_factory=list)
    intervention_refs: list[UUID] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    status: Literal["pending", "running", "completed", "blocked", "failed", "cancelled"]
    final_response: str | None = None
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None


class RepairLimits(Contract):
    max_attempts: int = Field(gt=0)
    max_seconds: int = Field(gt=0)
    max_cost_usd: float = Field(ge=0, allow_inf_nan=False)


class RepairCandidate(Contract):
    id: UUID
    task_id: UUID
    baseline_environment_version_id: UUID
    kind: Literal["tool_repair", "missing_tool", "context_repair"]
    artifact_uri: NonBlank
    artifact_sha256: Digest
    diff: NonBlank
    permissions: PermissionScope
    limits: RepairLimits
    created_at: AwareDatetime


class VerificationResult(Contract):
    id: UUID
    candidate_id: UUID
    artifact_sha256: Digest
    baseline_sha256: Digest
    category: Literal["component", "original_task", "fresh_task", "regression", "isolation"]
    status: Literal["passed", "failed", "missing"]
    verifier_version: NonBlank
    evidence_refs: list[UUID] = Field(default_factory=list)
    notes: str | None = None
    completed_at: AwareDatetime


class VersionTransition(Contract):
    id: UUID
    action: Literal["publish", "rollback"]
    from_version_id: UUID | None = None
    to_version_id: UUID
    reason: NonBlank
    recorded_at: AwareDatetime


class EnvironmentVersion(Contract):
    schema_version: Literal[1] = 1
    id: UUID
    previous_version_id: UUID | None = None
    candidate_id: UUID | None = None
    manifest_sha256: Digest
    tools: list[ToolVersion] = Field(default_factory=list)
    context_rule_version: NonBlank
    status: Literal["staged", "active", "superseded", "rolled_back"]
    verification_refs: list[UUID] = Field(default_factory=list)
    history: list[VersionTransition] = Field(default_factory=list)
    created_at: AwareDatetime


class RepairAttempt(Contract):
    candidate_id: UUID
    number: int = Field(gt=0)
    decision: Literal["pending", "rejected", "published"]
    verification_refs: list[UUID] = Field(default_factory=list)
    reason: NonBlank


class RepairRecord(Contract):
    id: UUID
    task_id: UUID
    run_id: UUID
    checkpoint_refs: list[UUID]
    trigger: NonBlank
    diagnosis: NonBlank
    uncertainty: list[str] = Field(default_factory=list)
    evidence_refs: list[UUID] = Field(default_factory=list)
    attempts: list[RepairAttempt] = Field(default_factory=list)
    resulting_environment_version_id: UUID | None = None
    created_at: AwareDatetime


class ProgressEvent(Contract):
    """Future SSE envelope; Phase 1 never emits execution events."""

    schema_version: Literal[1] = 1
    id: UUID
    task_id: UUID
    run_id: UUID | None = None
    sequence: int = Field(gt=0)
    type: Literal[
        "task.created",
        "task.status_changed",
        "brief.created",
        "checkpoint.updated",
        "run.updated",
        "repair.updated",
        "intent.revised",
        "error",
    ]
    emitted_at: AwareDatetime
    payload: Task | TaskBrief | Checkpoint | Run | RepairRecord | IntentRevision | ErrorEnvelope

    @model_validator(mode="after")
    def validate_payload_kind(self) -> "ProgressEvent":
        expected = {
            "task.created": Task,
            "task.status_changed": Task,
            "brief.created": TaskBrief,
            "checkpoint.updated": Checkpoint,
            "run.updated": Run,
            "repair.updated": RepairRecord,
            "intent.revised": IntentRevision,
            "error": ErrorEnvelope,
        }
        if not isinstance(self.payload, expected[self.type]):
            raise ValueError("Event payload must match its type")
        payload_task_id = getattr(self.payload, "task_id", None)
        if isinstance(self.payload, Task):
            payload_task_id = self.payload.id
        if payload_task_id is not None and payload_task_id != self.task_id:
            raise ValueError("Event task_id must match its payload")
        return self
