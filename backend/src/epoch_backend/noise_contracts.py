"""Host-owned policy contracts; local model findings cannot authorize activation."""

from copy import deepcopy
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
TraceID = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]
Rule = Literal["deduplicate", "prefer_current_approved", "match_topic"]
Case = Literal["original", "fresh", "unaffected", "historical"]
NOISE_SCHEMA_VERSION = "noise-outcome-rules-v1"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Analyze(Strict):
    client_request_id: UUID
    trace_id: TraceID
    issue: Text


class Finding(Strict):
    kind: Literal["duplicate", "stale", "irrelevant", "conflict", "tool_defect", "unknown"]
    explanation: Text
    evidence_ids: list[str] = Field(min_length=1, max_length=12)
    confidence: Literal["low", "medium", "high"]


class NoiseAnswer(Strict):
    outcome: Literal["context_noise", "tool_defect", "insufficient_evidence", "no_issue"]
    summary: Text
    relevant_evidence_ids: list[str] = Field(min_length=1, max_length=12)
    findings: list[Finding] = Field(max_length=10)
    rules: list[Rule] = Field(max_length=3)
    missing_evidence: list[Text] = Field(max_length=8)


def noise_response_schema(schema):
    """Constrain outcome/rules together without changing the saved answer shape.

    Use complete alternatives: an if/then annotation alone is not reliably enforced
    by grammar converters. Keep shared definitions at the root so existing refs resolve.
    The flat Pydantic contract and the service's cross-field check remain authoritative.
    """
    common = deepcopy(schema)
    definitions = common.pop("$defs", {})
    context_noise = deepcopy(common)
    context_noise["properties"]["outcome"]["enum"] = ["context_noise"]
    other = deepcopy(common)
    other["properties"]["outcome"]["enum"] = [
        outcome for outcome in common["properties"]["outcome"]["enum"] if outcome != "context_noise"
    ]
    # A literal [] avoids an empty-array repetition rule in the local grammar engine.
    other["properties"]["rules"] = {"type": "array", "const": []}
    return {"$defs": definitions, "anyOf": [context_noise, other]}


class Draft(Strict):
    client_request_id: UUID
    analysis_id: UUID
    title: Label
    rules: list[Rule] = Field(min_length=1, max_length=3)


class SourceLabels(Strict):
    family: str = Field(default="", max_length=120)
    version: str = Field(default="", max_length=120)
    status: Literal["unknown", "current", "superseded"] = "unknown"
    approved: bool = False
    topics: list[Label] = Field(default_factory=list, max_length=12)
    protected: bool = False


class LabelSource(Strict):
    client_request_id: UUID
    expected_revision: int = Field(ge=0)
    source_id: str = Field(min_length=1, max_length=300)
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    labels: SourceLabels


class Preview(Strict):
    client_request_id: UUID
    case: Case = "original"
    purpose: Literal["current", "historical", "all"] = "current"
    version: Label | None = None
    topic: Label | None = None
    required_ids: list[str] = Field(default_factory=list, max_length=200)


class Validation(Strict):
    client_request_id: UUID
    preview_id: UUID
    trace_id: TraceID
    passed: bool
    notes: Text


class Activate(Strict):
    client_request_id: UUID
    expected_revision: int = Field(ge=0)
    validation_ids: list[UUID] = Field(min_length=4, max_length=4)


class Rollback(Strict):
    client_request_id: UUID
    expected_revision: int = Field(ge=0)
    activation_id: UUID
