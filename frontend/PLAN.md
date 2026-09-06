# UI lane implementation plan

Base: `origin/main` at `e1395bc`, fresh branch `ao/epoch-5/anushrut-ui`.

1. Describe a **PROPOSED, frontend-local** data contract for Rajdeep. Keep transport, backend schema and joint tooling decisions open.
2. Build an accessible task workspace: original request and clarifications, sourced checkpoints, observable activity, repair diagnosis/diff/test/rejection history, inspectable fixture artifacts, feedback and retained revisions.
3. Keep a replaceable in-memory fixture adapter separate from presentation. Require explicit fixture events for progress; defend presentation against missing evidence, duplicate/stale events, stream gaps and uncertain command acknowledgements.
4. Run state and browser tests, including forms, keyboard/mobile, reconnect/retry and feedback. Inspect desktop/mobile in one bounded QA batch, fix material findings together, then confirm once.
5. Record actual evidence and blocked integration, preserve the direction document, commit/push and open a PR without merging. Send proposal, progress and verification to epoch-2.

Scope: frontend source/tests and frontend handoff documentation with minimal status updates. No backend logic, evaluator implementation, live endpoints, secrets, framework commitment or CI decision. All sample execution, repair and verification records are authored fixtures, not a simulated service or real run.

Completed: fixture workspace, proposal and frontend documentation implemented; 18 state tests and 20 browser tests passed; AO preview/repair inspection and feedback revision exercised; desktop/mobile/AO screenshots retained. Backend integration remains blocked on the named handoff in the proposal. Commit/push/PR are the final delivery steps.

Review follow-up: clarify authorized scope transitions and frozen submissions; add a fixture-only transition adoption path, acknowledgement lookup and reload-uncertainty guard; verify acknowledged/missed transitions, late old events, edited pending input and reload behavior; update PR #2 without backend changes or merge.

Review follow-up verified: 24 state tests and 26 desktop/mobile browser tests passed. Both contract risks are addressed locally; backend integration remains blocked.

## Phase 1 intake integration plan

Authorized after the rebase onto `0a062dd`. Keep backend files unchanged.

1. Use the published `TaskCreate`, `Task`, `TaskList`, `HealthResponse` and error envelope for real health/create/list/detail requests. Make intake the primary page and retain future fixtures on a separate labeled page.
2. Freeze and retain the submitted request ID/content before HTTP submission. Handle unknown acknowledgement, identical retry, rejection/conflict, reload, stale reads and disconnected state without starting duplicate unresolved work. Render only pending intake, never execution progress.
3. Verify against the unchanged backend with temporary storage and explicit loopback CORS settings: real HTTP/browser intake, retries, errors, reconnect and restart persistence. Keep fault-injected browser checks distinct from actual server responses. Re-run fixture regression checks and bounded desktop/mobile/AO inspection.
4. Update boundary mapping and evidence/status, then commit, push, update PR #2 and report to epoch-2. Future event/feedback/repair questions remain review requests; actual supervised repair stays blocked.

Phase 1 integration completed locally: primary intake/list/detail UI, frozen recoverable submission payloads and explicit retry, separate future fixtures, 35 state tests, 26 fixture browser tests and 10 real-backend browser checks pass. Actual HTTP restart persistence and response semantics passed. AO preview is visible but API connection is blocked by the backend CORS origin validator; reported to epoch-2 without backend changes. Evidence and PR handoff follow.
