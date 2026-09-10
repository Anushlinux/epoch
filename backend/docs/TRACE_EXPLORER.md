# Local Neatlogs trace explorer — Phases 1 and 2

**Implemented but unverified.** The user explicitly requested development without
tests, SDK probes, example execution, browser acceptance or model calls. The commands
below are usage instructions, not a record of successful runtime acceptance.

Epoch receives Neatlogs SDK spans over local HTTP and retains their original OTLP
payloads in SQLite. A separate projection makes names, inputs, outputs and errors
searchable. The browser shows traces, their recorded hierarchy and original evidence.
Raindrop Workshop is a workflow reference; no Raindrop installation or API is used.
AI investigation and all later feature phases are outside this delivery.

## Required setup

Python 3.12, uv and Node.js are required. Neatlogs is already declared in the backend
development dependency group; synchronize the existing lock without upgrading it.
In a PowerShell terminal, from `backend/`:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
$env:EPOCH_TELEMETRY_TOKEN = Read-Host "Choose a local collector token"
$env:EPOCH_DATA_DIR = "data/trace-explorer"
$env:EPOCH_NEATLOGS_CLOUD_ENABLED = "false"
uv run --frozen epoch-backend serve --profile trace-debugger
```

The token is a local SDK-to-collector credential. Choose a nonempty value and use
that same value in the example terminal. Do not put it in a committed file or the
browser. No Neatlogs cloud credential, Hermes setup, Docker or local model is needed.

The profile starts telemetry and its index without initializing task execution,
incidents, chat or repairs. It uses the existing exclusive server lease, so two
profiles cannot write the same data directory simultaneously. It rejects
`EPOCH_NEATLOGS_CLOUD_ENABLED=true`, even when inherited from a process or app file.
Run the regular `serve` command to retain Epoch's complete chat/repair API; it also
exposes the trace read endpoints, with its existing separately configured cloud
forwarding behavior. The browser reports that behavior explicitly.

## Open the interface

In a second terminal, from the repository root:

```powershell
npm run dev --prefix frontend
```

Open [Traces](http://127.0.0.1:5173/traces). The default API origin is
`http://127.0.0.1:8000`. Connection settings accept a loopback HTTP origin only.
No model call, execution or repair starts when opening or refreshing this page.

If port 8000 is occupied, choose `EPOCH_PORT=8001` in the collector terminal and
connect the browser to `http://127.0.0.1:8001`. Pass that same endpoint to the example.
An alternate frontend port must appear in the backend's allowed CORS origins.

## Run the supplied SDK example yourself

In another PowerShell terminal, from `backend/`:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
$env:EPOCH_TELEMETRY_TOKEN = Read-Host "Enter the same local collector token"
uv run --frozen python scripts/neatlogs_trace_example.py
```

The example executes ordinary Python functions with synthetic invoices. It does
not call a model or issue a real refund. The selection function deliberately picks
the first invoice, even when the request names the second. Four nested spans record
the request, invoice lookup, selection and simulated result. No manufactured
exception is added: absence of a recorded error does not imply the task succeeded.
The printed trace ID identifies attempted capture; inspect collector storage to
confirm receipt. The script flushes and shuts down the SDK before exiting.

Optional example arguments:

```powershell
uv run --frozen python scripts/neatlogs_trace_example.py --invoice-id INV-41 --session-id review-session
uv run --frozen python scripts/neatlogs_trace_example.py --endpoint http://127.0.0.1:8001 --project-id trace-demo
```

The first variation requests the first invoice and serves as a healthy control for
manual inspection. Neither command was executed as part of this delivery.

## Connect another application

Use the application's installed Neatlogs SDK. Initialize it once with
`api_key=os.environ["EPOCH_TELEMETRY_TOKEN"]` and the local collector's base URL as
`endpoint`. Instrument the workflow root and the tool functions whose inputs and
outputs matter. Use the SDK's documented client wrappers for model calls in your
own application; that application's model routing remains its responsibility.

Neatlogs exports to `/v1/traces` using OTLP HTTP protobuf. The collector accepts
identity or gzip encoding with `x-api-key`. Existing 4 MiB compressed/decoded and
1,000-spans-per-request limits apply. Logs/media endpoints and OTLP JSON are not
implemented; leave log capture and media uploads disabled for this collector.
Source masking/redaction must be configured before export when needed: original
local payloads can contain sensitive prompts and tool results.

Set `epoch.project_id` on spans when a project is known. The explorer also recognizes
`project_id` and `neatlogs.workflow.project_id`. Spans without a project use
`unassigned`; trace summaries show recorded project labels. Workflow/session values
can be present on the root only; trace filters match any span in the trace. A trace
is identified by its OTLP ID, not by an Epoch task or Hermes conversation ID.

Official reference: [Neatlogs Python SDK](https://docs.neatlogs.com/sdk/python).
Source compatibility was reviewed against the installed SDK; live compatibility
remains unverified.

## Read API and CLI

| Interface | Contract |
| --- | --- |
| `GET /api/traces` | `items`, `total`, `limit`, `offset`, `warnings`; default 50, maximum 100 traces |
| `GET /api/traces/{trace_id}` | `trace`, `spans`, `total`, `limit`, `offset`, `warnings`; default 200, maximum 500 spans |
| `GET /api/traces/{trace_id}/spans/{span_id}` | Complete normalized span with input/output, attributes, resource, events, links, timing and original `source_ref` |
| `GET /api/telemetry/traces/{trace_id}/spans/{span_id}` | Preserved original OTLP source and prior structural evidence |
| `GET /api/telemetry/runtime` | Existing collection/export status plus `trace_index` readiness, backlog, failures and conflict count |
| `POST /v1/traces` | Existing token-authenticated SDK ingestion |

List filters: `project_id`, `workflow`, `session_id`, `q`, `started_after`,
`started_before`. Dates require an ISO timestamp with timezone. Bounds are inclusive
and refer to the first observed span start in the trace. Search treats input as
literal terms, not SQL or FTS syntax. All terms must match one span's indexed fields;
an exact trace or span ID is also supported. Results are ordered newest first.

From `backend/`, with the collector running:

```powershell
uv run --frozen epoch-backend traces --project-id trace-demo --q INV-42
uv run --frozen epoch-backend trace TRACE_ID
uv run --frozen epoch-backend trace TRACE_ID --span-id SPAN_ID
uv run --frozen epoch-backend trace TRACE_ID --span-id SPAN_ID --raw
uv run --frozen epoch-backend telemetry-info
```

Replace IDs with values returned by your collector. CLI commands read the running
HTTP API and do not acquire another database lease. Use the collector's `EPOCH_PORT`
when connecting to an alternate port. JSON output comes from the saved records.

## Storage, migration and limitations

All trace data is under the selected `EPOCH_DATA_DIR/telemetry.sqlite3`. Startup adds
`trace_spans`, `trace_span_fts`, `trace_index_state`, `trace_index_failures` and
`span_conflicts`. Original spans and older databases are preserved; no manual reset
is required. Stop the server before backing up the complete data directory. Do not
delete the original `spans` table to clear a search issue.

Indexing uses batches of 200 with an atomic persistent cursor. Restart resumes from
the last committed batch. Failed normalization is recorded and skipped so later
spans can be indexed; original sources remain accessible by ID. Search indexes up
to 64,000 characters per field; normalized details and original sources are retained
in full. Historical native structural events lacking original OTLP are excluded and
counted explicitly. A projection version mismatch disables the index, not collection.

Identical SDK retries do not duplicate stored spans. A conflicting identity rejects
the complete incoming batch with HTTP 409, preserving existing spans. Conflicting
payloads and their hashes are retained in `span_conflicts`; its count is exposed in
runtime status. When a new batch contains conflicting versions of the same span,
both versions are retained there. SDK delivery retry behavior is not a successful
acceptance claim.

The browser refreshes every five seconds while visible, preserves selection in the
URL and retains the previous view on connection failure. Parent spans can arrive
later. Paginated trees distinguish missing parents from parents on another page;
malformed or excessively deep hierarchy is displayed separately. Timing and error
indicators describe captured execution only. There is no automatic task evaluator.

## Settings and validation status

Required process-only setting: `EPOCH_TELEMETRY_TOKEN`, also provided to the SDK
process. Optional app-file or process settings: `EPOCH_DATA_DIR`, `EPOCH_PORT`,
`EPOCH_CORS_ORIGINS` and existing telemetry enablement. `--profile` is a CLI option,
not a new environment variable. `.env` files are loaded only with `--env-file PATH`,
before the subcommand; process values take precedence. No new credential is needed.

Dependency synchronization and source review were performed. Tests, syntax/lint
commands, SDK probes, sample execution, browser checks and model calls were skipped
at the user's request. Runtime acceptance remains pending. Later phases require a
separate user instruction.
