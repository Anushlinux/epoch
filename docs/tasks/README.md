# Ordered implementation tasks

**Planning only. All seven tasks are unstarted; all product runtime capabilities remain unimplemented.** Assign one task at a time. A copied prompt authorizes only that brief's scope and does not authorize the rest of the roadmap.

Read [AGENTS.md](../../AGENTS.md), [direction](../direction.md), [status](../status.md), [architecture](../architecture.md), and the [integration checklist](../integrations.md) before starting. Preserve the direction unchanged.

| Order | Task | Dependency | Intended deliverable |
| --- | --- | --- | --- |
| 01 | [Technical selections and runtime foundation](01-technical-plan.md) | Documentation foundation | Runtime/tooling/persistence/testing/CI decisions and minimal foundation |
| 02 | [Simulated services, trusted checks and early traces](02-local-environment.md) | 01 | Simulated Jira/Notion/Slack/directory, fixtures, tool/context boundaries and local evidence |
| 03 | [Actual Hermes integration and frozen configuration proof](03-executor-evidence.md) | 02 | Actual discovery/invocation linked to evidence and a fixed executor baseline |
| 04 | [First complete tool-repair loop](04-tool-repair.md) | 03 | Automatic diagnosis, real patch, safe verification and durable publication |
| 05 | [Generate a missing capability](05-missing-tool.md) | 04 | New authorized adapter discovered and used by unchanged Hermes |
| 06 | [Repair supplied context](06-context-repair.md) | 05 | Persistent scoped retrieval change with historical regression coverage |
| 07 | [Integration verification and inspectable CLI demonstration](07-demo-evidence.md) | 06 | Verified Neatlogs/Workshop wiring and reproducible three-scenario evidence |

Use Python, a command-line interface before UI, and local simulated services first. Task 01 chooses runtime/tooling, libraries, concrete schemas, storage, transport, testing, CI and layout before building the minimal foundation. Do not infer those choices from conceptual examples in these documents. No task is being executed as part of this documentation change, and the sequence makes no ten-hour completion promise.

## Safe independent work

Keep the seven-task acceptance order. Once Task 01 has fixed and reviewed the shared tool/context, state and trace interfaces, separately assigned work within Task 02 can cover service adapters, fixture data and trusted checks in distinct owned files. Agree on state-reset semantics and evidence identifiers before splitting that work; combine it and run boundary checks before Task 03.

After the local repair loop and evidence contracts are established, separately assigned Neatlogs and Workshop compatibility investigations can proceed independently of report writing within Task 07. Their wiring and final acceptance still depend on shared identifiers and actual rerun evidence. Do not split work across unsettled interfaces or edit another task's owned area.

Every task must preserve the fixed executor, protected evaluator, bounded permissions, safe replay, real persistent repairs and honest evidence. If a dependency is incomplete, inspect its evidence and report the blocking gap. Do not label a stub, a test double, or a vendor documentation reference as a completed integration.

For each handoff, record changed files, commands actually run, outcomes, evidence locations and known limitations. Update [status](../status.md) only for what those results establish. The three scenarios share one release workflow; they are not proof of three distinct domains.
