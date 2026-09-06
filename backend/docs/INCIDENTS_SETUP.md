# Incidents and Neatlogs setup

Epoch groups saved execution evidence into inspectable incidents. Slack/support
JSON imports and Neatlogs traces add related evidence. Analyze and question actions
use the existing Luna route only when explicitly requested. Opening an incident
does not call a model. Incident text never authorizes a repair: the existing
supported trigger, opt-in, Docker checks and publication controller retain that role.

## Required and optional setup

From `backend/`, run `uv sync --frozen` after updating the checkout. Start the backend
with `uv run --frozen epoch-backend serve`, then run `npm run dev --prefix frontend`
from the repository root. Connect the frontend to the backend's loopback origin.

Existing `.env` files need no edits for local incidents. Two optional app settings
are added to [.env.example](../.env.example):

| App setting | Default | Effect |
| --- | --- | --- |
| `EPOCH_TELEMETRY_ENABLED` | `true` | Enable the telemetry service; a token is still required for SDK ingestion |
| `EPOCH_NEATLOGS_CLOUD_ENABLED` | `false` | Explicitly enable cloud forwarding when a cloud key is present |

`NEATLOGS_API_KEY` is optional and accepted in the backend `.env` file or process
environment. Process values take precedence. To load the file, start from `backend/`
with `uv run --frozen epoch-backend --env-file .env serve`. Existing process-based
setups need no changes. If the key previously caused an "Extra inputs are not
permitted" error, keep it in `.env` and restart with this command after updating.
The key is excluded from configuration output. Cloud forwarding still requires
`EPOCH_NEATLOGS_CLOUD_ENABLED=true`; no database migration is needed.

These other credentials belong only in the backend **process environment**, not the
app `.env` file or browser:

- `EPOCH_TELEMETRY_TOKEN`: a local token you choose for SDK-to-Epoch ingestion.
- `OPENAI_API_KEY`: optional alternative to the existing configured Hermes/Codex
  route; see [debugger setup](DEBUGGER_SETUP.md).

Keep all credentials out of the browser and never commit them.
The local token and cloud key are different credentials. Incoming authentication
headers are never reused for cloud requests.

Docker is unnecessary for incident storage, imports and telemetry. Generated repair
verification and published Python artifacts still require the existing Linux Docker
setup and locally pulled digest-pinned image in [repair setup](REPAIR_SETUP.md).
Ollama, local model downloads and SaaS OAuth connections are not required.

Startup adds `incidents.sqlite3` and `telemetry.sqlite3` under `EPOCH_DATA_DIR`.
No manual migration, database reset or deletion of previous evidence is required.
Back up the entire data directory with the server stopped. Existing run and
environment stores remain authoritative; projection cursors allow catch-up.

## Send Neatlogs SDK traces locally

Configure the local token in both processes, then use the SDK's custom endpoint:

```python
import os
import neatlogs

neatlogs.init(
    api_key=os.environ["EPOCH_TELEMETRY_TOKEN"],
    endpoint="http://127.0.0.1:8000",
    workflow_name="release",
)

with neatlogs.trace("Observed release check", kind="GUARDRAIL") as span:
    span.set_attribute("epoch.project_id", "demo")
    span.set_attribute("epoch.workflow", "release")

neatlogs.flush()
neatlogs.shutdown()
```

The collector accepts `POST /v1/traces` with `x-api-key`, using gzip-compressed
OTLP protobuf. SDK export needs a key even for a local custom endpoint. The local
token provides that key without a Neatlogs cloud account. See the official
[SDK configuration](https://docs.neatlogs.com/sdk/python) and
[transport source](https://github.com/neatlogs/neatlogs/blob/main/neatlogs/init.py).

Set `EPOCH_NEATLOGS_CLOUD_ENABLED=true` and configure `NEATLOGS_API_KEY` to forward
structural telemetry to Neatlogs. Raw prompts, arguments, tool results, documents
and private reasoning are excluded from the export allowlist. Cloud failures retain
local evidence and expose delivery/retry status at `/api/telemetry/runtime`. Enabling
cloud forwarding at restart also queues previously retained structural spans. Export
uses batches of up to 100 spans, with at most three attempts per span.
Configured credentials are not proof of delivery; check the returned status and
your Neatlogs project during acceptance.

## Import reports and investigate

The Incidents screen accepts a JSON array of Slack/support records, for example:

```json
[
  {
    "source_type": "slack",
    "source_id": "sample-report-1",
    "timestamp": "2026-09-06T12:00:00Z",
    "project_id": "demo",
    "workflow": "release",
    "text": "Illustrative report: release checklist creation failed."
  }
]
```

This is illustrative input, not evidence of a real Slack message. The HTTP API
wraps records in `{ "client_request_id": "UUID", "records": [...] }` and returns
an import receipt. Retain the same request ID for an identical retry. Changed
content under a used source/request identity returns a conflict.

Use the incident view to inspect source records, inclusion/exclusion explanations,
related runs, repair reports and measured recurrence. Imported reports remain
untrusted statements. Analysis answers cite only the selected evidence and retain
hypotheses and missing information. Each explicit Analyze/question action permits
one Luna request with a 60-second deadline. Failed or interrupted actions remain
saved and are not silently retried under the same request identity.

## CLI inspection and explicit actions

With the backend running, use these commands from `backend/`. They call the local
HTTP API, so they do not acquire a competing execution lease:

```sh
uv run --frozen epoch-backend incidents --project-id demo
uv run --frozen epoch-backend incident INCIDENT_UUID
uv run --frozen epoch-backend evidence EVIDENCE_UUID
uv run --frozen epoch-backend telemetry-info
uv run --frozen epoch-backend import-evidence reports.json --request-id REQUEST_UUID
uv run --frozen epoch-backend analyze-incident INCIDENT_UUID --request-id REQUEST_UUID
uv run --frozen epoch-backend ask-incident INCIDENT_UUID "What changed?" --request-id REQUEST_UUID
```

Replace identifiers with actual values. Create a fresh request UUID for each new
import/analysis/question; retain it for identical retries. Import JSON may embed
`client_request_id` instead. CLI writes print the retained request ID before dispatch.
Analysis and questions invoke Luna; list/detail/status commands do not.

Original OTLP sources are available at
`/api/telemetry/traces/{trace_id}/spans/{span_id}` and linked from evidence records.
Local raw sources are retained even when normalized evidence is rejected. The
normalization failure count appears in telemetry readiness details.

## Verification limits

The runtime API remains Phase 7. Phase 6/7 live repair acceptance remains pending.
Focused integration results are recorded in [status](../../docs/status.md).
SDK-to-local ingestion, controlled transport checks, authenticated cloud delivery,
and full Hermes/Luna repair workflows are separate claims. Live Jira/Notion/Slack,
Workshop and production deployment are outside this integration.
