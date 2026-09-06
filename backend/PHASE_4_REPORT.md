# Phase 4 implementation report

**Implemented and verified. This report was delivered before push; the user has now authorized publication to main.** Phase 4 and Task 03
acceptance pass; Phase 5 remains unstarted. Rajdeep owns this backend work and
Anushrut retains the unchanged frontend.

The changes are on `codex/backend-phase-4`, based on pulled main `948ea47`, in:

```text
C:\Users\Rajdeep\AppData\Local\Temp\epoch-phase-4-590ee3f3
```

The original checkout has an unfinished merge and frontend edits. This isolated
checkout preserves that work. Run the commands below from its `backend` folder.

## What works

1. An explicit supervised release request goes to **OpenAI `gpt-5.6-luna`**. It
   returns an enhanced brief and sourced checkpoints. Trusted code rejects invalid
   plans and asks for clarification when the supported requirements are unclear.
2. Your existing **Hermes / `gpt-6-astra`** executes through the local MCP service.
   Trusted checks inspect ticket, checklist and QA-message state after meaningful
   tool completions and at pass boundaries. Private reasoning stays inside Hermes.
3. If a completed executor pass omits a supported step, Luna issues a targeted
   continuation with the unmet checkpoint and saved object references. Hermes
   continues the same conversation and reuses completed work.
4. User feedback starts an explicit revision over the same sandbox. Supported
   changes add checklist items or exact QA-message phrases. Existing objects are
   updated in place; earlier requirements, sources, results and evidence remain.
5. Run/revision APIs and SSE expose actual progress, questions, interventions,
   outcome checks, errors and counters. Request IDs prevent duplicate submissions;
   expected revision IDs reject stale changes. Cancellation and restart retain
   partial effects without automatic replay.

**Limits:** at most **20 shared model requests and 600 seconds per operation**.
Luna requests and every actual Hermes request, including summaries/retries, consume
this same host-enforced allowance. Automatic continuations cannot reset it. A new
explicit feedback or clarification submission has its own allowance. Limits can
be lowered by callers, never raised. Conservative admission can charge a request
cancelled immediately before dispatch.

## API and CLI

Existing direct execution remains available. Add `supervised: true` to
`POST /api/tasks/{task_id}/runs` for Phase 4. New routes are:

- `POST /api/runs/{run_id}/feedback`
- `POST /api/runs/{run_id}/clarifications`
- `GET /api/runs/{run_id}/revisions`

Feedback/clarification bodies require `client_request_id`, `expected_revision_id`
and `message`; optional limits default to 20/600. The
[frontend handoff](docs/FRONTEND_HANDOFF.md) contains complete bodies and event rules.

```powershell
uv sync --frozen
uv run --frozen epoch-backend debugger-info
uv run --frozen epoch-backend run-release --supervised --project demo --release 2.4
```

To demonstrate the omitted-step correction followed by feedback:

```powershell
uv run --frozen python scripts/run_phase4_acceptance.py --data-dir data/my-phase4-demo
```

This invokes actual models. For HTTP use `uv run --frozen epoch-backend serve`
and open `http://127.0.0.1:8000/docs`. Stop the server before using execution CLI
commands against the same data directory; its lease allows one execution owner.

## Demonstrated results

**264 tests passed**, Ruff check/format passed for 53 files, contract exports match,
and actual local HTTP/MCP/restart checks passed. Two existing upstream deprecation
warnings remain. Tests use explicit model doubles; the following results used real
Luna and Hermes independently of those tests.

| Actual operation | Outcome | Requests | Duration |
| --- | --- | --- | --- |
| Deliberately omitted QA notice | Luna issued one correction; Hermes completed it in the same conversation; all 3 checks passed | 15 total: 2 Luna + 13 Hermes | 114.05 s |
| User feedback | Added checklist item and QA phrase; all 4 checks passed; same 1 ticket, 1 checklist and 1 message | 7 total: 1 Luna + 6 Hermes | 71.83 s |

Run: `f54cb5bf-a9b2-4204-9afe-e3fcaf8a2b34`. The first operation's full record was
unchanged after feedback; retrying feedback created no new operation/event.
All required executor baselines were present and unchanged between continuations.
HTTP readback replayed 245 SSE events after cursor 1 and preserved the run across
restart. See [portable evidence](fixtures/supervision/README.md) and
[exact validation commands](../docs/status.md#phase-4-validation-record).

An earlier actual attempt hit the existing provider's 12-second stream-idle
watchdog after creating the ticket/checklist. It remains blocked with its partial
state and failed QA check preserved. Earlier debugger parsing probes are retained
too. These are development/provider failures, not erased or presented as successes.

## Changed areas

- New debugger transport, supervision contracts, shared budget and supervisor:
  `debugger_bridge.py`, `supervision_contracts.py`, `operation_budget.py`, `supervisor.py`.
- Hermes session/request gate; execution persistence/admission, feedback and status;
  HTTP/CLI commands and runtime contracts.
- Sandbox additive criteria history; scoped `checklists.update` and `messages.update`;
  trusted `release-state-v3` evaluation and registry metadata.
- Tests, locked explicit JSON Schema dependency, generated contracts, acceptance
  harness and portable success/failure evidence.
- Backend setup/phase plan, debugger/Hermes/frontend handoffs, root README, canonical
  instructions, integration/status records and Task 03 ownership/status.

All implementation files remain under `backend/`; shared handoff documents stay
at the repository root and under `docs/`. No frontend source, test or asset changed.
The preserved direction and historical Phase 3 evidence remain unchanged. Runtime
databases, credentials, caches and virtual environments are excluded from the commit.

## Limits and remaining work

- This release supervisor supports additive checklist/QA-text changes. Arbitrary
  workflows, removing earlier requirements, changing channels/titles or subjective
  output evaluation are not implemented; unsupported requests ask for clarification.
- **No generated environment repair or persistent learning yet.** Broken adapters,
  missing tools and permission failures remain blockers. Phase 5 must add generated
  patches, protected verification, publication, rollback and later-session proof.
- The current frontend still rejects Phase 4 health/task states. Use CLI/API until
  Anushrut integrates the published contract. No browser sign-off is claimed.
- Actual Luna validation used your existing OpenAI/Codex credential route. The
  official API-key route has transport tests but no live key test on this machine.
  No credentials, model defaults or installed Hermes source were changed.
- The Codex route does not accept the output-token cap; turn/time limits apply,
  but no exact monetary spend cap is claimed. Provider failures can stop work.
- Business services are local simulations. No live Jira/Notion/Slack, Neatlogs,
  Workshop, production isolation or remote CI is claimed. Abrupt process-death
  containment remains unverified; normal cancellation and restart are tested.

The initial report preceded publication. The subsequent authorized integration fetched main at `f16b1ef` and preserved its complete frontend tree. See the latest status record and Git history for publication evidence.
