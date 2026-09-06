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
