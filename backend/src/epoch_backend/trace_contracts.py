"""Read-only trace explorer contracts; no execution or investigation authority."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class TraceSpanSummary(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: str
    otlp_kind: int
    project_id: str
    workflow: str | None = None
    session_id: str | None = None
    start_time: str
    end_time: str
    duration_ms: float
    status: Literal["recorded_error", "no_recorded_error"]
    status_code: int
    tool: str | None = None
    model: str | None = None
    has_input: bool
    has_output: bool
    parent_missing: bool = False
    source_ref: str


class TraceSpan(TraceSpanSummary):
    input: Any = None
    output: Any = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    resource_attributes: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    links: list[dict[str, Any]] = Field(default_factory=list)
    status_message: str = ""
    start_time_unix_nano: str
    end_time_unix_nano: str
    warnings: list[str] = Field(default_factory=list)


class TraceSummary(BaseModel):
    trace_id: str
    name: str
    project_ids: list[str]
    workflows: list[str]
    session_ids: list[str]
    start_time: str
    end_time: str
    duration_ms: float
    span_count: int
    error_count: int
    missing_parent_count: int
    root_count: int
    status: Literal["recorded_error", "no_recorded_error"]


class TraceList(BaseModel):
    items: list[TraceSummary]
    total: int
    limit: int
    offset: int
    warnings: list[str]


class TraceDetail(BaseModel):
    trace: TraceSummary
    spans: list[TraceSpanSummary]
    total: int
    limit: int
    offset: int
    warnings: list[str]
