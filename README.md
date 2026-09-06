# Epoch

Epoch is a planned task supervisor and debugger. The user describes the desired result in the interface; Epoch turns that request into verifiable checkpoints, gives Hermes a structured task brief, monitors execution, and directs corrections until the checks pass or a clear limit is reached. When the cause lies in the tools or supplied context, Epoch verifies and publishes an environment repair that benefits future tasks.

**Current state: documentation only. All product runtime capabilities are unimplemented.** There is no application to install or run, no runtime test suite, and no verified integration. See the [implementation status](docs/status.md) for the exact boundary.

## Start here

1. Read the [product direction](docs/direction.md), preserved unchanged from the approved source.
2. Read [AGENTS.md](AGENTS.md), the canonical instructions for agents working in this repository.
3. Follow the [architecture and data flow](docs/architecture.md) and [integration verification checklist](docs/integrations.md).
4. Follow the [Anushrut / Rajdeep work split](docs/tasks/README.md). Rajdeep starts with [Task 01: technical selections and runtime foundation](docs/tasks/01-technical-plan.md); Anushrut builds the UI against their agreed contracts. The seven backend tasks retain their dependency order.

## User flow

1. **Request:** the user describes the work in the Epoch interface. Epoch asks only for missing details that materially affect the result.
2. **Checkpoints:** Epoch creates a structured brief with deliverables, constraints, dependencies, and evidence required for completion. Explicit requirements and inferred defaults remain distinguishable.
3. **Execution:** Hermes receives that brief, plans the operational steps, discovers tools, and performs the business work.
4. **Monitoring:** Epoch observes tool calls, results, retrieved context, artifacts, and explicit progress summaries. It evaluates at meaningful execution events; it does not depend on private model reasoning or inspecting every token.
5. **Recovery:** for an omitted or incorrect step, Epoch sends Hermes a targeted continuation instruction that identifies the unmet checkpoint and preserves completed work. For a tool defect, missing capability, or context problem, it stages an environment repair and verifies it before activation.
6. **Delivery:** independent checks verify the actual result. Epoch reports completed deliverables, supporting links/artifacts, and any remaining limitations. Retry, time, and access limits can stop an unresolved task.
7. **User feedback:** if the checks pass but the user is dissatisfied, their feedback identifies a missed requirement, evaluation mistake, or new preference. Epoch records the revised intent and directs Hermes to revise the work; it does not automatically treat every preference as a shared-tool defect.

```text
User -> Epoch interface -> Supervisor: brief + checkpoints -> Hermes
                              ^                              |
                              |     observable execution     v
                              +---- trusted outcome checks <- tools/context
                              |
                   unmet checkpoint or user feedback
                              |
                   targeted instruction to Hermes
                              or
                   isolated environment repair -> verify -> publish
```

**Task recovery and learning are different claims.** A better instruction may complete this task. Learning requires a persistent tool or retrieval change that improves a meaningful fresh task. Keep Hermes' implementation, system prompt, model, and discovery interface fixed. Compare environment versions using equivalent initial briefs and checks; record supervisory interventions separately.

## Who builds what

| Owner | Scope | Deliverable |
| --- | --- | --- |
| **Anushrut** | User interface, request/clarification flow, checkpoint board, execution activity, repair/diff/test views, results and feedback, frontend integration and tests | An interface whose states and checkmarks come from real backend evidence |
| **Rajdeep** | Python backend, task planning and checkpoint contracts, Hermes integration, event capture, evaluator, corrective instructions, shared tools/simulators, debugger, isolated verification, persistent versions and rollback | One working supervised task and verified environment-repair loop |
| **Both** | Agree API/event contracts and task states first; integrate early and rehearse the demo | UI and backend express the same request, checkpoints, evidence, and result |

Both can use Codex in parallel on separately owned files. Anushrut starts with clearly labeled development fixtures while Rajdeep establishes the runtime; fixtures are replaced by real events before claiming an end-to-end demo. Detailed handoffs and acceptance checks are in the [task README](docs/tasks/README.md).

## Intended first demonstration

A user asks Epoch to prepare a release: create a ticket, add a checklist, and notify QA with both links. Epoch turns these into checkpoints and delegates execution to Hermes. A deliberately faulty adapter fails. Epoch should inspect the failure, correct the adapter, test the change, and publish it. Hermes should then complete both the original task and a meaningful fresh variation using the same executor configuration. Show one targeted task correction and one user-feedback revision separately from the persistent repair claim.

Two later scenarios exercise the same loop: generating a missing QA-owner lookup tool, and repairing retrieval that supplied an outdated runbook. The first implementation will use clearly labeled local simulated services. Their inspectable state can prove simulated effects; it cannot prove delivery to Jira, Notion, or Slack.

## Build direction

- Use Python for the future implementation. Choose runtime/tooling, libraries, concrete schemas, storage, transport, testing, CI and repository layout in Task 01 before building its minimal foundation.
- Keep a CLI/harness for early backend verification while Anushrut builds the product UI in parallel against agreed contracts. Prove one complete repair loop before expanding the demonstration.
- Keep Hermes fixed during runtime repair. Protect trusted evaluators, bound maintenance permissions, and prevent duplicate side effects during replay.
- Persist executable tool or retrieval changes. A successful-looking response, a reminder, or a prerecorded patch is not a repair.
- Keep evidence honest: planned behavior, simulation, local test results, and verified live behavior are different claims.

The 10-hour target is: agree contracts and smoke-test integrations in hour 1; connect the UI to a real failed task by hour 3; finish the first verified repair and fresh-task test by hour 5; use hours 5–8 for feedback handling, further scenarios only if feasible, and integration; reserve hours 8–10 for checks and rehearsal. These are targets, not a completion guarantee. If the first repair slips, reduce scenario breadth.

## Working with this repository

There are no setup or execution commands yet. Do not infer a working runtime from these documents. Claude and Copilot have minimal entry files pointing to [AGENTS.md](AGENTS.md); the shared rules live there.

For documentation changes, check relative links and anchors, preserve the exact direction source, inspect the diff for scope, and run `git diff --check`. The [documentation validation notes](docs/status.md#documentation-validation) describe the handoff checks and their limits.

The preserved direction remains unchanged. The supervisor flow and named work split above record the user's later decision and supersede the earlier passive-debugger/CLI-only presentation. This change updates documentation only; implementation must be assigned explicitly through the task briefs.

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
