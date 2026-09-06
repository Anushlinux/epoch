# Frontend contract for Anushrut

**Current development contract: phase 7.** Phases 6/7 are implemented but untested. The user requested a code-only push. See [Phase 6/7 integration changes](PHASES_6_7_HANDOFF.md) for generated lookup/retrieval artifacts and new response fields. Runtime publication gates remain mandatory.

Rajdeep owns the backend; Anushrut owns the UI. Phase 4 adds optional OpenAI `gpt-5.6-luna` supervision to the existing release workflow: sourced checkpoints, progress checks, targeted Hermes continuations, clarification and user-feedback revisions. Task submission alone still leaves a task `pending`; a separate run request starts execution. Phase 5 adds opt-in generated checklist repair, verification, project versions and rollback.

This document describes the implemented HTTP contract. Actual installed-Hermes/model acceptance results and evidence gaps are recorded separately in [implementation status](../../docs/status.md). Installation detection alone does not prove a model call will succeed.

The default API origin is `http://127.0.0.1:8000`. Allowed browser origins default to `http://localhost:5173` and `http://127.0.0.1:5173`; configure `EPOCH_CORS_ORIGINS` as a JSON list for another local frontend origin. This is a single-user local server without authentication or multi-user isolation. All business effects and `simulated://` references are simulated. The UI talks to HTTP; Hermes accesses the tools through the backend's MCP connection.

**Existing frontend compatibility:** the committed [intake client](../../frontend/src/intake-api.mjs) requires health `phase: 3`; the [execution client](../../frontend/src/execution-api.mjs) also requires Phase 3 with automatic supervision/repair false. These guards reject the Phase 7 backend. Anushrut owns updating those guards and adding supervision/repair states. This backend change edits no frontend files. Historical browser evidence used real HTTP/storage with an explicit test executor; it does not prove current model-backed UI support.

## Available routes

| Request | Success response | Expected error responses |
| --- | --- | --- |
| `GET /api/health` | 200: `{"status":"ok","phase":7,"storage":"ok","execution_enabled":true}`; the final flag may be false | 503 when task storage is unavailable |
| `GET /api/runtime` | 200: `RuntimeInfo`, including availability, enablement and `active_run_id` | Internal errors when applicable |
| `POST /api/tasks` | 201 new intake; 200 identical retry; returns `Task` | 409 changed content with the same request ID; 422 invalid input |
| `GET /api/tasks?limit=20&offset=0` | 200: `TaskList`, newest first | 422 invalid pagination |
| `GET /api/tasks/{task_id}` | 200: `Task` | 404 missing task; 422 malformed UUID |
| `POST /api/tasks/{task_id}/runs` | 202 new execution; 200 identical retry; returns `ExecutionRecord` | 404 missing task; 409 changed request or busy executor; 422 invalid input; 503 unavailable/disabled executor or unresolved execution state |
| `GET /api/tasks/{task_id}/runs` | 200: array of `ExecutionRecord`, newest first | 404 missing task; 422 malformed UUID |
| `GET /api/runs/{run_id}` | 200: `ExecutionRecord` | 404 missing run; 422 malformed UUID |
| `GET /api/runs/{run_id}/revisions` | 200: `SupervisionOperation[]`, initial operation first; `[]` for a direct run | 404 missing run; 422 malformed UUID |
| `POST /api/runs/{run_id}/feedback` | 202 new operation; 200 identical retry; returns latest `ExecutionRecord` | 404 missing run; 409 busy, stale revision, direct run, unfinished run or changed retry; 422 invalid input; 503 unavailable supervision/unresolved state |
| `POST /api/runs/{run_id}/clarifications` | Same body/statuses as feedback; allowed only while `needs_input` | Feedback errors above, plus 409 when no clarification is pending |
| `GET /api/runs/{run_id}/state` | 200: current simulated state snapshot | 404 missing run; 422 malformed UUID |
| `GET /api/runs/{run_id}/trace?after=0` | 200: persisted `RunEvent` array with sequences strictly greater than `after` | 404 missing run; 422 invalid cursor/UUID |
| `GET /api/runs/{run_id}/events?after=0` | 200: SSE stream of persisted `RunEvent` | 404 missing run; 422 invalid cursor/UUID or `Last-Event-ID` |
| `POST /api/runs/{run_id}/cancel` | 202: latest `ExecutionRecord`; cancellation is asynchronous | 404 missing run; 422 malformed UUID |
| `GET /openapi.json` | Concrete live HTTP schema | — |

Write requests from a disallowed browser origin return 403. Errors use `{"error":{"code":"...","message":"...","details":[]}}`. Display messages safely as text. Validation details contain sanitized field locations/types. Do not depend on Python exception text or interpret a tool's successful-looking response as task completion.

## Request and execution flow

1. Read `/api/runtime` to show availability and whether another operation is active. `hermes_available` reports a detected installation/configuration; `execution_enabled` additionally reflects server configuration and unresolved execution state. `supervision_enabled` also requires a detected debugger credential route. These fields do not test provider connectivity, credential validity or model capacity. Do not present them as "model connected."
2. Submit the user's message to `/api/tasks`. Show the returned pending task without starting an execution indicator.
3. Let the user explicitly choose the release workflow and its release value. Its core scope is a release ticket, the required linked checklist and a QA message containing both links. Set `supervised: true` to let Luna interpret the request into sourced checkpoints and supported additions. Omit that flag, or use false, for the existing direct template run.
4. Submit the run request, retain its run ID, and subscribe to its events. Display the backend-provided brief/checkpoints and real tool activity. A supervised run starts `planning`; material ambiguity stops it at `needs_input` with explicit questions.
5. Refresh the run record as it changes. Display trusted verification, actual object references and the executor's final response separately. Preserve failed checkpoints and missing evidence.
6. When input is requested, show the latest operation's `questions` and post the user's answer to `/clarifications`. After a result, post corrections to `/feedback`. Both create a recorded operation on the same run and reuse its sandbox objects.
7. On cancellation, timeout, failure or interruption, show the recorded state and partial effects. Do not automatically replay execution. An intentional new run uses a new request ID and a separate sandbox; feedback uses the existing run and preserves earlier results.

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
  "supervised": true,
  "max_turns": 20,
  "timeout_seconds": 600
}
```

Generate each `client_request_id` once with `crypto.randomUUID()`. Keep the same ID and content when retrying an uncertain HTTP response. A changed submission needs a new ID. Intake and run-request IDs belong to separate operations; a run request ID is scoped to its task. An identical run retry returns the existing execution even when another run is active and never restarts it.

Messages are nonblank and at most 16,000 characters; project IDs are nonblank and at most 100. Their outer whitespace is normalized. Execution additionally requires a project slug matching `[A-Za-z0-9][A-Za-z0-9_-]{0,99}`. The project defaults to `demo` and is a grouping label, not a multi-user authorization boundary. Release values are nonblank and at most 80 characters. `workflow` must be `release`; new requests accept integer `max_turns` from 1–20 and `timeout_seconds` from 10–600, defaulting to 20 and 600. Historical Phase 3 records can retain their originally accepted larger turn limit. Unknown properties are rejected; model credentials are not accepted from the browser.

The turn/time budget applies to each initial run or explicitly submitted feedback/clarification operation. For supervised execution, Luna planning/review requests and Hermes model requests share the same maximum of 20 turns and 10 minutes; continuations do not reset it. Feedback is a new user-authorized operation with a new bounded budget. `/api/runtime` advertises `max_agent_turns: 20`, `max_operation_seconds: 600`, `automatic_supervision: true` and `automatic_repair: false`. The debugger model is fixed to `gpt-5.6-luna`; Hermes retains its separately configured executor model.

`scenario` is an explicit local demonstration setting: `control`, `broken_checklist`, `missing_lookup` or `outdated_context`. Label it as a sandbox scenario. The latter fixtures prepare later capability/context work; their availability does not mean automatic repairs exist.

`demo_omit_notification: true` is an optional, explicitly labeled supervision demonstration. It requires `supervised: true` and deliberately asks the first Hermes pass to omit QA so the supervisor can detect and request the missing step. It defaults to false; do not describe this staged omission as an accidental real-world agent failure.

Only one operation runs at a time across this server's tasks. A fresh request while busy receives 409 with code `executor_busy`; retain the form so the user can retry after the active operation ends or is cancelled. `hermes_unavailable`, `debugger_unavailable` and `execution_state_unresolved` return 503. A 202 response means execution was admitted, not that the requested work succeeded.

## Feedback, clarification and retained history

Both feedback routes accept `FeedbackRequest`:

```json
{
  "client_request_id": "00000000-0000-0000-0000-000000000003",
  "expected_revision_id": "00000000-0000-0000-0000-000000000004",
  "message": "Add the checklist item Security review approved. Include Deployment starts at 10:00 UTC in the QA message.",
  "max_turns": 20,
  "timeout_seconds": 600
}
```

Replace the example `expected_revision_id` with `run.supervision.current_revision_id` read from the current server record. It identifies the latest operation, including an operation awaiting clarification; it is not the run ID, request ID or a numeric revision counter. Generate `client_request_id` once per submission. Preserve the ID, expected revision, endpoint and complete body when retrying an uncertain response. An identical accepted retry returns the current run without replaying the operation. Changed content with the same ID returns 409.

`/feedback` requires a supervised run whose latest operation is terminal. `/clarifications` additionally requires `status: "needs_input"`. Terminal statuses are `completed`, `needs_input`, `blocked`, `failed`, `cancelled` and `interrupted`. A stale expected revision returns `stale_revision`; refetch history and let the user review their intended change before submitting a new request ID. Other 409 codes include `not_supervised`, `run_not_finished` and `no_clarification_pending`.

Supported changes are **additive checklist items** and **required exact QA-message phrases** sourced from the user's request or feedback. Existing requirements remain required. Changing project/release/channel/titles, removing or replacing existing requirements, unsupported tools and subjective quality checks require clarification or are reported unsupported. Feedback does not authorize evaluator edits or environment repair. A feedback classification such as `evaluation_mistake` is a recorded interpretation, not permission to weaken a trusted check.

Successful feedback can update the existing checklist's items and message text through ordinary business tools. Ticket/checklist/message IDs and URLs remain stable, with before/after state and idempotency receipts retained. The new tools cannot change the checklist's ticket/title or the message's channel/links. A broken checklist adapter still fails update calls.

Read `/revisions` or `supervision.operations` for history. Each `SupervisionOperation` contains its `id`, `previous_revision_id`, `trigger` (`initial`, `feedback`, `clarification`), exact `user_input` and request, plan, brief, questions, intent revision when applicable, criteria and state before/after, verification before/after, debugger calls, executor passes, interventions, status, error, missing evidence, timestamps and budget counters. Earlier operation outcomes stay separate from the current result. `turns_used`, `debugger_turns` and `executor_turns` count authorized model requests, not UI events or dollar cost. These history records are actual observations; do not present an LLM classification or final message as a trusted pass decision.

## Records and result presentation

`Task` retains `schema_version: 1`, `id`, nested original `request`, `status`, `created_at` and `updated_at`. `TaskList` contains `items`, `total`, `limit` and `offset`. Times are ISO 8601 with explicit timezones. Task status changes when an explicit operation starts; inspect run records for execution details. A run at `needs_input` maps to task `awaiting_clarification`; an interrupted run maps to task `blocked`. Task intake remains `pending` until a run is explicitly started.

The current runtime record is **`ExecutionRecord`**, defined in [execution_contracts.py](../src/epoch_backend/execution_contracts.py). It differs from the original future-facing `Run` model.

| Field | UI meaning |
| --- | --- |
| `id`, `task_id`, `request` | Execution identity and exact structured request |
| `status` | `planning`, `running`, `verifying`, `repairing`, `completed`, `needs_input`, `blocked`, `failed`, `cancelled` or `interrupted` |
| `brief` | Current `TaskBrief` with sourced checkpoints and dependencies; the preliminary template exists before supervised planning finishes |
| `final_response` | Latest delivery or supervisor explanation, or null if unavailable; individual executor responses remain in operation history |
| `executor_success` | Whether the executor completed its conversation; null until known |
| `verification` | Trusted checks against persisted business state, or null before evaluation/unavailable evidence |
| `baseline` | Captured executor/configuration/evaluator identities; empty or incomplete before available |
| `missing_evidence` | Explicit observations the backend could not establish |
| `error` | Execution error details, or null |
| `supervision` | Null for direct runs; otherwise fixed debugger model, `current_revision_id` and ordered `operations` |
| `created_at`, `updated_at` | Persisted timestamps |

`completed` requires both executor success and passing trusted verification. Supervised runs also require the recorded executor invariants and retained conversation history; unavailable or changed baselines block completion. Verification includes `passed`, named `checks`, matching object IDs/evidence IDs, evaluator version and state/criteria digests. Use `brief.checkpoints[].status` and evidence references for the checkpoint board. In supervised runs, trusted state checks run after meaningful tool completions and at pass boundaries. Luna can request a targeted continuation after a completed Hermes pass leaves a deliverable missing. The debugger reads observable actions/results; no private thinking is exposed.

Checkpoint statuses are `pending`, `verified`, `failed` and `blocked`, distinct from run statuses. The trusted rules are `release_ticket`, `release_checklist`, `qa_notification`, optionally `qa_owner`, and `qa_message_content` when exact phrases are required. A new brief has new checkpoint IDs, so use the rule plus operation identity to compare revisions. The `release-state-v3` evaluator requires one correctly linked QA message to contain all required phrases; phrases scattered across separate messages do not pass. Older evidence keeps its original evaluator identity and outcome.

The state endpoint returns `simulated`, `project_id`, `generation`, and arrays of `tickets`, `checklists`, `messages`, `directory` and `runbooks`. Treat simulated references as identifiers for an in-app detail view; they are not Jira/Notion/Slack web links. State and trace are read-only inspection routes. Arbitrary tool invocation and sandbox resets are not frontend HTTP operations.

Cancelling an active run records the request and signals execution; its returned status can still be `planning`, `running` or `verifying`. Keep observing until a terminal status is persisted. Cancelling a finished run returns its existing record. After a restart, unfinished runs become `interrupted` and their parent task becomes `blocked`. Partial state remains inspectable; the server does not silently resume or replay those runs. A new explicit feedback operation can inspect and reuse retained state within the supported scope.

## Live events and reconnects

The implemented wire format is **`RunEvent`**, not the original `ProgressEvent`. It contains UUID `id`, `task_id`, `run_id`, positive per-run `sequence`, string `type`, dictionary `payload` and timezone-aware `emitted_at`. It has no `schema_version` field. Deduplicate by `(run_id, sequence)`.

SSE frames use the sequence as `id`, the event type as `event`, and the complete `RunEvent` JSON as `data`. Register named listeners with `EventSource.addEventListener("tool.result", handler)` and the other event names below. A plain `source.onmessage` does not receive named events.

| Event names | Payload |
| --- | --- |
| `sandbox.initialized`, `sandbox.reset`, `state.changed` | Sandbox setup/effect observations; update effects include `before`/`after`; resets belong to the developer harness |
| `brief.template_prepared`, `brief.created` | Preliminary release template or actual ready `TaskBrief` |
| `run.started`, `run.verifying`, `run.finished`, `run.interrupted`, `run.cancellation_requested` | Run lifecycle, final verification/error details where available |
| `tool.discovery`, `tool.described` | Actual permitted tools and published contracts |
| `tool.called`, `tool.result`, `tool.error` | Tool name/version, call ID, arguments/result/error as applicable |
| `context.supplied` | Retrieved content and source/version/selection provenance |
| `mcp.invalid_call` | Rejected MCP facade request |
| `executor.started`, `executor.step`, `executor.message` | Observable executor progress and user-facing messages |
| `executor.tool_started`, `executor.tool_completed` | Hermes-side tool observations |
| `executor.baseline`, `executor.error` | Captured baseline or executor error |
| `verification.completed`, `checkpoint.updated` | Trusted verification result or updated `Checkpoint` |
| `supervisor.requested`, `supervisor.plan`, `supervisor.decision` | Debugger purpose/model, structured plan or review decision |
| `debugger.started`, `debugger.completed` | Actual debugger request lifecycle and returned usage/identity metadata when available |
| `supervisor.intervention` | Recorded targeted instruction, checkpoint references and supporting evidence |
| `intent.submitted`, `intent.revised`, `requirements.revised` | Exact submitted feedback, accepted intent revision, or additive trusted criteria with prior/current digests and provenance |
| `clarification.requested` | Questions for the user |
| `budget.turn_authorized` | Actor, shared used count and maximum, recorded before an authorized model request |
| `supervision.finished` | Completed supervision operation with outcome, history and usage counters |
| `demo.omission_requested` | Explicit staged omission and the first-pass instruction used for the demonstration |

Payloads vary by event type and may gain fields. The `RunEvent` schema deliberately uses a dictionary payload; tolerate unknown fields/types. Registry observations and Hermes callbacks describe related activity at different layers, so do not count them as separate business effects. No private model reasoning is provided.

Supervision-emitted payloads include `revision_id` to identify their operation. Other persisted tool/state events always carry the run identity in the envelope and may not carry a revision ID. Do not treat their absence as a different run or fabricate an operation association.

For a new connection, request `events?after=N`, using the highest processed sequence for this run, or zero initially. Native `EventSource` supplies `Last-Event-ID` when reconnecting the same connection. When recreating an `EventSource` after navigation, pass the saved sequence in `after`. The server resumes after the greater query/header cursor. Cursors must be nonnegative integers, not event UUIDs. The trace endpoint supports the same `after` query for catch-up, without the header.

The server sends keepalive comments during idle execution and closes the stream after draining a terminal run's events. A stream close or browser error alone does not establish task failure. Refetch `/api/runs/{run_id}` on `run.finished`, `run.interrupted`, and connection errors. Call `source.close()` once its authoritative status is terminal so the browser does not reconnect indefinitely. On transient disconnection, retain the cursor and reconnect; use persisted trace/run endpoints to recover updates. HTTP errors before a stream opens may not expose their JSON through `EventSource`, so use normal HTTP reads to display the actual error.

Feedback and clarification reuse the **same run ID** and continue its event sequence. Reopen the stream after a new operation is accepted, using the last processed cursor. Compare the server's current revision/status before treating a replayed earlier `run.finished` event as completion of the new operation.

## Schema exports and development fixtures

[execution-schemas.json](../contracts/execution-schemas.json) exports actual `ReleaseRunRequest`, historical `StoredReleaseRunRequest`, `ExecutionRecord`, `RuntimeInfo` and `RunEvent` schemas. [supervision-schemas.json](../contracts/supervision-schemas.json) exports `FeedbackRequest`, `SupervisorPlan`, `SupervisorDecision`, `SupervisionOperation` and `SupervisionState`. [schemas.json](../contracts/schemas.json) exports shared contracts, including task intake and `TaskBrief`. Each file has a `models` mapping; each selected model has its own `$defs` and local references. Extract the model before handing it to a JSON Schema tool. [execution_contracts.py](../src/epoch_backend/execution_contracts.py), [supervision_contracts.py](../src/epoch_backend/supervision_contracts.py), [contracts.py](../src/epoch_backend/contracts.py) and live `/openapi.json` are the sources.

From `backend/`, regenerate with `uv run --frozen python scripts/export_contracts.py`; check drift by adding `--check`. The exporter also maintains the clearly labelled [development.json](../fixtures/development.json) fixtures. Their `fixture_only: true` examples are independent screen states, not a live timeline or executed evidence. Fixture URIs/digests do not identify real artifacts.

The original `Run` and `ProgressEvent` models are not these runtime wire formats. Repair/publication models and their development fixtures still describe future behavior; generated environment repair starts in Phase 5. Keep fixture screens labeled and use actual run/checkpoint/operation evidence for the implemented planning, continuation and feedback interfaces.

## Phase 5 repair contract

Set both `supervised: true` and `repair_enabled: true` on the release run request.
Repair is opt-in and cannot be combined with the omission demonstration. Existing
run requests remain valid. `RuntimeInfo.phase` is 7; `automatic_repair` and
`repair_opt_in` are true. Availability is separately inspected through
`GET /api/repair/runtime`; it is not a model-connectivity test.

| Route | Response |
| --- | --- |
| `GET /api/repair/runtime` | Container/image availability, immutable image ID and runner metadata |
| `GET /api/environments/{project_id}` | `active_version`, immutable `versions`, `repairs`, and publication/rollback `history` |
| `POST /api/environments/{project_id}/rollback` | Idempotent rollback receipt; 409 for active execution, stale expected version or changed retry input; 422 for invalid UUIDs |

Rollback input is `{"client_request_id":"UUID","expected_version":"UUID"}`.
See [repair schemas](../contracts/repair-schemas.json) and [setup](REPAIR_SETUP.md).
There are no public candidate-stage or publish endpoints.

Run status adds `repairing`. `ExecutionRecord.environment_version` identifies the
pinned executable, initially `builtin`. Each supervision operation contains
`repairs` (diagnosis, attempts, source/diff, proofs and decision) and `repair_budget`
(overall request count/ceiling). Each attempt's `active_verification` shows the
current isolated stage and its own request count. Preserve the distinction between
verified environment publication and checked completion of the user's task.

SSE/trace events include `repair.triggered`, `repair.budget_authorized`,
`repair.candidate_staged`, `repair.candidate_rejected`, `repair.blocked` and
`environment.published`; tool records include `environment_version`. As with other
events, render source/diff/error strings as untrusted text. Refresh run/version
records after events; do not infer pass decisions from model text. Original/fresh
verification evidence lives in the repair record, separately from original effects.

Each isolated verification has 20 requests/600 seconds; primary work shares 20/600
active seconds; overall repair is 60 requests/1,800 wall seconds and two candidates.
Rollback changes new-run discovery only; existing runs remain pinned. Failed and
interrupted candidates remain visible and inactive. No frontend integration or
browser acceptance for these new controls is claimed by this backend handoff.
