# Task 02: Simulated services, trusted checks and early traces

Status: unstarted. Intended future implementation.

## Goal

Build an inspectable local release workflow environment with trusted outcome checks and basic traces before connecting Hermes or implementing repair.

## Prerequisites

Read [AGENTS.md](../../AGENTS.md), [direction](../direction.md), [status](../status.md), [architecture](../architecture.md), and completed [Task 01](01-technical-plan.md) decisions, interfaces and foundation evidence. Resolve missing shared contracts before coding; preserve unrelated work.

## Owned area

Implement simulated Jira tickets, Notion checklists/pages, Slack messages and directory records using Task 01's Python foundation. Add scoped tool discovery/descriptions/invocation/dispatch and context boundaries with retained current/historical runbooks. Do not expose a prewritten owner-lookup adapter.

Own fixture setup/reset, trusted checks for requested objects, content, links and destinations, and early local trace capture of task/run identity, tool versions, calls/arguments/results/errors, supplied context and state. Keep trusted expected outcomes and any fault setup separate from debugger-editable surfaces. Seed Scenario A's real adapter serialization defect, B's absent lookup capability and C's misleading old context without providing canned diagnoses or patches.

## Exclusions

No Hermes integration, debugger, missing-tool generation, retrieval repair, Neatlogs/Workshop integration, UI or live business connections. Simulated service state is not secure generated-code isolation. Use only the shared interfaces and dependencies chosen in Task 01.

## Acceptance checks

- The CLI initializes/reset states, discovers only permitted tools, inspects contracts, invokes operations and shows actual simulated ticket/page/message state. Valid, invalid and denied operations are distinguishable.
- Scenario A fails for a meaningful contract violation after a ticket succeeds. Scenario B lacks lookup despite an authorized directory resource. Scenario C supplies versioned old/current context and can represent a wrong destination with a successful call.
- Trusted checks evaluate actual state and sourced requirements, including wrong links/recipient despite success output. Passing controls and deliberate failures produce the expected trusted results.
- Basic traces already correlate calls, errors, context metadata and state to task/run identifiers; absent observations stay explicitly missing. No later integration is required to inspect them.
- Resets restore equivalent starting state without cross-run contamination or duplicate effects. Discovery, execution and context access honor grants. Protection tests establish that candidate-facing access cannot change trusted checks.
- Fixtures vary releases, projects, owners and document scope, preserve historical sources, and do not leak reference patches. Every effect/reference is labeled simulated; no credentials or live writes are required.

## Evidence

Provide exact setup/CLI/test commands, actual successful/invalid/denied state snapshots, early traces for passing and failing fixtures, trusted outcome results, reset/duplicate-effect checks and tool/context permission tests. Report missing evidence and remaining components; do not claim repair or Hermes compatibility.

## Copy-paste prompt

```text
Implement only Task 02 in docs/tasks/02-local-environment.md. Read AGENTS.md,
the completed Task 01 plan/interfaces and foundation evidence first. Build local
simulated Jira/Notion/Slack/directory services, scoped tool/context boundaries,
three scenario fixtures, trusted state checks and basic correlated traces now.
Preserve historical sources and separate trusted checks/fault setup from the
future repair surface. No canned diagnoses, hidden lookup adapter, Hermes,
debugger, tracing-service integrations, UI or live business connections. Verify
valid/invalid/denied calls, actual state, partial failure, reset and duplicates;
retain commands, traces and trusted results. Update status only from evidence.
```
