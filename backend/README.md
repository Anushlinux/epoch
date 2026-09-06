# Epoch backend

The backend provides durable task intake, simulated release services, scoped MCP tools, trusted outcome checks and bounded execution through an existing Hermes installation. Intake stays `pending` until an explicit release run is started. Phase 4 automatic planning/continuation/feedback and Phase 5 generated repairs remain unimplemented.

Rajdeep owns this backend. Anushrut's UI handoff is in [FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md). See [technical decisions](DECISIONS.md), [phase boundaries](PHASES.md), and the repository [status](../docs/status.md).

Actual installed-Hermes control and failure runs, matching executor baselines, and preserved development attempts are in the [Phase 3 evidence](fixtures/hermes/README.md).

## Setup

Install Python 3.12 and uv. From `backend/`, in PowerShell:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
uv run --frozen epoch-backend check-config
uv run --frozen epoch-backend init-db
uv run --frozen epoch-backend serve
```

For a POSIX shell, use `export UV_CACHE_DIR="$PWD/.uv-cache"` before the same uv commands. The lockfile pins the dependencies. Setup, intake and sandbox checks require no model credentials or business-service accounts; explicit Hermes execution uses its existing configured model credential.

The server listens at `http://127.0.0.1:8000`. Open `/docs` for the API explorer, `/openapi.json` for implemented HTTP contracts, `/api/health` for storage health, and `/api/runtime` for Hermes availability and capabilities. Stop with Ctrl+C. `python -m epoch_backend` supports the same commands. Run one server per data directory; a local OS lease prevents competing execution and recovery.

Defaults require no configuration file. To customize them, copy `.env.example` to `.env`, edit it, then use `uv run --frozen epoch-backend --env-file .env serve`. Environment variables override that file. Relative `EPOCH_DATA_DIR` paths resolve against the backend package root; the default database is `backend/data/epoch.sqlite3`. Generated data, `.env`, local caches and virtual environments are ignored by Git. Configuration validation does not create the data directory.

This is an unauthenticated local development service. The CLI accepts loopback bind addresses only; CORS permits the frontend's localhost and 127.0.0.1 ports 5173. Set `EPOCH_CORS_ORIGINS` to an explicit JSON list of local origins if your UI uses a different port. Unexpected browser origins cannot submit tasks or start runs. Deployment, authentication and multiple workers remain outside scope.

## Try task intake

In a second PowerShell terminal:

```powershell
$payload = @{
    client_request_id = [guid]::NewGuid().ToString()
    message = "Prepare the release checklist"
    project_id = "demo"
} | ConvertTo-Json
$task = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/tasks -ContentType application/json -Body $payload
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/tasks/$($task.id)"
```

Retain the same `client_request_id` when retrying a submission: an identical normalized request returns the saved task with HTTP 200; a new request returns 201; changing its content under that ID returns 409. `project_id` is a label at this stage, not an access grant. Restarting the server retains tasks. To start a separate empty store, set `EPOCH_DATA_DIR` to another directory.

## Phase 2: inspect the sandbox

No model or provider credential is needed for these commands:

```powershell
$sandbox = uv run --frozen epoch-backend sandbox init --scenario control --project demo --release 2.4 | ConvertFrom-Json
uv run --frozen epoch-backend sandbox discover $sandbox.sandbox_id
uv run --frozen epoch-backend sandbox describe $sandbox.sandbox_id tickets.create
uv run --frozen epoch-backend sandbox state $sandbox.sandbox_id
uv run --frozen epoch-backend sandbox events $sandbox.sandbox_id
```

Use `sandbox invoke ID TOOL --arguments JSON` with the described schema to perform an operation. `sandbox check ID` evaluates actual state; it exits 1 when required outcomes are missing. `sandbox reset ID` restores the same setup, clears simulated effects and idempotency receipts, and retains prior evidence under an earlier generation. Administrative reset/evaluation never appear in MCP tool discovery.

Scenarios are `control`, `broken_checklist`, `missing_lookup`, and `outdated_context`. Tickets, checklist pages, messages, directory records and versioned runbooks are local simulations, with `simulated://` object references. The broken adapter serializes checklist items incorrectly and the service rejects that payload. Directory lookup is deliberately absent. Historical guidance can direct a successful message call to the wrong channel; independent checks still fail that business outcome.

## Phase 3: actual Hermes execution

Use the already installed Hermes and its configured provider, as detailed in [HERMES_SETUP.md](docs/HERMES_SETUP.md). The model receives synthetic task/tool data over that existing remote route; no live Jira/Notion/Slack operations occur. Personal Hermes sessions/configuration are preserved.

```powershell
uv run --frozen epoch-backend hermes-info
uv run --frozen epoch-backend run-release --release 2.4 --scenario control
uv run --frozen epoch-backend run-release --release 2.4 --scenario broken_checklist
```

These CLI runs start actual inference and should be run while the HTTP server is stopped, or with a separate `EPOCH_DATA_DIR`. The control should pass; the broken checklist case should fail while retaining the successful ticket and actual failure evidence. Each run uses fresh simulated state and an isolated Hermes home. The last command exits 1 for its expected failed outcome. A run is limited to 16 turns/180 seconds by default; the API caps overrides at 30 turns/300 seconds. Set `EPOCH_ENABLE_HERMES=false` to disable model execution while keeping intake/sandbox commands usable.

To run through the API, submit a task first, then `POST /api/tasks/{task_id}/runs` with `{"client_request_id":"UUID","workflow":"release","release":"2.4","scenario":"control"}`. Explicit template selection supplies predefined checkpoints; arbitrary request planning is Phase 4. Run submission returns 202, identical retries 200, conflicting IDs or an active executor 409. Only one run is active at a time.

Read `/api/runs/{run_id}` for status, brief/checkpoints, actual executor response, baseline and trusted verification. `/state` returns simulated objects; `/trace?after=SEQUENCE` returns persisted activity; `/events` streams the same activity over SSE and accepts `Last-Event-ID` or `after` for replay. `POST /api/runs/{run_id}/cancel` requests cancellation; inspect the final record because prior effects remain. Server restart marks unfinished runs interrupted and never replays them automatically. Finalization storage failures disable further execution until the state is inspected and the server restarted.

Task success requires both executor completion and passing independent state checks. Tool success, assistant text, or a fixture cannot override missing outcomes. Each run starts a new MCP server; mid-run catalog hot reload and publication remain unimplemented. See the [frontend handoff](docs/FRONTEND_HANDOFF.md) for exact wire contracts.

## Checks and contract export

```powershell
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen python scripts/export_contracts.py --check
uv run --frozen python scripts/smoke_test.py
```

Contract fixtures are labelled development data and never served as real execution. The API publishes live OpenAPI at `/openapi.json`; running the export script without `--check` regenerates the shared schema bundle and examples. The smoke script starts the real CLI server on a temporary loopback port, verifies intake and restart persistence, then stops it and removes its temporary database. CI runs these checks and verifies exports have no drift on Python 3.12. Remote CI execution is distinct from local verification.
