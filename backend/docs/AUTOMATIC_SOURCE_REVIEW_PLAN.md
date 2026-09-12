# Evidence-based source suggestions — September 12, 2026

The earlier investigation suggested a general rule but could not preview an exclusion
without user-entered source labels. This change lets an investigation propose exact
outdated or duplicate source/replacement pairs from recorded or saved document text.

1. Include a balanced set of source texts and the actual catalog/read observations
   in the local analysis. Distinguish current saved inspection from historical delivery.
2. Ask the model for specific source IDs, retained replacements, reasons and exact
   supporting quotations. Validate identities, content hashes, citations and quotes.
3. Show validated suggestions directly. Review and apply the selected pairs without
   requiring version-label entry. Unsupported suggestions remain visible as limitations.
4. Persist approved exclusions by content hash within the existing project/environment.
   Retain original files, traces, historical/explicit reads, protected sources and Undo.
   New or changed content requires fresh evidence and approval.
5. Keep earlier analyses and rule policies readable. No silent retry, model change,
   background model call, automatic activation, metadata rewriting or task-success claim.

No new dependency or environment setting. Existing local Ollama configuration is reused.
Static review and diff formatting only; tests, servers, models, SDK probes, Docker and
browser checks remain unexecuted at the user's request.

## Implemented flow

Chat with your own PDFs → open the message's trace → describe the suspected problem
→ inspect the suggested source and replacement → Review affected sources → Apply filter.

The model proposes the source IDs and evidence; the host validates the actual catalog,
content hashes, observed exposure, cited quotes and source protections. Approval stores
the reviewed source/replacement relationship, without adding inferred authority labels.
Later `documents.list` calls with `purpose=current` use the filter. Originals and
explicit/historical access stay available; Undo restores the previous active policy.
The policy applies within the same project and Documents environment. Matching uploads
can reuse it by content hash; missing/changed replacements prevent the exclusion.

The specific action types are superseded documents and byte-identical duplicates.
This does not implement arbitrary paragraph removal or guarantee the model will
diagnose every problem correctly. Quotes establish the cited text exists; they do not
independently prove supersession or that noise caused an incorrect answer. Required
unique content must remain. The user reviews the evidence before approval.

## Required setup

Stop and restart the normal backend from its existing terminal:

```powershell
cd C:\Users\Rajdeep\Desktop\Syndicate\epoch\backend
uv run --frozen epoch-backend --env-file .env serve
```

Keep the frontend running, then press **Ctrl+Shift+R** in the browser. If it is stopped:

```powershell
cd C:\Users\Rajdeep\Desktop\Syndicate\epoch
npm run dev --prefix frontend
```

Keep existing `.env` settings and the same data directory. No dependency sync, model
download, new variable or manual database migration is required. Existing Ollama
settings remain app-file settings; Hermes credentials/path settings and external
collector tokens remain process-only. No credentials are changed by this delivery.

## Manual acceptance for the existing procurement chat

These steps have not been executed by the developer.

1. Open the existing procurement chat's trace. Use **Investigate again** on the old
   answer, or submit: "Identify any outdated or duplicate documents supplied for this
   current purchase. Show what should be excluded, the retained replacement and the
   supporting source passages. Do not claim the final recommendation was wrong."
   Saved PDFs can be reused; uploading again or rerunning the purchase task is unnecessary
   to obtain a new investigation. Old analyses remain unchanged in history.
2. Inspect the proposed change. For the supplied Kaveri fixture, a supported recommendation
   would exclude `04_Sahyadri_Previous_Quotation_v1.pdf` while retaining
   `02_Sahyadri_Current_Quotation_v2.pdf`, citing its supersession statement. The purchase
   brief and Malhar quotation must remain. This is an expected review result, not an
   observed model result. If no supported suggestion appears, inspect its evidence notice;
   do not interpret a no-op review as successful cleanup.
3. Press **Review affected sources**. Confirm one old source is excluded and three
   sources remain. Review must not activate the filter. Then press **Apply filter**.
4. In chat, request: "Call documents.list with purpose current and show the filenames
   and source IDs returned. Do not create or modify anything." Inspect **Delivered
   context** under **Manage sources and history**. Confirm the old quotation is absent,
   the replacement remains, and the recorded selection names the approved relationship.
5. Request `purpose=historical`, then explicitly read the old source. Its original text
   must remain accessible. **Undo filter**, then repeat current listing: all four return
   if there was no earlier active filter. Existing messages remain unchanged throughout.

For a clean business comparison after Apply, use a new Documents chat in the same
project with the same PDFs and repeat the purchase request. This avoids old content
already saved in the original conversation. The recommendation may still be Malhar:
the demonstrated improvement is excluding unnecessary context, not manufacturing an
incorrect baseline or claiming model reasoning was observed.

## Additional unexecuted checks

- A changed source/replacement, missing replacement, protected source, conflicting
  authority, unsupported quote/citation or replacement chain must not be excluded.
- Source changes between analysis/review or review/Apply require a fresh review or
  investigation. Exact retries return the original receipt; altered payloads conflict.
- Different projects/environments stay unaffected. Matching later uploads in the same
  scope may reuse the approved relationship only when the retained replacement exists.
- Tool-defect/no-issue/insufficient-evidence results cannot propose context filters.
- More than 16 documents or long/excerpted text must disclose evidence limits; missing
  text must not be described as proof that Hermes did not read a document.

See [API bodies, CLI and preserved trial route](NOISE_WORKFLOW.md#http-and-cli).
