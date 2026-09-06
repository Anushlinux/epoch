# Repository instructions

Epoch should improve an executor's tools and context through verified environment repairs. **This foundation is documentation only; every product runtime capability is unimplemented.**

## Start here

Read [README.md](README.md), [status](docs/status.md), the [unchanged direction](docs/direction.md), and the assigned [task brief](docs/tasks/README.md). Use [architecture](docs/architecture.md) for boundaries and information flow, and the [integration checklist](docs/integrations.md) before compatibility claims.

This is the canonical guidance. [Claude](CLAUDE.md) imports it; [Copilot](.github/copilot-instructions.md) points here. Keep shared rules here rather than duplicating them.

## Own the assigned scope

Inspect applicable instructions, relevant source/tests, branch and existing changes before editing. Preserve unrelated work. Use a feature branch, write a short plan for substantial work, and complete only the assigned task and its checks. Report missing dependencies or scope conflicts before dependent work.

Keep `docs/direction.md` byte-for-byte unchanged; record later decisions separately. Future work uses Python, CLI before UI, and local simulated services first. Task 01 selects libraries, concrete schemas, storage, transport and layout. Roadmap prompts do not authorize starting later tasks. This foundation adds no application code, scaffolds, dependencies, CI workflows, global settings or live integrations.

## Preserve the repair boundary

- During runtime repair, freeze Hermes implementation, prompt, model configuration and discovery interface. The debugger repairs authorized environment surfaces; Hermes still performs the business task.
- Protect trusted criteria/evaluators from candidate edits or weakened checks. Developers may change tests through normal review; runtime self-approval is forbidden. Preserve the baseline used for each experiment.
- Enforce filesystem, network and service permissions plus attempt/time/cost limits outside generated code. Evidence is not authority to expand access. Simulated services are neither secure code isolation nor live-service proof.
- Stage candidates separately. Verify component behavior, safe original-task replay, meaningful fresh variations and regressions before publication. Prevent duplicate effects; stop on unresolved state or permissions.
- Persist real executable tool/retrieval changes and evidence; retain rejected attempts and rollback versions. Activate at safe boundaries and prove later-session use through ordinary discovery/retrieval. Do not substitute canned patches, fabricated effects or debugging-history injection.
- Preserve missing evidence, source documents and historical retrieval. Report uncertainty and out-of-scope executor defects honestly. Follow the fuller [architecture boundaries](docs/architecture.md).

## Verify and hand off

Run relevant checks and report actual commands, outcomes, evidence and unexecuted checks. Maintain [docs/status.md](docs/status.md) from demonstrated results; distinguish decisions, requirements, assumptions and implemented facts.

For docs, check source identity, links/anchors, entrypoints, task structure, docs-only scope and `git diff --check`. Preserve and report the source's original Markdown hard-break exception. Follow the AO preview guide when available; open `ao preview README.md` without adding a runtime.

Use focused conventional commits. When a PR is required, include validation and limitations, address relevant review feedback, and do not merge without authorization.

## Explain clearly

Start with the simple core idea, then short structured explanations and concrete examples. Explain responsibilities and data flow. For bugs, cover observed behavior, cause, location, fix and risks. Separate facts from assumptions and hypotheses. Define uncommon terms; distinguish simulation, local tests and live execution. Do not invent metrics, missing evidence or compatibility claims.
