# Epoch frontend

Epoch has a Hermes-inspired chat interface and a separate debugger pipeline. The real workspace saves and reads Phase 1 tasks. The interactive Atlas release example is a separate, clearly labeled demo.

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
| `/debugger?task=UUID` | Saved request context and an unstarted pipeline |
| `/demo/chat` | Existing Atlas 2.4 release fixture as a conversation |
| `/demo/debugger` | The same demo's failure, candidate, checks, publication and continuation |
| `/`, `/index.html` | Compatibility aliases for real chat |
| `/fixtures.html` | Compatibility alias for demo chat |

Same-mode navigation retains in-memory drafts, selection, disclosures and page scroll. Browser Back/Forward and task-ID links are supported. Real and demo modes use separate entrypoints and controllers. Demo policy forbids connections; the real entrypoint permits only explicit loopback API requests. Opening or navigating never submits a request. Connecting remains an explicit read-only action.

## Real task intake

A chat is currently one saved request, with a system receipt saying **Request saved. Execution is not available yet.** No executor or reply is fabricated. New chat starts another request. The debugger remains unstarted for real tasks because no execution endpoint exists.

The existing Phase 1 adapter and HTTP contracts remain unchanged. Before POST it freezes the client request ID, message, project label, and API origin; stores the complete pending payload in per-tab session storage; and blocks edits until reconciliation. An unknown acknowledgement is recoverable by read-only reconnect followed by an explicit exact retry. No replacement ID is silently allocated. Rejected content returns to the draft only through an explicit action. Unavailable or corrupt recovery storage blocks new submissions.

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
```

The integration runner uses isolated temporary backend data and a configurable frontend port (`EPOCH_FRONTEND_PORT`, default 5173), stopping only its own processes. It exercises real HTTP intake and restart persistence. Browser transport-fault cases are labeled separately. See [the evidence record](evidence/README.md) for actual results and limitations.

The frontend remains plain HTML/CSS/browser modules with no runtime framework or build step. [Design notes](DESIGN.md), [implementation plan](PLAN.md), and [product context](PRODUCT.md) describe this UI scope. Backend execution and later repair phases remain separate work.
