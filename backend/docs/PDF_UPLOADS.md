# Multiple PDF uploads and Docker recovery

**Implemented but unverified - September 12, 2026.** Static source review and diff
formatting only. No tests, syntax/lint checks, Docker probes, server runs, browser
acceptance or model calls were performed. See the [assigned plan](PDF_UPLOAD_PLAN.md).

## Current user flow

1. Start Docker Desktop and wait for its Linux engine to be ready.
2. Restart the normal backend from `backend`, retaining existing settings:

   ```powershell
   uv run --frozen epoch-backend --env-file .env serve
   ```

3. Refresh the frontend with Ctrl+Shift+R. If the frontend server is stopped, start it
   from the repository root with `npm run dev --prefix frontend`.
4. Open the intended Documents conversation. For a new chat, set Project before the
   first upload. Choose **Upload PDFs** in the composer's plus menu or the Files section.
5. Select several PDFs with Ctrl-click, Shift-click or Ctrl+A in the file picker. The
   browser accepts up to 20 PDFs per selection, each non-empty and at most 10 MiB.
   Validation of the whole selection happens before creating a chat or sending files.
6. Files are inspected and uploaded one at a time into the same conversation. The queue
   shows waiting, inspecting/uploading, saved, failed or unconfirmed items. It stops at
   the first failure and keeps completed uploads. The URL records the created chat as
   soon as the upload destination is known, including during a retry.
7. Fix the reported dependency or file problem, then use **Retry remaining PDFs**. No
   agent runs on upload. After a page reload, select the same files again; saved request
   identities recover receipts without duplicating already successful uploads.

The four supplied procurement PDFs can now be selected together from their
`PDFs_to_upload` folder. Keep their guide and expected answers outside the uploads.

## Docker failures and old cached errors

The original runtime attempted container creation before proving Docker was available.
Its cleanup failure could replace the original startup failure with **PDF container
cleanup could not be confirmed**. Upload receipts also preserve failures, so starting
Docker alone does not change the result of an already failed request identity.

Before creating a new PDF container, the runtime now checks the selected local Docker
endpoint, Linux engine, seccomp availability and configured immutable PDF image. It
does not install Docker, pull an image or change configuration. A failure at this stage
reports the dependency and explicitly says no PDF container was created. Confirmed
preflight upload failures allow a new request identity on the next explicit retry.

For an old **cleanup_unresolved** upload:

1. Start the same Docker Desktop installation and context used by that upload.
2. Reselect the files if the old page was reloaded. The failed receipt remains visible.
3. Choose **Check Docker and retry remaining PDFs**.
4. If asked, confirm the earlier upload used this same Docker installation and context.
   Older failures did not save their endpoint; this confirmation fills that specific
   evidence gap. Do not confirm if the Docker context or installation changed.
5. Epoch checks that no `epoch.pdf=true` containers remain, including stopped ones. If
   any remain, it stops with an instruction to inspect them in Docker Desktop. This
   check never removes containers. Newer receipts must match their recorded endpoint.
6. After successful reconciliation, a new upload request is sent. The old failure and
   a separate recovery audit event remain stored. Unknown requests with no completed
   failure receipt are not eligible for this recovery.

Legacy recovery relies on the user's same-engine confirmation plus checks of the
current local engine; it is not independent proof of an unrecorded historical endpoint.
There is no automatic retry, cleanup bypass, database reset or deletion of old receipts.

If the configured PDF image is missing, run the existing setup only when requested by
that error, with Docker ready:

```powershell
uv run --frozen python scripts/setup_pdf_runtime.py
```

Setup defaults to the existing `backend/data`; pass its `--data-dir` option only if the
backend already uses a different directory. Do not change the backend data directory to
work around an upload error. Existing `EPOCH_PDF_IMAGE_ID` overrides remain in effect.

## API and manual inspection

The upload API is unchanged: one PDF body per
`POST /api/chats/{chat_id}/assets?name=...&client_request_id=...`.
Batching is performed in the frontend. Successful responses must confirm the asset's
chat and SHA-256 before the queue advances. An interrupted acknowledgement reuses the
same identity. A preflight failure may include these fields inside `error`:

```json
{"retryable": true, "retry_mode": "new_request", "stage": "preflight"}
```

Explicit recovery uses `POST /api/chats/{chat_id}/assets/uploads/{request_id}/reconcile`,
with optional `{"confirm_same_engine": true}` for old receipts. The response must contain
matching `chat_id` and `request_id`, `safe_to_retry: true`, `retry_mode: "new_request"`,
`checked_at` and `recovery_id`. Each call rechecks current state; a past safe verdict is
not reused. The backend requires idle execution, preserves upload digests/failures, and
records `pdf.upload_retry_checked` evidence. Errors have no safe-retry acknowledgement.

For manual verification, select all four procurement PDFs and confirm four saved assets
in one conversation. Reload and reselect them; confirm no duplicate assets. Check an
invalid selection before upload, partial failure/retry, Docker unavailability while idle,
old cleanup recovery, retained containers blocking recovery, and a changed Docker
endpoint being refused. Check that navigation does not redirect uploads to another chat.
Verify normal single-file uploads, Northstar seeding and chat still work.

No new packages, credentials, environment variables or database migration are required.
App-file settings still require `--env-file .env`; existing process-only credentials
remain process-only. Preserve the normal data directory. Runtime acceptance is pending.
