"""HTTP access to retained incidents; GET never performs model inference."""

from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from epoch_backend.incident_contracts import EvidenceImport, IncidentAction
from epoch_backend.incidents import IncidentError


def incident_router(service):
    router = APIRouter(prefix="/api")

    def invoke(callback, *args):
        try:
            return callback(*args)
        except IncidentError as error:
            return JSONResponse(
                status_code=error.status,
                content={"error": {"code": error.code, "message": error.message, "details": []}},
            )

    @router.get("/incidents")
    def incidents(
        project_id: str | None = None,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        service.refresh_all()
        return invoke(service.list_incidents, project_id, limit, offset)

    @router.get("/incidents/{incident_id}")
    def incident(incident_id: UUID):
        service.refresh_all()
        return invoke(service.get_incident, incident_id)

    @router.get("/evidence/{evidence_id}")
    def evidence(evidence_id: UUID):
        return invoke(service.get_evidence, evidence_id)

    @router.post("/evidence/import")
    def import_evidence(payload: EvidenceImport):
        service.refresh_all()
        return invoke(service.import_records, payload)

    @router.post("/incidents/{incident_id}/analyze")
    def analyze(incident_id: UUID, payload: IncidentAction):
        service.refresh_all()
        return invoke(service.analyze, incident_id, payload)

    @router.post("/incidents/{incident_id}/questions")
    def question(incident_id: UUID, payload: IncidentAction):
        if not payload.question:
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "question_required",
                        "message": "A nonblank question is required.",
                        "details": [],
                    }
                },
            )
        service.refresh_all()
        return invoke(service.analyze, incident_id, payload)

    return router
