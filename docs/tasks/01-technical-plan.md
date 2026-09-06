# Task 01: Technical plan and contracts

Status: unstarted. This task is planning only; it does not implement a runtime.

## Scope

Translate the approved product direction into a small, buildable Python plan. Specify a command-line interface before UI and local simulated services before live business integrations. Select libraries, concrete data schemas, persistence, registry transport, version lifecycle, isolation mechanism, test approach and initial source layout here, with reasons tied to required behavior.

Define how a request moves through Hermes, scoped discovery, tool execution, context assembly, trace capture, trusted evaluation, candidate isolation, publication and later runs. Define the minimum CLI operations and evidence contracts. Separate one-time executor setup from runtime repair. Plan Neatlogs and Workshop verification using the integration checklist, including a fallback that does not misrepresent missing integrations.

Do not create packages, application scaffolds, dependency installations, workflows, credentials, global settings, or live service connections in this task. Reading primary vendor documentation is permitted; record versions and unresolved runtime assumptions without claiming installed behavior.

## Dependencies

The [documentation foundation](../../README.md), [architecture](../architecture.md), and [integration checklist](../integrations.md). There is no assumed runtime dependency.

## Acceptance criteria

- A written technical plan makes the deferred selections explicitly, explains practical trade-offs, and identifies any unresolved blocker before downstream code begins.
- Contracts cover task/run identity, requirement provenance, visible tool versions, calls/results/errors, supplied context, application state, candidate diffs, rejected attempts, verification and publication/rollback history.
- The plan identifies fixed executor and evaluator artifacts, editable repair surfaces, authority boundaries, and how restrictions will be enforced outside candidate code. Attempt, time and cost limits and stop conditions are explicit.
- Secure candidate-code isolation is designed separately from simulated service state. A local fake service or reset fixture is not filesystem/network containment; specify how denied access will be tested from candidate execution.
- Replay design covers equivalent isolated starting state, partial success and uncertain effects. Live continuation remains deferred and cannot inherit a safety claim from simulation.
- Tool generation requires an authorized resource and rejects missing/ambiguous identity; context repair preserves historical retrieval and original documents.
- Verification distinguishes documentation, component doubles, simulation, actual Hermes execution, and live provider evidence. The implementation sequence still prioritizes one complete loop before breadth.

## Required evidence

Commit the decision document and contract descriptions, a map from each product invariant to its enforcement and test plan, and an integration uncertainty list with source/version references where consulted. Include a review checklist showing every later task has enough contract detail to start. No runtime results may be reported.

## Copy-paste prompt

```text
Implement Task 01 from docs/tasks/01-technical-plan.md only. Read AGENTS.md,
README.md, docs/direction.md, docs/status.md, docs/architecture.md and
docs/integrations.md first. Preserve direction.md unchanged and unrelated work.
Write the concrete Python technical plan: CLI first, local simulated services
first. Choose libraries, schemas, storage, transport, isolation, layout and tests;
explain decisions and unresolved integration assumptions. Specify fixed executor,
protected evaluator, enforced bounded permissions, replay, durable publication,
rollback and honest evidence contracts. Do not add code, scaffolds, dependencies,
CI, global settings or live integrations. Meet every acceptance criterion, validate
documentation, and report decision/evidence paths and remaining blockers. Update
status only for completed planning; runtime remains unimplemented.
```
