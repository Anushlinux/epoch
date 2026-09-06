"""Actual Luna-generated repair, isolated Hermes verification, reuse and rollback.

Uses local simulated services and real configured models. Preserves every attempt.
Primary: 20 requests/600 active seconds; each verification: 20/600; overall: 60/1800.
"""

import argparse
import json
import time
from pathlib import Path
from uuid import UUID, uuid4

from epoch_backend.config import Settings
from epoch_backend.contracts import TaskCreate
from epoch_backend.execution import TERMINAL, ExecutionService
from epoch_backend.execution_contracts import ReleaseRunRequest
from epoch_backend.storage import SQLiteStore
from epoch_backend.tool_registry import ToolRegistry


def wait(service, run_id):
    previous = None
    while True:
        record = service.get(run_id)
        operation = record.supervision.operations[-1] if record.supervision else None
        report = operation.repairs[-1] if operation and operation.repairs else {}
        attempt = report.get("attempts", [{}])[-1] if report.get("attempts") else {}
        stage = attempt.get("active_verification", {})
        progress = {
            "run_id": str(run_id),
            "status": record.status,
            "turns": operation.turns_used if operation else None,
            "overall": (operation.repair_budget or {}).get("used") if operation else None,
            "repair": report.get("status"),
            "attempt": attempt.get("number"),
            "stage": stage.get("kind"),
            "stage_turns": stage.get("turns_used"),
        }
        if progress != previous:
            print(json.dumps(progress), flush=True)
            previous = progress
        if record.status in TERMINAL and (
            service.active_run_id is None or not service._thread.is_alive()
        ):
            return record
        time.sleep(0.25)


def start(service, tasks, release, *, repair=False):
    task, _ = tasks.create_task(
        TaskCreate(
            client_request_id=uuid4(),
            project_id="demo",
            message=f"Prepare release {release}: create the release ticket, its checklist, "
            "and notify QA with links to both.",
        )
    )
    record, _ = service.start(
        task.id,
        ReleaseRunRequest(
            client_request_id=uuid4(),
            workflow="release",
            release=release,
            supervised=repair,
            repair_enabled=repair,
            scenario="broken_checklist",
        ),
    )
    record = wait(service, record.id)
    assert record.status == "completed", {"run_id": str(record.id), "error": record.error}
    assert record.verification["passed"]
    assert all(
        len(service.sandbox(record).snapshot()[key]) == 1
        for key in ("tickets", "checklists", "messages")
    )
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--resume-original",
        type=UUID,
        help="Explicitly verify an already completed repair; retain prior failures",
    )
    args = parser.parse_args()
    settings = Settings(data_dir=args.data_dir, enable_hermes=True, _env_file=None)
    tasks = SQLiteStore(settings.database_path)
    tasks.initialize()
    service = ExecutionService(settings, tasks)
    service.initialize()
    try:
        if args.resume_original:
            original = service.get(args.resume_original)
            assert original.status == "completed"
            assert service.environments.active_id("demo") == original.environment_version
        else:
            assert service.environments.active_id("demo") == "builtin", "Use a fresh data directory"
            original = start(service, tasks, "2.4", repair=True)
        repair = original.supervision.operations[0].repairs[0]
        assert repair["status"] == "published"
        version = service.environments.version(original.environment_version)
        assert len(version["proofs"]) == 5 and all(p["passed"] for p in version["proofs"])
        assert (
            repair["state_before"]["tickets"][0]["id"]
            == service.sandbox(original).snapshot()["tickets"][0]["id"]
        )
        service.close()
        service = ExecutionService(settings, tasks)
        service.initialize()
        later = start(service, tasks, "3.7")
        assert later.environment_version == original.environment_version
        assert later.supervision is None
        from epoch_backend.supervisor import BASELINE_KEYS

        assert all(later.baseline[k] == original.baseline[k] for k in BASELINE_KEYS)
        discovery = ToolRegistry(service.sandbox(later)).discover_tools()["result"]["tools"]
        assert (
            next(t for t in discovery if t["name"] == "checklists.create")["implementation_version"]
            == original.environment_version
        )
        request_id = uuid4()
        rollback = service.rollback("demo", original.environment_version, request_id)
        assert rollback["version_id"] == "builtin"
        assert service.rollback("demo", original.environment_version, request_id) == rollback
        result = {
            "accepted": True,
            "original_run": str(original.id),
            "later_run": str(later.id),
            "version_id": version["id"],
            "artifact_sha256": version["artifact_sha256"],
            "proofs": [
                {"kind": p["kind"], "passed": p["passed"], "turns_used": p.get("turns_used")}
                for p in version["proofs"]
            ],
            "original_shared_requests": original.supervision.operations[0].turns_used,
            "overall_requests": original.supervision.operations[0].repair_budget["used"],
            "later_mode": "direct Hermes without debugger",
            "original_objects_retained": True,
            "restart_and_ordinary_discovery": True,
            "rollback": rollback,
        }
        output = settings.data_dir / f"acceptance-{original.id}.json"
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2), flush=True)
        return 0
    finally:
        service.close()


if __name__ == "__main__":
    raise SystemExit(main())
