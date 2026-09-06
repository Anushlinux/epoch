"""Editable business adapters, kept separate from trusted outcome criteria.

The legacy checklist serializer intentionally reproduces a real wire-contract
defect: JSON-encoding an array before passing it to a service expecting an array.
It does not manufacture an exception or create a hidden successful effect.
"""

import json

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError


class ChecklistPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ticket_id: StrictStr = Field(min_length=1)
    title: StrictStr = Field(min_length=1, max_length=300)
    items: list[StrictStr] = Field(min_length=1, max_length=50)


class AdapterContractError(ValueError):
    """The simulated service rejected the actual adapter payload."""


def serialize_checklist(
    ticket_id: str, title: str, items: list[str], *, legacy: bool = False
) -> dict:
    return {
        "ticket_id": ticket_id,
        "title": title,
        "items": json.dumps(items) if legacy else items,
    }


def validate_checklist_payload(payload: dict) -> dict:
    try:
        validated = ChecklistPayload.model_validate(payload)
    except ValidationError as error:
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        raise AdapterContractError(
            "Checklist service rejected payload fields: "
            + ", ".join(fields)
            + ". Expected items to be a nonempty array of strings."
        ) from error
    if any(not item.strip() for item in validated.items):
        raise AdapterContractError("Checklist service requires nonblank checklist items.")
    return validated.model_dump()
