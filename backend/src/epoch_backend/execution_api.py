"""Actual run/status/trace endpoints for the local frontend."""

import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from epoch_backend.candidate_runner import inspect_runner
from epoch_backend.contracts import ErrorEnvelope
from epoch_backend.execution import TERMINAL, ExecutionService
from epoch_backend.execution_contracts import (
    ExecutionRecord,
    ReleaseRunRequest,
    RunEvent,
    RuntimeInfo,
)
from epoch_backend.repair_contracts import RollbackRequest
from epoch_backend.supervision_contracts import FeedbackRequest, SupervisionOperation


def execution_router(service: ExecutionService) -> APIRouter:
    router = APIRouter(
        prefix="/api",
        responses={status: {"model": ErrorEnvelope} for status in (403, 404, 409, 422, 503)},
    )

    @router.get("/runtime", response_model=RuntimeInfo)
    def runtime_info():
        return service.runtime_info()

    @router.get("/repair/runtime")
    def repair_runtime():
        return inspect_runner(service.settings.repair_image)

    @router.get("/environments/{project_id}")
    def environments(project_id: str):
        return service.environments.inspect(project_id)

    @router.post("/environments/{project_id}/rollback")
    def rollback(project_id: str, payload: RollbackRequest):
        return service.rollback(
            project_id, str(payload.expected_version), payload.client_request_id
        )

    @router.post(
        "/tasks/{task_id}/runs",
        response_model=ExecutionRecord,
        status_code=202,
        responses={200: {"model": ExecutionRecord, "description": "Idempotent retry"}},
    )
    def start_run(task_id: UUID, payload: ReleaseRunRequest, response: Response):
        record, created = service.start(task_id, payload)
        response.status_code = 202 if created else 200
        return record

    @router.get("/tasks/{task_id}/runs", response_model=list[ExecutionRecord])
    def task_runs(task_id: UUID):
        if service.tasks.get_task(task_id) is None:
            raise HTTPException(404, "Task not found.")
        return service.store.list(task_id)

    @router.get("/runs/{run_id}", response_model=ExecutionRecord)
    def get_run(run_id: UUID):
        return service.get(run_id)

    @router.get("/runs/{run_id}/revisions", response_model=list[SupervisionOperation])
    def run_revisions(run_id: UUID):
        record = service.get(run_id)
        return record.supervision.operations if record.supervision else []

    @router.post(
        "/runs/{run_id}/feedback",
        response_model=ExecutionRecord,
        status_code=202,
        responses={200: {"model": ExecutionRecord, "description": "Idempotent retry"}},
    )
    def submit_feedback(run_id: UUID, payload: FeedbackRequest, response: Response):
        record, created = service.feedback(run_id, payload)
        response.status_code = 202 if created else 200
        return record

    @router.post(
        "/runs/{run_id}/clarifications",
        response_model=ExecutionRecord,
        status_code=202,
        responses={200: {"model": ExecutionRecord, "description": "Idempotent retry"}},
    )
    def submit_clarification(run_id: UUID, payload: FeedbackRequest, response: Response):
        record, created = service.feedback(run_id, payload, clarification=True)
        response.status_code = 202 if created else 200
        return record

    @router.post("/runs/{run_id}/cancel", response_model=ExecutionRecord, status_code=202)
    def cancel_run(run_id: UUID):
        return service.cancel(run_id)

    @router.get("/runs/{run_id}/state")
    def run_state(run_id: UUID):
        return service.sandbox(service.get(run_id)).snapshot()

    @router.get("/runs/{run_id}/trace", response_model=list[RunEvent])
    def run_trace(run_id: UUID, after: int = Query(default=0, ge=0)):
        return service.sandbox(service.get(run_id)).events(after=after)

    @router.get("/runs/{run_id}/events")
    async def run_events(
        run_id: UUID,
        request: Request,
        after: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None),
    ):
        record = service.get(run_id)
        if last_event_id is not None:
            try:
                cursor = int(last_event_id)
                if cursor < 0:
                    raise ValueError
                after = max(after, cursor)
            except ValueError as exc:
                raise HTTPException(422, "Last-Event-ID must be a nonnegative sequence.") from exc
        sandbox = service.sandbox(record)

        async def stream():
            cursor = after
            idle = 0
            while not await request.is_disconnected():
                events = await asyncio.to_thread(sandbox.events, after=cursor)
                for event in events:
                    cursor = event["sequence"]
                    yield f"id: {cursor}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
                current = await asyncio.to_thread(service.get, run_id)
                if current.status in TERMINAL:
                    # Drain any events added between the initial read and terminal status.
                    for event in await asyncio.to_thread(sandbox.events, after=cursor):
                        cursor = event["sequence"]
                        yield f"id: {cursor}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
                    break
                idle += 1
                if idle % 30 == 0:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.25)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
