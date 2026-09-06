# Incident integration contract

Implementation plan: finish Phase 7 frontend compatibility; add incident storage and
HTTP contracts; connect Neatlogs transport and incident UI; wire execution refresh;
run focused checks and record limits. Existing runtime repair authority is unchanged.

## Shared Python boundary

`IncidentService(data_dir: Path, execution=None)` owns `incidents.sqlite3`.
It exposes `initialize()`, `refresh_run(record, sandbox, trigger=None)`, `refresh_all()`,
`ingest_evidence(records: list[dict])`, `list_incidents(project_id=None, limit=50,
offset=0)`, `get_incident(id)`, `get_evidence(id)`, `import_records(payload)`,
and `analyze(id, payload)`. Refresh must be idempotent. Primary wiring calls refresh
after persisted execution/check boundaries and before repair diagnosis. The service
may read execution stores but never initiate execution or repair.

Normalized evidence fields: `source_type` (`epoch`, `trace`, `slack`, `support`),
`source_id`, `timestamp`, `project_id`, `text`, `structured_payload`, optional
`task_id`, `run_id`, `revision_id`, `workflow`, `tool`, `error_code`, `check_id`,
`environment_version`, `source_ref`, `trace_id`, `span_id`, `native_event_id`.
Imports/OTLP correlations are untrusted; only the native projection can establish
trusted facts. Deduplicate native event re-imports without overwriting native facts.

## HTTP contract

- `GET /api/incidents?project_id=&limit=50&offset=0` returns
  `{items: IncidentSummary[], total: number, warnings: string[]}`.
- `GET /api/incidents/{id}` returns the summary plus `evidence`, `decisions`,
  `repairs`, `recurrence`, `analyses`, `warnings`.
- `GET /api/evidence/{id}` returns individually inspectable normalized evidence.
- `POST /api/evidence/import` accepts `{client_request_id: UUID, records: [...]}`.
  Records require `source_type` (`slack` or `support`), `source_id`, `timestamp`,
  `project_id`, `text`; optional `source_ref`, `task_id`, `run_id`, `workflow`.
  Returns `{id, imported, deduplicated, evidence_ids, incident_ids}`.
- `POST /api/incidents/{id}/analyze` and `/questions` accept
  `{client_request_id: UUID, question?: string}`; questions requires nonblank text.
  Return `{id, status, answer, evidence_ids, hypotheses, missing_evidence, error}`.
  One 60-second model request per action, identical retries return saved outcome;
  interrupted/failed requests are never silently repeated.
- `GET /api/telemetry/runtime` returns local collector readiness, cloud configured
  state, queue/delivery/failure counts and safe warnings; never credentials.
- `POST /v1/traces` accepts gzip OTLP protobuf using `x-api-key` local token.
- `GET /api/telemetry/traces/{trace_id}/spans/{span_id}` exposes the preserved local source.

IncidentSummary: `id`, `title`, `status` (`open` or `monitoring`), `project_id`,
`workflow`, `opened_at`, `updated_at`, `evidence_count`, `run_ids`, `signature`.
Evidence includes stable `id` and `trusted` boolean. Decisions contain `evidence_id`,
`decision` and `reasons` (string array). Repairs retain existing report IDs/status.
Recurrence has `before`, `after` each `{affected, comparable}`, and separately
`recovered_runs`, `verification_runs`, `excluded_runs` (counts).

Router factory: `incident_router(service)`; normal errors use the existing API
envelope. GET refreshes local projection but never invokes a model.

## Telemetry ownership

`TelemetryService(settings, incidents)` owns durable `telemetry.sqlite3` and exposes
`initialize()`, `close()`, `project_events(record, sandbox)`, `runtime_info()`.
Router factory: `telemetry_router(service)`. Project native saved events with stable
IDs, real times and bounded structural attributes. Transport failures cannot change
task success. Ingestion calls the shared normalized-evidence boundary.

Settings: `EPOCH_TELEMETRY_ENABLED=true`, `EPOCH_NEATLOGS_CLOUD_ENABLED=false`.
Process-only credentials: `EPOCH_TELEMETRY_TOKEN` for local ingestion and
`NEATLOGS_API_KEY` for cloud forwarding. No cloud endpoint override in user input;
production forwarding targets the official Neatlogs ingestion service.

## Validation boundary

Use focused unit/API/browser checks and one actual SDK-to-local collector smoke.
Do not run live model repairs or authenticated cloud acceptance. Keep their status
unverified. Existing Docker publication gates remain mandatory in the product.
