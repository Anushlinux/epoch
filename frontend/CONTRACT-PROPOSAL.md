# PROPOSED frontend contract for Rajdeep

**Not agreed. Not a backend schema or endpoint specification.** This local shape supports a replaceable UI fixture adapter. Rajdeep owns backend contracts, trusted evaluation, persistence, execution and repairs. Anushrut owns presentation and input handling. Backend Phase 1 now has published field names and technical selections. Mapping this separate fixture shape to those contracts, future transport/recovery semantics and frontend tooling still requires agreement.

Rebase update: [backend/FRONTEND_HANDOFF](../backend/docs/FRONTEND_HANDOFF.md) is available from `main` at `0a062dd`. It implements task intake/read/list; tasks remain pending. Its future progress envelope uses per-task sequence numbers, whereas this fixture models cursors per task/run/revision. That difference requires explicit reconciliation before integration; neither contract is silently treated as the other. No network adapter or execution integration was added by the rebase.

## Published Phase 1 mapping now consumed

The primary intake view consumes Rajdeep's published models directly; it does not send the fixture's command, revision or event fields. This is implementation against the published handoff, not a claim of joint approval for the older fixture proposal.

| Published model / route | Frontend behavior |
| --- | --- |
| `HealthResponse`, GET `/api/health` | Require `status=ok`, `storage=ok`, `phase=1`, `execution_enabled=false` before enabling intake. |
| `TaskCreate`, POST `/api/tasks` | Freeze `client_request_id`, `message`, `project_id` and local API origin. Store the exact pending payload in per-tab session storage before sending. No expected revision exists in this Phase 1 model. |
| `Task`, POST response / GET `/api/tasks/{task_id}` | Validate schema version, IDs, original request and timestamps. Support only `pending`; display a storage receipt, never task success or progress. Preserve backend-normalized text. |
| `TaskList`, GET `/api/tasks?limit=20&offset=…` | Display server records with pagination; no fixture merging. Reject late or unrelated detail responses. |
| HTTP 201 / 200 | New intake / identical normalized retry. Require acknowledgement to match the frozen request before clearing it. |
| HTTP 409 / 422 / 403 with `ErrorEnvelope` | Display the backend message/status; preserve rejected content until an explicit return-to-draft action. Never automatically allocate another ID. |
| Lost response, malformed acknowledgement, 5xx | Acknowledgement remains unknown. Read-only reconnect does not POST. Explicit exact retry uses published server deduplication. Corrupt/unavailable recovery storage blocks new submissions. |

A pending intake payload includes task text in session storage; it is removed after acknowledgement. This differs intentionally from the fixture's ID-only marker below. No lookup-by-client-ID, SSE, checkpoint, feedback, result or repair endpoint has been invented. Browser requests omit credentials and accept only the configured local API origin. Backend intake persistence and deduplication were verified against an isolated unchanged server; future execution semantics below remain review requests.

## Future interface information needs (PROPOSED)

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

The fixture implementation uses `taskId`, `runId`, `revision`, `seq`, `eventId`, `kind`, `data`, and `category: "fixture"`. These are local names for review, not proposed HTTP routes. The separate intake network adapter never consumes these fixture fields. Current sample code and test outcomes are authored display data; they are not executable repairs or sandbox effects.

## Adapter seam

`FixtureAdapter` exposes `snapshot()`, `command(command)`, read-only `lookup(command)`, `reconnect()` and manual `next()` fixture events. The fixture view has no `fetch`, socket or model client; the separate intake view uses only the published Phase 1 routes. Replace this adapter only after agreement; retain the reducer's completeness checks and rendering tests. A real adapter will need explicit evidence categories such as simulated-service execution, actual Hermes execution, local component test and live provider observation. Merely relabeling a fixture is forbidden.

## Future fixture recovery and evidence rules to agree

- First submission freezes the command ID, payload, kind, task identity and expected revision together. Edits before submission are drafts; edits after an unknown acknowledgement cannot change that submitted identity or create a replacement command for the same unresolved action. The UI disables further submission/editing while it reconciles the frozen command.
- **Acknowledgement unknown is neither rejection nor task success.** Only explicit rejection releases the draft for a new decision. Lookup/reconnect must reconcile the submitted identity before any replacement or replay. The fixture's “Check submission status” action performs read-only lookup; an unknown lookup stays pending and does not call `command()` again. A future backend must specify authoritative rejection, lookup and safe retry semantics; a timeout alone cannot supply them.
- Task data and deduplication remain in page memory. A small per-tab session-storage marker contains only the pending command ID, never its text/payload. After reload the adapter/payload cannot be recovered: the UI explicitly reports recovery uncertainty, disables new work, and never resubmits silently. “Discard lost fixture session” only clears the local fixture warning; it neither reconciles nor cancels backend work. The marker must be recorded before submission; a failed storage write refuses the local action and retains the draft. If marker storage cannot be read, a detected reload is treated conservatively as uncertain. Durable recovery, cross-tab coordination, retention and server deduplication remain future backend agreement work.
- **Ordinary event filtering and scope adoption are separate.** Ordinary events from another task/run/revision remain ignored, including late events from a previously current run. Duplicate IDs and old cursors are ignored only within that event's declared stream. A gap pauses that stream until a reconciled snapshot is available.
- A new feedback revision or replacement run becomes current only through an authoritative, reconciled adapter transition tied to the expected parent/current task. The transition retains the prior scope and evidence in history, identifies the new scope and, for feedback, binds the acknowledged submitted command. The fixture checks this link through `adoptScope()` on acknowledgement or reconnect after a missed transition. `authority: "fixture-adapter"` labels a local test double; it is not backend authentication or a finalized field.
- Cursors are compared **within the same task/run/revision stream**. A new run may begin at cursor zero even when its parent ended at a higher cursor. Reconnect verifies continuity against the archived parent stream before adopting the new stream; it does not compare the new cursor to the old cursor or replay a command. Unrelated, missing-parent, stale-parent or unreconciled transitions retain the current view and report uncertainty. The fixture supports one reconciled transition at a time; multiple missed transitions require an explicit chain and remain a backend handoff question, not implicit revision skipping.
- Same-scope reconnect requires an exact checkpoint ID set with no duplicates; events, reconnect and scope adoption require complete references and matching scoped outcome evidence for passed, failed and needs-input states. Receipt-order cursors `checkpointSeq` and `outcomeSeq` are fixture presentation metadata, not new backend fields. A checkpoint change after delivery hides the current Delivered label until a newer explicit task outcome arrives, while retaining the supplied verdict/result for inspection. Disconnected fixture creation is blocked at both the UI and dispatch boundary.
- The UI cannot establish the truth of an evidence record. Its guard only refuses incomplete or mismatched display data. A fixture `passed` label requires a fixture outcome record matching checkpoint and criterion version; it remains a **fixture pass**, never a real checkmark.
- Task delivery requires an explicit task outcome, all current checkpoints with matching pass evidence, and inspectable result references. Repair events cannot update task outcome. A missing result reference or criterion mismatch leaves the result unavailable.
- Feedback retains prior checkpoints, results and repair evidence in the previous revision; new work starts without inherited pass decisions. Historical rejected candidates, partial effects, documents and supervisory interventions remain inspectable.
- User-controlled text is rendered as text. Result links must be validated against the future authorized service policy; this fixture has only inline JSON inspection and labeled JSON download, with no remote result URLs.

## Handoff needed before execution integration

1. Available: [Task 01 decisions](../backend/DECISIONS.md) and [backend handoff](../backend/docs/FRONTEND_HANDOFF.md). Pending: joint fixture-to-backend mapping, frontend tooling and future event/recovery agreement.
2. Available: Phase 1 intake endpoints and HTTP/error semantics in that handoff. Implemented: Phase 1 intake/list/detail and exact retry. Pending for later phases: feedback acknowledgement lookup and execution-stream reconnect/transition behavior.
3. Real sanitized failure/repair run, checkpoint provenance and evaluator evidence, partial-effect/replay cases, rejected candidate and result objects.
4. Intent revision semantics, result history retention, missing evidence behavior and documented service permissions.

The intake UI is now integrated with the published Phase 1 API. Future fixture screens remain disconnected. Actual supervised repair verification remains **blocked** on the unimplemented execution/repair endpoints and the remaining agreement above. Real task/request IDs establish intake only. There are no backend run IDs, real task-result links or execution compatibility claims to report.
