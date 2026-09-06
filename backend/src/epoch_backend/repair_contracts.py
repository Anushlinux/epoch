"""Host-owned repair limits and the only accepted generated artifact contract."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from epoch_backend.contracts import Contract


class RepairProposal(Contract):
    outcome: Literal["repair", "unsupported"]
    diagnosis: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=10)
    target: Literal["checklist_serializer.py"]
    source: str = Field(max_length=20_000)
    uncertainty: str = Field(max_length=2000)


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
