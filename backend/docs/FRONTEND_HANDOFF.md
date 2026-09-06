# Frontend contract for Anushrut

Rajdeep owns this backend; Anushrut owns the UI. Phase 1 provides real task intake and SQLite persistence. Tasks remain `pending`: planning, Hermes execution, checkpoints, repairs and feedback processing arrive in later phases. Do not show execution starting after submitting a task in this phase.

The default API origin is `http://127.0.0.1:8000`. Allowed browser origins default to `http://localhost:5173` and `http://127.0.0.1:5173`; configure `EPOCH_CORS_ORIGINS` as a JSON list to use another local frontend origin. The server is intended for a single local developer and has no authentication or multi-user isolation.

## Available now

| Request | Success response | Expected error responses |
| --- | --- | --- |
| `GET /api/health` | 200: `{"status":"ok","phase":1,"storage":"ok","execution_enabled":false}` | 503 when storage is unavailable |
| `POST /api/tasks` | 201 for new intake; 200 for an identical retry; both return `Task` | 409 for changed content with the same request ID; 422 for invalid input |
| `GET /api/tasks?limit=20&offset=0` | 200: `TaskList`, newest first | 422 for invalid pagination |
| `GET /api/tasks/{task_id}` | 200: `Task` | 404 for a missing task; 422 for malformed UUID |
| `GET /openapi.json` | FastAPI's concrete live HTTP schema | — |

Generate `client_request_id` once per submission with `crypto.randomUUID()`. Preserve that ID and the submitted content if retrying after a timeout. A newly edited submission needs a new ID. Message and project ID outer whitespace is normalized, so whitespace-only differences are an identical retry. The project ID defaults to `demo`; it is a grouping label, not an authorization boundary.

```json
{
  "client_request_id": "00000000-0000-0000-0000-000000000001",
  "message": "Draft a release checklist.",
  "project_id": "demo"
}
```

`Task` contains `schema_version: 1`, `id`, the nested original `request`, `status`, `created_at`, and `updated_at`. Times use ISO 8601 with an explicit timezone. `TaskList` contains `items`, `total`, `limit`, and `offset`. Messages must be nonblank and at most 16,000 characters; project IDs are nonblank and at most 100. Unknown properties are rejected.

Errors use `{"error":{"code":"...","message":"...","details":[]}}`. Display `message`; for validation errors, `details` contains sanitized field information. Do not depend on exception text or echo stored request text into HTML. API error codes are documented by the backend implementation and its tests; HTTP status governs the behavior above.

## UI fixtures and future contracts

[development.json](../fixtures/development.json) contains an explicit `fixture_only: true` marker and examples shaped as `{"name":"Checkpoint","model":"Checkpoint","value":{...}}`. Every example is validated by tests. These examples are independent screen states for UI development, not a live timeline or proof that a task ran. Clearly label fixture screens and keep fixture data separate from API responses. Fixture URIs and digests do not identify actual artifacts.

[schemas.json](../contracts/schemas.json) maps model names to standalone JSON Schemas. Each model's `$defs` and local references belong to that model schema. Extract the selected model before handing it to a JSON Schema tool. Regenerate with `uv run python scripts/export_contracts.py`; check drift with the same command plus `--check`. [contracts.py](../src/epoch_backend/contracts.py) is the source of truth. All models reject extra properties. Python validators additionally enforce verified-checkpoint evidence, acyclic brief dependencies and event type/payload matching.

Future progress uses a `ProgressEvent` envelope with `schema_version`, UUID `id`, `task_id`, optional `run_id`, positive per-task `sequence`, `type`, `emitted_at`, and typed `payload`. Planned SSE delivery persists sequence numbers, accepts a replay cursor, and lets the UI deduplicate by task and sequence. **There is no SSE endpoint in Phase 1.** Its route, retention and reconnect error behavior will be specified when implemented.

| Future event type | Payload model |
| --- | --- |
| `task.created`, `task.status_changed` | `Task` |
| `brief.created` | `TaskBrief` |
| `checkpoint.updated` | `Checkpoint` |
| `run.updated` | `Run` |
| `repair.updated` | `RepairRecord` |
| `intent.revised` | `IntentRevision` |
| `error` | `ErrorEnvelope` |

Future screens can use these models for checkpoint sources/dependencies/evidence, observable runs and tool calls, user feedback revisions, staged candidates, rejected repair attempts and environment publication/rollback history. `SupervisorIntervention` records task guidance separately from environment changes. Permission and verification records are data contracts; their existence does not enforce isolation or authorize publication. API routes for these operations remain unimplemented.
