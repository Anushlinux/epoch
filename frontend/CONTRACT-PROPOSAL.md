# PROPOSED frontend contract for Rajdeep

**Not agreed. Not a backend schema or endpoint specification.** This local shape supports a replaceable UI fixture adapter. Rajdeep owns backend contracts, trusted evaluation, persistence, execution and repairs. Anushrut owns presentation and input handling. Final field names, versions, transport, storage and frontend tooling require joint Task 01 agreement.

## What the interface needs

| Record | Proposed information | Responsibility |
| --- | --- | --- |
| Intent | Original text, constraints, immutable revision number, clarification question/answer, explicit versus inferred requirements, source references | Backend interprets; UI retains and displays |
| Command | Stable client command ID, task ID, expected revision, kind and payload; acknowledgement or known rejection | Backend must deduplicate; UI reuses an ID after uncertain acknowledgement |
| Snapshot | Task ID, run ID, revision, monotonic cursor, task status, brief, checkpoints, evidence, activity, repairs, result and prior revisions | Backend supplies authoritative scoped state |
| Event | Unique event ID, task/run/revision, sequence, category, payload and evidence category | Adapter validates; UI ignores duplicate/old events and stops on gaps |
| Checkpoint | Stable ID, criterion version, description, dependencies, explicit/inferred source, planned/running/checking/passed/failed/needs-input, evidence references | Trusted backend evaluator alone decides pass/fail |
| Evidence | Stable ID, task/run/revision/checkpoint and criterion binding, category, observed value, expected value, verdict, missing fields, inspector data | Backend establishes truth; UI shows supplied facts |
| Observable activity | Tool/version, sanitized input/output/error, supplied context/version/source, artifact, state observation or explicit supervisor continuation; captured time | No private-reasoning stream |
| Repair | Trigger, supported diagnosis and uncertainty, permitted scope, diff artifact, rejected/verified/active status, component/replay/fresh/regression evidence, limits, environment versions and rollback history | Never implies task completion |
| Result | Explicit delivery status, object/evidence IDs, unresolved requirements, missing evidence, link or inspectable sandbox object | Requires separate outcome event and checkpoint evidence |
| Feedback | Stable command ID, parent revision, exact feedback, category (missed requirement, evaluation concern, new preference), previous result and requirements | Backend creates explicit revision; original history survives |

The fixture implementation uses `taskId`, `runId`, `revision`, `seq`, `eventId`, `kind`, `data`, and `category: "fixture"`. These are local names for review, not proposed HTTP routes. No network adapter exists. Current sample code and test outcomes are authored display data; they are not executable repairs or sandbox effects.

## Adapter seam

`FixtureAdapter` exposes `snapshot()`, `command(command)`, `reconnect()` and manual `next()` fixture events. The view has no `fetch`, socket or model client. Replace this adapter only after agreement; retain the reducer's completeness checks and rendering tests. A real adapter will need explicit evidence categories such as simulated-service execution, actual Hermes execution, local component test and live provider observation. Merely relabeling a fixture is forbidden.

## Recovery and evidence rules to agree

- A command ID is created once for a draft and reused after acknowledgement loss. Reconnect retrieves state; it does not resubmit work. The in-memory fixture demonstrates this within one page session only. Durable deduplication, reload recovery, retention, authentication and authorization belong to the backend agreement.
- Events from another task/run/revision are ignored. Duplicate IDs and old cursors are ignored. A cursor gap blocks updates until a full matching snapshot is obtained. Reconnect must not rewind the current revision/cursor or erase known history.
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
