# Frontend contract for Anushrut

Rajdeep owns the backend; Anushrut owns the UI. The implemented interface accepts tasks, explicitly starts the supported release workflow, exposes its sandbox state and execution evidence, and reports independently checked results. Task submission alone still leaves a task `pending`. Automatic planning, corrective supervision, feedback revisions and environment repair belong to later phases.

This document describes the implemented HTTP contract. Actual installed-Hermes/model acceptance results and evidence gaps are recorded separately in [implementation status](../../docs/status.md). Installation detection alone does not prove a model call will succeed.

The default API origin is `http://127.0.0.1:8000`. Allowed browser origins default to `http://localhost:5173` and `http://127.0.0.1:5173`; configure `EPOCH_CORS_ORIGINS` as a JSON list for another local frontend origin. This is a single-user local server without authentication or multi-user isolation. All business effects and `simulated://` references are simulated. The UI talks to HTTP; Hermes accesses the tools through the backend's MCP connection.

## Available routes

| Request | Success response | Expected error responses |
| --- | --- | --- |
| `GET /api/health` | 200: `{"status":"ok","phase":3,"storage":"ok","execution_enabled":true}`; the final flag may be false | 503 when task storage is unavailable |
| `GET /api/runtime` | 200: `RuntimeInfo`, including availability, enablement and `active_run_id` | Internal errors when applicable |
| `POST /api/tasks` | 201 new intake; 200 identical retry; returns `Task` | 409 changed content with the same request ID; 422 invalid input |
| `GET /api/tasks?limit=20&offset=0` | 200: `TaskList`, newest first | 422 invalid pagination |
| `GET /api/tasks/{task_id}` | 200: `Task` | 404 missing task; 422 malformed UUID |
| `POST /api/tasks/{task_id}/runs` | 202 new execution; 200 identical retry; returns `ExecutionRecord` | 404 missing task; 409 changed request or busy executor; 422 invalid input; 503 unavailable/disabled executor or unresolved execution state |
| `GET /api/tasks/{task_id}/runs` | 200: array of `ExecutionRecord`, newest first | 404 missing task; 422 malformed UUID |
| `GET /api/runs/{run_id}` | 200: `ExecutionRecord` | 404 missing run; 422 malformed UUID |
| `GET /api/runs/{run_id}/state` | 200: current simulated state snapshot | 404 missing run; 422 malformed UUID |
| `GET /api/runs/{run_id}/trace?after=0` | 200: persisted `RunEvent` array with sequences strictly greater than `after` | 404 missing run; 422 invalid cursor/UUID |
| `GET /api/runs/{run_id}/events?after=0` | 200: SSE stream of persisted `RunEvent` | 404 missing run; 422 invalid cursor/UUID or `Last-Event-ID` |
| `POST /api/runs/{run_id}/cancel` | 202: latest `ExecutionRecord`; cancellation is asynchronous | 404 missing run; 422 malformed UUID |
| `GET /openapi.json` | Concrete live HTTP schema | — |

Write requests from a disallowed browser origin return 403. Errors use `{"error":{"code":"...","message":"...","details":[]}}`. Display messages safely as text. Validation details contain sanitized field locations/types. Do not depend on Python exception text or interpret a tool's successful-looking response as task completion.

## Request and execution flow

1. Read `/api/runtime` to show availability and whether another run is active. `hermes_available` reports a detected installation/configuration; `execution_enabled` additionally reflects server configuration and unresolved execution state. These fields do not test provider connectivity, credentials or model capacity. Do not present them as "model connected."
2. Submit the user's message to `/api/tasks`. Show the returned pending task without starting an execution indicator.
3. Let the user explicitly choose the release workflow and its release value. Show its template scope: create a release ticket, attach the required checklist, then send QA both links. This phase does not infer arbitrary deliverables from the message.
4. Submit a separate run request, retain its run ID, and subscribe to its events. Display the backend-provided brief/checkpoints and real tool activity.
5. Refresh the run record as it changes. Display trusted verification, actual object references and the executor's final response separately. Preserve failed checkpoints and missing evidence.
6. On cancellation, timeout, failure or interruption, show the recorded state and partial effects. Do not automatically submit another execution. An intentional new run uses a new request ID and a separate sandbox.

Task intake example:

```json
{
  "client_request_id": "00000000-0000-0000-0000-000000000001",
  "message": "Prepare the demo project's 1.0 release.",
  "project_id": "demo"
}
```

Explicit run request to `POST /api/tasks/{task_id}/runs`:

```json
{
  "client_request_id": "00000000-0000-0000-0000-000000000002",
  "workflow": "release",
  "release": "1.0",
  "scenario": "control",
  "max_turns": 16,
  "timeout_seconds": 180
}
```

Generate each `client_request_id` once with `crypto.randomUUID()`. Keep the same ID and content when retrying an uncertain HTTP response. A changed submission needs a new ID. Intake and run-request IDs belong to separate operations; a run request ID is scoped to its task. An identical run retry returns the existing execution even when another run is active and never restarts it.

Messages are nonblank and at most 16,000 characters; project IDs are nonblank and at most 100. Their outer whitespace is normalized. The project defaults to `demo` and is a grouping label, not a multi-user authorization boundary. Release values are nonblank and at most 80 characters. `workflow` must be `release`; `max_turns` is 1–30 and `timeout_seconds` is 10–300. Defaults are shown above. Unknown properties are rejected; model credentials are not accepted from the browser.

`scenario` is an explicit local demonstration setting: `control`, `broken_checklist`, `missing_lookup` or `outdated_context`. Label it as a sandbox scenario. The latter fixtures prepare later capability/context work; their availability does not mean automatic repairs exist.

Only one execution runs at a time across this server's tasks. A fresh request while busy receives 409 with code `executor_busy`; retain the form so the user can retry after the active run ends or is cancelled. `hermes_unavailable` and `execution_state_unresolved` return 503. A 202 response means execution was admitted, not that the requested work succeeded.

## Records and result presentation

`Task` retains `schema_version: 1`, `id`, nested original `request`, `status`, `created_at` and `updated_at`. `TaskList` contains `items`, `total`, `limit` and `offset`. Times are ISO 8601 with explicit timezones. Task status changes when an explicit run starts; inspect its run records for execution details and history.

The current runtime record is **`ExecutionRecord`**, defined in [execution_contracts.py](../src/epoch_backend/execution_contracts.py). It differs from the original future-facing `Run` model.

| Field | UI meaning |
| --- | --- |
| `id`, `task_id`, `request` | Execution identity and exact structured request |
| `status` | `running`, `verifying`, `completed`, `failed`, `cancelled` or `interrupted` |
| `brief` | Template-generated `TaskBrief`, including sourced checkpoints and dependencies |
| `final_response` | Executor's final text, or null if unavailable |
| `executor_success` | Whether the executor completed its conversation; null until known |
| `verification` | Trusted checks against persisted business state, or null before evaluation/unavailable evidence |
| `baseline` | Captured executor/configuration/evaluator identities; empty or incomplete before available |
| `missing_evidence` | Explicit observations the backend could not establish |
| `error` | Execution error details, or null |
| `created_at`, `updated_at` | Persisted timestamps |

`completed` requires both executor success and passing trusted verification. Verification includes `passed`, named `checks`, matching object IDs/evidence IDs, evaluator version and state/criteria digests. Use `brief.checkpoints[].status` and evidence references for the checkpoint board. Checkpoints start pending and update during final verification; this phase does not continuously replan or reinstruct Hermes after each step.

The state endpoint returns `simulated`, `project_id`, `generation`, and arrays of `tickets`, `checklists`, `messages`, `directory` and `runbooks`. Treat simulated references as identifiers for an in-app detail view; they are not Jira/Notion/Slack web links. State and trace are read-only inspection routes. Arbitrary tool invocation and sandbox resets are not frontend HTTP operations.

Cancelling an active run records the request and signals the executor; its returned status can still be `running` or `verifying`. Keep observing until a terminal status is persisted. Cancelling a finished run returns its existing record. After a restart, unfinished runs become `interrupted` and their parent task becomes `blocked`. Partial state remains inspectable; the server does not silently resume or replay those runs.

## Live events and reconnects

The implemented wire format is **`RunEvent`**, not the original `ProgressEvent`. It contains UUID `id`, `task_id`, `run_id`, positive per-run `sequence`, string `type`, dictionary `payload` and timezone-aware `emitted_at`. It has no `schema_version` field. Deduplicate by `(run_id, sequence)`.

SSE frames use the sequence as `id`, the event type as `event`, and the complete `RunEvent` JSON as `data`. Register named listeners with `EventSource.addEventListener("tool.result", handler)` and the other event names below. A plain `source.onmessage` does not receive named events.

| Event names | Payload |
| --- | --- |
| `sandbox.initialized`, `sandbox.reset`, `state.changed` | Sandbox setup/effect observations; resets belong to the developer harness |
| `brief.created` | Actual `TaskBrief` |
| `run.started`, `run.verifying`, `run.finished`, `run.interrupted`, `run.cancellation_requested` | Run lifecycle, final verification/error details where available |
| `tool.discovery`, `tool.described` | Actual permitted tools and published contracts |
| `tool.called`, `tool.result`, `tool.error` | Tool name/version, call ID, arguments/result/error as applicable |
| `context.supplied` | Retrieved content and source/version/selection provenance |
| `mcp.invalid_call` | Rejected MCP facade request |
| `executor.started`, `executor.step`, `executor.message` | Observable executor progress and user-facing messages |
| `executor.tool_started`, `executor.tool_completed` | Hermes-side tool observations |
| `executor.baseline`, `executor.error` | Captured baseline or executor error |
| `verification.completed`, `checkpoint.updated` | Trusted verification result or updated `Checkpoint` |

Payloads vary by event type and may gain fields. The `RunEvent` schema deliberately uses a dictionary payload; tolerate unknown fields/types. Registry observations and Hermes callbacks describe related activity at different layers, so do not count them as separate business effects. No private model reasoning is provided.

For a new connection, request `events?after=N`, using the highest processed sequence for this run, or zero initially. Native `EventSource` supplies `Last-Event-ID` when reconnecting the same connection. When recreating an `EventSource` after navigation, pass the saved sequence in `after`. The server resumes after the greater query/header cursor. Cursors must be nonnegative integers, not event UUIDs. The trace endpoint supports the same `after` query for catch-up, without the header.

The server sends keepalive comments during idle execution and closes the stream after draining a terminal run's events. A stream close or browser error alone does not establish task failure. Refetch `/api/runs/{run_id}` on `run.finished`, `run.interrupted`, and connection errors. Call `source.close()` once its authoritative status is terminal so the browser does not reconnect indefinitely. On transient disconnection, retain the cursor and reconnect; use persisted trace/run endpoints to recover updates. HTTP errors before a stream opens may not expose their JSON through `EventSource`, so use normal HTTP reads to display the actual error.

## Schema exports and development fixtures

[execution-schemas.json](../contracts/execution-schemas.json) exports actual `ReleaseRunRequest`, `ExecutionRecord`, `RuntimeInfo` and `RunEvent` schemas. [schemas.json](../contracts/schemas.json) exports shared contracts, including task intake and `TaskBrief`. Each file has a `models` mapping; each selected model has its own `$defs` and local references. Extract the model before handing it to a JSON Schema tool. [execution_contracts.py](../src/epoch_backend/execution_contracts.py), [contracts.py](../src/epoch_backend/contracts.py) and live `/openapi.json` are the sources.

From `backend/`, regenerate with `uv run --frozen python scripts/export_contracts.py`; check drift by adding `--check`. The exporter also maintains the clearly labelled [development.json](../fixtures/development.json) fixtures. Their `fixture_only: true` examples are independent screen states, not a live timeline or executed evidence. Fixture URIs/digests do not identify real artifacts.

The original `Run` and `ProgressEvent` models and repair/feedback/publication fixtures remain future contracts. Automatic checkpoint planning, targeted continuations and intent revisions arrive in Phase 4; generated environment repair starts in Phase 5. No HTTP routes currently implement those operations. Keep future/fixture screens labelled and use actual run/checkpoint/evidence responses for implemented execution screens.
