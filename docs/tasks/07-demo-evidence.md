# Task 07: Integration verification and inspectable CLI demonstration

Status: unstarted. Intended future implementation.

## Goal

Verify the intended Neatlogs/Workshop integrations against the implemented loop and deliver a reproducible CLI demonstration with inspectable evidence.

## Prerequisites

Read [AGENTS.md](../../AGENTS.md), [direction](../direction.md), [status](../status.md), [architecture](../architecture.md), the [integration checklist](../integrations.md), and the completed Task 01 plan. Preserve unrelated work and report missing prerequisite evidence before dependent edits.

[Task 06](06-context-repair.md), plus passing evidence for Tasks 04 and 05. If a repair type is missing or fails, report the partial demonstration and do not mark the full task complete.

## Owned area

Implement and verify Neatlogs tracing and Raindrop Workshop inspection/replay against the installed versions and the integration checklist. Build any required evidence adapter explicitly; preserve the early local trace contracts rather than replacing them. Verify task/run correlation, custom tool/context boundaries, data routing, redaction, missing traces and failed replay. Do not assume interoperability or complete capture from SDK installation.

Package the three implemented scenarios into a reproducible CLI demonstration of one release workflow. Show requested outcome, actual failure, automatic investigation, generated environment change, trusted verification, publication and benefit on a meaningful later task. Use readable summaries with inspectable traces, actual diffs and simulated state one step away.

Exercise clean starting state and persistent repaired versions deliberately: the baseline must not inherit repaired state, while the later-session demonstration must load the actual published artifact. Document how to reproduce both. Keep UI, live business services, new repair families and claims of broad multi-domain support out of scope.

## Exclusions

No graphical UI, live Jira/Notion/Slack/directory integrations, new repair families or multi-domain claim. Do not acquire credentials or silently change data routes; use only explicitly authorized integration configuration. No promise to finish within ten hours.

## Acceptance checks

- Neatlogs captures actual configured model/tool/context boundaries with correlated evidence, and Workshop inspects the intended traces and executes a configured safe replay. Record exact versions, wiring and failure behavior. If either integration is blocked, label the result partial and identify which local evidence remains valid; do not claim full task completion.
- Documented commands reproduce all three scenarios from clean isolated state and show real diagnoses, generated diffs, trusted checks and inspectable simulated effects.
- The primary demonstration includes automatic initiation; it does not depend on manually selecting a prerecorded repair. Human interventions after setup are counted and described.
- Original, meaningful fresh-task, regression and fresh-session persistence results are inspectable for each repair type. Show active versions, rejection and rollback evidence, safe replay, unchanged executor and protected evaluator checks.
- A report separates repair overhead from later-task latency and available token/tool-call usage. Missing measurements are labeled unavailable. Any recurrence or completion metric states its test population and denominator.
- The report uses precise claims such as “did not recur in the tested variations.” It does not imply permanent reliability, three domains, local-only inference or live SaaS delivery from local evidence.
- README setup/run instructions are verified against a clean environment; status and integration checklist match actual installed-version tests. Unavailable Neatlogs/Workshop behavior remains clearly unverified.
- The documentation handoff opens the primary README in AO using its preview guide; no graphical app or preview-only dependency is added.

## Evidence

Retain actual Neatlogs traces, Workshop inspection/replay outcomes and any bridging code/configuration evidence, plus capture-failure/redaction checks. Keep unavailable integration evidence explicitly missing.

Retain exact reproduction commands, environment and integration versions, sanitized task/run references, baseline/repaired/fresh/regression result matrix, generated artifact diffs, simulated object state, active-version and rollback records, limits/permissions checks and measured usage/interventions. Include a plain-English repair report for each scenario with failed expectation, evidence, cause, change, verification, persistence and limitations.

## Copy-paste prompt

```text
Implement only Task 07 in docs/tasks/07-demo-evidence.md. Read AGENTS.md and
all predecessor evidence. Implement and verify Neatlogs capture and Workshop
inspection/replay against installed versions using docs/integrations.md. Preserve
early local trace contracts, verify wiring and data routing, and label any missing
integration partial. Package and verify the Python CLI demonstration of
three repair types in one local simulated release workflow. Reproduce real
failures, automatic investigation, actual generated changes, protected verification,
safe publication, fresh-task transfer and persistence. Keep executor fixed and
permissions/replay bounded. Report measured results and missing measurements
honestly; no UI, live business-service or multi-domain claims. Verify clean setup commands,
update README/status/integration evidence, follow the AO preview guide for README,
and hand off commands, artifacts, test outcomes and remaining limitations.
```
