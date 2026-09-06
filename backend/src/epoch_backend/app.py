"""HTTP intake and explicit execution; creating a task does not schedule a run."""

import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from epoch_backend.config import Settings
from epoch_backend.contracts import ErrorEnvelope, HealthResponse, Task, TaskCreate, TaskList
from epoch_backend.execution import ExecutionError, ExecutionService
from epoch_backend.execution_api import execution_router
from epoch_backend.incident_api import incident_router
from epoch_backend.sandbox import SandboxError
from epoch_backend.storage import RequestConflict, SQLiteStore
from epoch_backend.telemetry_api import telemetry_router

logger = logging.getLogger(__name__)


def error_response(
    status: int, code: str, message: str, details: list[dict] | None = None
) -> JSONResponse:
    body = ErrorEnvelope(error={"code": code, "message": message, "details": details or []})
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()
    store = SQLiteStore(config.database_path)
    execution = ExecutionService(config, store)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store.initialize()
        execution.initialize()
        try:
            yield
        finally:
            execution.close()

    app = FastAPI(
        title="Epoch Backend",
        version="0.1.0",
        description=(
            "Local task intake, simulated release tools and bounded actual Hermes execution. "
            "Optional Luna supervision, feedback and gated environment repair. "
            "Incident evidence and on-demand analysis; Phases 6/7 live acceptance pending."
        ),
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.settings = config
    app.state.execution = execution
    app.include_router(execution_router(execution))
    app.include_router(incident_router(execution.incidents))
    app.include_router(telemetry_router(execution.telemetry))

    @app.middleware("http")
    async def require_allowed_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and origin is not None
            and origin not in config.cors_origins
        ):
            return error_response(403, "origin_not_allowed", "This browser origin is not allowed.")
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
        allow_credentials=False,
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Never echo request bodies, rejected input values or validator contexts.
        details = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return error_response(422, "validation_error", "Request validation failed.", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        codes = {404: "not_found", 405: "method_not_allowed"}
        message = (
            str(exc.detail) if exc.status_code < 500 else "The request could not be completed."
        )
        return error_response(exc.status_code, codes.get(exc.status_code, "http_error"), message)

    @app.exception_handler(RequestConflict)
    async def request_conflict(request: Request, exc: RequestConflict):
        return error_response(
            409, "request_conflict", "This client_request_id was used for a different request."
        )

    @app.exception_handler(ExecutionError)
    async def execution_error(request: Request, exc: ExecutionError):
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(SandboxError)
    async def sandbox_error(request: Request, exc: SandboxError):
        return error_response(422, exc.code, exc.message)

    async def storage_error(request: Request, exc: Exception):
        logger.error("Storage unavailable (%s)", type(exc).__name__)
        return error_response(503, "storage_unavailable", "Task storage is unavailable.")

    app.add_exception_handler(sqlite3.Error, storage_error)
    app.add_exception_handler(OSError, storage_error)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        logger.error("Unhandled request error (%s)", type(exc).__name__)
        return error_response(500, "internal_error", "An internal error occurred.")

    errors = {422: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope}}

    @app.get(
        "/api/health", response_model=HealthResponse, responses={503: {"model": ErrorEnvelope}}
    )
    def health() -> HealthResponse | JSONResponse:
        if not store.health():
            return error_response(503, "storage_unavailable", "Task storage is unavailable.")
        enabled = execution.runtime_info().execution_enabled
        return HealthResponse(execution_enabled=enabled)

    @app.post(
        "/api/tasks",
        response_model=Task,
        status_code=201,
        responses={
            **errors,
            200: {"model": Task, "description": "Identical request already persisted"},
            403: {"model": ErrorEnvelope},
            409: {"model": ErrorEnvelope},
        },
    )
    def create_task(payload: TaskCreate, response: Response) -> Task:
        task, created = store.create_task(payload)
        response.status_code = 201 if created else 200
        return task

    @app.get("/api/tasks", response_model=TaskList, responses=errors)
    def list_tasks(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> TaskList:
        return store.list_tasks(limit=limit, offset=offset)

    @app.get(
        "/api/tasks/{task_id}",
        response_model=Task,
        responses={**errors, 404: {"model": ErrorEnvelope}},
    )
    def get_task(task_id: UUID) -> Task:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return task

    return app
