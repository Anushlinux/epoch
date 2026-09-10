# Epoch frontend

**Context quality:** open Traces from a chat to investigate noise, inspect relevant
evidence, annotate source versions/approvals, preview a draft policy and submit explicit
trial messages. Record trial assessments before activating a policy; rollback and actual
selection evidence stay visible. See [setup/manual checks](../backend/docs/NOISE_WORKFLOW.md).
Implemented but unverified. Browsing never starts analysis or publishes a policy.

**Live answers:** ordinary Hermes chat now receives public text and actual stages over
SSE, then replaces the preview with the saved message. Returned chats render immediately;
runtime information, file lists and PDF previews refresh independently. See [lifecycle,
setup and manual checks](../backend/docs/CHAT_LATENCY.md). Implemented but unverified.

**Chat → Traces:** the sidebar and **Conversation traces** open the current chat's
recorded runs; each new request also has a **View trace** link. The explorer keeps
conversation/selection context in its URL and links back to the chat. Earlier
messages without capture and incomplete runs are labeled. See [the integration
handoff](../backend/docs/CHAT_TRACES.md). Implemented but unverified.

The new [local trace explorer](../backend/docs/TRACE_EXPLORER.md) at `/traces`
shows captured Neatlogs executions, searchable inputs/outputs and original evidence.
Use the normal backend `serve` command and the existing data directory to keep chat,
debugger and traces together. Traces inherits this tab's saved chat API connection.
The optional standalone collector profile supports trace pages only. This addition is implemented but
unverified; browser and unit testing were explicitly skipped. [Phase 3](../backend/docs/TRACE_QUESTIONS.md)
adds an Ask about this trace panel, local Ollama answers, clickable span references,
saved evidence snapshots and question history. Opening or refreshing never calls a model.

Epoch opens with a normal Hermes conversation. The debugger investigates a selected conversation only after an explicit action. Release execution and the interactive Atlas fixture remain separate, clearly labeled examples. The incident workspace supports broader imported evidence.

## Run

From the repository root:

Use Node.js 22 or newer. Restart an already-running frontend once to load the
updated route/path handling. `npm run dev` now watches the host source and restarts
when its route table changes. `/traces/` redirects to `/traces`; the allowlisted
host compares canonical paths using Windows-aware filesystem semantics.

```sh
npm run dev --prefix frontend
```

Open http://127.0.0.1:5173/chat. Start the unchanged backend using [its setup guide](../backend/README.md). Open **Connection settings**, enter its local origin (default http://127.0.0.1:8000), then **Connect / reconnect**.

The host uses Node's built-in HTTP server and binds to loopback. It serves only explicit frontend routes, source assets, and the bundled font. It has no API proxy. If the default port is occupied, either stop that server yourself or explicitly choose `EPOCH_FRONTEND_PORT=5174 npm run dev --prefix frontend`. An alternate origin must also be included in the backend's explicit `EPOCH_CORS_ORIGINS` configuration; do not weaken browser security.

## Pages

| URL | Behavior |
| --- | --- |
| `/chat`, `/chat?chat=UUID` | Hermes chat and saved conversation history |
| `/debugger`, `/debugger?chat=UUID` | Select a conversation, inspect its requirements and explicitly request an investigation |
| `/debugger?mode=release` | Separate release evaluation example using local simulated services |
| `/debugger?task=UUID` | Actual run history, sourced checkpoints, activity and simulated state |
| `/incidents` | Incident list, source evidence, related runs, recurrence and explicit Luna analysis |
| `/traces` | Local trace search, span hierarchy and explicit Ollama questions with saved cited answers |
| `/demo/chat` | Existing Atlas 2.4 release fixture as a conversation |
| `/demo/debugger` | The same demo's failure, candidate, checks, publication and continuation |
| `/`, `/index.html` | Compatibility aliases for real chat |
| `/fixtures.html` | Compatibility alias for demo chat |

Same-mode navigation retains in-memory drafts, selection, disclosures and page scroll. Browser Back/Forward and task-ID links are supported. Real and demo modes use separate entrypoints and controllers. Demo policy forbids connections; the real entrypoint permits only explicit loopback API requests. Startup and navigation may read connection status and saved records. They never send messages, run evaluations or request investigations. Connection settings can change the local server.

## Hermes chat and manual investigation

Send a message to start Hermes and continue the same saved conversation with
follow-up messages. The chat API stores visible messages and operation status
separately from release tasks. Requests use exact retry identities saved before
submission; uncertain acknowledgements require an explicit retry. Reloading and
reconnecting do not replay work. While the selected operation runs, SSE provides
provisional text/stages and the UI polls its saved conversation every 1.5 seconds.
Runtime/list refreshes run independently on full reads and completion; PDF metadata
refreshes independently during work and at completion. Separate notices preserve an
available answer when a panel fails. Live text updates do not rebuild PDF previews.
Polling stops while idle after runtime becomes available, including after a failure.
Hidden tabs close SSE and pause polling; returning performs a read-only refresh and
reconnects to the current snapshot. When another operation occupies Hermes, availability
checks run at most every five seconds. Failed active reads back off up to 30 seconds.

Open **Debugger** from a conversation to inspect it. Starting an investigation
explicitly requests Luna analysis of original user requirements, visible responses,
operation errors and captured tool activity. Findings retain evidence references,
hypotheses and missing evidence. This is a general investigation surface, not a
new trusted evaluator for arbitrary tasks. Existing release criteria and repair
permissions remain unchanged. Standard investigation remains diagnosis-only;
the PDF actions below can generate a tool change and run Hermes recovery.

Hermes still has only the configured tools; the current business tools use local
simulated services. General conversation does not imply access to arbitrary live
services. Debugger analysis requires the existing backend debugger configuration.

## PDF workshop

New chats default to PDF workshop. Add a retreat/festival pack or upload a static
PDF, then send the sample task. Files are scoped to the current conversation;
published tools are shared within its project. Adding files and opening Debugger
never start a model call. Preview displays pages rendered from the actual PDF.

The initial renderer genuinely draws past the first page boundary. Its saved output
and host checks make **Fix PDF tool** eligible. When Hermes records a missing merge
capability, **Create merge tool** becomes eligible. Both require explicit action and
show generation, verification, publication and recovery separately. Generated source,
proofs and saved versions appear in expandable details. Rollback restores a prior
bundle only while idle. CSV history is retained on disk but retired from execution.

See [backend PDF setup](../backend/docs/PDF_WORKSHOP.md) for the required local image.
The browser request journal preserves the exact endpoint and payload. Old pending CSV
requests are archived rather than replayed as PDF requests. Desktop/mobile HTTP tests
are in `tests/pdf-http.browser.mjs`; they need the separate local test API on port
8011 and the normal frontend server. These browser tests disable models; the backend
acceptance harness separately executes real Hermes and Luna.

## Separate release evaluation

Open `/debugger?mode=release`, enter the request and release value, choose a
sandbox scenario, then select **Run release evaluation**.
The release workflow creates a ticket, attaches the required checklist and notifies
QA with both links. Luna supervision defaults on and interprets supported additions
from the request. Direct execution remains available. Arbitrary workflows are not inferred.

The UI reads `/api/runtime` and blocks starting while execution is unavailable or
another run is active. Installation detection is not a model-connectivity test.
The backend uses its existing Hermes configuration; no credentials come from the
browser. Business objects are local simulations. The server's configured model
provider receives the execution inputs when you explicitly start a run.

The release evaluation view shows the selected run's backend checkpoints, source and
evidence references, trusted verification, final executor text, missing evidence,
and partial objects. **Run history** selects earlier attempts. **Request
cancellation** waits for the backend's terminal status. **Start another release
run** opens a separate sandbox; it does not resume or repair the previous attempt.

The intake and execution adapters each freeze their own request ID and payload in
per-tab session storage before POST. Uncertain acknowledgements survive reload.
Reconnect and navigation only read; **Retry exact run request** uses the original
ID, task, content and server. Explicitly rejected requests return to the form only
through a review action. Corrupt or unavailable recovery storage blocks new writes
for the affected operation.

Named Server-Sent Events (SSE) trigger authoritative run/state/trace refreshes.
Persisted trace sequences provide ordered, deduplicated activity. Read-only polling
also recovers stream failures and unknown future event types. The stream closes
when the backend records a terminal status. Same-page navigation reuses the trace
cursor; a full reload safely rereads persisted history from zero. Neither action
replays execution. Missing evidence never becomes a fabricated success.

Supervised runs expose recorded clarification questions and additive feedback.
Each submission preserves the current revision and exact retry identity. Opt-in
environment repair follows the server's advertised targets and Docker availability:
checklist serialization, missing QA-owner lookup and outdated guidance selection.
The debugger shows generated source, investigation, verification proofs, publication,
effective shared artifacts and the run's pinned artifacts. Rollback applies to future
runs. Publication and task completion remain separate outcomes. The backend's
Phase 6/7 development-acceptance warning remains visible.

## Incidents and telemetry

Open **Incidents** to filter by project and inspect source records, inclusion/exclusion
reasons, related run links, repair records and recurrence counts. Read-only refreshes
run every five seconds while this page is visible; hidden pages do not poll incidents.
The telemetry panel separates local collector readiness from configured Neatlogs cloud
export acceptance and verified cloud readback. Export acceptance alone does not establish successful readback. Credentials belong in the backend process, never this UI.

Import up to 200 exported Slack or support JSON records by pasting or loading a file.
Each record requires `source_type`, `source_id`, timezone-aware `timestamp`, `project_id`
and `text`; optional source/task/run/workflow references help correlation. Imported
observations remain untrusted. Importing does not start a model, executor or repair.

**Analyze incident** and **Ask question** each explicitly request one bounded Luna
analysis. The view keeps citations, hypotheses, missing evidence and failed outcomes.
These explanations do not authorize repairs. Imports and model actions retain their
request IDs in per-tab storage before sending; uncertain acknowledgements require an
explicit exact retry, including after reload.

The server normalizes outer whitespace. Responses are validated; late or unrelated records do not replace current selection. Missing selected tasks retain a clearly unavailable receipt while healthy list/connection reads continue. Switching servers clears previous receipts. Pagination and detail refresh remain available.

## Demo and evidence

Use **Explore release demo**. It starts at the existing interrupted Atlas release, including a rejected candidate. Open **Demo controls** to advance records, restart from planned, or explore disconnection and acknowledgement-loss cases. Nothing runs on a timer.

The debugger stages are Failure → Diagnosis → Candidate change → Verification → Publish → Resume task. Each derives its status from fixture evidence. Rejected candidates, partial artifacts, original intent, clarification, sourced checkpoints, and prior revisions remain inspectable. Repair activation does not complete the task. Feedback creates a new fixture revision without inherited passes.

On the fixture demo pages, all displayed execution, diagnoses, diffs, tests and artifacts are authored UI fixtures. JSON inspection and downloads preserve that label. No real business services, live model, secure repair runner, or persistent environment change is represented as implemented. Only the existing release example is included.

Demo state exists in page memory. Reload resets it. The existing ID-only pending marker reports lost-submission uncertainty after an unresolved reload and never silently repeats a command. Read-only acknowledgement lookup and the existing evidence/scope guards remain in place. The [future contract proposal](CONTRACT-PROPOSAL.md) remains unagreed; it is not an implemented API.

## Verification

Run checks after the complete UI implementation:

```sh
npm ci --prefix frontend
npm exec --prefix frontend -- playwright install chromium
npm run test:all --prefix frontend
npm run test:integration --prefix frontend
npm run test:execution --prefix frontend
```

The integration runner uses isolated temporary backend data and a configurable frontend port (`EPOCH_FRONTEND_PORT`, default 5173), stopping only its own processes. It exercises real HTTP intake and restart persistence. The execution runner uses `backend/tests/frontend_server.py` with explicit test actors and real API, SQLite, sandbox tools and trusted checks. It does not invoke actual Hermes, Luna or Docker and is never used by the production entrypoint. Browser transport-fault cases are labeled separately. Filter a focused run with `EPOCH_BROWSER_GREP` and `EPOCH_BROWSER_PROJECT` (for example `desktop`). See [the evidence record](evidence/README.md) for historical results and [current status](../docs/status.md) for this integration's actual checks and limitations.

The frontend remains plain HTML/CSS/browser modules with no runtime framework or build step. [Design notes](DESIGN.md), [implementation plan](PLAN.md), [product context](PRODUCT.md) and [integration plan](INTEGRATION_PLAN.md) preserve the earlier UI planning context. The [backend handoff](../backend/docs/FRONTEND_HANDOFF.md), [Phase 6/7 handoff](../backend/docs/PHASES_6_7_HANDOFF.md) and [incident contract](../backend/docs/INCIDENT_IMPLEMENTATION.md) describe the current interfaces. Focused local checks do not establish live-model repair or authenticated Neatlogs cloud acceptance.
