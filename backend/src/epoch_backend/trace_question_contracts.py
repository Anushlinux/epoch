"""Local question contracts. References are checked; model conclusions are not verdicts."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Statement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)]
EvidenceId = Annotated[str, StringConstraints(pattern=r"^E[1-9][0-9]*$")]


class QuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_request_id: UUID
    question: QuestionText
    span_id: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{16}$")] | None = None


class CitedStatement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Statement
    evidence_ids: list[EvidenceId] = Field(min_length=1, max_length=6)


class TraceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: list[CitedStatement] = Field(max_length=8)
    hypotheses: list[CitedStatement] = Field(max_length=4)
    missing_evidence: list[Statement] = Field(max_length=8)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.answer and not self.hypotheses and not self.missing_evidence:
            raise ValueError("An answer must state findings or explain missing evidence")
        return self


class TraceQuestion(BaseModel):
    id: str
    trace_id: str
    question: str
    span_id: str | None
    state: Literal["running", "answered", "failed"]
    created_at: str
    completed_at: str | None
    model: str
    ollama_base_url: str
    snapshot: dict
    answer: TraceAnswer | None
    error: dict | None
    usage: dict | None
    prompt_version: str


class QuestionList(BaseModel):
    items: list[TraceQuestion]
    total: int
    limit: int
    offset: int
