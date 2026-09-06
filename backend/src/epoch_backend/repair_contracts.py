"""Host-owned repair limits and the only accepted generated artifact contract."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from epoch_backend.contracts import Contract


class GeneratedToolContract(Contract):
    name: Literal["directory.lookup_qa_owner"]
    description: str = Field(min_length=1, max_length=1500)
    input_schema_json: str = Field(min_length=2, max_length=12000)
    output_schema_json: str = Field(min_length=2, max_length=12000)


class RepairProposal(Contract):
    outcome: Literal["repair", "unsupported"]
    diagnosis: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=10)
    target: Literal["checklist_serializer.py", "qa_lookup.py", "runbook_selector.py"]
    source: str = Field(max_length=20_000)
    uncertainty: str = Field(max_length=2000)
    tool_contract: GeneratedToolContract | None = None


class RollbackRequest(Contract):
    client_request_id: UUID
    expected_version: UUID


class RepairLimits(Contract):
    max_attempts: Literal[2] = 2
    max_model_requests: Literal[60] = 60
    max_wall_seconds: Literal[1800] = 1800
    verification_max_turns: Literal[20] = 20
    verification_max_seconds: Literal[600] = 600
    inference_cost_unit: Literal["authorized_model_request"] = "authorized_model_request"
    guaranteed_usd_cap: None = None
