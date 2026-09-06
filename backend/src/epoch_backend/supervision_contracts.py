"""Structured debugger output and durable, user-visible supervision history."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints

from epoch_backend.contracts import Contract, IntentRevision, SupervisorIntervention, TaskBrief

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
OperationStatus = Literal[
    "planning",
    "running",
    "verifying",
    "repairing",
    "completed",
    "needs_input",
    "blocked",
    "failed",
    "cancelled",
    "interrupted",
]


class SourcedRequirement(Contract):
    value: ShortText
    source_quote: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]


class PlannedCheckpoint(Contract):
    kind: Literal["release_ticket", "release_checklist", "qa_notification", "qa_owner"]
    description: ShortText
    source_quote: str = Field(max_length=1000)


class SupervisorPlan(Contract):
    outcome: Literal["ready", "needs_input", "unsupported"]
    summary: Text
    instructions: Text
    checkpoints: list[PlannedCheckpoint] = Field(max_length=4)
    additional_checklist_items: list[SourcedRequirement] = Field(max_length=20)
    required_message_phrases: list[SourcedRequirement] = Field(max_length=20)
    classification: Literal["omitted_requirement", "evaluation_mistake", "new_preference"]
    questions: list[ShortText] = Field(max_length=5)


class SupervisorDecision(Contract):
    action: Literal["continue", "needs_input", "environment_defect"]
    reason: Text
    instruction: str = Field(max_length=16000)
    questions: list[ShortText] = Field(max_length=5)


class FeedbackRequest(Contract):
    client_request_id: UUID
    expected_revision_id: UUID
    message: Text
    max_turns: int = Field(default=20, ge=1, le=20, strict=True)
    timeout_seconds: int = Field(default=600, ge=10, le=600, strict=True)


class SupervisionOperation(Contract):
    id: UUID
    client_request_id: UUID
    previous_revision_id: UUID | None = None
    trigger: Literal["initial", "feedback", "clarification"]
    user_input: Text
    request: dict[str, Any]
    status: OperationStatus = "planning"
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None
    max_turns: int = Field(ge=1, le=20)
    timeout_seconds: int = Field(ge=10, le=600)
    turns_used: int = Field(default=0, ge=0, le=20)
    debugger_turns: int = Field(default=0, ge=0)
    executor_turns: int = Field(default=0, ge=0)
    plan: SupervisorPlan | None = None
    brief: TaskBrief | None = None
    intent_revision: IntentRevision | None = None
    questions: list[str] = Field(default_factory=list)
    criteria_before: dict[str, Any] = Field(default_factory=dict)
    criteria_after: dict[str, Any] = Field(default_factory=dict)
    state_before: dict[str, Any] = Field(default_factory=dict)
    state_after: dict[str, Any] = Field(default_factory=dict)
    verification_before: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    final_response: str | None = None
    error: dict[str, Any] | None = None
    debugger_calls: list[dict[str, Any]] = Field(default_factory=list)
    executor_passes: list[dict[str, Any]] = Field(default_factory=list)
    interventions: list[SupervisorIntervention] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    repairs: list[dict[str, Any]] = Field(default_factory=list)
    repair_budget: dict[str, Any] | None = None


class SupervisionState(Contract):
    debugger_model: Literal["gpt-5.6-luna"] = "gpt-5.6-luna"
    current_revision_id: UUID
    operations: list[SupervisionOperation]
