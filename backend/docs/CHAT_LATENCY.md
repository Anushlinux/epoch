# Conversation workers and live Hermes answers

**Implemented but unverified — September 10, 2026.** Development used static source
review and diff formatting only. No tests, syntax/lint checks, servers, SDK probes,
sample executions, browser acceptance or model calls were run. No latency or
installed-version acceptance claim is made. See the [assigned plan](CHAT_LATENCY_PLAN.md).

## Flow and lifecycle

Send a normal chat message. Epoch saves the request and starts its bounded operation.
The browser reads that chat immediately and subscribes to its live answer. Hermes
connects its tools on a cold start, then streams public text while working. When the
final response is saved, the browser replaces the provisional text with that saved
message. Runtime information, files and PDF previews update independently.

Epoch retains **one warm worker per local workspace**, for the most recently executed
conversation. That process keeps its initialized agent, private conversation history
and MCP connection. Merely opening a different chat does not execute anything; sending
in a different chat closes the previous worker and starts a separate one.

Reuse requires the same workspace, chat, project, environment, sandbox, MCP grant and
saved visible history. Before admitting each message, Epoch compares the environment
manifest, backend/Hermes source identities, Hermes settings, model configuration and
credential identities, plus the configured PDF image/runtime identity where applicable.
Credential fingerprints stay in memory. A changed or unreadable identity prevents reuse.

The child still checks source, settings, discovery and effective/static prompt integrity.
Parent admission gates every provider request. Each separately submitted chat message
gets its existing 20-request/600-second allowance; release and repair continuations
retain their original lifetime budgets. A warm worker does not enlarge permissions.
Version activation/rollback causes fresh initialization on the next message; no executor
source, prompt or model configuration is rewritten by this feature.

Cancellation, failure, timeout, missing history/integrity evidence, failed final saving
or a scope change during execution discard the worker. No automatic execution retry
occurs. Completed tool effects remain. Uncertain cleanup blocks further execution;
inspect the state and restart. Idle timeout and normal application shutdown also close
the process and its MCP connection. Only successful, durably saved operations qualify
for reuse. Older messages and historical results are never replayed to populate a worker.

This remains Epoch's **unauthenticated local, single-user API**. Worker history is scoped
to a conversation and backend workspace; different chats never borrow it. Authentication
and tenant authorization were not added, so this is not a multi-user deployment boundary.
Private history is held only in the child, never sent through SSE. Cold starts receive
only that conversation's existing visible user/Hermes messages, excluding debugger output.

## Live transport and rendering

`GET /api/chats/{chat_id}/operations/{operation_id}/events` serves SSE for an existing
chat operation. It uses the same chat/operation lookup boundary as ordinary chat reads.
Each JSON frame contains `chat_id`, `operation_id`, `sequence`, `type` and `data`.

| Event | Data and meaning |
| --- | --- |
| `snapshot` | Current `text`, `block`, `stage`, `activity`, `status`, `truncated`, `saved` |
| `answer_delta` | Append `text` to the matching `block`; includes `truncated` |
| `answer_reset` | Start a new model-response `block` and clear the provisional text |
| `stage` | Current `stage` and readable `activity` from actual execution events |
| `complete` | Terminal `status`, `stage`, `activity`, `saved` and optional cleanup `warning` |
| `unavailable` | Read the durable conversation; a restart or eviction removed the preview |

Stages follow actual callbacks: checking conversation setup, starting or reusing Hermes,
connecting tools, preparing/waiting for the model, writing answer, running the named tool,
checking executor integrity and saving. Concurrent tool calls show their active count.
Warm reuse skips connection stages it did not perform. Tool discovery and description
are distinguished from invoking the business tool. Progress is not a timer animation.

The installed Hermes `stream_delta_callback` is connected only for ordinary chat workers.
Its text passes through the installed thinking/memory-context scrubbers and a redactor
that retains credential prefixes across chunk boundaries. No reasoning callback is
connected. Existing filtering of final public events remains in place. Public answer
content can still contain sensitive user/task information, like ordinary saved chat.

Each connection starts with the current snapshot, including after browser reconnection;
the client replaces its preview instead of appending a duplicate. Sequential frames and
chat/operation IDs are checked. New model requests reset provisional text, since text
before a tool call is not necessarily the final answer. A stopped/failed preview remains
labeled partial until navigation; it is never submitted as a new assistant message.

The in-memory hub retains 16 recent operations, 512 events per operation and up to
128,000 Unicode code points of current preview text. A slow reader gets a replacement
snapshot if its event cursor falls behind. Bridge text frames are at most 2,048 characters
and its queue is bounded. Final saved messages remain authoritative; these preview limits
do not truncate the final result. Preview memory is not durable and restart does not replay
operations. Losing SSE falls back to saved-chat polling and never cancels work.

The frontend updates the live text/stage directly, batching visual updates over 40 ms.
Runtime, conversation-list and PDF metadata requests have separate errors and context
guards. Active chat polling remains every 1.5 seconds, with failure backoff; PDF metadata
refreshes at most every five seconds during work and again at completion. Hidden tabs
close their stream and pause polling, then read/reconnect on return. Loaded PDF images
are retained across ordinary renders when their conversation, URL and page are unchanged.
Slow metadata can delay action availability but does not delay rendering a saved answer.

Each message still gets its own local Neatlogs trace, even when the worker is reused.
Token chunks are not written as individual trace/SQLite events; the workflow span keeps
the final public response and normal execution events. See [chat trace capture](CHAT_TRACES.md).

## Setup and migration

**Required:** restart backend and frontend to load the changed code. Keep the existing
`.env`, `EPOCH_DATA_DIR`, credentials, Ollama configuration and databases. This change adds
no dependency and requires no manual database migration; optional operation JSON fields
`stage`, `worker_reused` and `worker_warning` have defaults for historical records.

**Optional app-file setting**, also accepted in the process environment:

```dotenv
EPOCH_CHAT_WORKER_IDLE_SECONDS=300
```

The default is five minutes of idle time after a successful message; allowed values are
0–3,600 seconds. Set `0` to disable reuse. Idle shutdown is checked about once per second,
then process termination takes its normal cleanup time. Restart after changing app
settings. Process values override the explicit app file. No new token is required.
Existing Hermes path/API-key overrides and external ingestion tokens remain process-only;
do not copy them into the backend app file. See [.env.example](../.env.example).

Start the backend in one terminal:

```powershell
cd C:\Users\Rajdeep\Desktop\Syndicate\epoch\backend
uv run --frozen epoch-backend --env-file .env serve
```

Start the frontend in a second terminal, with Node.js 22 or newer:

```powershell
cd C:\Users\Rajdeep\Desktop\Syndicate\epoch
npm run dev --prefix frontend
```

Open [chat](http://127.0.0.1:5173/chat). Use normal `serve`; the optional standalone
`trace-debugger` profile intentionally has no chat routes. If earlier chat-trace
dependencies have not been synchronized yet, first follow [that setup](CHAT_TRACES.md).

## Manual checks for the user

These steps are instructions, not reported results. Messages invoke your configured
Hermes provider; trace questions invoke Ollama only when explicitly submitted.

1. Send a normal message requesting several paragraphs. In browser Network, inspect
   the operation's `/events` stream. Confirm incremental answer text and real stages,
   followed by exactly one saved assistant message matching `GET /api/chats/{chat_id}`.
2. Send a follow-up in the same chat before five minutes. Inspect the operation JSON:
   `worker_reused` should be `true` after the earlier successful operation; the first
   cold operation should be `false`. Confirm the prior context remains available and
   the reused path does not display a new tool-connection stage. Confirm integrity
   fields in the captured `executor.result` remain true.
3. Send in another conversation. Expect `worker_reused: false`; the first chat's
   private/tool history must not appear. Return to the first chat and confirm a cold
   worker continues only its own saved visible conversation. Switch the frontend's
   local API origin while a read is pending; stale responses must not enter the new view.
4. Temporarily set the optional idle timeout to `15`, restart, complete a message,
   then wait past the idle interval and cleanup time. The next message should use a
   cold worker. Repeat with `0` to disable reuse. Restore the preferred setting.
5. With a successful warm conversation, use a supported environment repair/rollback
   while idle; then submit a new message. Its worker must be fresh and discover the
   selected version. Likewise, a legitimate Hermes configuration/credential change
   must invalidate the next reuse without printing secret values. Keep configuration
   valid; no credential change is necessary just to use this feature.
6. Cancel while Hermes works. Confirm the operation stops, completed effects remain,
   and a subsequent explicitly submitted message starts cold. Also check a failed
   model/tool execution. No automatic replay should occur on reload/reconnection.
7. Disconnect/reconnect the browser or hide/restore the tab during a response. Confirm
   snapshot recovery, no duplicated text, and selection isolation when switching chats.
   If the stream is unavailable, saved messages must still arrive through polling.
8. With a PDF preview open, use browser request blocking or targeted throttling for
   `/api/runtime` and the chat's `/environment` endpoint. Keep chat and SSE unblocked.
   The answer must render while those panels are pending/failed, with separate notices.
   Inspect Network to ensure text chunks do not repeatedly request the same PDF page.
9. Open each message's trace, including a reused-worker message. Confirm separate
   operation/trace IDs, correctly associated tool spans and the final saved response.
10. Run any failure-injection/storage-cleanup checks only against a disposable copy of
    the workspace. Failed final persistence or failed process cleanup must block reuse
    and report uncertainty. Never corrupt the existing conversation database to check it.

Existing release/repair acceptance and all new lifecycle, transport, browser, isolation
and performance checks remain unexecuted. The original direction document and its three
Markdown hard breaks are preserved.
