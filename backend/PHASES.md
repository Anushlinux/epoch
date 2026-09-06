# Backend implementation phases

Status: Phases 1–5 complete; Phases 6–8 unstarted. Owner: Rajdeep. Anushrut owns the separate UI and can use the [published backend contracts](docs/FRONTEND_HANDOFF.md). This implementation changes no frontend files. See [setup](README.md) and the [Phase 4 validation record](../docs/status.md#phase-4-validation-record).

All backend source, package configuration, tests, fixtures, development scripts, and runtime setup belong under `backend/`. Secrets and generated runtime data must not be committed. Shared repository instructions and product documentation remain at the repository root and under `docs/`.

## Working rule

Implement only the phase explicitly requested. Complete its checks, report the result and remaining gaps, then stop for review before starting another phase. Do not scaffold later phases in advance or treat this roadmap as authorization to implement everything. Update implementation documentation when delivering the assigned phase.

This plan breaks the existing seven backend task briefs into smaller delivery steps. Phases 3 and 4 together cover Task 03; the other mappings remain sequential.

## Phase 1 — Foundation and shared contracts

**Complete:** local API/CLI, validated contracts, SQLite intake persistence, frontend fixtures and tests. Contracts for future components are data definitions only. Anushrut's consuming UI and live progress remain separate work.

Choose the Python runtime/tooling, libraries, persistence, API/event transport, candidate-isolation approach, and minimal package layout before creating the runtime foundation.

- Define request, task, run, checkpoint, evidence, intent-revision, candidate, and environment-version contracts.
- Agree API responses, progress events, error states, and development fixtures with Anushrut.
- Build only the minimal server/CLI harness, configuration validation, persistence setup, and test harness. Preserve interfaces for future components without implementing them.

**Pass condition:** clean setup works, the service health check responds, configuration errors are clear, and a task record survives a storage round trip. Anushrut has concrete contracts to build against.

Existing brief: [Task 01](../docs/tasks/01-technical-plan.md).

## Phase 2 — Sandbox tools, evidence, and trusted checks

**Complete:** scoped registry/MCP, stateful simulated services, durable evidence, trusted checks, idempotency and seeded failure scenarios. See [sandbox evidence](fixtures/sandbox/README.md).

- Implement the small shared tool registry with discovery, descriptions/schemas, scoped invocation, and structured errors.
- Add stateful local ticket, checklist, messaging, directory, and runbook fixtures; begin with the narrow release workflow.
- Persist tool/context events and application state. Implement trusted outcome checks, equivalent-state resets, and duplicate-effect prevention.
- Seed an actual broken checklist adapter and preserve the relevant service contract as investigation evidence.

**Pass condition:** tools can be invoked through the harness; the seeded defect fails without creating a checklist; the evaluator detects the missing outcome; repeated safe operations do not duplicate objects. No agent diagnosis or repair exists yet.

Existing brief: [Task 02](../docs/tasks/02-local-environment.md).

## Phase 3 — Real Hermes execution

**Complete:** installed Hermes executes the explicit release template through MCP; HTTP/SSE expose real state, progress and checked results. Actual control/failure evidence and frozen-baseline comparisons are recorded in the [validation record](../docs/status.md#phases-2-and-3-validation-record). Automatic supervision remains Phase 4.

- Connect actual Hermes to the shared environment and send a structured task brief using the agreed contracts.
- Capture observable messages, tool calls, returned context, results, and errors under the same task/run identity.
- Record and freeze executor implementation, system prompt, model configuration, discovery interface, and controlled memory state.
- Expose actual progress and final results to the UI contract. Keep initial test briefs explicit; automatic checkpoint planning arrives in Phase 4.

**Pass condition:** actual Hermes performs a control task and encounters the seeded adapter failure, with both outcomes visible in independent state checks and correlated traces. A mocked executor does not pass.

Existing brief: the executor-integration part of [Task 03](../docs/tasks/03-executor-evidence.md). Phase 4 below completes the supervision acceptance for Task 03.

## Phase 4 — Supervisor, checkpoints, and user feedback

**Complete:** opt-in OpenAI `gpt-5.6-luna` planning/review, sourced release checkpoints, checks at meaningful events, same-session Hermes continuations, explicit feedback/clarification operations, durable revision history and backend-enforced budgets. The [actual acceptance harness](scripts/run_phase4_acceptance.py) passed omission recovery and a sourced feedback revision. The final local checks passed 264 tests, lint/format checks, contract-export checks and the actual no-model HTTP/restart smoke test; two upstream warnings remain. See the [saved supervision evidence](fixtures/supervision/README.md) and [validation record](../docs/status.md#phase-4-validation-record).

Direct release execution remains the default. `--supervised` or API `supervised: true` enables the debugger while preserving the configured Hermes executor and recording supervisory instructions separately. Each initial, feedback or clarification operation shares **20 model-request turns / 600 seconds** across Luna and Hermes; explicit later feedback starts a new bounded operation. The debugger uses an OpenAI API key when configured, otherwise the observed existing Hermes Codex route, with no model substitution. [DEBUGGER_SETUP.md](docs/DEBUGGER_SETUP.md) records the exact route and limitations.

Supported revisions add user-sourced checklist items or exact QA-message phrases, reuse existing objects, retain earlier requirements and preserve prior outcomes. Removing/replacing requirements or requesting unsupported criteria is not silently accepted. Trusted evaluator code remains outside model control. Phase 4 does not repair tools/context, publish environment versions or alter the frontend.

- Convert a user request into an enhanced brief and sourced, verifiable checkpoints. Preserve explicit constraints and surface material ambiguity.
- Evaluate progress at meaningful execution events. For an omitted step, issue a bounded targeted continuation to Hermes that reuses completed work.
- Report outcomes and accept feedback after delivery. Distinguish evaluation mistakes, missing requirements, new preferences, and environment defects; preserve intent revisions and earlier results.
- Enforce continuation/time limits, handle interruption and needs-input states, and keep checkpoint pass decisions in trusted evaluation code.

**Pass condition:** a deliberately omitted step is completed after a recorded supervisor instruction; a user-feedback revision updates the result without duplicating completed effects or silently weakening criteria. This demonstrates supervision, not persistent environment learning.

**Demonstrated:** the initial operation used 15 shared turns (2 Luna / 13 Hermes), one targeted intervention and two passes in the same Hermes session to satisfy all three original checks. Feedback used 7 shared turns (1 Luna / 6 Hermes), added `Security review complete` to the checklist and `QA sign-off required` to the QA message, and passed all four revised checks. Exactly one ticket, checklist and message remained, with the same object IDs; earlier operation data stayed unchanged and an identical feedback retry created no new operation. The earlier provider-stream failure is retained separately. Task 03's Phase 4 pass condition is met; environment repair remains Phase 5.

Existing brief: the supervision part of [Task 03](../docs/tasks/03-executor-evidence.md).

## Phase 5 — First complete environment-repair loop

**Complete:** actual Luna-generated serializer repair, Linux Docker isolation, all five verification gates, same-session Hermes recovery, persisted later-session discovery and rollback. See [setup](docs/REPAIR_SETUP.md), [evidence](fixtures/repairs/README.md), and the [validation record](../docs/status.md#phase-5-validation-record). Each isolated verification receives 20 requests/600 seconds; primary work shares 20 requests/600 active seconds; the whole operation is capped at 60 requests/1,800 wall seconds and two candidates. No new model credential is required on the verified setup.

- Detect a supported failure automatically and assemble evidence for an actual model-generated diagnosis and adapter change.
- Enforce candidate isolation, permitted edit paths, service grants, and attempt/time limits outside generated code.
- Test the component, the original task in isolated state, a meaningful new task, and regressions using protected checks.
- Publish only the exact verified artifact at a safe boundary. Retain rejected attempts, active/prior versions, restart persistence, and rollback evidence.

**Pass condition:** the broken checklist adapter is repaired by a generated executable change; unchanged Hermes succeeds on the original and a fresh release; a later session loads the persisted repair. Failed candidates remain inactive and recovery does not duplicate objects.

Existing brief: [Task 04](../docs/tasks/04-tool-repair.md).

**This is the minimum complete backend product milestone.** If the time window is tight, stabilize this loop before expanding repair types.

## Phase 6 — Missing-tool generation

- Confirm a needed capability is absent from the permitted catalog.
- Generate and test a QA-owner lookup adapter against the already authorized directory service, including its description and schema.
- Publish it through the same repair machinery and prove Hermes discovers and invokes it without executor changes.

**Pass condition:** one-owner, missing-owner, ambiguous-owner, and different-project cases behave correctly; no identity is hardcoded or guessed.

Existing brief: [Task 05](../docs/tasks/05-missing-tool.md).

## Phase 7 — Context repair

- Diagnose a failure caused by unsuitable retrieved guidance using the documents actually supplied to Hermes.
- Generate and verify a scoped retrieval-policy change while keeping access controls and source documents intact.
- Test current approved guidance, historical questions, unrelated projects, and ambiguous or missing guidance.

**Pass condition:** the observed current-workflow failure is corrected, and relevant historical information remains retrievable. Publication follows the same protected verification gate.

Existing brief: [Task 06](../docs/tasks/06-context-repair.md).

## Phase 8 — Integration, reliability, and demo handoff

- Verify the intended Neatlogs/Workshop integrations against real local execution; preserve local evidence and disclose unsupported integration paths.
- Check frontend/API integration, progress reconnection, interrupted runs, persistence, limits, and safe recovery with Anushrut.
- Package reproducible setup/reset/demo commands and artifact-backed results. Separate supervisory interventions, repair overhead, and later-task performance.

**Pass condition:** a clean-start demo is reproducible, the UI reflects real backend outcomes, and every claimed integration or repair type has execution evidence. Partial scope remains explicitly partial.

Existing brief: [Task 07](../docs/tasks/07-demo-evidence.md).

## Phase handoff

For every phase report: implemented scope, changed files, exact checks and outcomes, evidence locations, known limitations, and whether its pass condition is met. Keep user-task success, isolated verification, and persistent-learning claims separate. Report Phase 4's completed evidence before any push, as requested by the user. Phase 5 was explicitly assigned and is complete. Phases 6–8 require separate implementation requests and have not started.
