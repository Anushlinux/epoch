# Epoch

Epoch is a planned debugger agent that improves the tools and context around a fixed executor. When a task fails, it should investigate the evidence, produce a real environment repair, verify it, and retain it for future tasks.

**Current state: documentation only. All product runtime capabilities are unimplemented.** There is no application to install or run, no runtime test suite, and no verified integration. See the [implementation status](docs/status.md) for the exact boundary.

## Start here

1. Read the [product direction](docs/direction.md), preserved unchanged from the approved source.
2. Read [AGENTS.md](AGENTS.md), the canonical instructions for agents working in this repository.
3. Follow the [architecture and data flow](docs/architecture.md) and [integration verification checklist](docs/integrations.md).
4. Start with [Task 01: technical selections and runtime foundation](docs/tasks/01-technical-plan.md). Complete the [seven tasks in order](docs/tasks/README.md); their prompts describe future work, not work already delivered.

## Intended first demonstration

A user asks Hermes to prepare a release: create a ticket, add a checklist, and notify QA with both links. A deliberately faulty adapter fails. Epoch should inspect the failure, correct the adapter, test the change, and publish it. Hermes should then complete both the original task and a meaningful fresh variation using the same executor configuration.

Two later scenarios exercise the same loop: generating a missing QA-owner lookup tool, and repairing retrieval that supplied an outdated runbook. The first implementation will use clearly labeled local simulated services. Their inspectable state can prove simulated effects; it cannot prove delivery to Jira, Notion, or Slack.

## Build direction

- Use Python for the future implementation. Choose runtime/tooling, libraries, concrete schemas, storage, transport, testing, CI and repository layout in Task 01 before building its minimal foundation.
- Build a command-line interface (CLI) before a graphical interface. Prove one complete repair loop before expanding the demonstration.
- Keep Hermes fixed during runtime repair. Protect trusted evaluators, bound maintenance permissions, and prevent duplicate side effects during replay.
- Persist executable tool or retrieval changes. A successful-looking response, a reminder, or a prerecorded patch is not a repair.
- Keep evidence honest: planned behavior, simulation, local test results, and verified live behavior are different claims.

## Working with this repository

There are no setup or execution commands yet. Do not infer a working runtime from these documents. Claude and Copilot have minimal entry files pointing to [AGENTS.md](AGENTS.md); the shared rules live there.

For documentation changes, check relative links and anchors, preserve the exact direction source, inspect the diff for scope, and run `git diff --check`. The [documentation validation notes](docs/status.md#documentation-validation) describe the handoff checks and their limits.

The preserved direction describes the eventual product, including a possible interface and connected services. It is not permission to add those capabilities in this documentation foundation.

## Generic agent startup prompt

Instruction discovery varies between coding tools. If your tool does not load the repository guidance automatically, paste this prompt and name the assigned task:

```text
Read AGENTS.md, README.md, docs/status.md and docs/direction.md first, then
docs/tasks/README.md and the assigned task brief. Inspect the current branch
and existing changes; preserve unrelated work. Explain the task scope and
dependencies before editing. Work only on the assigned task, follow its
acceptance criteria, and report checks actually run, evidence and limitations.
Update docs/status.md only for demonstrated results. Do not start later tasks.
For the first implementation handoff, use docs/tasks/01-technical-plan.md;
that future task selects the stack before implementing its minimal foundation.
```
