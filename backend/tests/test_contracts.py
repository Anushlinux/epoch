import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from epoch_backend import contracts as c

BACKEND = Path(__file__).resolve().parents[1]


def request(**overrides):
    return {"client_request_id": str(UUID(int=1)), "message": "Write a checklist", **overrides}


def test_request_normalizes_outer_whitespace_and_rejects_unknown_fields():
    parsed = c.TaskCreate(**request(message="  Write a checklist  ", project_id=" demo "))
    assert parsed.message == "Write a checklist"
    assert parsed.project_id == "demo"
    with pytest.raises(ValidationError, match="Extra inputs"):
        c.TaskCreate(**request(skip_verification=True))


@pytest.mark.parametrize("message", ["", " \n ", "x" * 16_001])
def test_request_rejects_empty_or_oversized_message(message):
    with pytest.raises(ValidationError):
        c.TaskCreate(**request(message=message))


def test_task_rejects_naive_timestamps():
    with pytest.raises(ValidationError, match="timezone"):
        c.Task(
            id=UUID(int=2),
            request=c.TaskCreate(**request()),
            created_at="2026-09-06T10:00:00",
            updated_at="2026-09-06T10:00:00Z",
        )


def checkpoint(**overrides):
    return {
        "id": str(UUID(int=5)),
        "description": "Checklist exists",
        "source_refs": [
            {
                "id": str(UUID(int=3)),
                "kind": "user_request",
                "locator": "task:fixture",
                "attribution": "explicit",
            }
        ],
        "scope": "demo",
        "verification_rule": "Artifact exists",
        "evaluator_version": "v1",
        **overrides,
    }


def test_verified_checkpoint_needs_provenance_and_evidence():
    with pytest.raises(ValidationError, match="requires evidence"):
        c.Checkpoint(**checkpoint(status="verified"))
    with pytest.raises(ValidationError):
        c.Checkpoint(**checkpoint(source_refs=[]))
    result = c.Checkpoint(**checkpoint(status="verified", evidence_refs=[UUID(int=4)]))
    assert result.status == "verified"


def test_brief_rejects_dependency_cycles():
    first = c.Checkpoint(**checkpoint(depends_on=[UUID(int=6)]))
    second = c.Checkpoint(**checkpoint(id=UUID(int=6), depends_on=[first.id]))
    with pytest.raises(ValidationError, match="cycle"):
        c.TaskBrief(
            id=UUID(int=7),
            task_id=UUID(int=2),
            instructions="Create checklist",
            checkpoints=[first, second],
            created_at="2026-09-06T10:00:00Z",
        )


def test_progress_event_rejects_payload_type_mismatch():
    with pytest.raises(ValidationError, match="payload must match"):
        c.ProgressEvent(
            id=UUID(int=9),
            task_id=UUID(int=2),
            sequence=1,
            type="run.updated",
            emitted_at="2026-09-06T10:00:00Z",
            payload=c.Checkpoint(**checkpoint()),
        )


def test_fixture_examples_are_labelled_and_validate():
    document = json.loads((BACKEND / "fixtures" / "development.json").read_text("utf-8"))
    assert document["fixture_only"] is True
    assert len(document["examples"]) >= 10
    for example in document["examples"]:
        model = getattr(c, example["model"])
        model.model_validate(example["value"])


def test_exported_schemas_match_python_models():
    document = json.loads((BACKEND / "contracts" / "schemas.json").read_text("utf-8"))
    expected = {
        name: value.model_json_schema()
        for name, value in vars(c).items()
        if isinstance(value, type) and issubclass(value, c.Contract) and value is not c.Contract
    }
    assert document["models"] == expected
