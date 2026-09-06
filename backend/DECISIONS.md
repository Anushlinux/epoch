# Phase 1 technical decisions

Historical decisions for the completed foundation. The [Phase 2–3 plan](PHASES_2_3_PLAN.md) records subsequent choices; [setup](README.md) and [frontend handoff](docs/FRONTEND_HANDOFF.md) describe the current runtime, including Phase 3 health responses.

Selected before implementation on 2026-09-06. Rajdeep owns the backend; Anushrut can build the UI against the published contracts and explicitly labelled fixtures. This phase implements task intake and persistence only.

## Runtime and layout

- Python 3.12, a `src/epoch_backend` package, and uv with a committed lockfile. Python 3.12 is available locally; Hermes will use its separately verified runtime in Phase 3.
- FastAPI and Uvicorn for HTTP, Pydantic 2 and pydantic-settings for contracts/configuration, and standard-library argparse for the CLI. The API uses lifespan initialization, so importing it does not create database files.
- Standard-library SQLite stores task records with schema version metadata. Connections are short-lived, queries are parameterized, and a unique client request ID makes concurrent retries idempotent. SQLite is sufficient for one local demo server; distributed workers are deferred.
- pytest plus HTTPX exercise HTTP, configuration, CLI and persistence behavior. Ruff checks Python style. A GitHub workflow runs the same checks on Python 3.12 without model credentials. All package code, tests, fixtures, scripts and setup live under `backend/`; GitHub requires the CI entrypoint under `.github/workflows/`.

## Shared implementation contract

The Python module `epoch_backend.contracts` exports `TaskCreate`, `Task`, `TaskStatus`, `TaskList`, `HealthResponse`, and `ErrorEnvelope`, alongside contracts for later phases. Models reject unknown fields. All timestamps are timezone-aware and all record IDs are UUIDs.

- `TaskCreate`: `client_request_id: UUID`, `message: str` (trimmed, nonblank, at most 16,000 characters), `project_id: str` (trimmed, nonblank, at most 100 characters, default `demo`).
- `Task`: `schema_version: 1`, `id: UUID`, `request: TaskCreate`, `status: TaskStatus` (initially `pending`), `created_at`, `updated_at`.
- `TaskList`: `items: list[Task]`, `total: int`, `limit: int`, `offset: int`.
- `HealthResponse`: `status: ok`, `phase: 1`, `storage: ok`, `execution_enabled: false`.
- `ErrorEnvelope`: `error: {code: str, message: str, details: list[object]}`. Validation errors use sanitized field paths/messages; internal errors do not expose filesystem paths or request payloads.

`SQLiteStore(path)` provides `initialize()`, `health() -> bool`, `create_task(TaskCreate) -> tuple[Task, bool]`, `get_task(UUID) -> Task | None`, and `list_tasks(limit=20, offset=0) -> TaskList`. `RequestConflict` signals reuse of a client request ID for a different normalized request. Exact retries return the original record and do not add another task.

`create_app(settings: Settings | None = None)` is the HTTP app factory. Settings use the `EPOCH_` prefix: `data_dir`, `host` (127.0.0.1), `port` (8000), `log_level` (info), and `cors_origins` (JSON list, localhost/127.0.0.1:5173). Runtime files default to `backend/data` independently of the working directory. `.env` loading is explicit through `--env-file`; no model/API credentials are needed. The unauthenticated foundation binds to loopback only.

| Route | Behavior |
| --- | --- |
| `GET /api/health` | Database health and an explicit Phase 1 capability response; 503 if unavailable. |
| `POST /api/tasks` | Persist a pending task; 201 on creation, 200 on identical retry, 409 on conflicting reuse, 422 on invalid input. This does not start execution. |
| `GET /api/tasks?limit=20&offset=0` | Newest-first records; limit 1–100, offset nonnegative. |
| `GET /api/tasks/{task_id}` | Stored task or 404; malformed UUID is 422. |
| `GET /openapi.json` | Concrete implemented HTTP schema. |

Future progress transport is Server-Sent Events with a persisted increasing sequence and replay cursor. Phase 1 supplies versioned event contracts/fixtures, not an SSE endpoint or invented execution events. Future feedback creates an intent revision and keeps prior evidence; it does not rewrite the user's original request.

The `epoch-backend` CLI exposes `check-config`, `init-db`, and `serve`; `--env-file PATH` precedes the subcommand. Configuration failures exit 2 with a useful field-level message. `check-config` has no storage side effects. The ASGI factory is `epoch_backend.app:create_app`.

## Future boundaries, selected but not implemented

Contracts cover task briefs, sourced checkpoints/dependencies, evidence, observable executor runs, scoped tool calls, retrieved context, intent revisions, repair candidates, verification and environment versions. A checkpoint's verified state requires evidence. No contract authorizes a runtime mutation by itself.

| Requirement | Planned enforcement and proof |
| --- | --- |
| Stable executor and tool interface | Phase 3 records Hermes implementation, system prompt, model settings and discovery fingerprint. A stable discover/describe/invoke facade will be exposed through a version-verified MCP integration then; no MCP dependency is needed in Phase 1. |
| Trusted checkpoints | Phase 2 keeps criteria/evaluators outside editable candidate artifacts; Phase 4 records provenance and bounded continuation/revision decisions. |
| Generated-code isolation | Phase 5 uses a separately verified Linux container runner with no network by default, a read-only base, an unprivileged user, explicit writable paths/service grants, and externally enforced resource/attempt limits. Local simulators and Python subprocesses alone do not provide this isolation. |
| Safe repair publication | Phase 5 verifies the exact artifact digest against component, original-task, fresh-task and regression checks in resettable isolated state. Activate at a task boundary, retain rejected attempts and prior versions, and prove restart persistence and rollback. |
| Integration evidence | Hermes, Neatlogs, Workshop and live services remain unverified. Phase 3/8 must record real execution; Phase 1 does not install or imitate these integrations. |

Framework choices use the documented [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/) and [uv CI workflow](https://docs.astral.sh/uv/guides/integration/github/). These establish framework behavior, not proof of product integrations.
