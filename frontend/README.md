# Epoch frontend workspace

The primary page connects to the **real local Phase 1 task-intake API**. It saves requests, lists stored tasks and inspects task details. Every task remains **pending; execution is disabled**. Checkpoints, activity, feedback, repairs and result artifacts exist only on the separate, clearly labeled fixture page.

## Open and connect

Run the minimal frontend development host from the repository root:

```sh
npm run dev --prefix frontend
```

Open `http://127.0.0.1:5173` in a browser, or use `ao preview http://127.0.0.1:5173` in AO. This ordinary HTTP page connects directly to the backend; there is no API proxy or request interception. Node's built-in HTTP server serves only the frontend entrypoints/assets, binds to loopback and uses port 5173, which the backend already permits. No dependencies, backend CORS changes or `.ao/launch.json` are needed. If port 5173 is occupied, stop your existing frontend explicitly before starting this one; the command never kills another process or silently changes the origin.

Set up the unchanged backend using its [README](../backend/README.md). For an isolated local preview on macOS/Linux, after its `uv sync --frozen` setup, run in another terminal:

```sh
EPOCH_DATA_DIR="$(mktemp -d)" uv run --project backend --frozen epoch-backend serve
```

The temporary data directory keeps this preview separate from existing tasks. The default API origin is `http://127.0.0.1:8000`; set that in the app and choose **Connect / reconnect**. The UI also accepts another explicit loopback HTTP port. The backend's default allowed origins already include `http://127.0.0.1:5173` and `http://localhost:5173`. No credentials are used. Saving a request stores data only; it does not schedule work.

Both servers must remain running while using the preview; stop each with Ctrl+C when finished. Closing only the browser does not stop them. The separate future fixture page is `http://127.0.0.1:5173/fixtures.html` and is linked from the app. Opening either page never submits automatically.

The older `ao preview frontend/index.html` static-file path is still available for disconnected inspection, but its generated `.localhost` subdomain is outside the current backend CORS validator. Use the supported dev URL above for functional integration. Actual AO intake through that URL is verified in the evidence record. Direct `file://` loading is unsupported.

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

Stop any existing frontend dev host before running `test:integration`, which needs port 5173. The integration runner starts the actual frontend dev command and unchanged installed backend CLI on a temporary backend port/database. It tests real HTTP/browser intake and restart persistence, then stops its servers and removes its database. The normal intake page and modules load over HTTP; source interception and special browser permissions are not used. Deliberate API transport-fault cases remain separately labeled.

HTML/CSS/browser modules remain provisional, with no frontend runtime framework, production build or frontend CI workflow. Backend selections and its CI workflow are recorded separately. Actual supervised repair remains **blocked on later backend phases**.
