# Epoch frontend

Epoch has a chat interface, an execution debugger and an incident workspace. The real workspace connects to the Phase 7 backend for explicit release execution, supervision, feedback and environment repair evidence. The interactive Atlas release example remains a separate, clearly labeled demo.

## Run

From the repository root:

```sh
npm run dev --prefix frontend
```

Open http://127.0.0.1:5173/chat. Start the unchanged backend using [its setup guide](../backend/README.md). Open **Connection settings**, enter its local origin (default http://127.0.0.1:8000), then **Connect / reconnect**.

The host uses Node's built-in HTTP server and binds to loopback. It serves only explicit frontend routes, source assets, and the bundled font. It has no API proxy. If the default port is occupied, either stop that server yourself or explicitly choose `EPOCH_FRONTEND_PORT=5174 npm run dev --prefix frontend`. An alternate origin must also be included in the backend's explicit `EPOCH_CORS_ORIGINS` configuration; do not weaken browser security.

## Pages

| URL | Behavior |
| --- | --- |
| `/chat` | Real request intake and saved conversations |
| `/debugger?task=UUID` | Actual run history, sourced checkpoints, activity and simulated state |
| `/incidents` | Incident list, source evidence, related runs, recurrence and explicit Luna analysis |
| `/demo/chat` | Existing Atlas 2.4 release fixture as a conversation |
| `/demo/debugger` | The same demo's failure, candidate, checks, publication and continuation |
| `/`, `/index.html` | Compatibility aliases for real chat |
| `/fixtures.html` | Compatibility alias for demo chat |

Same-mode navigation retains in-memory drafts, selection, disclosures and page scroll. Browser Back/Forward and task-ID links are supported. Real and demo modes use separate entrypoints and controllers. Demo policy forbids connections; the real entrypoint permits only explicit loopback API requests. Opening or navigating never submits a request. Connecting remains an explicit read-only action.

## Real task intake

A chat starts as one saved request. Saving does not start Hermes. After saving,
enter a release value, choose a sandbox scenario, and select **Start release run**.
The release workflow creates a ticket, attaches the required checklist and notifies
QA with both links. Luna supervision defaults on and interprets supported additions
from the request. Direct execution remains available. Arbitrary workflows are not inferred.

The UI reads `/api/runtime` and blocks starting while execution is unavailable or
another run is active. Installation detection is not a model-connectivity test.
The backend uses its existing Hermes configuration; no credentials come from the
browser. Business objects are local simulations. The server's configured model
provider receives the execution inputs when you explicitly start a run.

Both chat and debugger show the selected run's backend checkpoints, source and
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

All displayed execution, diagnoses, diffs, tests and artifacts are authored UI fixtures. JSON inspection and downloads preserve that label. No real business services, live model, secure repair runner, or persistent environment change is represented as implemented. Only the existing release example is included.

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
