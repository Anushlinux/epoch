# Frontend verification evidence

## Phase 3 frontend/backend connection — September 6, 2026

Implemented on `codex/connect-frontend-backend` against the published backend
handoff. The production backend source, evaluators and fixture entrypoint are
unchanged. The additional Python file is a test-only browser server.

| Check | Actual result |
| --- | --- |
| `npm test --prefix frontend` | 50 unit/state tests passed |
| `npm run test:browser --prefix frontend` | 34 fixture browser checks passed |
| `EPOCH_FRONTEND_PORT=5191 npm run test:integration --prefix frontend` | Real Phase 3 HTTP checks plus 14 desktop/mobile intake cases passed |
| `EPOCH_FRONTEND_PORT=5192 npm run test:execution --prefix frontend` | Real HTTP/SSE/storage/checks with an explicit test executor; 8 desktop/mobile execution cases passed |
| `backend/.venv/bin/python -m pytest backend/tests -q` | 156 passed; two existing dependency deprecation warnings |
| `backend/.venv/bin/ruff check backend` | Passed |
| `backend/.venv/bin/ruff format --check backend` | 40 files passed |
| `backend/.venv/bin/python backend/scripts/export_contracts.py --check` | Published exports match source |

Execution coverage includes explicit start, pending checkpoints, successful trusted
verification, the broken-checklist failure with its partial ticket, independent
executor text, named SSE, contiguous trace recovery, cancellation, run history,
reload, uncertain-acknowledgement recovery and no automatic execution replay.
Unit cases additionally cover corrupt storage, origin/task identity, stale reads,
unknown event types, sequence gaps, busy conflicts and uncertain storage errors.

The backend is real; **Hermes is explicitly replaced in the test process only**.
`backend/tests/frontend_server.py` calls existing simulated tools, and the unchanged
trusted evaluator judges their persisted state. These checks do not establish a
new installed-Hermes/model acceptance result, automatic supervision or repairs.
The test runner stops its own processes and removes its temporary databases.

- HTTP records: [intake](phase3-intake-http.json), [execution test harness](phase3-execution-http.json).
- Saved run/state/trace evidence: [desktop](phase3-execution-runs-desktop.json), [mobile](phase3-execution-runs-mobile.json). Each explicitly identifies the test executor.
- Intake screenshots: [desktop](phase3-intake-desktop.png), [mobile](phase3-intake-mobile.png).
- Execution screenshots: [desktop](phase3-execution-desktop.png), [mobile](phase3-execution-mobile.png).
- Trusted-result screenshots: [desktop](phase3-results-desktop.png), [mobile](phase3-results-mobile.png).

Screenshots were visually inspected. This caught stale pending/unavailable copy;
that copy was corrected and the affected browser suites rerun. Existing fixture
screens and historical evidence below remain separate from the Phase 3 evidence.

A read-only check found the pre-existing backend on port 8000 still serving Phase
1. It was left untouched. The current production backend was started on port 8002
with its normal local data directory and no global configuration changes. Its
health reports Phase 3; its runtime reports Hermes unavailable because it cannot
read the local model configuration safely. Actual model execution is therefore
unavailable on this host until Hermes configuration is resolved. This is separate
from the completed frontend/API connection. The in-app browser blocked the local
preview; desktop/mobile Playwright HTTP tests provide browser evidence instead.

Use the existing frontend at `http://127.0.0.1:5173/chat` and enter
`http://127.0.0.1:8002` in Connection settings for this running backend. Reloads
require an explicit reconnect. No live model or business-service write was made.

## Chat and debugger redesign — September 6, 2026

Implemented from refreshed `origin/main` at `4bfb841` on `codex/epoch-chat-debugger`. All initial UI changes were completed before test execution, as requested. The earlier records below describe previous layouts; the named intake screenshots and HTTP artifact now contain the latest verification run.

| Check | Actual result |
| --- | --- |
| `npm test --prefix frontend` | 41 state tests passed |
| `npm run test:browser --prefix frontend -- --workers=1` | 34 checks passed: 17 cases each on desktop and mobile Chromium |
| `EPOCH_FRONTEND_PORT=5175 npm run test:integration --prefix frontend` | Real HTTP checks and 14 intake browser checks passed |

The demo checks cover both page routes, browser Back/Forward, independent request and feedback drafts, disclosure and scroll restoration, direct task links, missing sessions, clarification, rejected repair attempts, verification versus publication, publication versus task completion, partial results, revision history, source inspection, JSON downloads, keyboard controls, reduced motion, and long content. Unknown acknowledgements remain frozen; lookup reconciles without replay. Disconnected or unrecoverable sessions cannot submit. Later checkpoint changes cannot inherit an old delivered label.

The integration runner used the real frontend server at port 5175, an unchanged local Phase 1 backend, and a temporary SQLite database. It verified saving and rereading original requests, persistence across backend restart, exact retries, rejected content recovery, unavailable detail, offline reads, independent drafts, direct debugger links, and an unstarted real pipeline. Read-only navigation sent no POST requests. The generated [HTTP evidence](intake-http.json) preserves exact status results. Both test servers and their database were removed by the runner.

The final screenshots were visually inspected. The review fixed a mobile grid placement issue, preserved drafts through history navigation, kept pipeline explanations visible, prevented the skip link from scrolling the fixed shell, and reduced the mobile header's debugger link to a labeled icon. A final focused desktop/mobile layout pass refreshed the screenshots after that header adjustment.

- Empty chat: [desktop](empty-chat-desktop.png) and [mobile](empty-chat-mobile.png).
- Atlas conversation: [desktop](chat-desktop.png) and [mobile](chat-mobile.png).
- Rejected repair pipeline: [desktop](debugger-desktop.png) and [mobile](debugger-mobile.png).
- Actual saved intake: [desktop](intake-desktop.png) and [mobile](intake-mobile.png).

The normal in-app preview runs at `http://127.0.0.1:5174/chat`, with an isolated backend at `http://127.0.0.1:8001`. Its only configured browser origin is `http://127.0.0.1:5174`. The existing servers at 5173 and 8000 were left untouched. Connection was confirmed through the actual page controls. Reloading still requires an explicit Connect / reconnect; the interface never auto-submits. The demo is at `/demo/chat` and `/demo/debugger` on the same frontend host.

The backend, HTTP adapter, fixture adapter, evidence guards, and `docs/direction.md` are unchanged. Route and asset allowlist checks passed, including demo `connect-src 'none'` and blocked backend/dotfile access. Font assets are bundled locally with their license. The first browser launch required the approved sandbox escalation; a later run exhausted temporary disk space and was repeated successfully after cleaning this task's generated cache. These were environment failures, not reported as application passes.

This proves frontend behavior and local request storage. All demo execution, tool activity, repair code, verification results and artifacts remain authored fixtures. No execution, feedback, conversation, or repair endpoint was added. Physical devices, Mobile Safari, screen-reader output, and a live executor were not tested. User visual feedback remains the next review input.

## Earlier Phase 1 intake integration

The primary `frontend/index.html` uses real health/create/list/detail endpoints. The separate `frontend/fixtures.html` workspace contains only authored execution/repair records. Verified against unchanged backend Phase 1 at `0a062dd` on September 6, 2026.

- `npm run test:all --prefix frontend`: **41 state tests and 30 fixture browser tests passed** (28 fixture state tests, 13 intake state tests; 15 browser cases each on desktop/mobile).
- `npm run test:integration --prefix frontend`: actual HTTP/dev-host checks and **12 Chromium intake browser tests passed**, six cases each on 1440px desktop and 390px mobile emulation. The runner starts the real Node frontend host at `http://127.0.0.1:5173` and the unchanged installed backend CLI on a random loopback port with temporary SQLite data. It stops its own servers and removes that test data afterward.
- [Actual HTTP evidence](intake-http.json): health with execution disabled, 201 create, 200 identical/whitespace-normalized retry, 409 changed-content conflict, 422 invalid input, 404 missing task, 403 unapproved origin, allowed CORS preflight, list/detail and record/request-ID persistence across a real server restart. The dev host serves the normal entrypoint/modules, refuses POST, and does not expose `.env` or backend files. This proves local intake/storage only; no business task executed.
- Intake browser source loads normally over HTTP from the same user-openable dev command. API requests reach the actual backend with its supported loopback CORS origin. No frontend source interception, API proxy, special browser permissions or disabled web security are used. The fixture-only browser suite still uses its isolated test harness.
- Intake browser coverage includes original text preservation, script-like text escaping, form validation, draft clearing after save, reload/list/detail, keyboard skip link and selection focus, mobile overflow, real 409 rejection and corrupt recovery identity. A deliberately dropped real 201 response tests acknowledgement loss: reload/reconnect sends zero POSTs, then explicit identical retry receives 200 with the same task ID and no extra task. Offline transport and a request-body mutation producing real 422 are deliberate test faults. A deliberately substituted real 404 tests missing-detail recovery without blocking healthy health/list reconnect. Switching API origins clears old-server notices and selected receipts.
- [Desktop intake screenshot](intake-desktop.png) and [mobile intake screenshot](intake-mobile.png) show actual renders from the normal dev host and temporary API. Their task IDs/times came from local intake; those test records were removed afterward. The screenshots are evidence, not links to shared persistent objects.
- The final fixture regressions reject duplicate, dropped or substituted checkpoint identities and missing failed/needs-input evidence on reconnect or scope adoption. Disconnected New request controls and dispatched form submissions cannot create commands. Later checkpoint changes hide stale Delivered labels; restoring checkpoint passes alone cannot restore delivery. A newer explicit task outcome is required. The supplied task verdict/result remain inspectable and unchanged; these are display guards, not a backend evaluator. The two reconnect regression cases failed before their fixes and passed afterward.

The delayed review of `c1030cc` identified the selected-task 404 issue already fixed in `d2ab892`. The existing state regression now additionally verifies two consecutive healthy reconnects, replacement of the old list with an empty current list, and preservation of a separate frozen acknowledgement-unknown submission with zero replay. `node --test frontend/tests/intake.test.mjs` passed all 13 intake tests after this test-only strengthening; runtime code and the earlier browser evidence are unchanged.

### Actual AO intake and usable preview

Run `npm run dev --prefix frontend`, start the isolated backend as described in the [frontend setup](../README.md), then open `ao preview http://127.0.0.1:5173`. The normal app was connected and exercised in the session-owned AO Browser panel: **Connect / reconnect → Save request → Reload detail**.

[AO intake HTTP confirmation](ao-intake-http.json) records task `7670bab2-0d53-4174-983e-4961fcaefc91` and client request ID `82e194b0-b74c-43b1-9146-ea7211ca62db`. Independent HTTP list/detail reads confirmed one stored request, the original text and **pending** status; health reported `execution_enabled: false`. The [AO connected intake screenshot](ao-intake-connected.png) shows the stored request and retained detail in the actual 618×987 panel. Desktop, mobile and AO screenshots were inspected together; no visual redesign followed.

The frontend at port 5173 and backend at port 8000 were left running with an isolated temporary data directory so the primary preview remains usable. These preview records are separate from the cleaned-up test-runner records. No backend source/default changes, CORS widening, proxy, launch configuration or browser permission override were used. The initial AO tab had unresponsive controls and screenshot errors; opening a fresh AO tab at the same supported URL restored interaction and screenshot capture. This supersedes the earlier generated-origin static-preview connection blocker. That static-file origin remains unsuitable for API integration.

The Phase 1 mapping is recorded in the [contract document](../CONTRACT-PROPOSAL.md). Future execution/event/transition/feedback/repair contracts remain review requests, not agreed endpoint behavior. No supervised repair or later-session environment reuse was verified. Mobile Safari, physical touch devices and screen-reader output were not tested. Frontend CI has not been added; reported frontend checks ran locally.

Final documentation validation passed for 171 relative Markdown links including six anchors, all seven task structures and canonical agent entrypoints. `docs/direction.md` remains byte-identical to `e1395bc` with its original hard breaks at lines 3–5. `git diff --check` passed; backend source/workflow match `origin/main`.

## Historical fixture and rebase verification

Verified September 6, 2026, from `origin/main` base `e1395bc`. This evidence establishes **frontend behavior only**. All in-app execution, repair, test-result and artifact records remain authored fixtures. No backend run IDs or actual sandbox/provider objects exist.

## Reproduce

From the repository root:

```sh
node --test frontend/tests/state.test.mjs
npm ci --prefix frontend
npm exec --prefix frontend -- playwright install chromium
npm run test:browser --prefix frontend
ao preview frontend/fixtures.html
```

Node 26.8.1 / npm 11.19.0 were used. Playwright 1.63.0 is pinned in the frontend-local lockfile as a development-only dependency. There are no browser runtime dependencies. Final tooling remains provisional until joint Task 01 agreement.

Browser tests serve local source through Playwright request interception at a reserved `.invalid` test origin. They do not start an application server or contact backend endpoints. Requests outside that origin are denied. This is a test harness, not an implemented API or live integration.

## Actual results

- `npm run test:all --prefix frontend`: **24 state tests and 26 browser tests passed** after the contract review follow-up. Browser coverage runs thirteen cases in Chromium at 1440×1000 and an emulated 390×844 mobile viewport.
- `npm ci --prefix frontend --ignore-scripts`: clean lockfile install passed (3 packages; npm reported 0 vulnerabilities). `node --check` passed for all three browser modules.
- Documentation integrity: 113 relative Markdown links/anchors checked; seven task structures and shared agent entrypoints passed. `docs/direction.md` matches the base byte-for-byte with SHA-256 `791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`; original Markdown hard breaks at lines 3–5 remain intact. Authored diff whitespace check passed.
- State checks cover all six checkpoint states, evidence scope and criterion binding, rejection of unsupported passes/completion, immutable original requirements, partial results, rejected candidates, repair/task separation, stale/duplicate events, event gaps, reconnect snapshot continuity, missing evidence, invalid inputs, repeated commands, acknowledgement loss, feedback history and reconnect failure/retry.
- Browser checks cover request/clarification preservation, required fields, script-like text escaping, uncertain request and feedback retries, blocked disconnected submissions, restored cursors, rejected repair evidence, partial artifacts, downloaded fixture provenance, revised intent/history, tabs with arrows/Home/End, skip link, dialog Escape/focus return, reduced motion and long-content/mobile overflow.
- First browser pass: 16/18 passed. The two failures were one test selector matching both a visible reconnect notice and a screen-reader announcement. The selector was scoped to the visible notice. Added reconnect-failure retry coverage; initial implementation finished at 20/20. The review follow-up added six browser cases and passed 26/26.
- Impeccable's detector ran once on the authored UI source: no regex findings. It reported **degraded mode** because its optional HTML/CSS parser modules were unavailable. It did not evaluate computed contrast or provide a full accessibility audit. Keyboard/mobile tests and screenshot inspection are separate evidence.
- A direct sRGB contrast calculation found three small-text colors below 4.5:1 (footer, placeholder and navigation label). Their colors now use a darker shared muted token; its contrast against the canvas/rail/white surfaces is at least 4.85:1. These are mechanical color corrections, not a full accessibility audit. Desktop/mobile screenshots were refreshed by the review regression run.
- Bounded visual QA: one desktop/mobile inspection batch and one final capture/confirmation batch. Final screenshots were opened and inspected. Full-page captures are taken from the document top.

## Screenshots and AO preview

- [Desktop task overview](desktop.png): actual Chromium test-browser render at 1440px width; full-page capture.
- [Mobile task overview](mobile.png): actual Chromium test-browser render at 390px CSS width (device emulation, not physical-device proof); full-page capture.
- [AO Browser repair view](ao-workspace.png): actual session-owned AO page at 618×987, showing the rejected fixture candidate, diagnosis, trigger and illustrative diff.

The app was opened using `ao preview frontend/index.html`, inspected using `ao browser snapshot`, and navigated to the repair view with `ao browser act 'Repairs'`. The first AO screenshot returned an internal error and an early click was not reflected. Reopening the exact preview URL restored interaction; the next AO screenshot succeeded and was inspected. No launch configuration or separate preview server was added. Network capture was not enabled. The actual AO page also completed Results → feedback entry → Create fixture revision → Revision 2; `ao browser errors` reported no browser errors.

## Integration gaps

The [contract proposal](../CONTRACT-PROPOSAL.md) is frontend-local and **not agreed with Rajdeep**. No backend handoff or endpoint was available during the original UI implementation. The rebase onto `0a062dd` now includes Phase 1 intake and a [backend handoff](../../backend/docs/FRONTEND_HANDOFF.md); the primary intake UI is now connected as recorded above; future fixture screens remain separate and no actual failure/repair run exists. Actual supervised repair verification, durable duplicate prevention, live reconnect, evaluator correctness, secure repair isolation, persistent environment changes and later-session reuse remain unverified. No live effect, deployment, model access, or backend compatibility is claimed.

Task data is retained only in page memory; reload/restart discards the fixture session. A pending ID-only session-storage marker triggers an explicit recovery-uncertainty notice after an unresolved submission reload; it cannot recover or replay the payload. Requests outside the authored release scenario remain verbatim with planned checkpoints. Feedback is recorded verbatim and does not rewrite old criteria or start execution. The UI's evidence guards check display completeness; they are not trusted outcome checks. Mobile Safari, physical touch devices and screen-reader output were not tested. Frontend CI has not been added; all reported frontend tests ran locally. Backend Phase 1 brings its own CI workflow and validation record.

## Contract review follow-up

Addressed epoch-4's two provisional contract risks. Ordinary event filtering stays strict; an explicit reconciled fixture transition now adopts an acknowledged feedback revision or replacement run. Tests verify parent/history continuity, cursor reset in the new stream, missed-transition reconnect, late old-scope events and rejected unrelated/mismatched transitions. Multi-hop transition chains remain a future backend agreement item.

First submission now freezes the ID, payload and expected revision. Unknown acknowledgement keeps input disabled; the recovery action does read-only lookup rather than resubmitting the command. State tests cover edited payloads and unavailable lookup identity; desktop/mobile tests cover locked controls, ID-only storage, reload uncertainty, explicit local discard and accepted-command marker cleanup. A storage-write failure is tested to refuse submission before any fixture action begins, preserving the draft. No backend durability or authority is implemented by these fixture guards.

The AO page was reopened for this follow-up and again completed feedback → revision 2 using the reconciled adoption path; `ao browser errors` reported no errors. The refreshed desktop/mobile screenshots were inspected without further visual changes.

## Rebase verification

PR #2 was rebased onto `origin/main` at `0a062dd` on September 6, 2026. Conflicts in the root README, status and task index were resolved by retaining the backend Phase 1 record alongside the frontend fixture implementation. Frontend documentation now acknowledges the published intake handoff and the unresolved difference between backend per-task sequences and fixture per-run/revision cursors.

- `npm run test:all --prefix frontend`: **24 state tests and 26 browser tests passed** after the rebase. The regenerated desktop/mobile screenshots are unchanged.
- Documentation checks passed for **163 relative Markdown links/anchors**, all seven task structures and canonical agent entrypoints. `docs/direction.md` remains byte-identical to `e1395bc`, with the SHA-256 and original hard breaks recorded above. `git diff --check` passed; no unresolved conflict entries remain.
- Frontend implementation, tests and tooling match the pre-rebase PR. Backend implementation and workflow match the new base. Backend tests were not rerun for this frontend rebase; their existing Phase 1 validation record is preserved separately.
- No network adapter, backend integration or actual supervised repair verification was added. Existing AO preview evidence above remains applicable to the unchanged UI; the documentation-only conflict resolution did not require another visual QA cycle.


## General chat and manual debugger — September 6, 2026

The replacement chat flow is covered by `tests/chat.test.mjs` and
`tests/chat.browser.mjs`. The full unit suite passes 69 tests. New chat browser
coverage passes six desktop/mobile cases; the existing fixture workspace passes
34 cases. Browser API responses are intercepted test data, not live model output.
The cases verify separate chat/debugger endpoints, read-only navigation and reload,
retained requirements, exact investigation retry, and debugger availability when
Hermes execution is unavailable.

- [General chat, desktop](generic-chat-desktop.png)
- [General chat, mobile](generic-chat-mobile.png)
- [Manual debugger, desktop](manual-debugger-desktop.png)
- [Manual debugger, mobile](manual-debugger-mobile.png)

These images record the new interface with explicitly mocked responses. Historical
screenshots retain their previous names/content. The historical intake browser
suite still targets the removed one-request release-chat form and was not run.
See [current status](../../docs/status.md) for backend checks and remaining limits.


## CSV environment — September 6, 2026

The CSV selector, explicit sample task, immutable environment recovery and
backend-derived verdicts are covered by 75 frontend unit tests and 10 focused
chat browser cases. The four CSV cases were rerun after mobile spacing fixes.
Their API transport is intercepted, but displayed customer/check data comes from
[actual local sandbox execution](../../backend/fixtures/csv/local-evidence.json).
No screenshot is evidence of live Hermes or Luna execution.

- [Broken adapter, desktop](csv-csv_broken-desktop.png)
- [Broken adapter, mobile](csv-csv_broken-mobile.png)
- [Healthy control, desktop](csv-csv_healthy-desktop.png)
- [Healthy control, mobile](csv-csv_healthy-mobile.png)
