# Task 05: Generate a missing capability

Status: unstarted. Intended future implementation.

## Goal

Generate a genuinely absent executable QA-owner lookup capability and prove that unchanged Hermes uses it across different projects.

## Prerequisites

Read [AGENTS.md](../../AGENTS.md), [direction](../direction.md), [status](../status.md), [architecture](../architecture.md), the [integration checklist](../integrations.md), and the completed Task 01 plan. Preserve unrelated work and report missing prerequisite evidence before dependent edits.

[Task 04](04-tool-repair.md), with a complete verified loop and persistent version lifecycle; Task 02's authorized directory resource and Task 03's discovery/evidence checks.

## Owned area

Extend the established repair loop to Scenario B. Hermes must hand a release to the project's QA owner but has no exposed owner-lookup capability. The debugger verifies absence in the permission-scoped registry, reads the authorized local directory contract, generates and tests an executable adapter plus discoverable description and input/output contract, then publishes it.

Hermes discovers the new tool through its unchanged interface and uses the existing message tool for the handoff. Demonstrate transfer to another project with another owner. Do not replace Hermes, enable a hidden prewritten adapter, hardcode an identity, acquire credentials or create new permissions. UI, live directories and context repair are outside scope.

## Exclusions

No hidden prewritten lookup adapter, guessed identities, new credentials or permissions, executor edits, UI, live directory integration or context repair.

## Acceptance checks

- Evidence distinguishes a genuinely absent tool from an existing tool that was undiscovered, poorly described or denied by permissions. Denied access does not authorize tool creation that bypasses the denial.
- The debugger generates an actual adapter and usable contract against the available directory operation; the diff shows what was produced.
- Trusted tests cover one match, no match, ambiguous matches, invalid inputs and denied access. Missing/ambiguous owners do not lead to guessed recipients or fabricated data.
- After verified publication, actual Hermes discovers and invokes the new capability without executor or per-tool prompt changes, then sends to the resolved simulated recipient with the expected links.
- A fresh session for a different project resolves its distinct owner from current directory state. Existing-tool repair regressions continue to pass.
- The new artifact survives restart, remains permission-scoped, and participates in rejection, safe activation and rollback like existing-tool repairs. Failed candidates remain inactive.

## Evidence

Record the original request and scoped tool list, absence investigation, authorized directory contract, generated adapter/contract diff, successful and negative test outcomes, registry version change, actual Hermes discovery and calls, simulated message state, fresh-project result, unchanged executor proof and persistence/rollback checks. Keep evidence of any incomplete or denied branch.

## Copy-paste prompt

```text
Implement only Task 05 in docs/tasks/05-missing-tool.md. Read AGENTS.md, the
technical plan and the verified Task 04 loop first. Extend that loop to generate
an actually missing QA-owner adapter over the authorized local directory. Prove
absence, generate real code and contract, test valid/missing/ambiguous/denied
cases, publish safely, and show unchanged Hermes discovers and uses it for two
different projects. Do not expose a hidden adapter, guess identities, broaden
permissions, add UI or use live services. Preserve rejection and rollback behavior,
record actual discovery/state/persistence evidence, run regressions, and update
status with demonstrated results and explicit limitations.
```
