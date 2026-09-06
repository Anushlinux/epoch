"""Export deterministic schemas and fixture-only UI examples; --check detects drift."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from epoch_backend import contracts as c

BACKEND = Path(__file__).resolve().parents[1]
STAMP = "2026-09-06T10:00:00Z"


def uid(value: int) -> str:
    return str(UUID(int=value))


def models() -> dict[str, type[c.Contract]]:
    return {
        name: value
        for name, value in vars(c).items()
        if isinstance(value, type) and issubclass(value, c.Contract) and value is not c.Contract
    }


def fixture_examples() -> list[dict]:
    request = c.TaskCreate(client_request_id=uid(1), message="Draft a release checklist.")
    task = c.Task(id=uid(2), request=request, created_at=STAMP, updated_at=STAMP)
    source = c.SourceReference(
        id=uid(3), kind="user_request", locator=f"task:{uid(2)}", attribution="explicit"
    )
    evidence = c.Evidence(
        id=uid(4),
        task_id=task.id,
        run_id=uid(7),
        category="simulation",
        kind="artifact",
        uri="fixture://release/checklist",
        sha256="0" * 64,
        captured_at=STAMP,
        summary="Fixture only: a simulated checklist artifact for layout development.",
    )
    checkpoint = c.Checkpoint(
        id=uid(5),
        description="A release checklist draft is available.",
        source_refs=[source],
        scope="demo project",
        verification_rule="Artifact is present.",
        evaluator_version="fixture-evaluator-v1",
        status="verified",
        evidence_refs=[evidence.id],
    )
    brief = c.TaskBrief(
        id=uid(6),
        task_id=task.id,
        instructions="Create a checklist draft in the demo workspace.",
        checkpoints=[checkpoint],
        created_at=STAMP,
    )
    tool = c.ToolVersion(name="checklist.create", version="fixture-v1", artifact_sha256="1" * 64)
    scope = c.PermissionScope(project_id="demo", service_grants=["simulation:checklists"])
    baseline = c.ExecutorBaseline(**{name: "2" * 64 for name in c.ExecutorBaseline.model_fields})
    environment = c.EnvironmentVersion(
        id=uid(8),
        manifest_sha256="3" * 64,
        tools=[tool],
        context_rule_version="fixture-v1",
        status="staged",
        created_at=STAMP,
    )
    run = c.Run(
        id=uid(7),
        task_id=task.id,
        brief_id=brief.id,
        environment_version_id=environment.id,
        executor_baseline=baseline,
        visible_tools=[tool],
        evidence_refs=[evidence.id],
        status="completed",
        final_response="Fixture only: checklist prepared.",
        started_at=STAMP,
        finished_at=STAMP,
    )
    revision = c.IntentRevision(
        id=uid(9),
        task_id=task.id,
        feedback="Also include rollback steps.",
        reason="new_preference",
        source_refs=[
            c.SourceReference(
                id=uid(10),
                kind="user_feedback",
                locator="fixture://feedback/1",
                attribution="explicit",
            )
        ],
        retained_evidence_refs=[evidence.id],
        created_at=STAMP,
    )
    candidate = c.RepairCandidate(
        id=uid(11),
        task_id=task.id,
        baseline_environment_version_id=environment.id,
        kind="tool_repair",
        artifact_uri="fixture://candidate/adapter.py",
        artifact_sha256="4" * 64,
        diff="Fixture only: adapter serialization patch.",
        permissions=scope,
        limits=c.RepairLimits(max_attempts=2, max_seconds=60, max_cost_usd=1),
        created_at=STAMP,
    )
    verification = c.VerificationResult(
        id=uid(12),
        candidate_id=candidate.id,
        artifact_sha256=candidate.artifact_sha256,
        baseline_sha256="2" * 64,
        category="component",
        status="failed",
        verifier_version="fixture-evaluator-v1",
        notes="Fixture only: regression detected.",
        completed_at=STAMP,
    )
    repair = c.RepairRecord(
        id=uid(13),
        task_id=task.id,
        run_id=run.id,
        checkpoint_refs=[checkpoint.id],
        trigger="Fixture only: invalid tool response.",
        diagnosis="Adapter serialization mismatch.",
        evidence_refs=[evidence.id],
        attempts=[
            c.RepairAttempt(
                candidate_id=candidate.id,
                number=1,
                decision="rejected",
                verification_refs=[verification.id],
                reason="Component check failed.",
            )
        ],
        created_at=STAMP,
    )
    event = c.ProgressEvent(
        id=uid(14),
        task_id=task.id,
        run_id=run.id,
        sequence=1,
        type="checkpoint.updated",
        emitted_at=STAMP,
        payload=checkpoint,
    )
    examples = [
        request,
        task,
        c.TaskList(items=[task], total=1, limit=20, offset=0),
        c.HealthResponse(),
        c.ErrorEnvelope(
            error={"code": "task_not_found", "message": "Task not found", "details": []}
        ),
        source,
        evidence,
        checkpoint,
        brief,
        run,
        revision,
        candidate,
        verification,
        repair,
        environment,
        event,
    ]
    return [
        {
            "name": value.__class__.__name__,
            "model": value.__class__.__name__,
            "value": value.model_dump(mode="json"),
        }
        for value in examples
    ]


def documents() -> dict[Path, dict]:
    return {
        BACKEND / "contracts" / "schemas.json": {
            "schema_version": 1,
            "description": "Data contracts only. Future models do not imply runtime support.",
            "models": {name: model.model_json_schema() for name, model in models().items()},
        },
        BACKEND / "fixtures" / "development.json": {
            "fixture_only": True,
            "description": "UI development examples. No execution or repair occurred.",
            "examples": fixture_examples(),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, document in documents().items():
        content = json.dumps(document, indent=2, sort_keys=True) + "\n"
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                print(f"Contract export is stale: {path.relative_to(BACKEND)}")
                return 1
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    print("Contract schemas and fixture examples are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
