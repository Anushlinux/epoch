# Local questions over traces — feature Phase 3

Normal Hermes chat now supplies traces automatically. Open **Conversation traces**
or **View trace** in Chat, then ask about that recorded run. See [the chat
integration](CHAT_TRACES.md); the invoice example below remains optional.

**Implemented but unverified.** The user requested development only and will perform
acceptance. No tests, syntax/lint commands, SDK probes, sample runs, browser checks
or model requests were executed for this phase. This is the trace-debugger roadmap,
separate from the older Hermes/repair phase numbering.

## Implemented flow

Trace capture, browsing and questions extend the existing Epoch workspace. Start
the normal server to use `/chat`, `/debugger`, `/incidents` and `/traces` together.
Hermes and the existing debugger retain their own model configurations and actions;
Ollama is used only for the newly submitted trace questions.

Open a trace in `/traces`, optionally select a step, and submit a question. Epoch
retrieves a bounded set of that trace's spans, sends the saved evidence snapshot to
local Ollama, validates the response shape and evidence IDs, and saves the answer.
Click a reference such as E1 to inspect its span. Expand Evidence sent to the model
to see exactly the snapshot that supported the answer.

The configured model is `qwen3:4b-instruct-2507-q4_K_M`, matching the user's installed
model name. No model installation, pull, cloud fallback or new API key is involved.
Trace input/output data, the question and the response schema are sent to the local
Ollama HTTP API only when a question is submitted. Ordinary browsing and GET requests
read Epoch's own storage/configuration and never call Ollama.

## Start it yourself

Keep the Ollama application running. If its server is not running, start `ollama serve`
in a separate terminal; do not start a second instance when its port is already in use.
The model is already installed, so no pull command is needed.

Use your existing `backend/.env` and data directory. In PowerShell, from `backend/`:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
# Optional: external SDK apps only; built-in Hermes chat needs no token.
# $env:EPOCH_TELEMETRY_TOKEN = Read-Host "Enter your local collector token"
$env:EPOCH_NEATLOGS_CLOUD_ENABLED = "false"
uv run --frozen epoch-backend --env-file .env serve
```

Use **the same EPOCH_DATA_DIR as the existing chat/workflow server**. The supplied
app-file setting is `EPOCH_DATA_DIR=data`; preserve a different existing value if
you configured one. If you followed the earlier trace-only instructions, stop that
server with Ctrl+C and clear its temporary PowerShell data override before starting
the command above:

```powershell
Remove-Item Env:EPOCH_DATA_DIR -ErrorAction SilentlyContinue
```

This removes only the current terminal's setting, so `.env` chooses the data folder.
It does not delete files. The earlier `data/trace-explorer` database remains on disk;
it is not automatically merged into `data`. New SDK submissions to the combined
server are stored alongside the original workspace's telemetry. Restart an already
running Epoch server to load code/settings; one server may own a data directory at a time.

If you do not use an app file, omit `--env-file .env` and keep your existing process
settings. The Qwen model and Ollama URL already have the correct defaults.

In another terminal, from the repository root:

```powershell
npm run dev --prefix frontend
```

Open [the trace explorer](http://127.0.0.1:5173/traces). Its collector connection
inherits the tab's saved chat API origin, defaulting to `http://127.0.0.1:8000`.
The displayed model is configuration, not a claim
that Ollama has already been contacted. The first question checks installed models
through `/api/tags`, then calls `/api/chat`.

### Optional standalone profile

`serve --profile trace-debugger` is available only when you deliberately want a
separate trace-only server. It omits chat, execution, incident and repair endpoints.
The normal `serve` command includes both the existing workflows and all new trace
interfaces. A 404 for `/api/chats` or `/api/runtime` while using the trace-only profile
means the wrong server profile was selected for the chat page; it is not evidence
that the chat implementation was removed.

## Quick manual acceptance

These steps are for the user to execute; they have not been run during development.

First open `/chat` and select an existing conversation. Confirm the normal chat,
its debugger page and saved files/state remain available, then use Traces in the
same sidebar. No new conversation or repair should start from navigation alone.

For acceptance with your actual conversation, use the [chat trace
steps](CHAT_TRACES.md#manual-acceptance-for-the-user). The optional synthetic
example below requires process `EPOCH_TELEMETRY_TOKEN` set in the collector terminal
before backend startup, with the same value in the example terminal.

1. In another terminal at `backend/`, capture the supplied invoice workflow:

   ```powershell
   $env:UV_CACHE_DIR = "$PWD/.uv-cache"
   $env:EPOCH_TELEMETRY_TOKEN = Read-Host "Enter the same collector token"
   uv run --frozen python scripts/neatlogs_trace_example.py
   ```

2. Find the printed trace ID in `/traces`, or filter project `trace-demo`. Wait for
   indexing to finish. Confirm the workflow asks for INV-42 while `select_invoice`
   outputs INV-41. The synthetic refund is not a real financial operation.

3. Submit: **The request was for INV-42. Which invoice was selected, and where does
   the evidence show the mismatch?** Expect a running question followed by a saved
   answer with clickable evidence IDs. The model should explain the difference
   between requested INV-42 and observed INV-41, citing the workflow/tool records.
   Exact wording is not fixed. It must not claim to have inspected source code,
   applied a fix or verified the business outcome.

4. Click a citation. Confirm its span belongs to the selected trace and contains
   the cited input/output. Open the saved model snapshot and compare the excerpt.
   Model conclusions still need human review: validating an ID does not prove
   that the accompanying explanation is correct.

5. Ask: **What was the customer's billing address?** It is absent from this example.
   Expect missing evidence instead of an invented address. Also ask about private
   reasoning or source-code lines: those are not captured and must not be invented.

6. Refresh the page, then restart the backend using the same data directory.
   Saved questions, answers and evidence should remain. Opening or refreshing the
   page must not create another question or start another generation.

7. While a question is running, try another submission (including from another
   tab). The UI should indicate that the model is busy; the API rejects a second
   independent request with 409. After completion, the next question can run.

8. Stop Ollama and submit a new question. Expect an actionable failed question and
   an intact trace viewer. Start Ollama again and explicitly submit a new question.
   To exercise model-name errors, temporarily configure an uninstalled model name
   and restart Epoch; asking should fail without downloading or substituting a model.

9. Stop Epoch during a question, then restart it. Interrupted work should be marked
   failed and never automatically resubmitted. If inference exceeds the configured
   timeout, expect `ollama_timeout`; no partial answer should be accepted.

HTTP failures now retain the status, endpoint and a bounded JSON provider error in
`error.details`; the displayed message includes that detail. The old generic memory
hint did not prove a memory problem. No non-JSON error page or request headers/body are
stored by this diagnostic path. See [Ollama troubleshooting](NOISE_WORKFLOW.md#if-the-local-investigation-fails).
Previously saved failures retain their original messages. This follow-up was reviewed
statically only; model/server and UI acceptance remain unexecuted.

For a healthy comparison **by manual inspection only**, run the existing example with
`--invoice-id INV-41`, open that new trace and ask which invoice was requested and
selected. Phase 3 does not implement automatic cross-run comparison.

## CLI and HTTP contracts

From `backend/`, with the server running (replace TRACE_ID, SPAN_ID and QUESTION_ID):

```powershell
uv run --frozen epoch-backend trace-model-info
uv run --frozen epoch-backend ask-trace TRACE_ID "Why was the wrong invoice selected?"
uv run --frozen epoch-backend ask-trace TRACE_ID "What input led to this output?" --span-id SPAN_ID
uv run --frozen epoch-backend trace-questions TRACE_ID
uv run --frozen epoch-backend trace-questions TRACE_ID --question-id QUESTION_ID
```

`ask-trace` returns promptly with the saved running question. Repeat the GET command
to read completion; it never triggers inference. The request UUID is printed to
stderr before sending, so an uncertain POST can be retried with the same question,
focus and `--request-id UUID`. Identical retries return the original record without
another model call. Reusing the UUID for different content returns 409. A failed
question requires a new explicit submission with a new UUID to try generation again.

| API | Behavior |
| --- | --- |
| `GET /api/trace-questions/runtime` | Configuration, storage availability, active question ID and warnings; no Ollama I/O |
| `POST /api/traces/{trace_id}/questions` | Body: `client_request_id` (UUID), `question` (1–2,000 characters), optional `span_id`; 202 new, 200 identical retry |
| `GET /api/traces/{trace_id}/questions` | Saved history, newest first; `limit` default 5/max 20, `offset` |
| `GET /api/traces/{trace_id}/questions/{question_id}` | Saved running/answered/failed record, evidence snapshot, model, answer or actionable error |

Questions are independent. Previous answers are not silently included as evidence;
write the relevant context in each question. A selected span prioritizes retrieval
but retains surrounding trace context. Selection uses URL parameters `trace`, `span`,
`question`, and `question_offset`; refreshing an answer link is read-only.

## Why these implementation choices

- **Retrieve before generating.** SQLite FTS ranks literal question terms within the
  selected trace. The host also selects the focused span, roots, errors, parents and
  nearby steps, so a result can be related to its original request. The model does
  not create SQL or choose a different project. No embedding service is required.
- **Bound the evidence.** At most 32 candidates become at most 12 model evidence
  records totaling at most 12,000 UTF-8 bytes. Individual input/output/event fields
  are excerpted when necessary. Missing parents, uncaptured values, index gaps and
  omissions are disclosed. The index searches only the first 64,000 characters per
  field, as in Phase 2. Retrieval is heuristic and can miss a relevant span; select
  that span as focus or ask a more specific question. Exact tokenization is model
  dependent; the request uses an 8,192-token context and 1,600-token output budget.
- **Use structured, cited answers.** Output separates answers, hypotheses and missing
  evidence. Host validation rejects malformed responses and unknown evidence IDs.
  This is reference validation, not an automatic factual evaluator or a repair gate.
  The Ollama sampling schema omits string-length bounds to avoid the observed grammar
  repetition failure. The full schema is still supplied in the prompt, and unchanged
  host validation enforces those lengths. Structural constraints and output budgets
  remain. New requests use prompt version `trace-question-v2`; successful usage records
  include `output_schema_version`. See the [grammar fix and manual retry](NOISE_WORKFLOW.md#if-the-local-investigation-fails).
- **Keep a durable snapshot.** The question, selected evidence, snapshot hash, prompt
  version, configured model, actual response usage (when reported), answer and errors
  are stored in SQLite. Later-arriving spans cannot silently rewrite an old answer.
- **Use explicit background work.** One question at a time avoids competing local
  generations. POST saves the request before scheduling it; GET polls only saved
  state. Unknown acknowledgements retain a retry identity in the browser tab.
  A total Ollama request deadline defaults to 180 seconds. There are no automatic
  inference retries, model downloads or fallback providers.
- **Keep the execution boundary.** Ollama receives text and a response schema with
  no tools, repository access or executable actions. Trace strings are treated as
  untrusted evidence. HTTP is restricted to the configured loopback origin, with
  redirects and environment proxies disabled. Remote/cloud model labels are refused.

The implementation follows Ollama's official [chat API](https://docs.ollama.com/api/chat),
[structured output](https://docs.ollama.com/capabilities/structured-outputs) and
[installed-model listing](https://docs.ollama.com/api/tags) documentation, reviewed
September 10, 2026. Runtime compatibility with the user's installation is unverified.

## Environment and migration

| Setting | Required? | Where |
| --- | --- | --- |
| `EPOCH_TELEMETRY_TOKEN` | Required for external SDK HTTP ingestion only; built-in Hermes capture needs no token | Process environment of collector and instrumented app only |
| `EPOCH_OLLAMA_BASE_URL` | Optional; default `http://127.0.0.1:11434` | Backend app file or process |
| `EPOCH_TRACE_MODEL` | Optional; defaults to the user's Qwen model above | Backend app file or process |
| `EPOCH_TRACE_QUESTION_TIMEOUT_SECONDS` | Optional; 180 default, allowed 15–600 | Backend app file or process |
| `EPOCH_DATA_DIR` | Existing optional setting; reuse the previous value | Backend app file or process |
| `EPOCH_NEATLOGS_CLOUD_ENABLED` | Keep false for local storage; required false in the optional trace-only profile | Backend app file or process |

App files load only when explicitly passed before the subcommand:
`uv run --frozen epoch-backend --env-file .env serve`.
Process values override app-file settings. No `.env` change is required when the
defaults match your installed local model. There are no new secret credentials.

Restart the server after code/configuration changes. Startup adds `trace_questions`
and its history index to the existing `telemetry.sqlite3`; no manual reset or
destructive migration is needed. Stop the server before backing up the complete
data directory. HTTPX was declared as a direct runtime dependency at its existing
locked version (0.28.1); package versions were not upgraded. Run `uv sync --frozen`
to synchronize the updated dependency metadata.

The regular server is the primary entrypoint and exposes questions alongside chat,
debugger and existing workflows. The optional standalone profile also exposes
questions, keeps cloud forwarding disabled and initializes no Hermes/repair services.
Existing chat, incidents, original spans, trusted checks and direction remain intact.
Cross-run questions, comparisons, MCP, replay, repair and incident enhancements
require a separate later assignment.
