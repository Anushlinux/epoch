# Current implementation status

As of September 6, 2026, Epoch is a documentation-only repository. **All product runtime capabilities are unimplemented.** The approved direction is a target, not a result.

## Implemented facts

Only the documentation below exists. No product code or runtime tests have been implemented or executed.

- [README](../README.md): product summary, current state, and reading order.
- [Direction](direction.md): unchanged source document.
- [AGENTS.md](../AGENTS.md): canonical shared rules, with minimal [Claude](../CLAUDE.md) and [Copilot](../.github/copilot-instructions.md) entrypoints.
- [Architecture](architecture.md): intended boundaries and evidence flow.
- [Integration checklist](integrations.md): verification required before compatibility claims.
- [Seven ordered task briefs](tasks/README.md): future scope, dependencies, acceptance criteria, required evidence, and prompts.

## Approved decisions

Use Python for future implementation, build a CLI before UI, and start with local simulated services. Keep the approved direction unchanged. Choose runtime/tooling, libraries, concrete schemas, storage, transport, testing, CI and layout in Task 01 before its minimal foundation; those choices have not been made.

## Requirements awaiting implementation

Keep Hermes fixed during runtime repair, protect trusted evaluation, enforce bounded permissions and repair budgets, prevent duplicate replay effects, and publish only verified persistent environment changes. Preserve rejected attempts, missing evidence and historical sources. These are requirements for future work, not controls already enforced by this repository.

## Unverified assumptions

Hermes discovery behavior, Neatlogs capture coverage, Workshop replay, and interoperability remain unverified against installed versions. The local simulations have not been built, and their proposed fidelity to business-service contracts is untested. Simulation alone would establish neither secure execution of generated code nor live-service compatibility. Model-provider choice and data routing are also unresolved. See the [integration checklist](integrations.md) for the evidence needed.

## Runtime capability inventory

| Capability | Current status | Planned work |
| --- | --- | --- |
| Concrete runtime/tooling, library, schema, storage, transport, testing and CI decisions | Not selected | Task 01 |
| Python runtime and command-line interface foundation | Unimplemented | Task 01 onward |
| Local simulated business services and inspectable state | Unimplemented | Task 02 |
| Permission-scoped tool registry and version lifecycle | Unimplemented | Tasks 02 and 04 |
| Hermes integration and dynamic tool discovery | Unimplemented; compatibility unverified | Task 03 |
| Early local trace/context capture and trusted outcome checks | Unimplemented | Task 02; extended to Hermes in Task 03 |
| Runtime tests, evaluator protection tests and regression suite | Unimplemented | Tasks 01–07 |
| Debugger agent and complete repair loop | Unimplemented | Task 04 onward |
| Automatic failure triggers and bounded investigation | Unimplemented | Task 04 |
| Existing-tool repair, isolated verification, publication and rollback | Unimplemented | Task 04 |
| Generated missing-tool repair | Unimplemented | Task 05 |
| Scoped context repair | Unimplemented | Task 06 |
| Persistent repairs benefiting fresh executor sessions | Unimplemented | Tasks 04–07 |
| Repeatable CLI demonstration and measured report | Unimplemented | Task 07 |
| Neatlogs and Raindrop Workshop integration | Unimplemented; compatibility unverified | Plan in Task 01; implement and verify in Task 07 |
| Live Jira, Notion, Slack or directory connections | Unimplemented; not in initial local implementation scope | Separate future authorization |
| Graphical interface, production deployment and broad multi-domain support | Unimplemented; deferred | Outside these initial briefs |

No package manifest, dependency installation, application scaffold, runtime test suite, CI workflow, global configuration, or live integration is part of this foundation. There are no runtime benchmark results or successful repair demonstrations to report.

## Documentation validation

Foundation handoff must check the following and report actual outcomes in the pull request:

1. Compare `docs/direction.md` byte-for-byte with the supplied source file. Record matching SHA-256 hashes. The source used for this foundation is `/Users/bhaskarpandit/.ao/electron/terminal-drops/1788694360022-direction_1_.md`; this is provenance, not a portable dependency or setup path.
2. Resolve every relative Markdown link and fragment to an existing file and heading. Check preserved footnote references separately. This does not verify remote URLs or installed integration behavior.
3. Confirm the README leads to the canonical instructions and all planning documents. Confirm the Claude and Copilot files resolve to the same AGENTS.md and do not duplicate its policies.
4. Check that exactly seven ordered briefs each contain goal, prerequisites, owned area, exclusions, acceptance checks, evidence, and a copy-paste prompt.
5. Inspect all changed and untracked files against the base commit: only the intended Markdown documentation and agent entry files may be added or changed. Run `git diff --check` and the corresponding staged check before committing.
6. Follow the AO preview guide and open `ao preview README.md` when working in AO. Inspect the rendered primary handoff without introducing a server, dependencies, or launch configuration.

These checks validate documentation integrity and navigation only. Update the runtime inventory only after future implementation has matching execution evidence; record partial or blocked results explicitly.

### Foundation validation record

The source copy was compared byte-for-byte during this handoff. Both files have SHA-256 `791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`. Checks passed for 88 local Markdown links, two heading fragments and five footnotes across 16 Markdown files. The Claude import target and Copilot pointer resolve to the canonical AGENTS.md. All seven briefs have the required goal, prerequisites, owned area, exclusions, acceptance checks, evidence and prompt sections. The change inventory contains only the intended Markdown files, with no tracked validation scripts. The README was opened with AO preview and its rendered content inspected. No nonexistent application command is presented as runnable; future commands must be established and tested during implementation.

The full staged `git diff --check` reports three trailing-whitespace findings in the unchanged source at `docs/direction.md` lines 3–5. Those original two-space Markdown hard breaks are intentionally preserved. Strict checking of all authored files passes with `git diff --cached --check -- . ':!docs/direction.md'`. A separate `git -c core.whitespace=-blank-at-eol diff --cached --check` also passes; the override applies only to that invocation and changes no repository or global settings. This exception does not waive whitespace checking for authored documentation.
