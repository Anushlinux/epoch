# Frontend verification evidence

## Current Phase 1 intake integration

The primary `frontend/index.html` now uses real health/create/list/detail endpoints. The original fixture workspace is at `frontend/fixtures.html`; all execution/repair records there remain authored fixtures.

- `npm run test:all --prefix frontend`: **37 state tests and 26 fixture browser tests passed** (13 intake adapter/state tests plus the original 24 state tests).
- `npm run test:integration --prefix frontend`: actual local HTTP checks and **12 Chromium intake browser tests passed**, six cases each on 1440px desktop and 390px mobile emulation. The unchanged installed backend CLI used a random loopback port and temporary SQLite data, then was stopped and its data removed.
- [Actual HTTP evidence](intake-http.json): Phase 1 health with execution disabled, 201 create, 200 identical/whitespace-normalized retry, 409 changed-content conflict, 422 invalid input, 404 missing task, 403 unapproved origin, allowed CORS preflight, list/detail and record/request-ID persistence across a real server restart. This is real local intake/storage proof only; no business task executed.
- Browser source files were served through test interception at `http://localhost:5173`, an origin supported by the backend's documented configuration. API requests went to the actual server with explicit CORS configuration. Chromium's local-network-access permission was granted to that test origin; web security was not disabled. No frontend preview server was created.
- Browser coverage includes saving and reading original text, script-like text escaping, form validation, post-save draft clearing, reload/list/detail, keyboard skip link and selection focus, mobile overflow, real 409 rejection and corrupt recovery identity. In the lost-acknowledgement test, the actual server's 201 response is deliberately dropped; reconnect after reload emits zero POSTs, and explicit identical retry receives 200 with the same task ID and no extra task. Offline mode and a transport-body mutation producing a real 422 are deliberate test faults, not spontaneous backend failures.
- [Desktop intake screenshot](intake-desktop.png) and [mobile intake screenshot](intake-mobile.png) show actual browser renders backed by the temporary API. Their task IDs/times came from local intake. The temporary records were removed after testing; they are not links to persistent shared objects. Both screenshots were visually inspected in one batch; no visual redesign followed.
- Early verification exposed an unbound native browser fetch call and an unsupported IPv6 CSP source; both were fixed. The test browser also needed the local-network permission above. A selector was narrowed to distinguish a visible notice from its screen-reader announcement. Concurrent browser suites initially shared an artifact directory and caused one trace-cleanup failure; the intake suite now uses its own output directory. Both complete suites subsequently passed.
- AO opened and interacted with the actual intake app. The separately started temporary backend returned healthy Phase 1 data, but AO fetch was denied by CORS. Explicitly configuring its generated `.localhost` origin failed backend `check-config` with exit 2 because only exact loopback hostnames are allowed. This limitation was reported to epoch-2; no backend edits, proxy or invented route were added. Both bounded AO intake screenshot attempts failed with an internal AO error; no intake screenshot from AO is claimed. Backend transport integration in AO remains blocked; the real browser integration proof above uses the documented origin.

Documentation validation passed for 167 relative Markdown links including six anchors, all seven task structures and canonical agent entrypoints. `docs/direction.md` remains byte-identical to `e1395bc` with its original hard breaks. `git diff --check` passed; backend source/workflow match `origin/main`.

Final completion checks also reproduce a missing selected detail with a deliberately substituted real 404 response. The API can reconnect through healthy health/list reads while the retained receipt is labeled unavailable; a later successful detail read clears that label. A unit regression verifies that switching API origins clears the previous server’s save notice and selected receipt. Both added state regressions failed before the fix and passed afterward.

The Phase 1 mapping is recorded in the [contract document](../CONTRACT-PROPOSAL.md). Future execution/event/transition/feedback/repair contracts remain review requests, not agreed endpoint behavior. No supervised repair or later-session environment reuse was verified.

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
