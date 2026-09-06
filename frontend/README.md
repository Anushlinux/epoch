# Epoch frontend fixture workspace

**UI implementation only. Backend integration is pending.** All displayed execution activity, diagnoses, diffs, verification results and artifacts are authored development fixtures. They are not simulated-service effects, real Hermes execution or verified repair evidence.

Open from the workspace root with `ao preview frontend/index.html`. AO serves the browser modules through its existing local preview. No application server, runtime dependency or launch configuration is required. Outside AO, serve the repository with a static HTTP server; direct `file://` module loading is not supported.

The rebase onto backend Phase 1 (`0a062dd`) brings a [published backend handoff](../backend/docs/FRONTEND_HANDOFF.md) with real task intake and persistence. This UI still uses its separate fixture adapter. Reconciling the proposed fixture contract with that handoff and wiring intake are separate integration work; execution, streaming, feedback and repair endpoints remain unimplemented.

## Explore

- The initial release example shows a failed checklist, a retained ticket and a rejected repair candidate.
- Open **Fixture controls** and choose **Advance fixture** to inspect verifying, active-but-incomplete, needs-input, checking and delivered states. These are manual authored events, never timer-driven execution.
- **Restart release example** clears the example session and starts with planned checkpoints.
- **New request** preserves your text and constraints, asks a fixed fixture clarification, and records a verbatim checkpoint. There is no backend interpretation or execution for arbitrary requests.
- **Results** exposes labeled JSON artifacts. Feedback records an explicit new revision and retains earlier requirements, evidence, artifacts and rejected candidates under **History**.
- Disconnect/reconnect retains current state without submitting work. The acknowledgement-loss control freezes the submitted ID/payload/revision. **Check submission status** looks up that identity without replaying work. After an unresolved submission is reloaded, a recovery-uncertainty notice blocks new work until the local fixture session is explicitly discarded.

Task content and deduplication live in page memory. Only a pending command-ID marker survives in per-tab session storage; it contains no task text. Reload resets the example and warns if the prior submission is unresolved. This is deliberate provisional tooling, not a durable task system. Backend task intake now has its own persistence and retry semantics; they are not exercised by this UI. Execution recovery, authorization and replay safety remain backend responsibilities.

## Implementation boundary

- [Contract proposal](CONTRACT-PROPOSAL.md): frontend-local information needs and open decisions; **not an agreed backend schema**.
- [State](src/state.mjs): presentation completeness, identity, event ordering and revision history guards. It cannot verify business truth.
- [Fixtures](src/fixtures.mjs): replaceable in-memory adapter and authored records; no network or executable repair.
- [View](src/app.mjs) and [styles](src/styles.css): semantic browser UI, responsive layout, safe text rendering, keyboard tabs and inspectable evidence.
- [Plan](PLAN.md), [product context](PRODUCT.md), [design notes](DESIGN.md) and [verification](evidence/README.md).

Run dependency-free state tests with `node --test frontend/tests/state.test.mjs`. Install development-only browser tests with `npm ci --prefix frontend`, install Chromium with `npm exec --prefix frontend -- playwright install chromium`, then run `npm run test:browser --prefix frontend`. The [verification record](evidence/README.md) lists actual results and limitations. There is no frontend runtime framework, production build, frontend CI workflow or network adapter. Frontend tooling remains provisional; backend selections are already recorded in Phase 1.
