"""Explicit PDF investigation, generated repair, publication and chat file routes."""

import difflib
import threading
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel

from epoch_backend import debugger_bridge
from epoch_backend.candidate_runner import CandidateError
from epoch_backend.environment_store import EnvironmentStore
from epoch_backend.execution import ExecutionError
from epoch_backend.incident_contracts import IncidentAnswer
from epoch_backend.pdf_contracts import (
    CreatePdf,
    EnvironmentAction,
    MergePdf,
    PdfProposal,
    literal_schema,
)
from epoch_backend.pdf_runtime import RUNNER_VERSION
from epoch_backend.pdf_verification import (
    clone,
    component_cases,
    execute_hermes,
    fresh_sandbox,
    invariant_match,
    output_check,
    protected_identity,
    protected_sources,
)
from epoch_backend.repair_budget import RepairBudget
from epoch_backend.storage import RequestConflict


class BundleRequest(BaseModel):
    pack: str


class PdfChat:
    def __init__(self, chats):
        self.chats = chats

    def initialize(self):
        store = EnvironmentStore(
            self.chats.execution.settings.data_dir / "pdf" / "environments.sqlite3"
        )
        store.initialize()
        store.recover_interrupted()

    def require_active(self, chat):
        if chat.environment in {"csv_broken", "csv_healthy"}:
            raise ExecutionError(
                "environment_retired",
                "The CSV environment is retired. Its records remain on disk.",
                410,
            )

    def sandbox(self, chat_id):
        chat = self.chats.get(chat_id)
        self.require_active(chat)
        if chat.environment != "pdf_workshop":
            raise ExecutionError(
                "environment_mismatch", "This action requires the PDF workshop.", 422
            )
        return self.chats.sandbox(chat)

    def start(self, chat_id, payload, investigate=False):
        from epoch_backend.chat import ChatOperation

        execution = self.chats.execution
        with execution._lock:
            chat = self.chats.get(chat_id)
            sandbox = self.sandbox(chat_id)
            action = "investigate" if investigate else payload.action
            serialized = payload.model_dump(mode="json")
            for op in chat.operations:
                if op.client_request_id == payload.client_request_id:
                    if op.action != action or (op.analysis or {}).get("request") != serialized:
                        raise RequestConflict()
                    return op, False
            if execution.active_run_id is not None or execution._unresolved_state:
                raise ExecutionError(
                    "executor_busy", "Wait for the active operation or resolve its state.", 409
                )
            if not execution.settings.enable_hermes or not debugger_bridge.detect_debugger().get(
                "available"
            ):
                raise ExecutionError(
                    "debugger_unavailable",
                    "Enable the configured Hermes and debugger connections.",
                    503,
                )
            if not investigate:
                available = sandbox.snapshot()["actions"]
                if not any(
                    a["eligible"]
                    and a["action"] == action
                    and a["evidence_id"] == str(payload.evidence_id)
                    and a["expected_version"] == payload.expected_version
                    for a in available
                ):
                    raise ExecutionError(
                        "repair_ineligible",
                        (
                            "No current eligible evidence supports this action. Refresh the "
                            "environment."
                        ),
                        409,
                    )
            op = ChatOperation(
                id=uuid4(),
                chat_id=chat.id,
                client_request_id=payload.client_request_id,
                status="running",
                kind="debugger",
                action=action,
                question=getattr(payload, "question", None),
                created_at=datetime.now(UTC),
                activity="Debugger is inspecting the saved evidence",
                analysis={
                    "request": serialized,
                    "attempts": [],
                    "answer": "Investigation started.",
                },
            )
            chat.operations.append(op)
            self.chats.save(chat)
            execution.active_run_id = op.id
            execution._cancel = threading.Event()
            execution._thread = threading.Thread(
                target=self.run, args=(chat, op, sandbox, execution._cancel), daemon=True
            )
            execution._thread.start()
            return op.model_copy(deep=True), True

    def run(self, chat, op, sandbox, cancel):
        from epoch_backend.chat import ChatMessage

        store = sandbox.versions()
        sandbox.cancelled = cancel
        candidate = None

        def progress(message):
            op.activity = message
            self.chats.save(chat)

        def record_usage(value):
            op.analysis["usage"] = value
            self.chats.save(chat)

        budget = RepairBudget(20, 600, cancel, lambda actor, used: None, record_usage)
        try:
            if op.action == "investigate":
                budget.consume("debugger")
                result = debugger_bridge.complete(
                    {
                        "instructions": (
                            "Investigate this PDF conversation using the supplied recorded "
                            "evidence. Cite supplied event IDs. Explain supported findings and"
                            " uncertainty. This is read-only; do not claim a repair or tool "
                            "creation occurred."
                        ),
                        "input": {
                            "question": op.question,
                            "messages": [
                                m.model_dump(mode="json")
                                for m in chat.messages
                                if m.agent != "debugger"
                            ][-12:],
                            "evidence": sandbox.events()[-30:],
                        },
                        "schema": IncidentAnswer.model_json_schema(),
                        "timeout_seconds": 300,
                    },
                    lambda e: None,
                    cancel,
                )
                if not result.get("success"):
                    raise CandidateError("investigation_failed", str(result.get("error")))
                answer = IncidentAnswer.model_validate(result["output"])
                allowed = {e["id"] for e in sandbox.events()[-30:]}
                if any(str(i) not in allowed for i in answer.evidence_ids):
                    raise CandidateError(
                        "unsourced_analysis", "Investigation cited unavailable evidence."
                    )
                op.analysis.update(answer.model_dump(mode="json"))
            else:
                evidence = next(
                    e for e in sandbox.events() if e["id"] == op.analysis["request"]["evidence_id"]
                )
                target = "render_pdf" if op.action == "repair_tool" else "merge_pdfs"
                filename = "pdf_renderer.py" if target == "render_pdf" else "pdf_merge.py"
                captured = evidence["payload"]["arguments"]
                previous = op.analysis["request"]["expected_version"]
                original_messages = [m for m in chat.messages if m.agent != "debugger"]
                index = next(
                    i
                    for i, m in enumerate(original_messages)
                    if str(m.operation_id) == evidence["operation_id"] and m.role == "user"
                )
                original = original_messages[index].content
                history = [
                    {"role": m.role, "content": m.content} for m in original_messages[:index]
                ]
                reference_event = next(
                    e
                    for e in reversed(sandbox.events())
                    if e["type"] == "executor.result"
                    and (
                        e["operation_id"] == evidence["operation_id"]
                        or e["payload"].get("chat_operation_id") == evidence["operation_id"]
                    )
                )
                reference = reference_event["payload"]["result"].get("baseline", {})
                source_before = sandbox.source(target)[0] if target == "render_pdf" else ""
                runtime = sandbox.runtime()
                baseline_protected = protected_identity()
                protected_dir = sandbox.root / "protected" / baseline_protected
                protected_dir.mkdir(parents=True, exist_ok=True)
                for name, contents in protected_sources().items():
                    (protected_dir / name).write_text(contents)
                prior_attempts = [
                    e
                    for e in sandbox.events()
                    if e["type"] == "pdf.candidate_attempt"
                    and e["payload"].get("evidence_id") == evidence["id"]
                ]
                schema = (CreatePdf if target == "render_pdf" else MergePdf).model_json_schema()
                proposal_schema = PdfProposal.model_json_schema()
                proposal_schema["properties"]["target"]["enum"] = [target]
                proposal_schema["properties"]["evidence_ids"].update(
                    minItems=1, maxItems=1, items={"type": "string", "enum": [evidence["id"]]}
                )
                proposal_schema["properties"]["input_schema_json"]["enum"] = [""]
                proposal_schema["required"].append("input_schema")
                proposal_schema["properties"]["input_schema"] = (
                    literal_schema(schema) if target == "merge_pdfs" else {"type": "null"}
                )
                rejected = [
                    {"attempts": prior.analysis.get("attempts", []), "error": prior.error}
                    for prior in chat.operations
                    if prior.id != op.id
                    and prior.analysis
                    and prior.analysis.get("request", {}).get("evidence_id") == evidence["id"]
                ]
                op.analysis.update(
                    evidence=evidence,
                    source_before=source_before,
                    original_request=original,
                    expected_version=previous,
                    protected_sha256=baseline_protected,
                )
                for number in range(len(prior_attempts), 2):
                    budget.check()
                    progress(
                        "Debugger is generating the renderer repair"
                        if target == "render_pdf"
                        else "Debugger is creating the missing PDF merge tool"
                    )
                    attempt_event = sandbox.record_event(
                        "pdf.candidate_attempt",
                        {
                            "evidence_id": evidence["id"],
                            "number": number + 1,
                            "operation_id": str(op.id),
                        },
                    )
                    attempt = {
                        "number": number + 1,
                        "event_id": attempt_event["id"],
                        "status": "generating",
                        "proofs": [],
                    }
                    op.analysis["attempts"].append(attempt)
                    budget.consume("debugger")
                    generated = debugger_bridge.complete(
                        {
                            "instructions": (
                                "You implement an explicitly authorized PDF environment change. "
                                "When action is create_tool, the absent implementation is "
                                "intentional: the capability-request event and missing catalog "
                                "authorize creating pdf.merge from scratch. Do not require a "
                                "pre-existing source or renderer failure for creation. Return "
                                "outcome=repair for a supported repair OR new tool creation. "
                                "When action is repair_tool, diagnose the existing renderer. "
                                "Return complete executable "
                                "Python, never a prerecorded answer or changed test. Use the "
                                "supplied source and evidence. Use unsupported only if the "
                                "requested authorized capability cannot be implemented. "
                                "The runtime has reportlab 4.4.3, pypdf 6.0.0,"
                                " pdfplumber and DejaVuSans regular/bold fonts under "
                                "/usr/share/fonts/truetype/dejavu/. The ONLY entrypoint is "
                                "render_pdf(document: dict)->bytes or merge_pdfs(inputs: "
                                "list[bytes])->bytes as specified. For render_pdf, use A4 pages, "
                                "margins at least 36 points, font size at least 10, complete "
                                "unchanged content in order. Heading/paragraph blocks have text, "
                                "bullet blocks items, table blocks rows. Handle paragraphs longer "
                                "than one page and tables splitting across pages without dropping "
                                "text. ReportLab Platypus may be used. For merge_pdfs preserve "
                                "exact page appearance, dimensions, rotation and order, including "
                                "duplicate inputs, using pypdf. No filesystem, network, "
                                "credentials, subprocess, tool calls, test edits, hardcoded "
                                "content, paths to host files, or permissions. Input/output PDF "
                                "bytes are in memory (io.BytesIO). DejaVu font reads inside the "
                                "container are permitted. source must be raw Python with NO "
                                "Markdown fences. input_schema_json must be empty. For "
                                "render_pdf return input_schema=null. For merge_pdfs return "
                                "the supplied public input_schema as a structured JSON object "
                                "in input_schema, including every type field. "
                                "Cite the failure"
                                " event ID. Return a useful accurate tool description and disclose"
                                " uncertainty. Code executes only in a restricted container and "
                                "independent verification decides publication."
                            ),
                            "input": {
                                "target": target,
                                "action": op.action,
                                "source": source_before,
                                "evidence": evidence,
                                "input_schema": schema,
                                "rejected_attempts": rejected + op.analysis["attempts"][:-1],
                            },
                            "schema": proposal_schema,
                            "timeout_seconds": min(300, budget.remaining_seconds()),
                            "max_output_tokens": 12000,
                        },
                        lambda e: None,
                        cancel,
                    )
                    if not generated.get("success"):
                        raise CandidateError("proposal_failed", str(generated.get("error")))
                    proposal = PdfProposal.model_validate(generated["output"])
                    attempt["proposal"] = proposal.model_dump(mode="json")
                    if (
                        proposal.outcome != "repair"
                        or proposal.target != target
                        or {str(i) for i in proposal.evidence_ids} != {evidence["id"]}
                        or (target == "merge_pdfs" and proposal.input_schema != schema)
                        or proposal.source.strip().startswith("```")
                    ):
                        attempt.update(
                            status="rejected",
                            error=(
                                "Source must be raw Python and match the authorized "
                                "interface and evidence."
                            ),
                        )
                        raise CandidateError(
                            "proposal_invalid",
                            "Proposal did not match the supported source, evidence and interface.",
                        )
                    contract = (
                        {
                            "name": "pdf.merge",
                            "description": proposal.description,
                            "input_schema": schema,
                        }
                        if target == "merge_pdfs"
                        else None
                    )
                    diff = "".join(
                        difflib.unified_diff(
                            source_before.splitlines(True),
                            proposal.source.splitlines(True),
                            fromfile="before/" + filename,
                            tofile="after/" + filename,
                        )
                    )
                    candidate = store.stage(
                        chat.project_id,
                        proposal.source,
                        image_id=runtime.image,
                        runner_version=RUNNER_VERSION,
                        parent=previous,
                        diagnosis=proposal.model_dump(mode="json"),
                        diff=diff,
                        target=filename,
                        tool_contract=contract,
                    )
                    attempt.update(candidate_id=candidate["id"], diff=diff, status="verifying")
                    manifest = store.manifest(chat.project_id, candidate["id"], staged=True)
                    common = {
                        "artifact_sha256": candidate["artifact_sha256"],
                        "bundle_sha256": candidate["bundle_sha256"],
                        "image_id": runtime.image,
                        "verifier_sha256": baseline_protected,
                    }

                    def proof(kind, passed, common=common, attempt=attempt, **details):
                        value = {"kind": kind, "passed": bool(passed), **common, **details}
                        attempt["proofs"].append(value)
                        self.chats.save(chat)
                        return value

                    try:
                        progress("Checking isolated execution and PDF behavior")
                        isolation = runtime.run({"mode": "probe"})
                        proof(
                            "isolation",
                            all(v is True for v in isolation.values()),
                            checks=isolation,
                        )
                        cases = component_cases(
                            candidate, sandbox, target, captured, cancel, budget
                        )
                        proof("component", all(c["passed"] for c in cases), cases=cases)
                        proof(
                            "regression",
                            all(c["passed"] for c in cases),
                            cases=cases,
                            protected_unchanged=protected_identity() == baseline_protected,
                        )
                        if not all(p["passed"] for p in attempt["proofs"]):
                            raise CandidateError(
                                "component_failed",
                                "Independent PDF component checks rejected the candidate.",
                            )
                        folder = sandbox.root / "verification" / candidate["id"]
                        original_box = clone(sandbox, folder / "original", manifest)
                        original_box.cancelled = cancel
                        # The same initial request/history executes against the candidate.
                        # Prior failed operation keys must not return its cached broken output.
                        with closing_connection(original_box.path) as db:
                            db.execute(
                                "DELETE FROM requests WHERE key LIKE 'pdf.create:%' "
                                "OR key LIKE "
                                "'pdf.merge:%'"
                            )
                        progress("Hermes is verifying the original task")
                        outcome = execute_hermes(
                            original_box, original, history, budget, cancel, progress
                        )
                        expected = (
                            captured["document"]
                            if target == "render_pdf"
                            else captured["asset_ids"]
                        )
                        checked = output_check(original_box, target, expected)
                        proof(
                            "original_replay",
                            outcome.get("success")
                            and checked["passed"]
                            and invariant_match(outcome.get("baseline", {}), reference),
                            executor=outcome,
                            verification=checked,
                        )
                        if not attempt["proofs"][-1]["passed"]:
                            raise CandidateError(
                                "original_replay_failed",
                                "Hermes original-task verification failed.",
                            )
                        progress("Hermes is verifying a fresh task")
                        fresh, fresh_prompt, expected = fresh_sandbox(
                            sandbox, folder / "fresh", manifest, target
                        )
                        fresh.cancelled = cancel
                        outcome = execute_hermes(fresh, fresh_prompt, [], budget, cancel, progress)
                        checked = output_check(fresh, target, expected)
                        proof(
                            "fresh_task",
                            outcome.get("success")
                            and checked["passed"]
                            and invariant_match(outcome.get("baseline", {}), reference),
                            executor=outcome,
                            verification=checked,
                        )
                        budget.overall_check()
                        if protected_identity() != baseline_protected:
                            raise CandidateError(
                                "protected_changed",
                                "Protected verification code changed during the operation.",
                            )
                        published = store.publish(
                            candidate["id"], attempt["proofs"], expected_active=previous
                        )
                        attempt["status"] = "published"
                        op.analysis.update(
                            published_version=published["id"],
                            answer=(
                                "Verified PDF tool published. Hermes is continuing the original "
                                "task."
                            ),
                        )
                        self.chats.save(chat)
                        sandbox.pin(op.id, store.manifest(chat.project_id))
                        continuation = (
                            "A verified environment update is available. Rediscover and "
                            "describe the tools, then complete the original request. Preserve "
                            "all content and existing files. Use a NEW idempotency key for the"
                            " new output. Original request: "
                        ) + original
                        sandbox.record_event(
                            "supervisor.pdf_continuation",
                            {
                                "instruction": continuation,
                                "original_request": original,
                                "version": published["id"],
                            },
                        )
                        progress(
                            "Hermes is completing the original request with the published tool"
                        )
                        result = execute_hermes(
                            sandbox,
                            continuation,
                            [{"role": m.role, "content": m.content} for m in original_messages],
                            budget,
                            cancel,
                            progress,
                        )
                        recovered = output_check(
                            sandbox,
                            target,
                            captured["document"]
                            if target == "render_pdf"
                            else captured["asset_ids"],
                        )
                        op.analysis["recovery"] = {"executor": result, "verification": recovered}
                        if result.get("final_response"):
                            chat.messages.append(
                                ChatMessage(
                                    id=uuid4(),
                                    role="assistant",
                                    agent="hermes",
                                    content=result["final_response"],
                                    operation_id=op.id,
                                    created_at=datetime.now(UTC),
                                )
                            )
                        if not result.get("success") or not recovered["passed"]:
                            raise CandidateError(
                                "recovery_failed",
                                (
                                    "The tool was published, but Hermes recovery did not complete "
                                    "successfully."
                                ),
                            )
                        op.analysis["answer"] = (
                            "The tool was generated, independently verified and published. "
                            "Hermes completed the original task. New chats in this project "
                            "discover the saved tool version."
                        )
                        break
                    except Exception as exc:
                        if store.version(candidate["id"])["status"] == "staged":
                            store.reject(candidate["id"], attempt["proofs"], str(exc))
                            attempt.update(status="rejected", error=str(exc))
                        if getattr(exc, "code", "") != "component_failed" or number == 1:
                            raise
                        progress("Candidate rejected; debugger is revising the code")
                else:
                    raise CandidateError("attempts_exhausted", "Both candidate attempts were used.")
            op.status = "completed"
        except Exception as exc:
            op.status = "cancelled" if cancel.is_set() else "failed"
            op.error = {
                "code": getattr(exc, "code", type(exc).__name__),
                "message": str(exc)[:2000],
            }
            op.analysis["answer"] = (
                "A tool version was published, but recovery is incomplete. "
                if op.analysis.get("published_version")
                else "No tool change was published. "
            ) + op.error["message"]
        finally:
            op.finished_at = datetime.now(UTC)
            op.activity = op.status.capitalize()
            chat.messages.append(
                ChatMessage(
                    id=uuid4(),
                    role="assistant",
                    agent="debugger",
                    content=op.analysis["answer"],
                    operation_id=op.id,
                    created_at=datetime.now(UTC),
                )
            )
            with self.chats.execution._lock:
                try:
                    self.chats.save(chat)
                except Exception:
                    self.chats.execution._unresolved_state = True
                if not self.chats.execution._unresolved_state:
                    self.chats.execution.active_run_id = None

    def routes(self, router):
        from epoch_backend.repair_contracts import RollbackRequest

        def idle():
            execution = self.chats.execution
            if execution.active_run_id is not None or execution._unresolved_state:
                raise ExecutionError(
                    "executor_busy", "Wait for the active operation before changing inputs.", 409
                )

        @router.post("/{chat_id}/assets/bundled")
        def bundled(chat_id: UUID, payload: BundleRequest):
            with self.chats.execution._lock:
                idle()
                return self.sandbox(chat_id).seed(payload.pack)

        @router.post("/{chat_id}/assets")
        async def upload(chat_id: UUID, request: Request, name: str, client_request_id: UUID):
            chunks = bytearray()
            async for block in request.stream():
                if len(chunks) + len(block) > 10 * 1024 * 1024:
                    raise HTTPException(413, "PDF upload exceeds 10 MiB")
                chunks.extend(block)
            from starlette.concurrency import run_in_threadpool

            def save():
                with self.chats.execution._lock:
                    idle()
                    return self.sandbox(chat_id).upload(name, bytes(chunks), client_request_id)

            return await run_in_threadpool(save)

        @router.get("/{chat_id}/assets")
        def assets(chat_id: UUID):
            return {"items": self.sandbox(chat_id).assets()}

        @router.get("/{chat_id}/assets/{asset_id}/content")
        def content(chat_id: UUID, asset_id: UUID):
            box = self.sandbox(chat_id)
            asset = box.asset(asset_id)
            return Response(
                box.raw(asset),
                media_type="application/pdf" if asset["kind"] == "pdf" else "application/json",
                headers={
                    "Content-Disposition": "attachment; filename*=UTF-8''"
                    + quote(asset["name"], safe=""),
                    "X-Content-Type-Options": "nosniff",
                },
            )

        @router.get("/{chat_id}/assets/{asset_id}/pages/{page}")
        def preview(chat_id: UUID, asset_id: UUID, page: int):
            box = self.sandbox(chat_id)
            asset = box.asset(asset_id)
            if asset["kind"] != "pdf" or not 1 <= page <= asset["page_count"]:
                raise HTTPException(404, "PDF page not found")
            return Response(
                box.runtime().preview(box.raw(asset), page),
                media_type="image/png",
                headers={"X-Content-Type-Options": "nosniff"},
            )

        @router.post("/{chat_id}/environment-actions")
        def action(chat_id: UUID, payload: EnvironmentAction, response: Response):
            op, created = self.start(chat_id, payload)
            response.status_code = 202 if created else 200
            return op

        @router.post("/{chat_id}/environment/rollback")
        def rollback(chat_id: UUID, payload: RollbackRequest):
            with self.chats.execution._lock:
                idle()
                box = self.sandbox(chat_id)
                result = box.versions().rollback(
                    box.metadata()["project_id"],
                    str(payload.expected_version),
                    payload.client_request_id,
                )
                box.pin(uuid4())
                box.record_event("pdf.rollback", result)
                return result


def closing_connection(path):
    """Short transaction used only by the host's isolated verification clone."""
    import sqlite3
    from contextlib import contextmanager

    @contextmanager
    def connection():
        db = sqlite3.connect(path)
        try:
            with db:
                yield db
        finally:
            db.close()

    return connection()
