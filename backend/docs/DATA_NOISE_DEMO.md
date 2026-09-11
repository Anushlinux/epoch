# Try a data-noise issue in Documents

This is a manual demonstration using ordinary document uploads and retrieval. The
filter does not recognize demo filenames or inject a canned wrong answer. Duplicate
content is redundant input even if Hermes still answers correctly; do not claim it
caused a business error unless the trace shows that connection.

1. Open a Documents chat and add the Northstar example, or use an existing uploaded PDF.
2. In Files, download `hotel-brochure.pdf` (or your own short PDF), then upload the exact
   same bytes again. Do not print/export it again: that can change its content hash.
3. Submit this prompt, substituting your own document name when needed:

   > Call documents.list with purpose current. Read every listed hotel brochure using
   > documents.read. Report the source IDs, room capacity, breakfast and accessibility
   > information. Do not create or modify a PDF.

4. Open this message's View trace and investigate:

   > Was identical brochure content supplied through multiple source IDs? Identify
   > redundant context, cite the recorded evidence, and suggest exact deduplication if
   > supported. Do not claim the duplicate caused a wrong answer without evidence.

5. A supported context-noise finding can suggest **Consolidate exact duplicates**.
   Choose **Review cleanup**. Inspect the excluded and retained source records and the
   scope. If nothing is excluded, the preview explains why and Apply stays unavailable.
6. Click **Apply filter**. This is your explicit approval of the reviewed rules, not
   automated task acceptance. Future ordinary document retrievals in the displayed
   project and Documents environment use them. Existing active rules are carried forward.
7. Submit a new message asking Hermes to call `documents.list` with purpose `current`
   and read the brochure again. Inspect **Actual context delivered**: one equivalent
   brochure should be listed; its required content should remain available.
8. Ask for `documents.list` with purpose `historical`: both records should remain
   available. Use **Undo filter** and inspect a new current retrieval to confirm rollback.

For this duplicate example, keep the two copies' metadata equivalent and avoid protecting
both copies. Different authority annotations and protected sources are intentionally
preserved. The original source and duplicate should have matching SHA-256 values in the
review. Run these checks before presenting the feature as verified.

Superseded-source cleanup is a separate example: upload actual old and current versions,
assign the same version family, mark the old source superseded, and mark exactly one
current source approved. An evidence-supported current-version suggestion can then be
reviewed and applied. Unknown/conflicting authority remains visible. Topic filtering
needs declared source topics and a tool request that explicitly includes its topic.

Filtering changes catalog selection; it does not delete source files, erase traces,
rewrite earlier chat messages or block direct reads by an explicit source ID. A model
that already saw an old source may still refer to visible conversation history. Inspect
fresh retrieval decisions when assessing prevention, and use a fresh chat with matching
sources in the same project when assessing later-session behavior.

Restart the normal backend and refresh the frontend after updating. Keep the existing
`.env`, model and data directory. See [setup](NOISE_WORKFLOW.md#setup). No test/model/server
execution was performed during this delivery; these steps remain for the user to run.
