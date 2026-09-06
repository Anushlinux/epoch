"""Additive incident interfaces. Imported evidence never grants execution authority."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints, field_validator

from epoch_backend.contracts import Contract

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class NormalizedEvidence(Contract):
    source_type: Literal["epoch", "trace", "slack", "support"]
    source_id: Key
    timestamp: AwareDatetime
    project_id: Key
    text: Text
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    run_id: str | None = None
    revision_id: str | None = None
    workflow: str | None = None
    tool: str | None = None
    error_code: str | None = None
    check_id: str | None = None
    environment_version: str | None = None
    source_ref: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    native_event_id: str | None = None

    @field_validator("structured_payload")
    @classmethod
    def bound_payload(cls, value):
        import json

        if len(json.dumps(value)) > 32000:
            raise ValueError("Evidence payload exceeds 32000 characters")
        return value


class ExternalRecord(Contract):
    source_type: Literal["slack", "support"]
    source_id: Key
    timestamp: AwareDatetime
    project_id: Key
    text: Text
    source_ref: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    workflow: str | None = None


class EvidenceImport(Contract):
    client_request_id: UUID
    records: list[ExternalRecord] = Field(min_length=1, max_length=200)


class IncidentAction(Contract):
    client_request_id: UUID
    question: Text | None = None


class IncidentAnswer(Contract):
    answer: str = Field(min_length=1, max_length=8000)
    evidence_ids: list[UUID] = Field(max_length=24)
    hypotheses: list[str] = Field(max_length=10)
    missing_evidence: list[str] = Field(max_length=10)
