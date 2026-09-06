# Phase 5: generated checklist repair

Epoch can detect a checklist serializer contract failure, ask the existing OpenAI
`gpt-5.6-luna` debugger for a sourced Python correction, verify it, and save the
accepted adapter for later release runs in that project. Hermes still creates the
ticket, checklist and QA message. All business services remain local simulations.

## Required setup and optional environment change

Keep the [existing Hermes setup](HERMES_SETUP.md) and [debugger setup](DEBUGGER_SETUP.md).
No new OpenAI API key or model setting is required on the verified existing account.
Install/start **Linux Docker**, then pull the default image once:

```powershell
docker pull python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
uv run --frozen epoch-backend repair-info
```

`repair-info` must report `available: true`. It inspects the local daemon, Linux
engine, seccomp and locally available pinned image. It makes no model request.
Runtime never pulls an image and has no fallback to executing generated Python on
the host. Docker is required for repair verification and for using a published
adapter; intake and the built-in adapter work without it.

**Optional new app setting:** `EPOCH_REPAIR_IMAGE`, shown in [.env.example](../.env.example).
Its default is the digest above, so existing `.env` files need no edits. Overrides
must be digest-pinned standard Python 3.12 Linux images with `/usr/bin/timeout`.
Changing this setting applies to future candidates; existing published versions
retain their verified immutable image ID. Keep that image locally available.
Credentials and optional Hermes-path overrides remain process-only variables.

Startup creates `environments.sqlite3` in `EPOCH_DATA_DIR`. Existing intake/run
records remain readable; no manual database migration or reset is needed. Back up
the whole data directory when stopped. Use a separate directory for a fresh demo;
do not delete rejected attempts or overwrite earlier evidence.

## Run the repair demonstration

With the HTTP server stopped, from `backend/`:

```powershell
uv run --frozen epoch-backend run-release --release 2.4 --scenario broken_checklist --repair
uv run --frozen epoch-backend environment --project demo
uv run --frozen epoch-backend run-release --release 3.7 --scenario broken_checklist --supervised
```

These commands make real model requests. `--repair` enables supervision and repair
for that run; direct and ordinary supervised execution remain available. The
initial failure triggers investigation automatically after the Hermes pass ends.
The third command starts a new task that discovers the saved adapter normally,
without a repair instruction or debugging history. Existing runs pin their version;
feedback on an existing run retains that version. New runs load the project's active
version. A published version alone does not prove the original task completed.

To exercise the complete acceptance sequence, including service restart and
idempotent rollback, use a new data directory:

```powershell
uv run --frozen python scripts/run_phase5_acceptance.py --data-dir data/my-phase5-demo
```

The harness retains all attempts and prints stage progress. It requires actual
Luna, actual Hermes, passing independent checks, retained original object IDs,
later-session use and rollback. Provider errors remain failures and are retained;
the harness does not silently retry or substitute a model.

## Limits and verification

| Work | Enforced maximum |
| --- | --- |
| Initial execution, diagnosis and resumed original execution together | 20 authorized model requests / 600 active seconds |
| Each isolated original-task or fresh-release verification | 20 requests / 600 seconds |
| Whole repair operation, including failed verification attempts | 60 requests / 1,800 wall seconds |
| Generated candidates | 2 |
| One candidate container | 128 MiB memory, 0.5 CPU, 16 processes, 2 CPU seconds, 5-second container timeout, bounded parent deadline/output |

Lower `--max-turns` and `--timeout` values also lower verification budgets and the
overall ceiling to three times those values. Only isolated verification pauses the
primary clock; request counts never reset. Cancellation denies further requests
and retains partial state. Cleanup can take bounded additional time.

Request counts are the enforced inference-usage budget. Available provider token
usage is retained; **there is no guaranteed dollar cap** on the subscription route.

The only generated surface is `checklist_serializer.py`. The module receives JSON
arguments inside a nonroot, read-only, network-disabled container with no host or
Docker-socket mounts, credentials, business service access, evaluator or publication
API. Docker restrictions follow the [official run reference](https://docs.docker.com/reference/cli/docker/container/run/).
The trusted host validates the returned service payload and preserves object identity.

Before publication the exact source digest must pass component tests, actual
container-boundary probes, an isolated copy of the original task, a fresh release
with a new identifier and extra multilingual item, and healthy-path regressions.
Trusted criteria, original effects, permissions and executor baselines stay fixed.
Publication is atomic in the environment store and uses an expected-active-version
check. The original run activates only between Hermes passes.

Rejected source, diagnosis, diff and checks are retained. Startup rejects unfinished
candidates and marks unfinished operations interrupted; it never resumes them or
turns partial evidence into approval. The local service lease permits one active
operation. Containers are a restricted execution boundary, not a production
multi-tenant security claim.

## Inspect and roll back

`GET /api/repair/runtime` inspects Docker. `GET /api/environments/{project_id}` returns
the active version, source/diff, attempts, proofs, publication and rollback history.
Normal run records and SSE expose `repairing`, `repair.*` and `environment.*` events.
See the [frontend handoff](FRONTEND_HANDOFF.md); frontend files are unchanged.

With execution idle, use the active version UUID returned by `environment`:

```powershell
uv run --frozen epoch-backend rollback-environment --project demo --expected-version VERSION_UUID --request-id REQUEST_UUID
```

The HTTP equivalent is `POST /api/environments/demo/rollback` with
`{"expected_version":"VERSION_UUID","client_request_id":"REQUEST_UUID"}`. Generate
the request UUID once and retain it for identical retries. Stale versions, changed
retry input and active execution return conflicts. Rollback restores the prior
version for new runs, preserves versions/evidence and never undoes business effects
or silently switches an already pinned run. There is no model-accessible publish,
rollback or evaluator endpoint.

## Checks

```powershell
uv run --frozen pytest
$env:EPOCH_TEST_DOCKER = '1'
uv run --frozen pytest tests/test_candidate_docker.py
Remove-Item Env:EPOCH_TEST_DOCKER
```

`EPOCH_TEST_DOCKER` is a process-only test switch, not an app `.env` setting. These
Docker tests make no model requests. The model acceptance harness is separate.
Missing-tool generation, context repair, live services, UI integration and
Neatlogs/Workshop remain later work.
