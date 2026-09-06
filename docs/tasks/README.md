# Implementation tasks: Anushrut and Rajdeep

**Task 01 / backend Phase 1 is complete; Tasks 02–07 remain unimplemented. The UI lane has Phase 1 intake integration and separate future-workflow fixtures; execution integration is pending.** Rajdeep owns the ordered backend tasks. Anushrut owns the separately assigned UI lane below and can use the [frontend contract handoff](../../backend/docs/FRONTEND_HANDOFF.md). A copied prompt authorizes only its assigned scope, not the entire roadmap. Follow the smaller [backend phases](../../backend/PHASES.md) for step-by-step implementation.

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

Use Python for the backend, retain a CLI/test harness, and use local simulated services first. The user-facing product is the Epoch interface described in the [README](../../README.md#user-flow). Task 01 records [technical selections](../../backend/DECISIONS.md) and provides concrete frontend contracts with a verified minimal foundation. The sequence makes no ten-hour completion promise. Phase 2 is next and remains unstarted.

## Anushrut: UI lane

**Local implementation:** [Frontend fixture workspace](../../frontend/README.md), [PROPOSED contract](../../frontend/CONTRACT-PROPOSAL.md), and [UI verification](../../frontend/evidence/README.md). The fixture contract is not agreed with Rajdeep. The primary UI consumes the published Phase 1 intake/list/detail API. Future fixture mapping remains under review; actual execution endpoints remain unimplemented. See UI verification for actual local HTTP/browser/AO intake proof and the supported frontend dev command at `127.0.0.1:5173`.

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
