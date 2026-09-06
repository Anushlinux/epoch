# Epoch backend

Phase 1 provides a local API for saving and reading tasks, SQLite storage, validated contracts, and a CLI. A submitted task stays `pending`; executor, checkpoints, streaming, feedback and repairs are later phases.

Rajdeep owns this backend. Anushrut's UI handoff is in [FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md). See [technical decisions](DECISIONS.md), [phase boundaries](PHASES.md), and the repository [status](../docs/status.md).

## Setup

Install Python 3.12 and uv. From `backend/`, in PowerShell:

```powershell
$env:UV_CACHE_DIR = "$PWD/.uv-cache"
uv sync --frozen
uv run --frozen epoch-backend check-config
uv run --frozen epoch-backend init-db
uv run --frozen epoch-backend serve
```

For a POSIX shell, use `export UV_CACHE_DIR="$PWD/.uv-cache"` before the same uv commands. The lockfile pins the dependencies. No model credentials or business-service accounts are required.

The server listens at `http://127.0.0.1:8000`. Open `/docs` for the API explorer, `/openapi.json` for implemented HTTP contracts, and `/api/health` for health. Stop with Ctrl+C. `python -m epoch_backend` also supports the same commands inside the installed environment.

Defaults require no configuration file. To customize them, copy `.env.example` to `.env`, edit it, then use `uv run --frozen epoch-backend --env-file .env serve`. Environment variables override that file. Relative `EPOCH_DATA_DIR` paths resolve against the backend package root; the default database is `backend/data/epoch.sqlite3`. Generated data, `.env`, local caches and virtual environments are ignored by Git. Configuration validation does not create the data directory.

This foundation is an unauthenticated local development service. The CLI accepts loopback bind addresses only; CORS permits the frontend's localhost and 127.0.0.1 ports 5173. Set `EPOCH_CORS_ORIGINS` to an explicit JSON list of local origins if your UI uses a different port. Unexpected browser origins cannot submit tasks. Deployment, authentication and multiple workers are outside Phase 1.

## Try task intake

In a second PowerShell terminal:

```powershell
$payload = @{
    client_request_id = [guid]::NewGuid().ToString()
    message = "Prepare the release checklist"
    project_id = "demo"
} | ConvertTo-Json
$task = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/tasks -ContentType application/json -Body $payload
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/tasks/$($task.id)"
```

Retain the same `client_request_id` when retrying a submission: an identical normalized request returns the saved task with HTTP 200; a new request returns 201; changing its content under that ID returns 409. `project_id` is a label at this stage, not an access grant. Restarting the server retains tasks. To start a separate empty store, set `EPOCH_DATA_DIR` to another directory.

## Checks and contract export

```powershell
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen python scripts/export_contracts.py --check
uv run --frozen python scripts/smoke_test.py
```

Contract fixtures are labelled development data and never served as real execution. The API publishes live OpenAPI at `/openapi.json`; running the export script without `--check` regenerates the shared schema bundle and examples. The smoke script starts the real CLI server on a temporary loopback port, verifies intake and restart persistence, then stops it and removes its temporary database. CI runs these checks and verifies exports have no drift on Python 3.12. Remote CI execution is distinct from local verification.
