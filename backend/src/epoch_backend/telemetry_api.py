"""Local token-protected OTLP transport endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from epoch_backend.telemetry import MAX_BYTES, TelemetryError


def telemetry_router(service):
    router = APIRouter()

    @router.get("/api/telemetry/runtime")
    def runtime():
        return service.runtime_info()

    @router.get("/api/telemetry/traces/{trace_id}/spans/{span_id}")
    def span(trace_id: str, span_id: str):
        try:
            return service.get_span(trace_id, span_id)
        except TelemetryError as exc:
            return JSONResponse(
                {"error": {"code": exc.code, "message": exc.message, "details": []}},
                status_code=exc.status,
            )

    @router.post("/v1/traces")
    async def ingest(request: Request):
        try:
            service.authorize(request.headers.get("x-api-key"))
            content_type = request.headers.get("content-type", "").split(";", 1)[0].strip()
            if content_type != "application/x-protobuf":
                raise TelemetryError(
                    "unsupported_content_type", "Use OTLP application/x-protobuf.", 415
                )
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise TelemetryError("trace_too_large", "Trace request exceeds 4 MiB.", 413)
            result = await run_in_threadpool(
                service.ingest, bytes(body), request.headers.get("content-encoding", "identity")
            )
            return Response(result, media_type="application/x-protobuf")
        except TelemetryError as exc:
            return JSONResponse(
                {"error": {"code": exc.code, "message": exc.message, "details": []}},
                status_code=exc.status,
            )
        except Exception:
            return JSONResponse(
                {
                    "error": {
                        "code": "telemetry_unavailable",
                        "message": "Local ingestion is temporarily unavailable.",
                        "details": [],
                    }
                },
                status_code=503,
            )

    return router
