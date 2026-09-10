# Epoch

**New, unverified:** [Neatlogs trace explorer Phases 1–2](backend/docs/TRACE_EXPLORER.md)
adds local SDK capture, persistent original spans, searchable inputs/outputs and a
read-only `/traces` interface. `serve --profile trace-debugger` runs collection and
browsing without task execution or repairs. Testing was explicitly skipped; AI
questions and later feature phases remain unimplemented.

**Current integration:** the frontend connects to the Phase 7 backend. Incident grouping, on-demand Luna investigation, JSON evidence imports and local Neatlogs ingestion with optional cloud export extend the existing repair flow. See [setup](backend/docs/INCIDENTS_SETUP.md) and [validation status](docs/status.md). Full Phase 6/7 model-backed repair acceptance remains pending; the API still reports phase 7.

Epoch pairs Hermes chat with an explicitly invoked debugger. The user chats with Hermes normally, then opens **Debugger** for that conversation and starts an investigation when they want to understand a failure. The debugger uses saved requests and observed execution evidence. Release supervision and verified environment repair remain separate, supported example workflows; they are not prerequisites for chatting. See the [current change plan](docs/CHAT_DEBUGGER_PLAN.md).

**Current state: backend Phases 1–5 are implemented and verified.** OpenAI `gpt-5.6-luna` plans sourced checkpoints and generates serializer corrections; the existing Hermes executor performs the work. Phase 5 adds opt-in Docker-isolated checks, original/fresh task verification, durable versions and rollback. Normal operations share 20 model requests/600 seconds; each repair verification gets its own 20/600 limit, with a 60-request/1,800-second overall repair ceiling and two candidate attempts. See [repair setup](backend/docs/REPAIR_SETUP.md) and [implementation status](docs/status.md).

The [frontend workspace](frontend/README.md) connects intake, supervised execution, feedback, all three repair views and artifact provenance to the current backend. The Incidents view groups related evidence and exposes explicit investigation actions. Fixture pages remain separately labelled; UI checkmarks still come from trusted backend checks.

The active demo environment is the [PDF workshop](backend/docs/PDF_WORKSHOP.md):
real files, an initially broken pagination tool, and explicit generated repair or
merge-tool creation. Standard chat and release evaluation remain available. CSV
conversations are hidden from active use; their records and evidence are retained.
See [current validation](docs/status.md) before making live acceptance claims.

## Start here

1. Read the [product direction](docs/direction.md), preserved unchanged from the approved source.
2. Read [AGENTS.md](AGENTS.md), the canonical instructions for agents working in this repository.
3. Follow the [architecture and data flow](docs/architecture.md) and [integration verification checklist](docs/integrations.md).
4. Follow the [Anushrut / Rajdeep work split](docs/tasks/README.md). Anushrut can connect to the actual run/status/state/SSE endpoints in the [frontend handoff](backend/docs/FRONTEND_HANDOFF.md). Implement subsequent [backend phases](backend/PHASES.md) only when requested.

## User flow

1. **Chat:** send a message to Hermes and continue the saved conversation. Sending does not create a release task or start debugger analysis.
2. **Inspect:** select **Debugger** to open the current conversation's investigation view. Opening it only reads saved records.
3. **Investigate:** explicitly start an investigation, optionally describing what went wrong. Luna compares the original requests with visible responses, recorded errors and tool evidence. It reports supported findings, hypotheses and missing evidence.
4. **Apply:** click **Verify and apply fix** for a supported CSV sample mapping failure. This separate action verifies and publishes a proposed adapter repair, then lets Hermes retry. Investigation alone remains diagnosis-only. Later CSV chats in the same project discover the saved mapping. Original requirements stay unchanged. See [CSV repair setup](backend/fixtures/csv/README.md).
5. **Supported evaluation:** separately open the release example to exercise its existing sourced checkpoints, trusted checks and opt-in generated repairs. Those checks cover that workflow; they do not certify arbitrary chat outcomes.

```text
User -> Hermes chat -> saved messages and observable tool evidence
                            |
                   user opens Debugger
                            |
                   explicit investigation -> Luna -> findings and evidence gaps
                                              |
                     supported CSV mapping -> verify -> publish -> Hermes retry

Separate release example -> supervisor -> trusted checks -> opt-in verified repair
```

**Task recovery and learning are different claims.** A better instruction may complete this task. Learning requires a persistent tool or retrieval change that improves a meaningful fresh task. Keep Hermes' implementation, system prompt, model, and discovery interface fixed. Compare environment versions using equivalent initial briefs and checks; record supervisory interventions separately.

## Who builds what

| Owner | Scope | Deliverable |
| --- | --- | --- |
| **Anushrut** | User interface, request/clarification flow, checkpoint board, execution activity, repair/diff/test views, results and feedback, frontend integration and tests | An interface whose states and checkmarks come from real backend evidence |
| **Rajdeep** | Python backend, task planning and checkpoint contracts, Hermes integration, event capture, evaluator, corrective instructions, shared tools/simulators, debugger, isolated verification, persistent versions and rollback | One working supervised task and verified environment-repair loop |
| **Both** | Agree API/event contracts and task states first; integrate early and rehearse the demo | UI and backend express the same request, checkpoints, evidence, and result |

Both can use Codex in parallel on separately owned files. Anushrut can use live backend events for the implemented release flow; fixture screens for future workflows remain clearly labelled. Detailed handoffs and acceptance checks are in the [task README](docs/tasks/README.md).

## Intended first demonstration

A user asks Epoch to prepare a release: create a ticket, add a checklist, and notify QA with both links. Epoch turns these into checkpoints and delegates execution to Hermes. A deliberately faulty adapter fails. Epoch should inspect the failure, correct the adapter, test the change, and publish it. Hermes should then complete both the original task and a meaningful fresh variation using the same executor configuration. Show one targeted task correction and one user-feedback revision separately from the persistent repair claim.

Two later scenarios exercise the same loop: generating a missing QA-owner lookup tool, and repairing retrieval that supplied an outdated runbook. The current implementation uses clearly labeled local simulated services. Their inspectable state can prove simulated effects; it cannot prove delivery to Jira, Notion, or Slack.

## Build direction

- The backend uses Python 3.12, FastAPI/Pydantic, SQLite, the official MCP SDK, uv, pytest and Ruff. See the [initial decisions](backend/DECISIONS.md), [Phase 2/3 implementation plan](backend/PHASES_2_3_PLAN.md) and [Phase 4 plan](backend/PHASE_4_PLAN.md) for boundaries.
- Keep a CLI/harness for early backend verification while Anushrut builds the product UI in parallel against agreed contracts. Prove one complete repair loop before expanding the demonstration.
- Keep Hermes fixed during runtime repair. Protect trusted evaluators, bound maintenance permissions, and prevent duplicate side effects during replay.
- Persist executable tool or retrieval changes. A successful-looking response, a reminder, or a prerecorded patch is not a repair.
- Keep evidence honest: planned behavior, simulation, local test results, and verified live behavior are different claims.

The 10-hour target is: agree contracts and smoke-test integrations in hour 1; connect the UI to a real failed task by hour 3; finish the first verified repair and fresh-task test by hour 5; use hours 5–8 for feedback handling, further scenarios only if feasible, and integration; reserve hours 8–10 for checks and rehearsal. These are targets, not a completion guarantee. If the first repair slips, reduce scenario breadth.

## Working with this repository

Run `npm run dev --prefix frontend` and open `http://127.0.0.1:5173/chat`. In **Connection settings**, connect to the backend's local origin. Sending a chat message explicitly starts Hermes. Opening **Debugger** only reads evidence; its investigation action explicitly starts Luna. Release execution lives in the separate release example. Run state tests with `npm test --prefix frontend`, actual intake browser checks with `npm run test:integration --prefix frontend`, and execution browser checks with `npm run test:execution --prefix frontend`. The execution test runner uses an explicit test executor with real HTTP/storage/checks; it does not prove live model execution. See the [frontend verification record](frontend/evidence/README.md).

From `backend/`, run `uv sync --frozen`, then `uv run --frozen epoch-backend serve`. The health check is at `http://127.0.0.1:8000/api/health`; API docs are at `/docs`. Follow the [backend README](backend/README.md) for Python/uv prerequisites, local cache setup, configuration, tests and the live-server smoke check. Claude and Copilot point to [AGENTS.md](AGENTS.md) for shared rules.

For documentation changes, check relative links and anchors, preserve the exact direction source, inspect the diff for scope, and run `git diff --check`. The [documentation validation notes](docs/status.md#documentation-validation) describe the handoff checks and their limits.

The preserved direction remains unchanged. The current chat/manual-debugger flow records the user's latest interaction decision and supersedes the earlier default release-intake presentation. The separately available supervisor remains limited to the release workflow and additive feedback. The repair controller supports the checklist serializer, missing lookup and context selector; the latter two still await live acceptance. Incident evidence does not expand its permissions or trigger rules.

## Generic agent startup prompt

Instruction discovery varies between coding tools. If your tool does not load the repository guidance automatically, paste this prompt and name the assigned task:

```text
Read AGENTS.md, README.md, docs/status.md and docs/direction.md first, then
docs/tasks/README.md and the assigned task brief. Inspect the current branch
and existing changes; preserve unrelated work. Explain the task scope and
dependencies before editing. Work only on the assigned task, follow its
acceptance criteria, and report checks actually run, evidence and limitations.
Update docs/status.md only for demonstrated results. Do not start later tasks.
Read backend/PHASES.md, backend/DECISIONS.md and backend/PHASES_2_3_PLAN.md;
implement only the next phase explicitly assigned by the user.
```
