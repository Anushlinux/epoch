# Epoch frontend workspace

The primary page connects to the **real local Phase 1 task-intake API**. It saves requests, lists stored tasks and inspects task details. Every task remains **pending; execution is disabled**. Checkpoints, activity, feedback, repairs and result artifacts exist only on the separate, clearly labeled fixture page.

## Open and connect

From the repository root, use `ao preview frontend/index.html`. This opens the actual application through AO's existing static preview; no frontend server, runtime dependencies or launch configuration are needed. The fixture workspace is at `frontend/fixtures.html` and is linked from the app. Opening either page never submits a request automatically.

Set up the unchanged backend using its [README](../backend/README.md), then set **API origin** to its loopback HTTP origin and choose **Connect / reconnect**. The UI accepts `http://127.0.0.1:<port>` or `http://localhost:<port>`. Its default is `http://127.0.0.1:8000`. No credentials are used. Saving a request stores data only; it does not schedule work.

For an existing local frontend host, configure the backend's `EPOCH_CORS_ORIGINS` to a JSON list containing that exact origin. The documented defaults include `http://localhost:5173`. A browser may also ask for local-network access; allow it for the intended local workspace. Do not disable browser security. Direct `file://` loading is unsupported.

**Current AO connection limitation:** AO's static preview uses a generated `.localhost` subdomain. Phase 1's configuration validator accepts only exact `localhost`, `127.0.0.1` and `::1` CORS hostnames. Setting the generated AO origin explicitly fails `check-config`; leaving it out causes an actual browser CORS denial. The UI can be inspected in AO, but intake there remains blocked pending a backend-owner decision. No backend source change or proxy workaround is included. Actual browser integration was verified from the documented `http://localhost:5173` origin with test-source interception and real API requests, as described in the evidence record.

## Submission and recovery

Before POST, the UI freezes the `client_request_id`, message, project label and API origin. It stores that full pending payload in **this tab's session storage**, then disables edits and new submissions until the response is reconciled. It refuses to send if that storage write fails. Successful acknowledgement clears the pending payload and the request draft. The saved record retains its original text; the backend normalizes outer whitespace.

An unknown acknowledgement means the task may already be saved. Reload retains a recoverable pending payload; reconnect performs health/list/detail reads only. **Retry exact submission** deliberately sends that same ID/content, using Phase 1's documented 200 identical-retry behavior. It never silently creates a replacement ID. A 409/422/403 rejection retains the frozen content until the user explicitly returns it to the draft. An unreadable recovery identity blocks submissions and permits read-only inspection. Closing a tab, clearing its storage or losing the browser session cannot provide durable client recovery; inspect the backend's saved tasks before making another submission. There is no client-request-ID lookup endpoint.

List/detail reads reject unrelated task IDs, malformed records and unsupported phases/statuses. Late reads cannot overwrite a newer selection. Reconnect retains the last loaded records while unavailable and revalidates them before claiming a connection. A missing selected task does not block a healthy reconnect: its previous receipt is marked unavailable until the API returns it again. Switching servers clears the previous server’s receipt and save notice. There is no polling, SSE, feedback or repair request from this page.

## Future workflow fixtures

The separate fixture page preserves requests/clarifications, sourced checkpoints, observable activity, rejected repairs, illustrative diffs/tests, inspectable labeled JSON artifacts, feedback revisions and history. Custom fixture requests stay verbatim without invented execution. Fixture progress advances only through explicit local controls. All displayed execution and repair evidence on that page is authored data, not real Hermes execution or a simulated-service effect.

Fixture data/deduplication live in page memory. Its separate ID-only reload marker cannot recover a payload; unresolved reload shows uncertainty. These fixture semantics are not the Phase 1 HTTP adapter. The [contract proposal](CONTRACT-PROPOSAL.md) records remaining future mapping/recovery questions, without claiming backend agreement.

## Implementation and checks

- [Intake adapter and state](src/intake-api.mjs), [intake view](src/intake.mjs), [styles](src/intake.css): published Phase 1 models and routes only.
- [Fixture adapter](src/fixtures.mjs), [fixture state guards](src/state.mjs), [fixture view](src/app.mjs): isolated future interaction examples.
- [Plan](PLAN.md), [product context](PRODUCT.md), [design notes](DESIGN.md) and [verification evidence](evidence/README.md).

```sh
npm ci --prefix frontend
npm exec --prefix frontend -- playwright install chromium
npm run test:all --prefix frontend
# After the documented backend uv sync --frozen setup:
npm run test:integration --prefix frontend
```

The integration runner launches the unchanged installed backend CLI on a temporary port/database, tests actual HTTP and browser intake, verifies restart persistence, and cleans up. It does not create a frontend server. Playwright intercepts only frontend source files; API requests reach the real backend. Deliberate transport-fault cases are separately labeled.

HTML/CSS/browser modules remain provisional, with no frontend runtime framework, production build or frontend CI workflow. Backend selections and its CI workflow are recorded separately. Actual supervised repair remains **blocked on later backend phases**.
