# Implementation tasks: Anushrut and Rajdeep

**Latest assigned work — September 11:** implement the discussed noise workflow,
including local diagnosis, context-policy drafts, source metadata, previews, explicit
trials, manual acceptance, activation/rollback and normal tool integration. Backend,
frontend and CLI are assigned. See [plan](../../backend/docs/NOISE_PLAN.md) and
[handoff](../../backend/docs/NOISE_WORKFLOW.md). Development testing remains explicitly
skipped; no model calls, automatic publication or later unrelated features are assigned.

**Preceding assigned work:** retain conversation-scoped Hermes workers with explicit
invalidation/idle cleanup, connect public text streaming and actual execution stages,
and render saved answers independently of runtime/PDF refreshes. Backend and frontend
are included. See the [plan](../../backend/docs/CHAT_LATENCY_PLAN.md) and
[handoff/manual checks](../../backend/docs/CHAT_LATENCY.md). Testing is explicitly skipped;
no later trace phases or multi-user deployment are assigned.

**Preceding assigned integration:** automatically capture actual Hermes chat messages
using Neatlogs, link each conversation/request to local traces, and fix the frontend
resource-not-found issue. Both backend and UI are in scope. See the [short
plan](../../backend/docs/CHAT_TRACES_PLAN.md) and [handoff](../../backend/docs/CHAT_TRACES.md).
Testing remains explicitly skipped. Existing execution and repair behavior stays intact.

**Later interaction clarification:** the user requires trace features to extend the
existing workflow. The main setup uses normal `serve` with the original app file/data
directory. Chat, its debugger, existing workflows and trace questions share one server;
the trace-only profile is optional. No workflow functionality is to be removed.

**Current trace-debugger assignment:** the user subsequently assigned feature Phase 3,
local questions over selected traces with installed Ollama Qwen. Backend, CLI and
the existing trace UI are included. See the [bounded plan](../../backend/docs/TRACE_QA_PLAN.md)
and [setup/manual acceptance](../../backend/docs/TRACE_QUESTIONS.md). Development is
unverified; the user will perform testing. No later trace phases are assigned.

**September 10 feature assignment:** the user assigned Rajdeep both backend and UI
for [Neatlogs trace explorer Phases 1–2](../../backend/docs/TRACE_EXPLORER_PLAN.md),
with testing explicitly skipped. This scope is local SDK capture/storage and trace
browsing/search only. [Setup](../../backend/docs/TRACE_EXPLORER.md) and
[status](../status.md) record the unverified delivery. Later trace-debugger phases
remain gated on a separate user instruction; historical repair phase acceptance
is unchanged.

**Tasks 01–03 are implemented and verified; Phase 4 actual-model evidence is recorded in [status](../status.md#phase-4-validation-record). Task 04 (Phase 5) is implemented with [actual repair evidence](../status.md#phase-5-validation-record); Tasks 05–06 have untested development delivered by explicit user request; Task 07 remains unimplemented.** Rajdeep owns the backend. Anushrut owns the separate UI and can connect to the [live endpoint handoff](../../backend/docs/FRONTEND_HANDOFF.md). A copied prompt authorizes only its assigned scope. Follow the smaller [backend phases](../../backend/PHASES.md); Task 03 spans Phases 3 and 4.

Read [AGENTS.md](../../AGENTS.md), [direction](../direction.md), [status](../status.md), [architecture](../architecture.md), and the [integration checklist](../integrations.md) before starting. Preserve the direction unchanged.

| Order | Rajdeep's backend task | Dependency | Intended deliverable |
| --- | --- | --- | --- |
| 01 | [Technical selections and runtime foundation](01-technical-plan.md) | Documentation foundation | Stack and supervisor/checkpoint/API/event contracts agreed with Anushrut; minimal foundation |
| 02 | [Simulated services, trusted checks and early traces](02-local-environment.md) | 01 | Simulated Jira/Notion/Slack/directory, fixtures, tool/context boundaries and local evidence |
| 03 | [Actual Hermes integration and frozen configuration proof](03-executor-evidence.md) | 02 | Structured brief delivery, checkpoint evaluation, bounded targeted continuation, actual tools, and a fixed executor baseline |
| 04 | [First complete tool-repair loop](04-tool-repair.md) | 03 | Automatic diagnosis, real patch, safe verification and durable publication |
| 05 | [Generate a missing capability](05-missing-tool.md) | 04 | New authorized adapter discovered and used by unchanged Hermes |
| 06 | [Repair supplied context](06-context-repair.md) | 05 | Persistent scoped retrieval change with historical regression coverage |
| 07 | [Integration verification and inspectable CLI demonstration](07-demo-evidence.md) | 06 | Verified Neatlogs/Workshop wiring and reproducible three-scenario evidence |

Use Python for the backend, retain a CLI/test harness, and use local simulated services first. The user-facing product is the Epoch interface described in the [README](../../README.md#user-flow). Task 01 records [technical selections](../../backend/DECISIONS.md); the [Phase 2/3 plan](../../backend/PHASES_2_3_PLAN.md) connects the sandbox and installed executor. The sequence makes no ten-hour completion promise. The user explicitly assigned Phases 6 and 7 and requested no testing; Phase 8 still requires its own assignment.

## Current integration assignment

The user explicitly assigned current frontend integration plus incident construction,
Neatlogs local/cloud wiring and JSON evidence imports. This delivery uses parallel
agents with shared contracts and preserves the existing backend architecture. The
Phase 7 frontend and incident screens are connected; focused checks are recorded in
[status](../status.md#frontend-incidents-and-neatlogs-integration--september-6-2026).
Full live repair/cloud acceptance remains pending. Workshop and live SaaS connectors
are deferred. This later assignment supersedes the older unassigned integration
statements below; the preserved direction remains unchanged.

## Anushrut: UI lane

**Local implementation:** the [frontend workspace](../../frontend/README.md) has historical Phase 3 intake and explicit-execution HTTP/browser evidence. Its health/runtime guards require Phase 3 and automatic supervision/repair disabled, so it rejects the current Phase 5 backend. Anushrut owns updating those guards and integrating supervision, feedback, repair/diff/check views and version history against the [frontend handoff](../../backend/docs/FRONTEND_HANDOFF.md). This backend change preserves every frontend file. Model-backed browser acceptance is still required for current UI support.

**Goal:** build the interface through which the user requests work, sees checkpoints and evidence, receives results, and provides revisions.

**Dependencies:** agree request/response shapes, event names, checkpoint IDs, error states, and ownership with Rajdeep in Task 01. UI layout and clearly labeled fixture states can proceed early; live execution depends on Rajdeep's implemented endpoints. UI acceptance does not require waiting for all seven backend tasks.

**Owned area:** frontend and frontend tests. Request/clarification form; checkpoint board; actual execution activity; repair diagnosis, diff and verification views; result links; user-feedback/revision flow; reconnect and failure states. Choose the frontend stack jointly in Task 01. Rajdeep owns backend schemas and evaluator logic.

**Exclusions:** no fabricated live progress, frontend-generated pass decisions, private reasoning viewer, model credentials in the browser, backend repair logic, or changes to another owner's files without coordination.

**Acceptance checks:**

- A request shows its interpreted deliverables and constraints, and clarifications preserve user intent.
- Checkpoint states come from backend evidence; distinguish planned, running, checking, passed, failed, and needs-input states.
- A repair being verified or active does not by itself mark the user task complete. Rejected candidates and partial side effects remain visible.
- Results expose actual sandbox objects. Feedback can revise the task with its original result and previous requirements retained.
- Reconnection and repeated submissions do not create duplicate work. Development fixtures cannot masquerade as live execution.
- Connect the first real failure/repair flow as soon as Rajdeep's endpoints are available; run a focused browser flow and relevant frontend checks.

**Evidence:** record actual UI checks, screenshots or a short demo, backend run IDs, result links, and incomplete states. Keep runtime status unimplemented until the corresponding integration is demonstrated.

**Copy-paste prompt:**

```text
You are implementing Anushrut's UI lane in docs/tasks/README.md. Read AGENTS.md,
README.md and docs/status.md first. Agree API/event/checkpoint contracts with
Rajdeep before dependent integration. Own frontend files and tests. Implement
request/clarification, checkpoints, execution activity, repair evidence and tests,
results, feedback revisions, and error/reconnect states. Use labeled development
fixtures until real endpoints exist, then verify the first actual supervised
repair flow. Checkmarks must come from backend evidence. Do not implement backend
repair logic, expose credentials, fabricate execution, or claim private-reasoning
access. Preserve unrelated work and report checks, evidence, and remaining gaps.
```

## Shared milestones and handoff

| Target | Rajdeep | Anushrut |
| --- | --- | --- |
| Hour 1 | Choose runtime; agree checkpoint/API/event contracts; smoke-test Hermes and model access | Agree contracts; define interface states and request-to-feedback flow |
| Hours 1–3 | Simulated services, real executor evidence, initial checkpoint checks | Build UI from fixtures, then connect real execution events |
| Hours 3–5 | Targeted continuation and first generated, verified, persistent repair | Show real failure, candidate, tests, result, and pending feedback |
| Hours 5–8 | User-feedback revisions; missing-tool/context scenarios only after core passes | Complete feedback, partial-result, reconnect, and repair-history states |
| Hours 8–10 | Regression, persistence, safe recovery, and setup checks | Browser verification, demo polish, and joint rehearsal |

Both may use multiple Codex sessions in separately owned files. Freeze contracts early and integrate small slices regularly. Rajdeep demonstrates backend behavior through the harness; Anushrut demonstrates the same behavior through the interface. If the first repair loop slips, preserve it and cut additional scenarios. All hours are planning targets.

## Safe independent work

Keep the seven-task backend acceptance order while Anushrut's UI lane proceeds against agreed contracts. Once Task 01 has fixed and reviewed the shared tool/context, state and trace interfaces, separately assigned work within Task 02 can cover service adapters, fixture data and trusted checks in distinct owned files. Agree on state-reset semantics and evidence identifiers before splitting that work; combine it and run boundary checks before Task 03.

After the local repair loop and evidence contracts are established, separately assigned Neatlogs and Workshop compatibility investigations can proceed independently of report writing within Task 07. Their wiring and final acceptance still depend on shared identifiers and actual rerun evidence. Do not split work across unsettled interfaces or edit another task's owned area.

Every task must preserve the fixed executor, protected evaluator, bounded permissions, safe replay, real persistent repairs and honest evidence. If a dependency is incomplete, inspect its evidence and report the blocking gap. Do not label a stub, a test double, or a vendor documentation reference as a completed integration.

For each handoff, record changed files, commands actually run, outcomes, evidence locations and known limitations. Update [status](../status.md) only for what those results establish. The three scenarios share one release workflow; they are not proof of three distinct domains.
