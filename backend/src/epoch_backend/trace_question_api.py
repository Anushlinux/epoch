"""A POST explicitly starts one local model request; every GET is a storage read."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response
from fastapi.responses import JSONResponse

from epoch_backend.trace_question_contracts import QuestionCreate, QuestionList, TraceQuestion
from epoch_backend.trace_store import TraceError


def trace_question_router(service):
    router = APIRouter(tags=["trace questions"])

    def invoke(callback, *args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except TraceError as exc:
            return JSONResponse({"error": {"code": exc.code, "message": exc.message, "details": []}}, status_code=exc.status)

    @router.get("/api/trace-questions/runtime")
    def runtime():
        return service.runtime_info()

    @router.post("/api/traces/{trace_id}/questions", response_model=TraceQuestion, status_code=202)
    async def ask(trace_id: str, payload: QuestionCreate, response: Response):
        result = invoke(service.submit, trace_id, payload)
        if isinstance(result, JSONResponse):
            return result
        record, created = result
        response.status_code = 202 if created else 200
        return record

    @router.get("/api/traces/{trace_id}/questions", response_model=QuestionList)
    def questions(trace_id: str, limit: Annotated[int, Query(ge=1, le=20)] = 5,
                  offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0):
        return invoke(service.list, trace_id, limit=limit, offset=offset)

    @router.get("/api/traces/{trace_id}/questions/{question_id}", response_model=TraceQuestion)
    def question(trace_id: str, question_id: UUID):
        return invoke(service.get, trace_id, str(question_id))

    return router
