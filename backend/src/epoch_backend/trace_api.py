"""Read-only trace APIs shared by the regular server and the local collector profile."""

from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime

from epoch_backend.trace_contracts import TraceDetail, TraceList, TraceSpan
from epoch_backend.trace_store import TraceError

Filter = Annotated[str | None, Query(max_length=300)]


def trace_router(store):
    router = APIRouter(prefix="/api/traces", tags=["traces"])

    def invoke(callback, *args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except TraceError as exc:
            return JSONResponse({"error": {"code": exc.code, "message": exc.message, "details": []}},
                                status_code=exc.status)

    @router.get("", response_model=TraceList)
    def traces(
        project_id: Filter = None,
        workflow: Filter = None,
        session_id: Filter = None,
        q: Annotated[str | None, Query(max_length=500)] = None,
        started_after: AwareDatetime | None = None,
        started_before: AwareDatetime | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    ):
        if started_after and started_before and started_after > started_before:
            return JSONResponse({"error": {"code": "invalid_time_range",
                "message": "Start time must precede end time.", "details": []}}, status_code=422)
        return invoke(store.list_traces, project_id=project_id, workflow=workflow,
                      session_id=session_id, q=q, started_after=started_after,
                      started_before=started_before, limit=limit, offset=offset)

    @router.get("/{trace_id}", response_model=TraceDetail)
    def trace(trace_id: str, limit: Annotated[int, Query(ge=1, le=500)] = 200,
              offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0):
        return invoke(store.get_trace, trace_id, limit=limit, offset=offset)

    @router.get("/{trace_id}/spans/{span_id}", response_model=TraceSpan)
    def span(trace_id: str, span_id: str):
        return invoke(store.get_span, trace_id, span_id)

    return router
