"""Explicit local noise actions. GET never invokes a model or publishes a policy."""

import sqlite3
from uuid import UUID
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from epoch_backend import noise_contracts as c
from epoch_backend.trace_store import TraceError


def noise_router(service):
    router = APIRouter(prefix="/api/chats/{chat_id}/noise", tags=["context noise"])

    def invoke(fn, *args):
        try:
            return fn(*args)
        except TraceError as exc:
            return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)
        except (sqlite3.Error, OSError):
            return JSONResponse({"error": {"code": "noise_storage", "message": "Noise storage is unavailable. No acceptance is claimed; inspect and retry with the same request ID."}}, status_code=503)

    @router.get("")
    def workspace(chat_id: UUID):
        return invoke(service.workspace, chat_id)

    @router.get("/records/{record_id}")
    def record(chat_id: UUID, record_id: UUID):
        return invoke(service.get, chat_id, record_id)

    @router.get("/decisions/{record_id}")
    def decision(chat_id: UUID, record_id: UUID):
        return invoke(service.decision, chat_id, record_id)

    @router.post("/analyses", status_code=202)
    async def analyze(chat_id: UUID, payload: c.Analyze):
        return invoke(service.analyze, chat_id, payload)

    @router.post("/sources/metadata")
    def labels(chat_id: UUID, payload: c.LabelSource):
        return invoke(service.labels, chat_id, payload)

    @router.post("/policies")
    def draft(chat_id: UUID, payload: c.Draft):
        return invoke(service.draft, chat_id, payload)

    @router.post("/cleanup-reviews")
    def review_cleanup(chat_id: UUID, payload: c.CleanupReview):
        return invoke(service.review_cleanup, chat_id, payload)

    @router.post("/cleanup-reviews/{review_id}/apply")
    def apply_cleanup(chat_id: UUID, review_id: UUID, payload: c.ApplyCleanup):
        return invoke(service.apply_cleanup, chat_id, review_id, payload)

    @router.post("/policies/{policy_id}/previews")
    def preview(chat_id: UUID, policy_id: UUID, payload: c.Preview):
        return invoke(service.preview, chat_id, policy_id, payload)

    @router.post("/policies/{policy_id}/validations")
    def validate(chat_id: UUID, policy_id: UUID, payload: c.Validation):
        return invoke(service.validate, chat_id, policy_id, payload)

    @router.post("/policies/{policy_id}/activate")
    def activate(chat_id: UUID, policy_id: UUID, payload: c.Activate):
        return invoke(service.activate, chat_id, policy_id, payload)

    @router.post("/rollback")
    def rollback(chat_id: UUID, payload: c.Rollback):
        return invoke(service.rollback, chat_id, payload)

    return router
