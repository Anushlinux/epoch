# Frontend verification evidence

Verified September 6, 2026, from `origin/main` base `e1395bc`. This evidence establishes **frontend behavior only**. All in-app execution, repair, test-result and artifact records remain authored fixtures. No backend run IDs or actual sandbox/provider objects exist.

## Reproduce

From the repository root:

```sh
node --test frontend/tests/state.test.mjs
npm ci --prefix frontend
npm exec --prefix frontend -- playwright install chromium
npm run test:browser --prefix frontend
ao preview frontend/index.html
```

Node 26.8.1 / npm 11.19.0 were used. Playwright 1.63.0 is pinned in the frontend-local lockfile as a development-only dependency. There are no browser runtime dependencies. Final tooling remains provisional until joint Task 01 agreement.

Browser tests serve local source through Playwright request interception at a reserved `.invalid` test origin. They do not start an application server or contact backend endpoints. Requests outside that origin are denied. This is a test harness, not an implemented API or live integration.

## Actual results

- `npm run test:all --prefix frontend`: **18 state tests and 20 browser tests passed**. Browser coverage runs ten cases in Chromium at 1440×1000 and an emulated 390×844 mobile viewport.
- `npm ci --prefix frontend --ignore-scripts`: clean lockfile install passed (3 packages; npm reported 0 vulnerabilities). `node --check` passed for all three browser modules.
- Documentation integrity: 113 relative Markdown links/anchors checked; seven task structures and shared agent entrypoints passed. `docs/direction.md` matches the base byte-for-byte with SHA-256 `791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`; original Markdown hard breaks at lines 3–5 remain intact. Authored diff whitespace check passed.
- State checks cover all six checkpoint states, evidence scope and criterion binding, rejection of unsupported passes/completion, immutable original requirements, partial results, rejected candidates, repair/task separation, stale/duplicate events, event gaps, reconnect snapshot continuity, missing evidence, invalid inputs, repeated commands, acknowledgement loss, feedback history and reconnect failure/retry.
- Browser checks cover request/clarification preservation, required fields, script-like text escaping, uncertain request and feedback retries, blocked disconnected submissions, restored cursors, rejected repair evidence, partial artifacts, downloaded fixture provenance, revised intent/history, tabs with arrows/Home/End, skip link, dialog Escape/focus return, reduced motion and long-content/mobile overflow.
- First browser pass: 16/18 passed. The two failures were one test selector matching both a visible reconnect notice and a screen-reader announcement. The selector was scoped to the visible notice. Added reconnect-failure retry coverage; final 20/20 passed.
- Impeccable's detector ran once on the authored UI source: no regex findings. It reported **degraded mode** because its optional HTML/CSS parser modules were unavailable. It did not evaluate computed contrast or provide a full accessibility audit. Keyboard/mobile tests and screenshot inspection are separate evidence.
- A direct sRGB contrast calculation found three small-text colors below 4.5:1 (footer, placeholder and navigation label). Their colors now use a darker shared muted token; its contrast against the canvas/rail/white surfaces is at least 4.85:1. These are mechanical color corrections after the screenshots, not a full accessibility audit.
- Bounded visual QA: one desktop/mobile inspection batch and one final capture/confirmation batch. Final screenshots were opened and inspected. Full-page captures are taken from the document top.

## Screenshots and AO preview

- [Desktop task overview](desktop.png): actual Chromium test-browser render at 1440px width; full-page capture.
- [Mobile task overview](mobile.png): actual Chromium test-browser render at 390px CSS width (device emulation, not physical-device proof); full-page capture.
- [AO Browser repair view](ao-workspace.png): actual session-owned AO page at 618×987, showing the rejected fixture candidate, diagnosis, trigger and illustrative diff.

The app was opened using `ao preview frontend/index.html`, inspected using `ao browser snapshot`, and navigated to the repair view with `ao browser act 'Repairs'`. The first AO screenshot returned an internal error and an early click was not reflected. Reopening the exact preview URL restored interaction; the next AO screenshot succeeded and was inspected. No launch configuration or separate preview server was added. Network capture was not enabled. The actual AO page also completed Results → feedback entry → Create fixture revision → Revision 2; `ao browser errors` reported no browser errors.

## Integration gaps

The [contract proposal](../CONTRACT-PROPOSAL.md) is frontend-local and **not agreed with Rajdeep**. No backend contract, branch/session handoff, endpoint or sanitized actual failure/repair run was available. Actual supervised repair verification, durable duplicate prevention, live reconnect, evaluator correctness, secure repair isolation, persistent environment changes and later-session reuse remain unverified. No live effect, deployment, model access, or backend compatibility is claimed.

Data is retained only in page memory; reload/restart discards the fixture session. Requests outside the authored release scenario remain verbatim with planned checkpoints. Feedback is recorded verbatim and does not rewrite old criteria or start execution. The UI's evidence guards check display completeness; they are not trusted outcome checks. Mobile Safari, physical touch devices and screen-reader output were not tested. CI has not been added or represented as running; all reported tests ran locally.
