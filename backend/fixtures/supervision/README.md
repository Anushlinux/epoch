# Phase 4 actual supervision evidence

Recorded on September 6, 2026 using actual OpenAI `gpt-5.6-luna` as debugger and
the existing installed Hermes / `gpt-6-astra` executor. Business effects are local
simulations. These files contain saved observations, not authored success fixtures.

- [Full runs, state, events and retained failure](phase4_runs.json)
- [Initial debugger probes, including failed transport attempts](debugger_probes.json)
- [Actual HTTP/SSE/restart readback](http_readback.json)
- [Implementation validation and limits](../../../docs/status.md#phase-4-validation-record)

## Accepted run

Run `f54cb5bf-a9b2-4204-9afe-e3fcaf8a2b34`, task
`fb338d2c-4ed2-49ad-a117-fe0f6c7fe52c`, contains two completed operations and
246 correlated events. Each operation received its own explicitly submitted
20-request/600-second budget; automatic continuations did not reset it.

| Operation | Observed result | Shared requests | Time |
| --- | --- | --- | --- |
| Initial `df647213-5eda-4ee7-a87a-6971785e1460` | Deliberately omitted QA notice; Luna issued one targeted continuation; same Hermes conversation completed all three checkpoints in two passes | 15: 2 debugger + 13 executor | 114.05 seconds |
| Feedback `87de6ef4-b740-4365-9c96-5a8637311333` | Added `Security review complete` to the checklist and `QA sign-off required` to the QA message; all four checks passed | 7: 1 debugger + 6 executor | 71.83 seconds |

The developer omission flag changes only the first-pass instruction. Original user
intent, full sourced brief and all trusted criteria stay visible and complete.
The actual Luna-generated intervention is retained under `interventions`, with
checkpoint/evidence references. It is task supervision, not an environment repair.

Both operations ended with exactly one ticket, one checklist and one message:

| Object | ID retained across feedback |
| --- | --- |
| Ticket | `05d2a105-e984-43de-8ee7-d223b4705678` |
| Checklist | `b4038750-25f8-46e5-bce5-7f6cee88f450` |
| QA message | `6207ffef-32d7-4cd7-aeaf-53d12349d2eb` |

The harness compared the entire initial operation before and after feedback; it
was unchanged. Repeating the identical feedback request returned the existing
result without a new operation or event. Criteria revisions retain before/after
hashes and exact user-source references. `release-state-v3` requires every earlier
checklist item and all requested message phrases in one correctly linked QA notice.

Every executor pass has complete implementation/model/full-and-static-prompt/
discovery/bridge hashes, unchanged invariant flags and retained conversation
history. The two automatic passes have identical invariant hashes. No accepted
operation has missing evidence. Initial briefs and feedback instructions differ
explicitly; no equivalent-task learning comparison is claimed.

The readback check launched the actual local HTTP server with inference disabled.
Run, revisions, task and state agreed; SSE after sequence 1 replayed 245 events,
including both `run.finished` events, then closed. An identical HTTP feedback retry
returned 200 with no new events. A server restart preserved the entire run record.

## Retained unsuccessful work

Run `989eda7a-ec10-4db3-9c44-2f7a38607101` stopped at the provider's existing
12-second SSE idle watchdog after 9 shared requests and 73.68 seconds. It retains
one ticket, one checklist, no QA message and a failed notification check. The run
is blocked, not accepted. No watchdog override, model fallback, automatic repair
or hidden retry was added. The successful run used a fresh sandbox.

The earlier debugger transport probes include a safe failure when the Codex
`response.completed` output array was empty. Normal development corrected public
message assembly from `response.output_item.done`; private reasoning is excluded.
The subsequent exact-Luna probe succeeded. Their bridge hashes identify those
development versions; final acceptance captures the final transport separately.

## Reproduce

From `backend/`, with the existing Hermes installation and a supported debugger
credential route configured:

```powershell
uv sync --frozen
uv run --frozen epoch-backend debugger-info
uv run --frozen python scripts/run_phase4_acceptance.py --data-dir data/phase4-demo
uv run --frozen python scripts/export_run_evidence.py --data-dir data/phase4-demo --output data/phase4-demo/export.json
```

The acceptance command invokes real configured models and may consume account
usage. Every invocation creates a fresh task/sandbox and retains failures. The
export command only reads saved evidence. Provider errors can stop a run, so a
future execution is not guaranteed to reproduce the same timing or request count.

For normal supervision without the deliberate omission, use `run-release
--supervised`; see the [backend README](../../README.md). Additive feedback,
clarification and API bodies are in the [frontend handoff](../../docs/FRONTEND_HANDOFF.md).
The frontend is unchanged and still needs its separate Phase 4 integration.
