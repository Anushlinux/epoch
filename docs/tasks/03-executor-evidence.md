# Task 03: Fixed executor, traces and evaluation

Status: unstarted. Intended future implementation.

## Scope

Connect Hermes once to the scoped local environment using Task 01's chosen interface. Make the release workflow observable from CLI task input through actual tool calls to final simulated state. Capture the executor baseline before experiments and control unrelated memory/skill updates.

Implement correlated execution and retrieval evidence, requirement provenance, and trusted outcome evaluation. Instrument the intended Neatlogs boundaries and verify Workshop trace access/replay support where available under the agreed plan. Report an unavailable integration explicitly; local trace capture is not proof that Neatlogs or Workshop works.

Keep the evaluator and baseline acceptance fixtures inaccessible to generated candidate edits. Define evaluation for the ticket, checklist, notification destination, actual links and truthful completion report. Retain inferred versus explicit requirements and missing evidence.

Do not implement automatic repair, generate a missing tool, build UI, or connect live business services. Any model provider needed by Hermes must use an explicitly authorized, documented data route from the plan; do not acquire credentials or silently choose another route.

## Dependencies

[Task 02](02-local-environment.md) and Task 01's executor, evidence, privacy and evaluation contracts.

## Acceptance criteria

- Actual Hermes discovers and invokes permitted local tools through one baseline interface. Record its installed version/configuration; a substitute executor cannot satisfy this criterion.
- A release run shows the partial failure and unmet checklist condition in both trace and simulated state. A control run passes trusted checks.
- Evidence ties request, requirement sources, visible tool versions, calls/arguments/results/errors, supplied documents and final state to task/run identifiers. Missing observations are marked missing.
- The trusted evaluator catches a successful tool call with a wrong business outcome, such as the wrong notification destination, and cannot be rewritten through the candidate maintenance surface.
- Tests cover denied access, missing evidence, ambiguous requirements and a correction that changes the goal rather than establishing a tool defect.
- Integration checklist results distinguish actual Neatlogs/Workshop tests from local-only evidence. Workshop replay claims require configured execution against isolated state, not a trace viewer screenshot.

## Required evidence

Retain the Hermes baseline identity/configuration evidence, actual discovery/invocation traces, sourced success conditions, passing and failing trusted check results, inspectable simulated state and evaluator protection checks. Record integration versions, commands and gaps without storing secrets. If Hermes is blocked, report partial component work and the dependency blocker; do not call the task complete.

## Copy-paste prompt

```text
Implement only Task 03 in docs/tasks/03-executor-evidence.md. Read AGENTS.md,
the approved technical plan and predecessor evidence first. Integrate actual
Hermes once with the local simulated environment, capture a fixed executor
baseline, instrument observable calls/context/state, and implement protected
outcome checks with requirement provenance. Verify Neatlogs and Workshop only
as supported by the plan and docs/integrations.md; label gaps honestly. Do not
build repair logic, UI or live business integrations. Run the specified checks,
retain actual traces and state, report unavailable observations/integrations,
and update status only where execution evidence supports it.
```
