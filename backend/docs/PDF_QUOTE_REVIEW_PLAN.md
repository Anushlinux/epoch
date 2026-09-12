# PDF quote matching and source review — September 12, 2026

Observed: the saved investigation identified the correct source/replacement, but its
quote inserted spaces at PDF extraction joins (`stockallocation`, `date ofissue`). The
exact-whitespace validator rejected the action, so Review/Apply was absent.

1. Match PDF layout whitespace only, with unchanged case, punctuation and non-space
   character sequence. Require a unique contiguous passage for this fallback and
   reject synthetic omission markers. Preserve actual source quotes and offsets.
2. Revalidate the saved proposal for display using its saved evidence and the current
   source catalog. Keep the stored answer and original validation outcome unchanged.
   Revalidation calls no model and changes no policy.
3. Show supported proposals with Review affected sources, then the existing explicit
   Apply filter. Source/hash/protection/revision checks and retained replacements stay.
4. Document restart/refresh and manual checks. No new settings or dependency.

Only read-only diagnosis, static review and diff formatting. Tests, model calls,
browser acceptance, SDK probes and Docker execution remain skipped by user request.

## Handoff

The quote matcher first accepts exact text or collapsed extraction whitespace. For
PDF-only layout fallback, it requires at least 24 non-whitespace characters and exactly
one match within a supplied source passage. It preserves case, punctuation and numeric
digit grouping; no fuzzy spelling or paraphrase matching is performed. Synthetic
omission boundaries cannot be crossed. Review contains the exact recorded source slice,
model-proposed quote, match method and character offsets into the saved evidence text.
Offsets describe the saved text, not coordinates on the rendered PDF.

Workspace/record reads expose a derived `source_validation` object with validator
version, proposals, warnings and current source-snapshot hash. Original `answer`,
`source_proposals` and `proposal_warnings` fields remain untouched in storage. The UI
uses the current validation view. Review creates the existing immutable approval
candidate, and Apply still requires explicit user action and an unchanged snapshot.
This revalidation does not rerun extraction, Hermes, Ollama or the business task.

Required: restart the backend from `backend` and hard-refresh the existing trace page:

```powershell
uv run --frozen epoch-backend --env-file .env serve
```

Then press **Ctrl+Shift+R**. Keep the same `.env`, data directory, PDFs and chat. No
new settings or migration. Existing app-file settings and process-only credentials
are unchanged. A saved v5 action with only this spacing mismatch can reach **Review
affected sources → Apply filter** without Investigate again. Older results that contain
no document-specific action still require a new investigation.

## Manual checks not executed

1. Reopen the reported saved analysis. Expect its Sahyadri v1 exclusion/v2 replacement
   and Review affected sources control. Expand Why this source: actual source text
   should include the recorded word joins and the PDF spacing note.
2. Review must show one source excluded, three retained, without activating anything.
   Apply should persist the existing reviewed filter only after explicit approval.
3. Confirm repeated page refreshes start no model request and do not rewrite the saved
   analysis. Its original rejection remains visible in stored history/API fields.
4. Changed quotation words, punctuation, digits/digit grouping, multiple matching PDF
   passages, omitted text and protected/changed sources must remain blocked.
5. After applying, use a new `documents.list` call with purpose current to check actual
   retrieval. Originals/historical reads and Undo remain available.

The matching fix and UI recovery were reviewed statically only. No application or
model execution establishes success yet. Original direction bytes and its three
Markdown hard breaks remain unchanged.
