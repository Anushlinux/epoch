# Task 02: Local environment and CLI baseline

Status: unstarted. Intended future implementation.

## Scope

Implement the smallest Python environment and CLI defined in Task 01. Provide permission-scoped discovery, descriptions, invocation requirements and dispatch for local simulated ticket, checklist/page and message tools. Provide directory data and retained current/historical runbooks as resources for later tasks, without exposing a prewritten owner-lookup adapter.

Make service state inspectable and resettable in isolated runs. Include a baseline adapter serialization defect for Scenario A and a correct control path for unrelated behavior. The fault must cause a real simulated contract violation, not a theatrical error unrelated to the operation. Separate fixture setup from tool behavior and trusted expected outcomes.

Do not implement the debugger, Hermes integration, missing-tool generation, retrieval repair, UI or live SaaS connections. Add only the runtime structure and dependencies justified by the completed technical plan.

## Dependencies

[Task 01](01-technical-plan.md), including resolved contracts, permissions and isolation choices. If those decisions are missing, stop dependent implementation and report the gap.

## Acceptance criteria

- The documented CLI can initialize isolated simulated state, discover permitted tools, inspect their contracts, invoke them, and inspect actual created state.
- Valid operations produce corresponding simulated objects and references. Denied calls and invalid inputs cannot produce successful-looking state.
- The faulty checklist adapter fails for the documented contract reason. A successful ticket step can precede that failure, preserving a realistic partial-success fixture.
- Baseline resets produce equivalent starting state without cross-run contamination. Permission tests demonstrate that discovery and execution do not exceed grants.
- Directory and runbook fixtures support meaningful variation in project, owner, release and document scope. No hidden ready-made missing tool or fixture-to-patch mapping is installed.
- State and CLI output are clearly labeled simulated. No external credentials or live business writes are required.

## Required evidence

Record clean setup and CLI reproduction commands, actual input/output and state snapshots for successful, invalid and denied calls, a baseline failure trace, reset/isolation checks, and the focused test results. Document which behavior is simulated and which later components remain absent. Do not claim a repair or Hermes compatibility yet.

## Copy-paste prompt

```text
Implement only Task 02 in docs/tasks/02-local-environment.md after reading
AGENTS.md and the completed Task 01 plan. Preserve direction.md and unrelated
work. Build the planned Python CLI and permission-scoped local environment with
inspectable, resettable simulated services. Include the genuine faulty checklist
adapter and partial-success fixture; retain directory/runbook resources without
a hidden missing-tool adapter. No debugger, Hermes integration, UI or live services.
Run every relevant acceptance check, retain reproducible commands and simulated
state evidence, and update docs/status.md only for demonstrated capabilities.
Report files, tests, limitations and evidence locations.
```
