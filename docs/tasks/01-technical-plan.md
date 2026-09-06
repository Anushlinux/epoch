# Task 01: Technical selections and runtime foundation

Status: unstarted. This brief describes future implementation; no selection or runtime work is delivered by the documentation foundation.

## Goal

Rajdeep chooses the smallest practical Python backend stack and establishes the shared foundation with Anushrut. Retain a CLI/test harness and local simulated services. Agree the product UI contracts before Anushrut's dependent integration; its implementation is a separate lane.

## Prerequisites

Read [AGENTS.md](../../AGENTS.md), [README](../../README.md), [status](../status.md), [direction](../direction.md), [architecture](../architecture.md), and the [integration checklist](../integrations.md). The documentation foundation is the only completed prerequisite. Preserve unrelated changes and direction.md unchanged.

## Owned area

First record runtime/version, tooling, libraries, concrete schemas, persistence, registry transport, isolation mechanism, source layout, testing and continuous integration (CI) choices, with reasons. Decide what CI should run and what must remain local or requires separately authorized access. Then establish only the minimal Python package/CLI entry, configuration, persistence/version foundation and test harness justified by that plan; add the selected repository-local CI checks if applicable. These are future task deliverables, not authorization to add them in the current docs-only change.

Define shared contracts for scoped tool invocation, context input, task/run evidence, sourced success conditions, candidate artifacts and repair/publication records. Map request flow and component responsibilities. Separate one-time executor setup from runtime repair, and plan later Neatlogs/Workshop verification without assuming interoperability.

Include user request/clarification, enhanced task brief, checkpoint identity/dependencies/evidence, supervisor continuation, intent revision, feedback, and completion/error states. Agree API/event shapes with Anushrut and supply clearly labeled development fixtures. Keep criteria/evaluator ownership outside candidate edits, and record task guidance separately from persistent environment changes.

## Exclusions

No business simulators, Hermes integration, debugger or repair scenarios yet. No UI, live business connections, credential acquisition or global settings. Do not select a stack before inspecting the requirements, or expand the foundation into unused infrastructure.

## Acceptance checks

- Decisions cover runtime, tooling, libraries, schemas, storage, transport, layout, testing and CI, with practical trade-offs and unresolved assumptions. Resolve shared-interface blockers before dependent implementation.
- Minimal foundation setup, CLI entry, configuration validation, persistence round trip and test runner work from a clean checkout using documented commands. Tests check observable behavior; CI runs the selected checks or has a documented reason for deferral.
- Contracts cover task/run identity, requirement provenance, visible tool versions, calls/results/errors, supplied context, state, candidate diffs, rejected attempts, verification and publication/rollback history.
- The plan identifies fixed executor/evaluator artifacts, editable surfaces, permissions and externally enforced attempt/time/cost limits. Define how these restrictions will be tested rather than claiming they already protect an unbuilt debugger.
- Secure candidate-code isolation is separate from simulated service state. Specify denied filesystem/network tests from inside candidate execution, equivalent-state replay, partial success, safe activation and rollback. Live continuation remains deferred.
- Missing tools require authorized resources; retrieval retains source history. Evidence categories distinguish local components, simulation, actual Hermes, intended tracing integrations and live provider results.

## Evidence

Provide the decision/contract document, invariant-to-enforcement/test map, integration uncertainty list and exact clean setup/check commands with results. Retain persistence test evidence and any actual CI result; label unrun or deferred checks. Update status only for the minimal foundation actually demonstrated, leaving all later capabilities unimplemented.

## Copy-paste prompt

```text
Implement only Task 01 in docs/tasks/01-technical-plan.md. Read AGENTS.md and
its linked context first; preserve direction.md and unrelated changes. Select
and document the Python runtime, tooling, libraries, schemas, persistence,
transport, isolation, testing and CI, then build only the minimal foundation
justified by those decisions. Define shared interfaces and enforcement/test plans
for fixed executor, protected evaluator, bounded access/budgets, safe replay and
durable versions. No business services, Hermes, debugger, UI, global settings or
live integrations. Verify clean setup, CLI/configuration, persistence and tests;
record actual CI results or deferral. Report decisions, files, commands, evidence
and limitations. Update status only for demonstrated foundation behavior.
```
