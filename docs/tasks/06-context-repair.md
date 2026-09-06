# Task 06: Repair supplied context

Status: unstarted. Intended future implementation.

## Scope

Extend the same debugger loop to Scenario C: functioning tools successfully notify an outdated destination because the supplied context includes misleading old guidance. Use a trusted outcome failure or an explicit correction to initiate investigation. Inspect the documents Hermes actually received, then generate a scoped retrieval/context-assembly change that prefers applicable current approved guidance.

Retain original source documents and their history. Verify that a historical question can still retrieve the old runbook. The repair is a persistent environment rule, not an edited executor prompt, deleted document or pasted debugging conversation. Do not assume that document presence proves causation; use a targeted comparison. UI, live services and broad retrieval redesign are out of scope.

## Dependencies

[Task 05](05-missing-tool.md) and the shared repair, publication and regression harness. Task 03 supplies actual retrieved-context evidence; Task 02 retains versioned/scoped runbook fixtures.

## Acceptance criteria

- Baseline evidence shows working tool calls, supplied old/current guidance and the incorrect destination in simulated state. The failed expectation has an authoritative source.
- The investigation distinguishes a supported context hypothesis from ambiguity, a changed user goal or a pure executor planning error. Unsupported causes are not published as proven diagnoses.
- The candidate changes only permitted retrieval/filtering/context assembly behavior and preserves required constraints, document provenance and originals.
- Equivalent-state comparison shows the original task and a fresh current release use the appropriate destination through unchanged Hermes. A historical question still accesses the old guidance, and a different workspace/workflow does not inherit the wrong scope.
- Existing-tool and missing-tool scenarios remain passing. Token reduction alone cannot satisfy any outcome check.
- The rule survives restart and a fresh executor session without debugging-history injection; candidate rejection, protected evaluation, bounded access, safe publication and rollback remain effective.

## Required evidence

Keep baseline and candidate supplied-context records with source/version/scope metadata, failed condition provenance, hypothesis and actual rule diff, trusted before/after state checks, historical and cross-scope regressions, unchanged source/executor/evaluator proof and restart/rollback results. Report uncertainty and available context/usage measurements without treating correlation as causation.

## Copy-paste prompt

```text
Implement only Task 06 in docs/tasks/06-context-repair.md. Read AGENTS.md, the
technical plan and predecessor evidence. Extend the existing loop to investigate
actual misleading context and generate a scoped persistent retrieval repair.
Keep Hermes and trusted checks fixed; preserve source documents, constraints and
historical access. Verify original/fresh current releases, a historical question,
cross-scope behavior and prior repair scenarios from comparable isolated state.
Do not claim causation from document presence or success from token reduction.
No UI or live services. Retain the rule diff, context/state evidence, failed
attempts and persistence/rollback results; update status truthfully.
```
