# Epoch frontend fixture workspace

**UI implementation only. Backend integration is blocked.** All displayed execution activity, diagnoses, diffs, verification results and artifacts are authored development fixtures. They are not simulated-service effects, real Hermes execution or verified repair evidence.

Open from the workspace root with `ao preview frontend/index.html`. AO serves the browser modules through its existing local preview. No application server, runtime dependency or launch configuration is required. Outside AO, serve the repository with a static HTTP server; direct `file://` module loading is not supported.

## Explore

- The initial release example shows a failed checklist, a retained ticket and a rejected repair candidate.
- Open **Fixture controls** and choose **Advance fixture** to inspect verifying, active-but-incomplete, needs-input, checking and delivered states. These are manual authored events, never timer-driven execution.
- **Restart release example** clears the example session and starts with planned checkpoints.
- **New request** preserves your text and constraints, asks a fixed fixture clarification, and records a verbatim checkpoint. There is no backend interpretation or execution for arbitrary requests.
- **Results** exposes labeled JSON artifacts. Feedback records an explicit new revision and retains earlier requirements, evidence, artifacts and rejected candidates under **History**.
- Disconnect/reconnect retains current state without submitting work. The acknowledgement-loss control demonstrates reusing the same command ID after an uncertain response.

Everything lives in page memory. Reload resets the example. This is deliberate provisional tooling, not a durable task system. Live deduplication, persistence, authorization and replay safety are backend responsibilities still awaiting agreement.

## Implementation boundary

- [Contract proposal](CONTRACT-PROPOSAL.md): frontend-local information needs and open decisions; **not an agreed backend schema**.
- [State](src/state.mjs): presentation completeness, identity, event ordering and revision history guards. It cannot verify business truth.
- [Fixtures](src/fixtures.mjs): replaceable in-memory adapter and authored records; no network or executable repair.
- [View](src/app.mjs) and [styles](src/styles.css): semantic browser UI, responsive layout, safe text rendering, keyboard tabs and inspectable evidence.
- [Plan](PLAN.md), [product context](PRODUCT.md), [design notes](DESIGN.md) and [verification](evidence/README.md).

Run dependency-free state tests with `node --test frontend/tests/state.test.mjs`. Install development-only browser tests with `npm ci --prefix frontend`, install Chromium with `npm exec --prefix frontend -- playwright install chromium`, then run `npm run test:browser --prefix frontend`. The [verification record](evidence/README.md) lists actual results and limitations. There is no frontend runtime framework, production build, CI workflow or backend endpoint. Final tooling remains a joint Task 01 decision.
