"""Local-only collector application. No executor, incidents or repairs are initialized."""

import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from epoch_backend.config import Settings
from epoch_backend.execution import ServerLease
from epoch_backend.telemetry import TelemetryService
from epoch_backend.telemetry_api import telemetry_router
from epoch_backend.trace_api import trace_router
from epoch_backend.trace_question_api import trace_question_router
from epoch_backend.trace_questions import TraceQuestions


def create_trace_app(settings: Settings):
    # An inherited .env must not silently enable cloud forwarding in this profile.
    if settings.neatlogs_cloud_enabled:
        raise ValueError("trace-debugger requires EPOCH_NEATLOGS_CLOUD_ENABLED=false")
    service = TelemetryService(settings)
    questions = TraceQuestions(settings, service.traces)
    lease = ServerLease(settings.data_dir / "execution.lock")

    @asynccontextmanager
    async def lifespan(app):
        lease.acquire()
        try:
            service.initialize()
            questions.initialize()
            yield
        finally:
            await questions.close()
            service.close()
            lease.release()

    app = FastAPI(title="Epoch local trace explorer", version="0.1.0", lifespan=lifespan)
    app.state.telemetry = service
    app.state.settings = settings
    app.state.trace_questions = questions
    app.include_router(telemetry_router(service))
    app.include_router(trace_router(service.traces))
    app.include_router(trace_question_router(questions))
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
                       allow_credentials=False)

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in settings.cors_origins:
            return JSONResponse({"error": {"code": "origin_not_allowed",
                "message": "This browser origin is not allowed.", "details": []}}, status_code=403)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": {"code": "validation_error",
            "message": "Request validation failed.",
            "details": [{"loc": list(error["loc"]), "type": error["type"]} for error in exc.errors()]}},
            status_code=422)

    async def storage_error(request, exc):
        return JSONResponse({"error": {"code": "storage_unavailable",
            "message": "Local trace storage is unavailable.", "details": []}}, status_code=503)

    app.add_exception_handler(sqlite3.Error, storage_error)
    app.add_exception_handler(OSError, storage_error)

    @app.get("/api/health")
    def health():
        runtime = service.runtime_info()
        return {"status": "ok", "profile": "trace-debugger", "execution_enabled": False,
                "local_only": True, "trace_index_ready": runtime["trace_index"]["ready"]}

    return app
