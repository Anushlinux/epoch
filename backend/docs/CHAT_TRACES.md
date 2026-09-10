# Real Hermes chat traces

**Implemented but unverified.** No tests, syntax/lint commands, SDK probes,
examples, servers, browser acceptance or model calls were run for this change.
The user requested development and will perform runtime acceptance.

## User flow

1. Chat normally with Hermes, using your existing files, tools and settings.
2. Each newly executed message gets a trace. **View trace** beside the request
   opens that run. **Conversation traces** and the sidebar **Traces** link show
   the current conversation's runs, filtered by its real session ID.
3. Select a tool step to inspect recorded arguments, results, structured errors
   and original OTLP evidence. **No recorded error** does not certify task success.
4. Optionally ask a question in the existing Phase 3 Ollama panel. Only submitting
   a question invokes Ollama. **Back to conversation** returns to the same chat;
   **All traces** removes the conversation filter.

This path requires neither the invoice script nor an authored example. The
existing debugger and opt-in repair actions remain available independently.

## How capture works

`ChatService.run` creates an isolated `neatlogs.Client` per actual Hermes message.
Its public `get_tracer` API creates a WORKFLOW root and TOOL children paired by
the existing bridge's `tool_call_id`. Public callbacks supply arguments/results,
reported provider/model identity, model-request events, interim messages and errors.
The root stores the visible request/history, final response and operation outcome.
Project, session, chat and operation IDs come from saved records.

[Conversation worker reuse and streaming](CHAT_LATENCY.md) retain the initialized
Hermes process when eligible; each submitted message still creates its own Neatlogs
client and trace root. Live token chunks are not saved as individual trace events.

The SDK processes spans; a local exporter encodes OTLP and calls the collector's
trusted in-process `ingest_local` entrypoint. This reuses the original-span,
retry/conflict and SQLite storage path. No HTTP credential is required inside this
process. External `/v1/traces` still authenticates every request. The background
cursor indexes evidence without putting projection work in the chat callbacks.
Spans use the existing `EPOCH_DATA_DIR/telemetry.sqlite3`; conversations remain in
`EPOCH_DATA_DIR/chats.sqlite3`.

SDK network export, uploads and log capture are disabled. Chat spans get delivery
status `local_only`; enabling legacy cloud forwarding later never queues them.
Existing external/native telemetry forwarding behavior is preserved. Hermes keeps
its current provider, prompts, credentials, tools, permissions and execution limits.
Its model may use the existing remote provider; “local” describes trace storage
and optional Ollama analysis.

Capture sees the bridge's public, already-filtered events. Private model prompts,
reasoning, token accounting and each raw model response are unavailable. Model
requests are root events, not invented LLM spans. Tool timing measures callback
observation. Only explicit structured tool errors set error status; prose is not
treated as a failure verdict. Missing tool completions produce incomplete-evidence
notices. SDK dropped-field counters and the collector's 4 MiB request limit still
apply. Export/storage failures remain capture warnings and never retry Hermes.

Ended tools are stored during a response; the root is stored when it ends. A crash
can lose unfinished spans, while previously stored children remain. Restart marks
interrupted capture incomplete. Earlier messages are not replayed or assigned
fabricated historical traces. Local records can contain sensitive inputs/results.

## Additive contracts

Chat operations include nullable `trace_id`, `trace_span_id`, `trace_capture` and
`trace_warnings`. Old JSON records load without a migration. Capture states are
`recording`, `stored`, `incomplete`, `unavailable`, or null for older/uninstrumented
operations. `stored` confirms local persistence, not task correctness or indexing.

`GET /api/chats/{chat_id}/trace-context?trace_id=...` returns the title, chat/project
IDs, latest and selected operation capture summaries, and older uncaptured-message
count. It never executes a task/model. Trace URLs retain `chat`, `session_id`,
`trace` and `span` with the existing filters/pages. `/api/telemetry/runtime` adds
`local_capture_ready` and `local_only_spans`; `collector_ready` still describes
external authenticated ingestion readiness, not an end-to-end SDK check.

## Start with existing settings

After active work finishes, stop the old backend and frontend with Ctrl+C. From
`backend/`:

```powershell
uv sync --frozen --cache-dir .uv-cache
uv run --frozen epoch-backend --env-file .env serve
```

Neatlogs 1.4.21 moves from development to runtime dependencies; synchronize the
lock without upgrading versions. Keep your existing `.env` and `EPOCH_DATA_DIR`.
If the terminal still has the earlier temporary `data/trace-explorer` override,
clear only that override before startup:

```powershell
Remove-Item Env:EPOCH_DATA_DIR -ErrorAction SilentlyContinue
```

This deletes no data. No database is moved or merged; new optional operation fields
need no manual migration. Use normal `serve`, not the standalone trace-only profile.

No new environment variables are required. Existing app-file/process
`EPOCH_TELEMETRY_ENABLED=true` enables capture and is the default.
`EPOCH_TELEMETRY_TOKEN` remains process-only, required only for a separate SDK app.
Keep `EPOCH_NEATLOGS_CLOUD_ENABLED=false` to keep external ingestion local too.
The existing Ollama defaults match the user's installed Qwen. No `.env` values
were changed for this integration.

From the repository root, in the frontend terminal:

```powershell
npm run dev --prefix frontend
```

Use Node.js 22 or newer for watch mode. The development host now compares canonical
filesystem paths using Windows-aware semantics and redirects trailing-slash routes.
The old string-prefix check could reject valid paths after drive-casing or junction
resolution. The screenshot alone cannot establish that cause; an older server
process can also retain a route table without `/traces`. Restart once to load these
changes. Startup prints both Chat and Traces URLs. No port/process was stopped here.

## Manual acceptance for the user

1. Open `/chat` and a saved conversation. Confirm history, files and debugger
   actions remain. Send an ordinary message using your own task.
2. Open **View live trace** while Hermes runs. Ended tool steps should appear after
   export/indexing and the next five-second refresh. Opening Traces must not send
   another message or invoke Ollama.
3. After the response, use **View trace** beside the request. Confirm root input
   matches the message, output matches the response, and tool arguments/results
   match the actual work. Inspect **Original evidence**.
4. Send a follow-up: expect another trace ID with the same session/chat ID. Check
   a second conversation has a separate filtered list.
5. Inspect an actual failure and its recorded tool error. A semantically incorrect
   answer without explicit error must still say **No recorded error**. Check an
   interrupted run for missing completion/output notices.
6. Reload a selected span, use Back/Forward and **Back to conversation**. Open
   `/traces` and `/traces/` directly: neither should show the resource-not-found page.
7. Restart after a finished run: saved chats/traces should persist. Earlier messages
   should disclose missing capture, with no automatic execution.
8. Optionally ask a trace question and follow citations. See [Phase 3
   acceptance](TRACE_QUESTIONS.md) for Ollama-specific checks and limitations.

All runtime steps above, including dependency synchronization, remain unexecuted.
