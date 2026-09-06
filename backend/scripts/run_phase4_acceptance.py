"""Explicit paid-model acceptance: Luna omission recovery, then sourced user feedback.

Uses actual configured Hermes/OpenAI and local simulated business services. This is
not a unit test. Each operation is limited to 20 shared model requests/600 seconds.
All runs, including failures, remain in the selected data directory.
"""

import argparse
import json
import time
from pathlib import Path
from uuid import uuid4

from epoch_backend.config import Settings
from epoch_backend.contracts import TaskCreate
from epoch_backend.execution import TERMINAL, ExecutionService
from epoch_backend.execution_contracts import ReleaseRunRequest
from epoch_backend.storage import SQLiteStore
from epoch_backend.supervision_contracts import FeedbackRequest


def wait(service, run_id):
    previous = None
    while True:
        record = service.get(run_id)
        operation = record.supervision.operations[-1]
        progress = (record.status, operation.turns_used, len(operation.interventions))
        if progress != previous:
            print(
                json.dumps(
                    {
                        "run_id": str(run_id),
                        "revision_id": str(operation.id),
                        "status": progress[0],
                        "turns": progress[1],
                        "interventions": progress[2],
                    }
                ),
                flush=True,
            )
            previous = progress
        if record.status in TERMINAL and service.active_run_id is None:
            return record
        time.sleep(0.25)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings(data_dir=args.data_dir, enable_hermes=True, _env_file=None)
    tasks = SQLiteStore(settings.database_path)
    tasks.initialize()
    service = ExecutionService(settings, tasks)
    service.initialize()
    try:
        task, _ = tasks.create_task(
            TaskCreate(
                client_request_id=uuid4(),
                project_id="demo",
                message="Prepare release 2.4: create the release ticket, its checklist, "
                "and notify QA with links to both.",
            )
        )
        record, _ = service.start(
            task.id,
            ReleaseRunRequest(
                client_request_id=uuid4(),
                workflow="release",
                release="2.4",
                supervised=True,
                demo_omit_notification=True,
            ),
        )
        record = wait(service, record.id)
        initial = record.supervision.operations[0].model_dump(mode="json")
        assert record.status == "completed", record.model_dump_json(indent=2)
        assert initial["interventions"], "Omission was not corrected through an intervention"
        assert len(initial["executor_passes"]) >= 2
        before = service.sandbox(record).snapshot()
        request = FeedbackRequest(
            client_request_id=uuid4(),
            expected_revision_id=record.supervision.current_revision_id,
            message="Add 'Security review complete' to the checklist. Also include the exact "
            "phrase 'QA sign-off required' in the QA message. Keep all earlier work.",
        )
        record, created = service.feedback(record.id, request)
        assert created
        record = wait(service, record.id)
        assert record.status == "completed", record.model_dump_json(indent=2)
        assert record.supervision.operations[0].model_dump(mode="json") == initial
        after = service.sandbox(record).snapshot()
        for collection in ("tickets", "checklists", "messages"):
            assert len(before[collection]) == len(after[collection]) == 1
            assert before[collection][0]["id"] == after[collection][0]["id"]
        metadata = service.sandbox(record).metadata()
        assert "Security review complete" in metadata["expected_items"]
        assert "QA sign-off required" in metadata["required_message_phrases"]
        assert record.verification["passed"]
        duplicate, created = service.feedback(record.id, request)
        assert (
            not created
            and duplicate.supervision.current_revision_id == record.supervision.current_revision_id
        )
        result = {
            "accepted": True,
            "run_id": str(record.id),
            "task_id": str(task.id),
            "operations": [
                {
                    "id": str(op.id),
                    "turns_used": op.turns_used,
                    "debugger_turns": op.debugger_turns,
                    "executor_turns": op.executor_turns,
                    "interventions": len(op.interventions),
                    "status": op.status,
                }
                for op in record.supervision.operations
            ],
            "same_object_ids": True,
            "prior_operation_unchanged": True,
            "feedback_retry_no_new_operation": True,
        }
        output = settings.data_dir / f"acceptance-{record.id}.json"
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2), flush=True)
        return 0
    finally:
        service.close()


if __name__ == "__main__":
    raise SystemExit(main())
