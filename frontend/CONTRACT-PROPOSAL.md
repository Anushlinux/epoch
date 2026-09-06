# PROPOSED frontend contract for Rajdeep

**Not agreed. Not a backend schema or endpoint specification.** This local shape supports a replaceable UI fixture adapter. Rajdeep owns backend contracts, trusted evaluation, persistence, execution and repairs. Anushrut owns presentation and input handling. Final field names, versions, transport, storage and frontend tooling require joint Task 01 agreement.

## What the interface needs

| Record | Proposed information | Responsibility |
| --- | --- | --- |
| Intent | Original text, constraints, immutable revision number, clarification question/answer, explicit versus inferred requirements, source references | Backend interprets; UI retains and displays |
| Command | Submitted command ID bound to immutable payload, task ID, expected revision and kind; accepted, explicitly rejected or acknowledgement-unknown state | Backend must deduplicate; UI reuses an ID after uncertain acknowledgement |
| Snapshot | Task ID, run ID, revision, cursor monotonic within its declared task/run/revision stream, task status, brief, checkpoints, evidence, activity, repairs, result and prior revisions | Backend supplies authoritative scoped state |
| Event | Unique event ID, task/run/revision, sequence, category, payload and evidence category | Adapter validates; UI ignores duplicate/old events and stops on gaps |
| Checkpoint | Stable ID, criterion version, description, dependencies, explicit/inferred source, planned/running/checking/passed/failed/needs-input, evidence references | Trusted backend evaluator alone decides pass/fail |
| Evidence | Stable ID, task/run/revision/checkpoint and criterion binding, category, observed value, expected value, verdict, missing fields, inspector data | Backend establishes truth; UI shows supplied facts |
| Observable activity | Tool/version, sanitized input/output/error, supplied context/version/source, artifact, state observation or explicit supervisor continuation; captured time | No private-reasoning stream |
| Repair | Trigger, supported diagnosis and uncertainty, permitted scope, diff artifact, rejected/verified/active status, component/replay/fresh/regression evidence, limits, environment versions and rollback history | Never implies task completion |
| Result | Explicit delivery status, object/evidence IDs, unresolved requirements, missing evidence, link or inspectable sandbox object | Requires separate outcome event and checkpoint evidence |
| Feedback | Stable command ID, parent revision, exact feedback, category (missed requirement, evaluation concern, new preference), previous result and requirements | Backend creates explicit revision; original history survives |

The fixture implementation uses `taskId`, `runId`, `revision`, `seq`, `eventId`, `kind`, `data`, and `category: "fixture"`. These are local names for review, not proposed HTTP routes. No network adapter exists. Current sample code and test outcomes are authored display data; they are not executable repairs or sandbox effects.

## Adapter seam

`FixtureAdapter` exposes `snapshot()`, `command(command)`, read-only `lookup(command)`, `reconnect()` and manual `next()` fixture events. The view has no `fetch`, socket or model client. Replace this adapter only after agreement; retain the reducer's completeness checks and rendering tests. A real adapter will need explicit evidence categories such as simulated-service execution, actual Hermes execution, local component test and live provider observation. Merely relabeling a fixture is forbidden.

## Recovery and evidence rules to agree

- First submission freezes the command ID, payload, kind, task identity and expected revision together. Edits before submission are drafts; edits after an unknown acknowledgement cannot change that submitted identity or create a replacement command for the same unresolved action. The UI disables further submission/editing while it reconciles the frozen command.
- **Acknowledgement unknown is neither rejection nor task success.** Only explicit rejection releases the draft for a new decision. Lookup/reconnect must reconcile the submitted identity before any replacement or replay. The fixture's “Check submission status” action performs read-only lookup; an unknown lookup stays pending and does not call `command()` again. A future backend must specify authoritative rejection, lookup and safe retry semantics; a timeout alone cannot supply them.
- Task data and deduplication remain in page memory. A small per-tab session-storage marker contains only the pending command ID, never its text/payload. After reload the adapter/payload cannot be recovered: the UI explicitly reports recovery uncertainty, disables new work, and never resubmits silently. “Discard lost fixture session” only clears the local fixture warning; it neither reconciles nor cancels backend work. The marker must be recorded before submission; a failed storage write refuses the local action and retains the draft. If marker storage cannot be read, a detected reload is treated conservatively as uncertain. Durable recovery, cross-tab coordination, retention and server deduplication remain future backend agreement work.
- **Ordinary event filtering and scope adoption are separate.** Ordinary events from another task/run/revision remain ignored, including late events from a previously current run. Duplicate IDs and old cursors are ignored only within that event's declared stream. A gap pauses that stream until a reconciled snapshot is available.
- A new feedback revision or replacement run becomes current only through an authoritative, reconciled adapter transition tied to the expected parent/current task. The transition retains the prior scope and evidence in history, identifies the new scope and, for feedback, binds the acknowledged submitted command. The fixture checks this link through `adoptScope()` on acknowledgement or reconnect after a missed transition. `authority: "fixture-adapter"` labels a local test double; it is not backend authentication or a finalized field.
- Cursors are compared **within the same task/run/revision stream**. A new run may begin at cursor zero even when its parent ended at a higher cursor. Reconnect verifies continuity against the archived parent stream before adopting the new stream; it does not compare the new cursor to the old cursor or replay a command. Unrelated, missing-parent, stale-parent or unreconciled transitions retain the current view and report uncertainty. The fixture supports one reconciled transition at a time; multiple missed transitions require an explicit chain and remain a backend handoff question, not implicit revision skipping.
- The UI cannot establish the truth of an evidence record. Its guard only refuses incomplete or mismatched display data. A fixture `passed` label requires a fixture outcome record matching checkpoint and criterion version; it remains a **fixture pass**, never a real checkmark.
- Task delivery requires an explicit task outcome, all current checkpoints with matching pass evidence, and inspectable result references. Repair events cannot update task outcome. A missing result reference or criterion mismatch leaves the result unavailable.
- Feedback retains prior checkpoints, results and repair evidence in the previous revision; new work starts without inherited pass decisions. Historical rejected candidates, partial effects, documents and supervisory interventions remain inspectable.
- User-controlled text is rendered as text. Result links must be validated against the future authorized service policy; this fixture has only inline JSON inspection and labeled JSON download, with no remote result URLs.

## Handoff needed before integration

1. Task 01 decision/contract location and owning branch/session; agreed tooling and event versions.
2. Actual authorized endpoint/transport details, identity and error semantics, acknowledgement lookup and reconnect cursor/snapshot behavior.
3. Real sanitized failure/repair run, checkpoint provenance and evaluator evidence, partial-effect/replay cases, rejected candidate and result objects.
4. Intent revision semantics, result history retention, missing evidence behavior and documented service permissions.

Until these arrive, integration and actual supervised repair verification are **blocked**. There are no backend run IDs, real result links or compatibility claims to report.
