# Task 03: Actual Hermes integration and frozen configuration proof

Status: executor integration is implemented under Phase 3; acceptance evidence is recorded in [status](../status.md). This broader task also includes Phase 4 supervision and feedback, which remain unstarted. Do not mark all of Task 03 complete when only Phase 3 passes. See [phase boundaries](../../backend/PHASES.md) and [Hermes setup](../../backend/docs/HERMES_SETUP.md).

## Goal

Have actual Hermes execute a supervisor-issued structured brief, discover and invoke the local environment, and support bounded targeted continuation against unmet checkpoints. Prove its implementation, system prompt, model and discovery interface remain fixed during later environment repairs.

## Prerequisites

Read [AGENTS.md](../../AGENTS.md), [direction](../direction.md), [status](../status.md), [architecture](../architecture.md), the [integration checklist](../integrations.md) and [Task 02](02-local-environment.md) evidence. Use Task 01's selected interfaces and Task 02's existing traces/trusted checks. Report unmet dependencies before dependent changes.

## Owned area

Connect Hermes once to the scoped local environment. Extend existing evidence to include the actual executor's request, relevant conversation, visible capabilities, tool calls, received context, response and state observations. Capture the executor baseline and control unrelated memory/skill updates.

Run the release workflow through the existing trusted checks. Preserve requirement provenance, ambiguity and missing evidence. Verify installed-version discovery and invocation, and record how a later environment version can become visible without per-tool executor edits.

Implement the initial task-supervision path using Task 01 contracts: derive a structured brief and sourced checkpoints, evaluate observable tool/step outcomes, and issue a bounded continuation when Hermes omits a required step. Preserve completed effects. Feedback that changes intent creates a revision rather than a retroactive passing result. Expose real progress/results to Anushrut's UI contract without implementing frontend code here.

## Exclusions

No automatic repair, generated lookup, context repair, Neatlogs/Workshop integration, UI or live business connections. A test double cannot substitute for Hermes acceptance. Model inference must use an explicitly authorized, documented route from Task 01; do not acquire credentials or silently change providers.

## Acceptance checks

- Actual Hermes discovers permitted tools, reads invocation requirements and invokes them through the selected interface. Record installed version/configuration, denied access and invalid-call behavior.
- A release run shows the partial adapter failure in existing traces and simulated state; a control run passes trusted checks. Wrong business outcomes remain failures even if tool calls return success.
- Record and compare implementation identity, system prompt, model configuration and baseline discovery interface across controlled runs. Show unrelated memory/skill updates are controlled; missing baseline evidence prevents a frozen-configuration claim.
- Correlate executor activity with Task 02 tool/context/state evidence using task/run identifiers. Retain sourced conditions and mark missing observations explicitly.
- Test denied access, ambiguous requirements and a correction that changes the goal rather than proves a tool defect. Keep trusted checks outside candidate maintenance access.
- Demonstrate a targeted continuation completing an omitted checkpoint, with the instruction and resulting effects recorded. Limit retries and do not weaken criteria. This proves supervision, not persistent environment learning; that requires Task 04.
- Document the installed discovery/version-refresh behavior needed for later publication, with actual invocation proof where tested. Neatlogs/Workshop verification remains pending Task 07; local traces do not establish those integrations.

## Evidence

Retain baseline identity/configuration comparisons, actual Hermes discovery/invocation traces, passing/failing trusted results and simulated state. Record exact commands, versions, data routing and gaps without secrets. If Hermes is unavailable, label any component work partial and report the blocker; do not call this task complete.

## Copy-paste prompt

```text
Implement only Task 03 in docs/tasks/03-executor-evidence.md. Read AGENTS.md,
the technical plan and Task 02 evidence first. Connect actual Hermes once to the
scoped local environment. Extend existing traces/trusted checks and prove actual
discovery, invocation and frozen implementation/prompt/model/discovery baseline,
with unrelated memory controlled. Implement structured briefs, sourced checkpoint
evaluation, bounded targeted continuation and explicit user-feedback revisions;
record supervisory instructions separately from environment repair. Keep denied access, missing evidence and
ambiguous goals honest. No repair logic, Neatlogs/Workshop integration, UI or live
business connections. Verify every acceptance check, retain baseline comparisons,
commands, traces and state, and update status only for demonstrated behavior.
```
