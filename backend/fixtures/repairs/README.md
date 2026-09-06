# Phase 5 actual repair evidence

Recorded September 6, 2026. [Full saved evidence](phase5_runs.json) contains actual
Luna/Hermes runs, simulated state, correlated events, generated source/diff,
verification, project versions and rollback. These are observed records, not
authored successful fixtures. The local runtime databases remain ignored by Git.

## Accepted repair

Original run: `b87e91a5-d00a-4285-a201-457d80933b7e`.
Published version: `05e25e52-72d0-4a26-8c0f-ce418d137144`.
Generated source SHA-256:
`404f25894d673611a8bc60f96ba9134a8b39ceb88813b7497b21bb4162806e3d`.

Luna inspected the actual failed checklist call, serializer source and service
schema. It generated Python that preserves `items` as a list. No reference patch
was selected by scenario name or installed in place of generated output. Only the
container executed that code; the host validated and persisted the real simulated
service payload.

| Stage | Actual result | Model requests |
| --- | --- | --- |
| Primary execution, diagnosis, resumed task | Completed; 217 correlated events; original ticket retained; exactly one ticket/checklist/message | 17: 2 Luna + 15 Hermes |
| Isolated original replay | Passed; identical protected criteria and executor baselines; prior effects retained | 9 Hermes |
| Fresh release variation | Passed with new release identity and extra multilingual item | 11 Hermes |
| Component and healthy regressions | Six actual candidate invocations passed; normal, multilingual and 50-item inputs | 0 |
| Container boundary probes | All enforced-boundary observations passed | 0 |
| Later session after restart | Release 3.7 completed through ordinary discovery without debugger input | Direct Hermes |

Primary plus verification used **37 requests**, within the 60-request overall
ceiling. Total original operation time was 315.20 seconds, including 154.97 seconds
of isolated verification excluded from the primary clock. The complete result,
five proof records and matching immutable hashes preceded publication. The original
Hermes conversation then resumed through a separately recorded intervention.

Later run `ccd11672-fceb-4f18-8ea3-9ccdd3fb4b97` completed in 62.38 seconds with
79 recorded events and exactly one ticket/checklist/message. It matched the original
executor implementation, model, prompt, bridge and discovery baselines, loaded the
saved version after a service restart, and received no debugging history. Explicit
rollback restored `builtin`; an identical rollback retry returned the same receipt.
Already pinned run records and simulated business effects remained unchanged.

## Retained failed follow-up

Supervised run `36da312c-53f8-4628-b706-0eee6be2f0dd` stopped at `needs_input`
after one Luna request. A proposed addition lacked an exact user-input quote, so
the existing provenance gate rejected the plan. There were no executor calls or
business effects. This record remains in the export; no check was weakened or
result rewritten. The later ordinary-discovery experiment explicitly started the
plain Hermes run above, independently of Luna planning.

## Validation and reproduction

The [acceptance harness](../../scripts/run_phase5_acceptance.py) makes actual model
requests. Its `--resume-original UUID` option explicitly verifies an already completed
published repair while retaining earlier follow-up failures. Default execution
starts with a fresh data directory. The [read-only exporter](../../scripts/export_repair_evidence.py)
retains all cases and project history. See [setup](../../docs/REPAIR_SETUP.md).

Ordinary orchestration tests use declared doubles. Separate actual Docker tests
exercise readonly/nonroot/network/capability/credential/host-file restrictions,
CPU and wall limits, output/JSON limits, and a faulty serializer whose failed
checks prevent publication and whose rejection survives restart. The negative
candidate is explicitly developer-authored test input, not a fabricated LLM result.
No generated Python is executed on the host.

The exact final commands and outcomes are recorded in the Phase 5 handoff below.
The same two upstream Starlette HTTPX/AnyIO warnings remain. These checks do not
establish live Jira/Notion/Slack behavior, remote CI, multi-user security or current
frontend compatibility. Hermes and Luna use the existing observed account route;
other installations need their own compatibility checks.

## Final hardening rerun

After deadline and unresolved-activation guards were tightened, a second actual
repair run `46f3019b-4cdb-4aa2-9109-14163cc4a161` completed in 320.64 seconds
with 214 events. It used 18 primary requests (2 Luna / 16 Hermes), 8 isolated
original-replay requests and 11 fresh-release requests: again 37 overall. All five
checks passed before publication. Independently generated version
`5a69874c-24e3-4781-93d3-6391d202a78d` produced the same source digest as the first
run; its actual Luna response is retained separately, not substituted.

Later run `88df1724-ea3b-484b-a27b-20158c16b75a` loaded the persisted adapter and
created the correct ticket/checklist, but its provider stream stopped before the
QA message: `Codex stream produced no SSE events for 12s after first byte`.
It is correctly recorded as failed, with one ticket, one checklist and no message.
The second harness therefore did not return complete end-to-end acceptance.
The first experiment retains the complete later-session acceptance; the final
rerun separately proves the hardened repair gates and original/fresh success.

An automatic approval review rejected another model-backed follow-up because it
could send task/source/repair context to OpenAI. No workaround or additional model
call was attempted. [Local ASGI readback](http_readback.json) then verified the
saved completion/SSE, explicit rollback, identical rollback retry, restart
persistence and restoration of the original serializer defect with inference
fully disabled. This is real saved-data/API evidence, not a model success claim.

## Final local checks

`EPOCH_TEST_DOCKER=1` followed by `python -m pytest -q` passed **296 tests**, including
9 actual Docker cases, with the two upstream warnings. `ruff check .`,
`ruff format --check .` (67 files), contract-export validation and the actual
inference-disabled HTTP/intake/restart smoke all passed. See the
[complete handoff](../../PHASE_5_REPORT.md). Original direction and frontend
identity checks passed; no remote CI or current browser sign-off is claimed.
