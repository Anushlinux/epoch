# Task 04: First complete tool-repair loop

Status: unstarted. Intended future implementation.

## Scope

Complete Scenario A through the CLI: an actual Hermes task fails because of the faulty checklist adapter; a supported signal automatically starts investigation; the debugger uses real trace and implementation evidence to generate a small executable correction. Stage and verify it in isolation, publish the accepted environment version, and prove that Hermes benefits on the original task and a fresh release.

Implement enforced attempt/time/cost limits, candidate isolation, trusted gating, persistent artifacts/evidence, safe activation and rollback. The debugger must not execute the business workflow in place of Hermes, install a reference patch, or map a fixture name directly to a diagnosis. Deterministic failure detection is acceptable; canned repair selection is not.

Keep Hermes implementation, prompt, model settings and discovery interface fixed, and keep evaluator/criteria/permissions outside the editable surface. Missing-tool and context repairs are later tasks. UI and live services stay out of scope.

## Dependencies

[Task 03](03-executor-evidence.md), including actual Hermes execution, protected evaluator and inspectable simulated effects. Task 02 provides resettable state and the genuine defect.

## Acceptance criteria

- At least one investigation starts automatically from a captured error or failed trusted check, without a manual investigate action.
- Diagnosis identifies the observed failed condition and supporting trace/code. The candidate changes actual serialization behavior and creates the required simulated checklist, not just a success response.
- Component tests, isolated rerun, meaningful fresh release variation and regressions pass trusted checks before publication. Baseline and repaired comparisons use equivalent starting state.
- A fresh Hermes session uses the durable repaired version through normal discovery with unchanged executor configuration and controlled unrelated memory.
- A failing candidate stays inactive with evidence retained. Tests enforce forbidden-write/network boundaries and stop at configured attempt/time/cost limits. Out-of-scope planning failures produce limitation reports.
- Partial-success replay does not duplicate effects. Publication occurs at a safe boundary; every run identifies its version. A restart preserves the active artifact and rollback restores the previous version.
- Evidence links the failure, generated diff, tests, publication decision and later benefit. No trusted criteria or failed traces are altered.

## Required evidence

Retain the pre-repair trace/state, automatic trigger, diagnosis with uncertainty, actual generated code diff, sandbox enforcement results, rejected-candidate and limit tests, trusted rerun/fresh/regression outcomes, fixed executor/evaluator comparisons, persistent artifact version, restart/rollback results and duplicate-effect checks. Record repair attempts, interventions and available latency/usage, separating repair overhead from subsequent runs.

## Copy-paste prompt

```text
Implement only Task 04 in docs/tasks/04-tool-repair.md after reading AGENTS.md,
the technical plan and Tasks 02–03 evidence. Complete one real automatic repair
loop for the broken adapter: evidence-based diagnosis, generated executable
patch, isolated trusted verification, durable safe publication, fresh-session
transfer and rollback. Keep executor and evaluator fixed, permissions externally
enforced, budgets bounded and replay free of duplicate simulated effects. Do not
use canned patches, fake results, UI or live services. Exercise every acceptance
criterion including rejection and failure limits. Preserve all evidence and
update status only for results actually demonstrated; report gaps explicitly.
```
