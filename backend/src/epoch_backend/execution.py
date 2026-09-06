"""Bounded actual Hermes execution of an explicitly selected release template."""

import json
import os
import sqlite3
import sys
import threading
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from epoch_backend import debugger_bridge, hermes_bridge
from epoch_backend.config import Settings
from epoch_backend.contracts import Checkpoint, SourceReference, Task, TaskBrief, TaskStatus
from epoch_backend.execution_contracts import ExecutionRecord, ReleaseRunRequest, RuntimeInfo
from epoch_backend.execution_store import ExecutionStore
from epoch_backend.sandbox import Sandbox, SandboxError
from epoch_backend.storage import RequestConflict, SQLiteStore
from epoch_backend.supervision_contracts import (
    FeedbackRequest,
    SupervisionOperation,
    SupervisionState,
)

TERMINAL = {"completed", "failed", "cancelled", "interrupted", "needs_input", "blocked"}


def task_status(status: str) -> TaskStatus:
    if status == "needs_input":
        return TaskStatus.awaiting_clarification
    if status == "interrupted":
        return TaskStatus.blocked
    return TaskStatus(status)


class ExecutionError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


class ServerLease:
    """OS releases this local lease if the process dies; no stale lock deletion."""

    def __init__(self, path: Path):
        self.path = path
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        try:
            self.file.seek(0)
            if not self.file.read(1):
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            self.file = None
            raise ExecutionError(
                "server_busy", "Another Epoch server is using this data directory."
            ) from exc

    def release(self):
        if self.file is not None:
            self.file.close()
            self.file = None


def release_brief(task: Task, run_id: UUID, metadata: dict) -> TaskBrief:
    """Expand a developer-authored template; no model-derived checkpoint planning."""
    project, release = metadata["project_id"], metadata["release"]
    source = SourceReference(
        id=uuid4(),
        kind="document",
        locator="epoch-template:release-v1",
        version="1",
        attribution="explicit",
        excerpt="The API caller explicitly selected workflow=release.",
    )
    descriptions = [
        f"Create the release ticket for {project} {release}.",
        "Attach a checklist containing all required release items to that ticket.",
        f"Notify {metadata['qa_channel']} with links to both the ticket and checklist.",
    ]
    if metadata.get("require_qa_owner"):
        descriptions.append("Identify the current QA owner from the authorized directory record.")
    checkpoints = []
    for description in descriptions:
        checkpoints.append(
            Checkpoint(
                id=uuid4(),
                description=description,
                source_refs=[source],
                scope=project,
                depends_on=[checkpoints[-1].id] if checkpoints else [],
                verification_rule="Compare persisted sandbox state against release-v1 criteria.",
                evaluator_version=metadata["evaluator_version"],
            )
        )
    instructions = (
        f"Original user request: {task.request.message}\n\n"
        f"Explicitly selected workflow: release-v1. Project: {project}. Release: {release}.\n"
        f"Create a ticket titled 'Release {project} {release}'. "
        f"Create a checklist titled 'Release checklist {release}' attached to that ticket, "
        f"with these items: {json.dumps(metadata['expected_items'])}. "
        f"Send a message to {metadata['qa_channel']} mentioning release {release} "
        "with both returned object URLs.\n"
        "Discover tools, inspect their input schemas, then invoke them. All effects are simulated. "
        "Use stable idempotency keys per action if retrying. Report actual successes and failures "
        "with returned references. If an operation fails, do not invent its result or bypass it. "
        "Do not create duplicate objects. Finish with a concise factual result."
    )
    if metadata.get("require_qa_owner"):
        instructions += (
            " Also identify the current QA owner using the authorized directory, and include "
            "their name in the QA notice. Report unavailable capabilities; do not guess identities."
        )
    return TaskBrief(
        id=uuid4(),
        task_id=task.id,
        instructions=instructions,
        checkpoints=checkpoints,
        constraints=["Use only granted Epoch sandbox tools.", "No live business-service writes."],
        created_at=datetime.now(UTC),
    )


class ExecutionService:
    def __init__(self, settings: Settings, tasks: SQLiteStore):
        self.settings, self.tasks = settings, tasks
        self.store = ExecutionStore(settings.data_dir / "executions.sqlite3")
        self.lease = ServerLease(settings.data_dir / "execution.lock")
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()
        self.active_run_id: UUID | None = None
        self._unresolved_state = False

    def initialize(self):
        self.lease.acquire()
        try:
            self.store.initialize()
            for record in self.store.list():
                if record.status not in TERMINAL:
                    record.status = "interrupted"
                    record.error = {
                        "code": "server_restarted",
                        "message": "Execution was interrupted.",
                    }
                    if record.supervision:
                        operation = record.supervision.operations[-1]
                        operation.status = "interrupted"
                        operation.finished_at = datetime.now(UTC)
                        operation.error = dict(record.error)
                        operation.missing_evidence.append(
                            "Server stopped before the operation completed; no automatic replay."
                        )
                    self.store.save(record)
                    self.tasks.set_task_status(record.task_id, TaskStatus.blocked)
                    try:
                        self.sandbox(record).record_event("run.interrupted", record.error)
                    except (OSError, ValueError, SandboxError, sqlite3.Error):
                        record.missing_evidence.append(
                            "Interrupted run's sandbox evidence unavailable."
                        )
                        self.store.save(record)
        except Exception:
            self.lease.release()
            raise

    def close(self):
        self._cancel.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=15)
            if thread.is_alive():
                # Keep the lease until process exit rather than allow competing writers.
                raise RuntimeError("Hermes worker did not stop within the shutdown limit.")
        self.lease.release()

    def runtime_info(self) -> RuntimeInfo:
        installation = hermes_bridge.detect_installation()
        available = bool(installation.get("available"))
        debugger = debugger_bridge.detect_debugger()
        enabled = self.settings.enable_hermes and available and not self._unresolved_state
        return RuntimeInfo(
            execution_enabled=enabled,
            hermes_available=available,
            active_run_id=self.active_run_id,
            installation=installation,
            debugger=debugger,
            supervision_enabled=enabled and bool(debugger.get("available")),
        )

    def sandbox(self, record: ExecutionRecord) -> Sandbox:
        return Sandbox(
            self.settings.data_dir / "runs" / str(record.id) / "sandbox.sqlite3",
            task_id=str(record.task_id),
            run_id=str(record.id),
        )

    def get(self, run_id: UUID) -> ExecutionRecord:
        record = self.store.get(run_id)
        if record is None:
            raise ExecutionError("not_found", "Run not found.", 404)
        return record

    def start(self, task_id: UUID, request: ReleaseRunRequest) -> tuple[ExecutionRecord, bool]:
        with self._lock:
            task = self.tasks.get_task(task_id)
            if task is None:
                raise ExecutionError("not_found", "Task not found.", 404)
            existing = self.store.find_request(task_id, request.client_request_id)
            if existing:
                if existing.request.model_dump() != request.model_dump():
                    raise RequestConflict("Run request ID belongs to different input.")
                return existing, False
            if self._unresolved_state:
                raise ExecutionError(
                    "execution_state_unresolved",
                    "Run finalization failed; inspect storage and restart before retrying.",
                    503,
                )
            if self.active_run_id is not None:
                raise ExecutionError("executor_busy", "Another run is active; wait or cancel it.")
            runtime = self.runtime_info()
            if not runtime.execution_enabled:
                raise ExecutionError(
                    "hermes_unavailable", "Hermes is unavailable or execution is disabled.", 503
                )
            if request.supervised and not runtime.supervision_enabled:
                raise ExecutionError(
                    "debugger_unavailable", "OpenAI Luna debugger is unavailable; see runtime.", 503
                )
            run_id = uuid4()
            sandbox = Sandbox(
                self.settings.data_dir / "runs" / str(run_id) / "sandbox.sqlite3",
                task_id=str(task_id),
                run_id=str(run_id),
            )
            sandbox.initialize(
                scenario=request.scenario,
                project_id=task.request.project_id,
                release=request.release,
            )
            now = datetime.now(UTC)
            record = ExecutionRecord(
                id=run_id,
                task_id=task_id,
                request=request,
                status="planning" if request.supervised else "running",
                brief=release_brief(task, run_id, sandbox.metadata()),
                created_at=now,
                updated_at=now,
            )
            if request.supervised:
                operation = SupervisionOperation(
                    id=uuid4(),
                    client_request_id=request.client_request_id,
                    trigger="initial",
                    user_input=task.request.message,
                    request=request.model_dump(mode="json"),
                    created_at=now,
                    max_turns=request.max_turns,
                    timeout_seconds=request.timeout_seconds,
                )
                record.supervision = SupervisionState(
                    current_revision_id=operation.id, operations=[operation]
                )
            self.store.insert(record)
            worker = None
            try:
                self.tasks.set_task_status(task_id, task_status(record.status))
                sandbox.record_event(
                    "brief.template_prepared" if request.supervised else "brief.created",
                    record.brief.model_dump(mode="json"),
                )
                sandbox.record_event(
                    "run.started", {"status": record.status, "simulation_only": True}
                )
                self._cancel = threading.Event()
                self.active_run_id = run_id
                worker = threading.Thread(target=self._execute, args=(record,), daemon=True)
                self._thread = worker
                worker.start()
            except Exception as exc:
                self._cancel.set()
                if worker is not None and worker.is_alive():
                    # An uncertain startup must not admit another worker or race its writes.
                    self._unresolved_state = True
                    raise ExecutionError(
                        "execution_state_unresolved",
                        "Executor startup could not be confirmed; inspect state before retrying.",
                        503,
                    ) from exc
                self._thread = None
                record.status = "failed"
                record.error = {
                    "code": "execution_admission_failed",
                    "message": f"Execution could not start ({type(exc).__name__}).",
                }
                record.missing_evidence.append("Hermes execution did not start.")
                if record.supervision:
                    operation.status = "failed"
                    operation.error = dict(record.error)
                    operation.finished_at = datetime.now(UTC)
                try:
                    self.tasks.set_task_status(task_id, TaskStatus.failed)
                    sandbox.record_event(
                        "run.finished",
                        {"status": "failed", "error": record.error, "executor_success": None},
                    )
                    # As in normal finalization, publish the final event before terminal status.
                    self.store.save(record)
                except Exception:
                    self._unresolved_state = True
                    record.missing_evidence.append(
                        "Admission failure could not be finalized consistently; inspect storage."
                    )
                    try:
                        self.store.save(record)
                    except Exception:
                        pass
                self.active_run_id = run_id if self._unresolved_state else None
                raise ExecutionError(
                    "execution_admission_failed",
                    "Execution could not start. Inspect the saved run before submitting again.",
                    503,
                ) from exc
            return record, True

    def feedback(
        self, run_id: UUID, request: FeedbackRequest, *, clarification: bool = False
    ) -> tuple[ExecutionRecord, bool]:
        """A new explicit operation keeps the same sandbox and immutable prior outcomes."""
        with self._lock:
            record = self.get(run_id)
            if not record.supervision:
                raise ExecutionError("not_supervised", "Feedback requires a supervised run.")
            trigger = "clarification" if clarification else "feedback"
            request_json = request.model_dump(mode="json")
            for previous in record.supervision.operations:
                if previous.client_request_id == request.client_request_id:
                    if previous.trigger != trigger or previous.request != request_json:
                        raise RequestConflict("Feedback ID belongs to different input.")
                    return record, False
            if self._unresolved_state:
                raise ExecutionError(
                    "execution_state_unresolved", "Inspect execution storage before retrying.", 503
                )
            if self.active_run_id is not None:
                raise ExecutionError("executor_busy", "Another operation is active.")
            if record.status not in TERMINAL:
                raise ExecutionError("run_not_finished", "Wait for the current operation to end.")
            if request.expected_revision_id != record.supervision.current_revision_id:
                raise ExecutionError("stale_revision", "Reload the latest revision before editing.")
            if clarification and record.status != "needs_input":
                raise ExecutionError("no_clarification_pending", "This run is not awaiting input.")
            if not self.runtime_info().supervision_enabled:
                raise ExecutionError(
                    "debugger_unavailable", "Supervised execution is unavailable.", 503
                )
            operation = SupervisionOperation(
                id=uuid4(),
                client_request_id=request.client_request_id,
                previous_revision_id=record.supervision.current_revision_id,
                trigger=trigger,
                user_input=request.message,
                request=request_json,
                created_at=datetime.now(UTC),
                max_turns=request.max_turns,
                timeout_seconds=request.timeout_seconds,
                verification_before=record.verification,
            )
            record.supervision.operations.append(operation)
            record.supervision.current_revision_id = operation.id
            record.status = "planning"
            record.error = None
            record.final_response = None
            record.executor_success = None
            record.missing_evidence = []
            sandbox = self.sandbox(record)
            worker = None
            # Save the submitted input and parent revision before any model call.
            self.store.save(record)
            try:
                self.tasks.set_task_status(record.task_id, TaskStatus.planning)
                sandbox.record_event(
                    "intent.submitted",
                    {"revision_id": str(operation.id), **request_json, "trigger": trigger},
                )
                self._cancel = threading.Event()
                self.active_run_id = run_id
                worker = threading.Thread(target=self._execute, args=(record,), daemon=True)
                self._thread = worker
                worker.start()
            except Exception as exc:
                self._cancel.set()
                if worker is not None and worker.is_alive():
                    self._unresolved_state = True
                    raise ExecutionError(
                        "execution_state_unresolved", "Inspect uncertain startup.", 503
                    ) from exc
                self._thread = None
                record.status = operation.status = "failed"
                record.error = operation.error = {
                    "code": "execution_admission_failed",
                    "message": "Feedback execution could not start.",
                }
                operation.finished_at = datetime.now(UTC)
                operation.missing_evidence.append("No model operation started.")
                try:
                    self.tasks.set_task_status(record.task_id, TaskStatus.failed)
                    sandbox.record_event(
                        "run.finished", {"status": "failed", "error": record.error}
                    )
                    self.store.save(record)
                except Exception:
                    self._unresolved_state = True
                    operation.missing_evidence.append("Admission cleanup could not be confirmed.")
                    try:
                        self.store.save(record)
                    except Exception:
                        pass
                self.active_run_id = run_id if self._unresolved_state else None
                raise ExecutionError(
                    "execution_admission_failed", "Inspect the saved feedback operation.", 503
                ) from exc
            return record, True

    def cancel(self, run_id: UUID) -> ExecutionRecord:
        with self._lock:
            record = self.get(run_id)
            if self.active_run_id == run_id:
                self._cancel.set()
                self.sandbox(record).record_event("run.cancellation_requested", {})
            return record

    def _execute(self, record: ExecutionRecord):
        sandbox = self.sandbox(record)
        try:
            if record.supervision is not None:
                from epoch_backend.supervisor import run_supervised

                def persist():
                    self.store.save(record)
                    self.tasks.set_task_status(record.task_id, task_status(record.status))

                run_supervised(record, sandbox, self._cancel, persist)
                return

            def on_event(event: dict):
                sandbox.record_event(
                    str(event.get("type", "executor.event")), event.get("data", {})
                )

            result = hermes_bridge.execute(
                {
                    "task_id": str(record.task_id),
                    "run_id": str(record.id),
                    "brief": record.brief.instructions,
                    "work_dir": str(self.settings.data_dir / "runs" / str(record.id) / "hermes"),
                    "mcp_command": sys.executable,
                    "mcp_args": [
                        "-m",
                        "epoch_backend.mcp_server",
                        "--database",
                        str(sandbox.path),
                        "--task-id",
                        str(record.task_id),
                        "--run-id",
                        str(record.id),
                    ],
                    "timeout_seconds": record.request.timeout_seconds,
                    "max_turns": record.request.max_turns,
                },
                on_event,
                self._cancel,
            )
            record.final_response = result.get("final_response")
            record.executor_success = bool(result.get("success"))
            record.baseline = result.get("baseline", {})
            record.baseline["evaluator_sha256"] = sha256(
                Path(__file__).with_name("trusted_checks.py").read_bytes()
            ).hexdigest()
            record.baseline["permission_grants_sha256"] = sha256(
                json.dumps(sandbox.metadata()["grants"], sort_keys=True).encode()
            ).hexdigest()
            record.baseline["criteria_sha256"] = sandbox.metadata()["criteria_sha256"]
            record.missing_evidence = result.get("missing_evidence", [])
            record.error = result.get("error")
            record.status = "verifying"
            self.store.save(record)
            self.tasks.set_task_status(record.task_id, TaskStatus.verifying)
            sandbox.record_event("run.verifying", {})
            record.verification = sandbox.evaluate()
            checks = {item["id"]: item for item in record.verification["checks"]}
            check_ids = ["release_ticket", "release_checklist", "qa_notification"]
            if sandbox.metadata().get("require_qa_owner"):
                check_ids.append("qa_owner")
            for checkpoint, check_id in zip(
                record.brief.checkpoints,
                check_ids,
                strict=True,
            ):
                checkpoint.status = "verified" if checks[check_id]["passed"] else "failed"
                checkpoint.evidence_refs = [UUID(record.verification["evidence_id"])]
                sandbox.record_event("checkpoint.updated", checkpoint.model_dump(mode="json"))
            if self._cancel.is_set():
                record.status = "cancelled"
            elif record.executor_success and record.verification["passed"]:
                record.status = "completed"
            else:
                record.status = "failed"
        except Exception as exc:
            record.status = "cancelled" if self._cancel.is_set() else "failed"
            record.error = {
                "code": "execution_error",
                "message": f"Execution failed ({type(exc).__name__}).",
            }
            record.missing_evidence.append("Executor did not produce a complete result.")
        finally:

            def sync_operation():
                if record.supervision:
                    operation = record.supervision.operations[-1]
                    operation.status = record.status
                    operation.error = dict(record.error) if record.error else None
                    operation.finished_at = operation.finished_at or datetime.now(UTC)
                    operation.missing_evidence = list(
                        dict.fromkeys([*operation.missing_evidence, *record.missing_evidence])
                    )

            sync_operation()
            try:
                self.tasks.set_task_status(record.task_id, task_status(record.status))
                sandbox.record_event(
                    "run.finished",
                    {
                        "status": record.status,
                        "executor_success": record.executor_success,
                        "verification": record.verification,
                        "error": record.error,
                    },
                )
                # Readers see terminal status only after its final event is durable.
                self.store.save(record)
            except Exception:
                self._unresolved_state = True
                record.status = "failed"
                record.error = {
                    "code": "finalization_failed",
                    "message": "Final state could not be recorded consistently; inspect storage.",
                }
                record.missing_evidence.append("Final status or event persistence failed.")
                sync_operation()
                try:
                    self.store.save(record)
                    self.tasks.set_task_status(record.task_id, TaskStatus.failed)
                except Exception:
                    pass
            finally:
                with self._lock:
                    if not self._unresolved_state:
                        self.active_run_id = None
