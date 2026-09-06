# Phase 5 implementation plan

Implement Task 04 only, from main `bf1c93f`, on `codex/backend-phase-5`.
Preserve frontend files, original direction, historical evidence and the user's
original unfinished checkout. No missing-tool/context repair or live integrations.

1. Add a Linux Docker runner for one Python checklist serializer. Candidate code
   receives JSON input only: no host mounts, credentials, database or service access.
   Use a pinned image, unprivileged user, read-only root, no network/capabilities,
   bounded temporary storage, CPU/memory/process/output/time limits and explicit
   cleanup. Never import generated Python in the backend or Hermes process.
2. Persist immutable generated artifacts, diagnosis/diff, verification evidence,
   rejection history and a project-scoped active/previous version in SQLite.
   Pin one version per run, with explicit safe-boundary repair activation. Hash-check artifacts on every invocation;
   activation/rollback are host-only operations at safe boundaries.
3. Detect captured checklist adapter-contract failures rather than scenario labels.
   Give actual code/contract/trace evidence to the existing OpenAI Luna debugger.
   Stage its executable output, enforce at most two attempts, and retain failures.
4. Protect component/permission/regression tests and equivalent-state replay criteria.
   Before publication, verify isolated original-task and fresh-release behavior;
   Hermes remains responsible for business work. Resume retained original effects
   safely and prove a later session uses the persisted version via normal discovery.
5. The user authorized separate verification budgets: each isolated replay/fresh
   run gets at most 20 model requests/600 seconds. Initial execution, repair
   diagnosis and resumed execution retain one shared 20-request/600-active-second
   budget; its clock pauses only during recorded isolated verification. The whole
   repair operation is capped at 60 model requests and 1,800 wall-clock seconds.
   At most two generated candidates are allowed. Request counts are
   the enforced inference-usage budget; report token usage where available without
   claiming a guaranteed dollar cap on the existing subscription route. No budget
   reset, candidate publication or fabricated completion after exhaustion.
6. Expose opt-in repair execution, version/attempt readback and explicit rollback
   through CLI/API. Update setup/environment guidance, schemas, tests and evidence;
   actual container and actual Luna/Hermes acceptance are required for completion.

Docker Desktop was installed but stopped; it was started for the assigned local
runner. Its Linux engine is available. Pull the standard Python 3.12 slim image
once during setup, resolve its immutable digest, and forbid implicit runtime pulls.
The [Docker runner reference](https://docs.docker.com/reference/cli/docker/container/run/)
documents the selected isolation/resource flags; tests must verify actual behavior.
