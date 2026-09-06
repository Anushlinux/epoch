# Ordered implementation tasks

**Planning only. All seven tasks are unstarted; all product runtime capabilities remain unimplemented.** Assign one task at a time. A copied prompt authorizes only that brief's scope and does not authorize the rest of the roadmap.

Read [AGENTS.md](../../AGENTS.md), [direction](../direction.md), [status](../status.md), [architecture](../architecture.md), and the [integration checklist](../integrations.md) before starting. Preserve the direction unchanged.

| Order | Task | Dependency | Intended deliverable |
| --- | --- | --- | --- |
| 01 | [Technical plan and contracts](01-technical-plan.md) | Documentation foundation | Decisions and enforceable contracts before code |
| 02 | [Local environment and CLI baseline](02-local-environment.md) | 01 | Executable simulated tools and isolated state |
| 03 | [Fixed executor, traces and evaluation](03-executor-evidence.md) | 02 | Observable Hermes workflow with protected outcome checks |
| 04 | [First complete tool-repair loop](04-tool-repair.md) | 03 | Automatic diagnosis, real patch, safe verification and durable publication |
| 05 | [Generate a missing capability](05-missing-tool.md) | 04 | New authorized adapter discovered and used by unchanged Hermes |
| 06 | [Repair supplied context](06-context-repair.md) | 05 | Persistent scoped retrieval change with historical regression coverage |
| 07 | [Repeatable CLI demonstration and evidence](07-demo-evidence.md) | 06 | Reproducible three-scenario report with truthful limitations |

Use Python, a command-line interface before UI, and local simulated services first. Task 01 chooses libraries, concrete schemas, storage, transport and layout. Do not infer those choices from conceptual examples in these documents.

Every task must preserve the fixed executor, protected evaluator, bounded permissions, safe replay, real persistent repairs and honest evidence. If a dependency is incomplete, inspect its evidence and report the blocking gap. Do not label a stub, a test double, or a vendor documentation reference as a completed integration.

For each handoff, record changed files, commands actually run, outcomes, evidence locations and known limitations. Update [status](../status.md) only for what those results establish. The three scenarios share one release workflow; they are not proof of three distinct domains.
