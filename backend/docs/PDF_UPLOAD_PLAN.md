# PDF upload usability and Docker recovery

Assigned September 12, 2026: support selecting several PDFs and fix the misleading
container-cleanup error encountered during upload when Docker may be stopped.

- Keep the existing per-file upload API, byte limits, exact request identities and
  conversation scope. Select multiple files, validate the selection, upload serially
  into one conversation, show per-file progress and stop on an unresolved failure.
- Retry remaining files only on user action; completed uploads keep their receipts.
  Preserve unknown outcomes. Rotate failed request identities only with an explicit
  backend no-effect hint or a successful scoped cleanup reconciliation.
- Check the pinned local Linux Docker engine and existing PDF image before container
  creation. Preserve isolation and cleanup checks. Reconcile old cleanup failures
  without removing containers or overwriting historical failure receipts; require
  confirmation when an old record omitted the original Docker endpoint.
- Update setup, status and manual retry instructions. Keep existing credentials,
  databases, models, generated procurement PDFs and original direction unchanged.
- Static source review and diff formatting only. No tests, syntax/lint checks,
  Docker commands/probes, servers, browser acceptance or model calls during delivery.
