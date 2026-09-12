# Epoch backend

**PDF quote spacing fix — implemented but unverified:** a supported source suggestion
could be hidden when the model restored spaces lost during PDF extraction. Matching
now preserves the original source passage while tolerating PDF word spacing. Restart
normal `serve` and refresh the frontend to recheck the saved analysis without a model
call. No settings or migration changes. See [details](docs/PDF_QUOTE_REVIEW_PLAN.md).

**Document-specific noise suggestions — September 12, implemented but unverified:**
local investigation can propose an exact superseded or duplicate PDF and its retained
replacement from recorded/saved text, without manual version labels. Review affected
sources, then Apply filter. Restart normal `serve`, refresh the frontend, and explicitly
rerun an old investigation. No settings or migration changes. See the
[handoff and manual checks](docs/AUTOMATIC_SOURCE_REVIEW_PLAN.md).

**PDF uploads:** the frontend accepts several PDFs in one selection, with serial
per-file receipts and progress. Docker readiness is checked before container creation;
an explicit recovery action handles eligible old cleanup failures. See
[setup and manual checks](docs/PDF_UPLOADS.md). No settings or migration changes.
Implemented but unverified; restart normal `serve` and refresh the frontend.

**Noise workflow:** [setup and manual checks](docs/NOISE_WORKFLOW.md) covers local
issue analysis, source metadata, Documents **Review cleanup → Apply filter → Undo filter**,
optional preview-bound trials and tool-boundary evidence. See the [data-noise example](docs/DATA_NOISE_DEMO.md).
Direct application records user approval, not verified task success. Restart normal
`serve`; existing settings and databases stay in use. A new SQLite policy store is
created within the existing data directory. No new dependency or credential.
Implemented but unverified; current Ollama settings serve noise analysis while Hermes
retains its configured inference provider.

**Conversation workers and live answers:** normal chat retains one initialized worker
for the same conversation and unchanged authorized environment, with default five-minute
idle cleanup. Public answer text is available over operation-scoped SSE; final saved
messages remain authoritative. Optional `EPOCH_CHAT_WORKER_IDLE_SECONDS` is an app-file
setting (process values override it); no credential/data-directory change or manual
migration is required. See [setup, lifecycle and manual checks](docs/CHAT_LATENCY.md).
Implemented but unverified. Restart normal `serve` and the frontend.

**Real chat tracing:** normal Hermes messages now use the Neatlogs SDK automatically
and retain original OTLP in the existing local telemetry database. No new token,
data folder or model setting is required for built-in capture. Synchronize locked
dependencies and restart normal `serve`. See [setup and manual
acceptance](docs/CHAT_TRACES.md). Implemented but unverified.

**Local trace explorer:** [setup and usage](docs/TRACE_EXPLORER.md) covers Neatlogs
capture, persistent original spans and search in the existing workspace. Use
`epoch-backend --env-file .env serve` for chat, the debugger and traces together.
Keep the existing data directory; the separate `trace-debugger` profile is optional
and omits chat/workflow endpoints. Phases 1–2 are implemented but unverified; testing was explicitly
skipped. Capture and browsing need no model. [Feature Phase 3 questions](docs/TRACE_QUESTIONS.md)
now use the installed local Ollama model after an explicit submission; that addition
is also unverified. The guide includes configuration and manual test instructions.

**Current code: Phase 7, with Phase 6/7 additions untested by explicit user request.** See [the development/integration handoff](docs/PHASES_6_7_HANDOFF.md). Earlier validation below applies to the recorded earlier code. Incident and Neatlogs integration adds optional telemetry flags and process-only credentials; see [incident setup](docs/INCIDENTS_SETUP.md).

The backend provides durable task intake, simulated release services, scoped MCP tools, trusted outcome checks and bounded execution through an existing Hermes installation. Phase 4 adds optional OpenAI `gpt-5.6-luna` supervision: sourced release checkpoints, targeted Hermes continuations, clarification and explicit feedback revisions. Intake stays `pending` until a release run is started. Phase 5 adds opt-in generated checklist repair with isolated verification, durable versions and rollback; see [repair setup](docs/REPAIR_SETUP.md).

Rajdeep owns this backend. Anushrut's UI handoff is in [FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md). See [technical decisions](DECISIONS.md), [phase boundaries](PHASES.md), and the repository [status](../docs/status.md).

Actual installed-Hermes control and failure runs, matching executor baselines, and preserved development attempts are in the historical [Phase 3 evidence](fixtures/hermes/README.md). **Phase 4 live omission recovery and feedback acceptance passed** using Luna and the installed Hermes; see the [supervision evidence](fixtures/supervision/README.md) and [validation record](../docs/status.md#phase-4-validation-record). The frontend now consumes Phase 7 supervision/repair contracts and the incident API. Full model-backed browser acceptance remains separate.

## Setup

Install Python 3.12 and uv. From `backend/`, in PowerShell:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
uv run --frozen epoch-backend check-config
uv run --frozen epoch-backend init-db
uv run --frozen epoch-backend serve
```

For a POSIX shell, use `export UV_CACHE_DIR="$PWD/.uv-cache"` before the same uv commands. The lockfile pins the dependencies. Setup, intake and sandbox checks require no model credentials or business-service accounts. Explicit Hermes execution uses its existing model credential; supervised execution also needs the debugger route described in [DEBUGGER_SETUP.md](docs/DEBUGGER_SETUP.md).

The server listens at `http://127.0.0.1:8000`. Open `/docs` for the API explorer, `/openapi.json` for implemented HTTP contracts, `/api/health` for storage health, and `/api/runtime` for Hermes/debugger availability, supervision enablement and limits. Stop with Ctrl+C. `python -m epoch_backend` supports the same commands. Run one server per data directory; a local OS lease prevents competing execution and recovery.

Defaults require no configuration file. To customize them, copy `.env.example` to `.env`, edit it, then use `uv run --frozen epoch-backend --env-file .env serve`. Environment variables override that file. Relative `EPOCH_DATA_DIR` paths resolve against the backend package root; the default database is `backend/data/epoch.sqlite3`. Generated data, `.env`, local caches and virtual environments are ignored by Git. Configuration validation does not create the data directory.

Optional Neatlogs cloud forwarding accepts `NEATLOGS_API_KEY` in this backend `.env`
or the process environment, with process values taking precedence. The key is excluded
from configuration output. Enable forwarding separately with
`EPOCH_NEATLOGS_CLOUD_ENABLED=true`. Existing process-based setups need no migration;
file-based setups must use `--env-file .env`. See [incident setup](docs/INCIDENTS_SETUP.md).

**Phase 5 adds optional `EPOCH_REPAIR_IMAGE`; existing files need no edits. Linux Docker and a locally pulled pinned image are required for repair.** See [repair setup and migration](docs/REPAIR_SETUP.md). Phase 4 needs no new environment settings on the verified existing Hermes/OpenAI setup. The app `.env` file accepts the app settings in [.env.example](.env.example). If you choose the separate API-key debugger route, set `OPENAI_API_KEY` in the terminal/process environment, not in that file; see [debugger setup](docs/DEBUGGER_SETUP.md). Optional `EPOCH_HERMES_HOME` and `EPOCH_HERMES_CHECKOUT` overrides also belong in the process environment and are needed only when automatic discovery cannot find your installation. The Luna model and maximum 20 turns/600 seconds need no environment variables. Future configuration changes must update the example/setup docs and be listed as required or optional in the handoff.

This is an unauthenticated local development service. The CLI accepts loopback bind addresses only; CORS permits the frontend's localhost and 127.0.0.1 ports 5173. Set `EPOCH_CORS_ORIGINS` to an explicit JSON list of local origins if your UI uses a different port. Unexpected browser origins cannot submit tasks or start runs. Deployment, authentication and multiple workers remain outside scope.

## PDF workshop

New chats default to the PDF workshop in the frontend. See [PDF setup and acceptance](docs/PDF_WORKSHOP.md) for the required isolated image, uploads, generated pagination repair, generated merge tool, evidence and rollback. CSV is retired from active execution; its historical records remain on disk.

## Chat and explicit debugger

The normal frontend uses `/api/chats`, separate from release tasks and runs.
Create a conversation with `client_request_id` and optional `project_id`, then
POST `{client_request_id, content}` to `/api/chats/{chat_id}/messages` to start
Hermes. Read the conversation or its operation endpoint for saved results.
Follow-up messages retain visible user/Hermes history. An eligible warm worker also
retains its private history and initialized tools within that conversation. Changed
scope, cancellation, failure or uncertain state discards it. Chat uses the existing
Hermes configuration and authorized simulated tools. Subscribe to
`GET /api/chats/{chat_id}/operations/{operation_id}/events` for provisional public
answer text and stages; read the saved conversation for the final message.

POST `{client_request_id, question}` to `/api/chats/{chat_id}/debugger` only when
an investigation is requested; `question` is optional. This starts one bounded
Luna analysis using the existing debugger connection, independently of Hermes
availability. Opening or refreshing a conversation never starts analysis.
Operations distinguish `kind: chat` from `kind: debugger`; debugger results retain
requirements, supplied evidence, citations and missing information. This endpoint
only investigates. `POST /api/chats/{chat_id}/environment-actions` explicitly starts
the authorized PDF repair or tool creation. Debugger
answers are labeled separately and are not silently injected into Hermes history.

Use the same request ID and payload for an uncertain retry. Restarted operations
are marked interrupted and never automatically resumed. Both operation types
share the existing single-operation lock and cancellation endpoint.

**Setup:** restart the backend to load these routes. No new environment settings,
credentials or manual migration are required. The additive `chats.sqlite3` store
is initialized inside `EPOCH_DATA_DIR`; historical task/run storage is preserved.
Hermes chat requires the existing Hermes setup; investigation requires the
existing [debugger setup](docs/DEBUGGER_SETUP.md). No Docker invocation is needed for investigation. PDF execution and verification
require the separate PDF runtime image.

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

These CLI runs start actual inference and should be run while the HTTP server is stopped, or with a separate `EPOCH_DATA_DIR`. The control should pass; the broken checklist case should fail while retaining the successful ticket and actual failure evidence. Each run uses fresh simulated state and an isolated Hermes home. The last command exits 1 for its expected failed outcome. New runs default to, and cannot exceed, **20 agent turns and 600 seconds**; `--max-turns` and `--timeout` can lower those limits. Historical Phase 3 records remain readable with their original accepted limits. Set `EPOCH_ENABLE_HERMES=false` to disable model execution while keeping intake/sandbox commands usable.

To run through the API, submit a task first, then `POST /api/tasks/{task_id}/runs` with `{"client_request_id":"UUID","workflow":"release","release":"2.4","scenario":"control"}`. Omitting `supervised`, or setting it to false, preserves direct execution with predefined checkpoints and no debugger call. Run submission returns 202, identical retries 200, conflicting IDs or an active executor 409. Only one run is active at a time.

Read `/api/runs/{run_id}` for status, brief/checkpoints, actual executor response, baseline and trusted verification. `/state` returns simulated objects; `/trace?after=SEQUENCE` returns persisted activity; `/events` streams the same activity over SSE and accepts `Last-Event-ID` or `after` for replay. `POST /api/runs/{run_id}/cancel` requests cancellation; inspect the final record because prior effects remain. Server restart marks unfinished runs interrupted and never replays them automatically. Finalization storage failures disable further execution until the state is inspected and the server restarted.

Task success requires both executor completion and passing independent state checks. Tool success, assistant text, or a fixture cannot override missing outcomes. Each run starts a new MCP server; catalog hot reload remains unimplemented. Phase 5 can activate a verified serializer between passes without changing the discovery interface. See the [frontend handoff](docs/FRONTEND_HANDOFF.md) for exact wire contracts.

## Phase 4: supervise and revise a release

The debugger uses exactly **`gpt-5.6-luna`**. Hermes keeps its existing executor implementation, model configuration, system prompt and discovery interface; the supervisor supplies task briefs and recorded continuation instructions. The debugger cannot invoke business tools, edit files or approve its own checkpoints.

If `OPENAI_API_KEY` is present in the backend process environment, the debugger uses the official OpenAI Responses API. Otherwise, it can use an existing Hermes `openai-codex` credential at the official Codex endpoint. That second route has been verified for this machine's Luna connectivity; it is not a universal compatibility guarantee for other accounts. It never changes the configured Hermes model, refreshes credentials, retries automatically or falls back to a different model. On the Codex route the output-token cap is unsupported and disclosed; turn and wall-time limits still apply. See [debugger setup and limitations](docs/DEBUGGER_SETUP.md).

With the HTTP server stopped, inspect configuration and run the supervised omission demonstration:

```powershell
uv run --frozen epoch-backend debugger-info
$run = uv run --frozen epoch-backend run-release --release 2.4 --supervised --demo-omit-notification | ConvertFrom-Json
$run.id
$run.status
$run.supervision.current_revision_id
```

This starts real OpenAI and Hermes inference. The demonstration deliberately asks Hermes to stop after creating the ticket/checklist on its first pass. Trusted checks retain the missing QA checkpoint; Luna should issue a recorded continuation, and the same Hermes session should send the missing message while reusing the existing objects. `--demo-omit-notification` requires `--supervised`. Omit the demo flag for ordinary supervised execution.

The **20 turns / 600 seconds are shared across the debugger and Hermes**, including planning and continuations. A turn is a model request, not an entire workflow or tool call. Limits are enforced by the backend before model requests; cancellation or a limit retains partial work. Progress checks run at meaningful events, and continuation decisions occur between executor passes. `needs_input` asks for a material clarification; `blocked` can identify an environment defect that Phase 4 cannot repair.

Supported customization is deliberately narrow: sourced additional checklist items and exact phrases required in the QA message. Core ticket/checklist/notification requirements and earlier requirements remain mandatory. Requests to remove requirements, change titles/channel/project/release, or apply unsupported subjective criteria stop for clarification rather than silently weakening the checks. Checklist/message updates preserve the existing object IDs and prior content. Opt-in Phase 5 repairs the checklist serializer; missing tools and context defects remain later phases.

After a terminal supervised run, submit explicit feedback against its latest revision:

```powershell
$requestId = [guid]::NewGuid().ToString()
$run = uv run --frozen epoch-backend feedback $run.id --expected-revision $run.supervision.current_revision_id --request-id $requestId --message "Add 'Security review complete' to the checklist. Also include the exact phrase 'QA sign-off required' in the QA message. Keep all earlier work." | ConvertFrom-Json
```

Each explicit feedback or clarification creates a new operation with its own shared budget of up to 20 turns / 600 seconds. Earlier requests, criteria, results and interventions remain in revision history. Reuse the same request ID and identical input for a retry; stale expected revision IDs or conflicting retry content return a conflict. Save the original expected revision when retrying that exact submission. To answer a pending question, use `clarify RUN_ID --expected-revision REVISION_ID --message "Your answer"`; this command is accepted only while the run is `needs_input`. Both commands accept lower `--max-turns` and `--timeout` values.

For HTTP clients:

| Action | Request | Result |
| --- | --- | --- |
| Start supervision | `POST /api/tasks/{task_id}/runs`, adding `"supervised": true` to the release request | `ExecutionRecord`; 202 new / 200 identical retry |
| Add feedback | `POST /api/runs/{run_id}/feedback` | Updated `ExecutionRecord`; 202 new / 200 identical retry |
| Answer a question | `POST /api/runs/{run_id}/clarifications` | Same payload/result as feedback; requires `needs_input` |
| Read earlier outcomes | `GET /api/runs/{run_id}/revisions` | Ordered `SupervisionOperation[]`; empty for direct runs |

Feedback and clarification bodies contain `client_request_id`, `expected_revision_id` and `message`, with optional `max_turns` and `timeout_seconds`. The latest revision ID is in `ExecutionRecord.supervision.current_revision_id`. Existing run/state/trace/SSE routes expose the actual revised result and progress. [FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md) contains complete schemas and error behavior.

The [actual Phase 4 acceptance harness](scripts/run_phase4_acceptance.py) runs the omitted-notification demonstration followed by sourced feedback, checks object reuse and immutable prior history, and verifies that a repeated feedback submission creates no extra operation:

```powershell
uv run --frozen python scripts/run_phase4_acceptance.py --data-dir data/phase4-acceptance
```

This harness invokes real models and retains every attempted run. The final actual acceptance passed:

| Operation | Shared model turns | Demonstrated result |
| --- | --- | --- |
| Omission recovery | 15: 2 Luna + 13 Hermes | One recorded targeted intervention; two passes in the same Hermes session; all three original checks passed |
| Explicit feedback | 7: 1 Luna + 6 Hermes | Added the checklist item and exact QA phrase; all four revised checks passed; the same ticket/checklist/message IDs were retained |

The earlier operation remained unchanged and retrying the same feedback created no new operation. An earlier provider-stream failure is retained as failed evidence; no transport override or model fallback was added. See the [saved supervision evidence](fixtures/supervision/README.md) and [validation record](../docs/status.md#phase-4-validation-record) for identities and limitations. This demonstrates task supervision and additive revision, not persistent environment repair.

## Checks and contract export

Final local verification passed **264 tests**, Ruff lint/format checks across 53 files, contract-export checks, and the actual no-model HTTP/restart smoke test. Two upstream deprecation warnings remain. These local checks are distinct from the actual model acceptance above and from remote CI execution.

```powershell
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen python scripts/export_contracts.py --check
uv run --frozen python scripts/smoke_test.py
```

Contract fixtures are labelled development data and never served as real execution. The API publishes live OpenAPI at `/openapi.json`; running the export script without `--check` regenerates the shared schemas, [execution schemas](contracts/execution-schemas.json), [supervision schemas](contracts/supervision-schemas.json), and examples. The smoke script starts the real CLI server on a temporary loopback port, verifies intake and restart persistence, then stops it and removes its temporary database. CI runs these checks and verifies exports have no drift on Python 3.12. Remote CI execution is distinct from local verification.

## Phase 5: verify and persist a generated repair

```powershell
uv run --frozen epoch-backend repair-info
uv run --frozen epoch-backend run-release --release 2.4 --scenario broken_checklist --repair
uv run --frozen epoch-backend environment --project demo
```

Complete Docker setup first in [REPAIR_SETUP.md](docs/REPAIR_SETUP.md). `--repair`
enables sourced Luna diagnosis and generated serializer code; actual Docker tests,
isolated original-task replay, a fresh variation and healthy regressions must pass
before publication. Hermes then resumes the original task. New runs discover the
persisted project version, while existing runs retain their pinned version.

The user authorized separate verification limits: each verification gets 20 requests
and 600 seconds; the primary work keeps 20 requests/600 active seconds; the complete
repair operation is capped at 60 requests/1,800 wall seconds and two candidates.
Request limits are an inference-usage budget, not a guaranteed monetary cap.
`GET /api/environments/{project_id}` exposes attempts, diffs, evidence and history;
rollback is an explicit idle-only operation. See setup for the full acceptance
harness and [implementation status](../docs/status.md) for demonstrated evidence.
