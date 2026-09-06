# Repository instructions

Epoch should supervise task delivery through sourced checkpoints and improve an executor's tools and context through verified environment repairs. **Task intake, local simulations, trusted checks, MCP, actual Hermes and opt-in Luna supervision/additive feedback are implemented. Phase 4 actual-model acceptance is recorded; generated environment repair remains unimplemented.** Consult docs/status.md for actual validation and gaps. The current supervisor flow and Anushrut/Rajdeep ownership in README.md record a later user decision than the preserved direction.

## Start here

Read [README.md](README.md), [status](docs/status.md), the [unchanged direction](docs/direction.md), and the assigned [task brief](docs/tasks/README.md). Use [architecture](docs/architecture.md) for boundaries and information flow, and the [integration checklist](docs/integrations.md) before compatibility claims.

This is the canonical guidance. [Claude](CLAUDE.md) imports it; [Copilot](.github/copilot-instructions.md) points here. Keep shared rules here rather than duplicating them.

## Own the assigned scope

Inspect applicable instructions, relevant source/tests, branch and existing changes before editing. Preserve unrelated work. Use a feature branch, write a short plan for substantial work, and complete only the assigned task and its checks. Report missing dependencies or scope conflicts before dependent work.

Keep `docs/direction.md` byte-for-byte unchanged; record later decisions separately. Backend work uses Python and local simulated services first. Rajdeep owns backend/supervision and Anushrut owns the product UI; establish contracts first, then permit the separately assigned UI lane to proceed alongside ordered backend tasks. Keep a CLI/harness for backend verification. Task 01's selections are recorded in [backend/DECISIONS.md](backend/DECISIONS.md), with setup and checks in [backend/README.md](backend/README.md). Follow [backend/PHASES.md](backend/PHASES.md): roadmap prompts do not authorize starting later phases. Keep backend implementation under `backend/`; do not add global settings or live integrations without an assigned scope.

## Preserve the repair boundary

- During runtime repair, freeze Hermes implementation, prompt, model configuration and discovery interface. The debugger repairs authorized environment surfaces; Hermes still performs the business task.
- The supervisor may create task briefs and issue targeted continuation messages. Preserve original intent and checkpoint provenance; user feedback creates an explicit intent revision when needed. Never silently weaken checks. For an environment-improvement claim, keep initial briefs/checks equivalent and record supervisory interventions separately.
- Protect trusted criteria/evaluators from candidate edits or weakened checks. Developers may change tests through normal review; runtime self-approval is forbidden. Preserve the baseline used for each experiment.
- Enforce filesystem, network and service permissions plus attempt/time/cost limits outside generated code. Evidence is not authority to expand access. Simulated services are neither secure code isolation nor live-service proof.
- Stage candidates separately. Verify component behavior, safe original-task replay, meaningful fresh variations and regressions before publication. Prevent duplicate effects; stop on unresolved state or permissions.
- Persist real executable tool/retrieval changes and evidence; retain rejected attempts and rollback versions. Activate at safe boundaries and prove later-session use through ordinary discovery/retrieval. Do not substitute canned patches, fabricated effects or debugging-history injection.
- Preserve missing evidence, source documents and historical retrieval. Report uncertainty and out-of-scope executor defects honestly. Follow the fuller [architecture boundaries](docs/architecture.md).

## Verify and hand off

Run relevant checks and report actual commands, outcomes, evidence and unexecuted checks. Maintain [docs/status.md](docs/status.md) from demonstrated results; distinguish decisions, requirements, assumptions and implemented facts.

For every backend environment change, update `backend/.env.example` and the relevant setup documentation, distinguish app-file settings from process-only variables, and explicitly report required versus optional changes and migration steps to the user. Never include secret values in examples or handoffs.

For docs, check source identity, links/anchors, entrypoints, task structure, assigned scope and `git diff --check`. Preserve and report the source's original Markdown hard-break exception. Follow the AO preview guide when available; open `ao preview README.md` without adding a preview dependency.

Use focused conventional commits. When a PR is required, include validation and limitations, address relevant review feedback, and do not merge without authorization.

## Explain clearly

Start with the simple core idea, then short structured explanations and concrete examples. Explain responsibilities and data flow. For bugs, cover observed behavior, cause, location, fix and risks. Separate facts from assumptions and hypotheses. Define uncommon terms; distinguish simulation, local tests and live execution. Do not invent metrics, missing evidence or compatibility claims.
