# Phase 5 implementation report

Implemented the first complete checklist-adapter repair loop on
`codex/backend-phase-5`, based on pulled main `bf1c93f`. Changes are local and
not pushed. Backend work is in
`C:\Users\Rajdeep\AppData\Local\Temp\epoch-phase-4-590ee3f3\backend`.
The original checkout's unfinished merge and frontend work are preserved.

## What now works

- `--repair` enables automatic investigation of an observed checklist contract
  failure. OpenAI `gpt-5.6-luna` receives actual trace/source/schema evidence and
  generates an executable serializer correction with cited evidence.
- Generated Python runs only in restricted Linux Docker. Trusted host code owns
  permissions, business state, checks, budgets and publication.
- Component, isolation, original replay, meaningful fresh release and healthy
  regressions gate publication of the exact source digest. Hermes resumes the
  original task at a safe boundary and reuses completed objects.
- Project versions, source/diff, rejected attempts and evidence persist in SQLite.
  New runs discover the active adapter normally. Existing runs remain pinned;
  explicit idle-only rollback affects new runs and retains effects/history.
- API/CLI expose runner readiness, repair progress, attempts, proofs, versions and
  rollback. Startup rejects unfinished candidates instead of silently publishing.

Each verification gets **20 requests / 600 seconds**. Primary work shares
**20 requests / 600 active seconds**. Overall repair is limited to
**60 requests / 1,800 wall seconds and two candidates**. Available tokens are
recorded; request budgeting does not guarantee a dollar cap.

## Validation

From the backend folder, using the existing Python 3.12 environment:

| Command | Actual result |
| --- | --- |
| `EPOCH_TEST_DOCKER=1` in process environment, then `python -m pytest -q` | 296 passed, including 9 actual Docker cases; 2 upstream deprecation warnings |
| `python -m ruff check .` | Passed |
| `python -m ruff format --check .` | 67 files passed |
| `python scripts/export_contracts.py --check` | Passed |
| `python scripts/smoke_test.py` | Actual local HTTP intake/idempotency/restart passed, inference disabled |

The first actual model acceptance completed repair, original/fresh verification,
post-restart plain-Hermes reuse and rollback. It used 37 overall requests. A final
hardening rerun also completed repair and original/fresh tasks in 37 requests;
its later session used the saved adapter but a provider stream timeout stopped
the conversation before QA notification. A separate rejected Luna follow-up plan
also remains visible. None of these failed outcomes was rewritten.

[Full evidence and limitations](fixtures/repairs/README.md) link all five actual
runs. Inference-disabled ASGI checks over the saved final data passed run/SSE
readback, rollback, identical rollback retry, restart and restoration of the
original adapter defect. Remote CI and current browser acceptance are unexecuted.

## Setup change and quick test

**Required for repair:** running Linux Docker and the pinned Python image from
[REPAIR_SETUP.md](docs/REPAIR_SETUP.md). **Optional new setting:**
`EPOCH_REPAIR_IMAGE`; existing `.env` files need no edit because the default is
already pinned. Startup adds `environments.sqlite3`; no manual migration/reset is
required. Existing Hermes/OpenAI credentials remain sufficient on the verified
route; no new API key or model environment variable is required.

After Docker setup, with the HTTP server stopped:

```powershell
uv run --frozen epoch-backend repair-info
uv run --frozen epoch-backend run-release --release 2.4 --scenario broken_checklist --repair
uv run --frozen epoch-backend environment --project demo
```

Only the checklist serializer repair is implemented. Missing-tool/context repair,
live business integrations and Neatlogs/Workshop remain later phases. Anushrut
owns updating the frontend's Phase 3 compatibility guards and adding the new
supervision/repair controls from the [handoff](docs/FRONTEND_HANDOFF.md). Every
frontend file and the original direction remain unchanged.

Automatic approval review rejected an additional model-backed follow-up because
it could transmit task/source/context to OpenAI. It was not bypassed; subsequent
validation used saved local evidence with inference disabled.
