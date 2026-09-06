# PDF workshop UI review

Reviewed on September 7, 2026. **Ship for the scoped UI presentation.** This is an
ordinary extension of the existing chat and debugger interface. The existing
[design guidance](../DESIGN.md) remains unchanged. This record does not declare
backend or live-model acceptance complete.

## Extension conventions

The workshop keeps the charcoal surfaces, restrained system typography, quiet
outline controls and separate Chat/Debugger navigation. Files occupy a flat list
with dividers rather than a new card system. The workshop content is bounded to
780px on desktop. File names wrap, upload controls wrap, and file actions occupy
their own row at narrow widths. The actual PDF page appears on a white document
surface, scaled to the available width without changing its aspect ratio.

File rows distinguish source briefs from PDFs, show page counts, and retain both
failed and corrected outputs. Content-check results use explicit text. Failed
checks expose a “What is missing?” disclosure. Tool versions, candidate source
diffs, proof results and rejected attempts remain available in expandable details.
These conventions are implemented in [chat-environment.mjs](../src/chat-environment.mjs),
[chat-repair.mjs](../src/chat-repair.mjs) and [chat.css](../src/chat.css).

## Controls and scope

- The initial environment defaults to PDF workshop. “New chat” carries the loaded
  conversation's project and environment forward without copying its files, as
  implemented in [chat-ui.mjs](../src/chat-ui.mjs). The environment picker also
  offers Standard tools. “Add retreat files”, “Add festival files” and “Upload PDF” are explicit
  file actions; the upload control states a 10 MB per-file limit.
- Files belong to the current conversation. Published tools are shared within
  that conversation's project. Adding files and opening Debugger do not start an
  agent run.
- “Preview” loads pages rendered from the actual saved PDF through the current
  conversation's asset endpoint. “Download”, “Close preview”, “Previous page” and
  “Next page” remain explicit controls. Navigation shows the current and total
  page counts and disables the unavailable direction at page boundaries.
- Debugger investigation is separate from “Fix PDF tool” and “Create merge tool”.
  The latter actions require recorded eligibility and an available debugger;
  unavailable actions display the backend's reason. Busy or blocked states
  disable dependent controls.
- A published tool version and Hermes recovery are separate results. Saved
  versions are inspectable, and restoring a previous version is an explicit
  action available only while idle.

## Executed browser checks

The coordinating implementation agent executed and reported the following checks
from `frontend/`. This documenter inspected the source and screenshots; it did not
rerun the tests or invoke models.

| Command | Reported result and proof boundary |
| --- | --- |
| `npm exec playwright test tests/pdf-http.browser.mjs -- --workers=1` | Final rerun: 2 passed, desktop and mobile, in 16.8s. Real local HTTP API on port 8011, models disabled, no intercepted responses. Includes the final New chat behavior check. |
| `EPOCH_PDF_REVIEW_CHAT=76cbc8e5-d257-4f7e-821a-4dd1ec8bb5f3 npm exec playwright test tests/pdf-review.browser.mjs -- --workers=1` | 2 passed, desktop and mobile, in 11.8s. API on port 8012 served saved actual `acceptance01` records with models disabled. |

The [HTTP test](../tests/pdf-http.browser.mjs) creates a conversation, adds retreat
files, loads a real rendered preview, checks invalid upload feedback, uploads a
PDF, and verifies that it survives reload. It also checks that file work created
no messages or operations, that no page errors occurred, and that the viewport
has no horizontal overflow. The final rerun also verifies that “New chat” retains
the `browser-proof` project and starts with no file list from the prior conversation.

The [saved-record review test](../tests/pdf-review.browser.mjs) opens the corrected
PDF, verifies that its image loads, clicks “Next page” and asserts “Page 2 of 2”.
It then inspects Debugger, candidate actions and expanded evidence. These checks
exercise actual HTTP and stored records; they do not repeat the live generation
that originally produced those records.

## Saved-state visual evidence

- [Desktop file list](pdf-files-top-desktop.png): the saved failed one-page retreat
  PDF remains next to the corrected two-page PDF, whose content checks passed.
  The interface separately reports that published tools are active.
- [Mobile PDF navigation](pdf-navigation-mobile.png): actual rendered document
  content, “Page 1 of 2”, disabled previous-page control and available next-page
  control remain readable in the narrow layout.
- [Mobile repair actions](pdf-actions-mobile.png): the saved merge attempts failed
  proposal metadata validation. The interface retains the failure, rejected
  candidate and “Attempt limit reached” reasons instead of implying success.

These screenshots show actual saved `acceptance01` records: renderer repair
succeeded, while merge proposal metadata attempts failed. They are historical
evidence for this UI review; any later acceptance run must be assessed separately.

## Review disposition and limits

The separate `pdf_ui_review` reviewer returned **ship for the scoped UI review**,
finding no material layout, readability or visible accessibility issue in the
reviewed desktop/mobile presentation. This documenter's inspection of the three
linked screenshots agrees with that bounded disposition.

This approves presentation of the available evidence only. It is not exhaustive
keyboard or contrast testing, live-model acceptance, proof that merge generation
works, or a backend-completion claim. Consult [current project status](../../docs/status.md)
and the [backend PDF acceptance record](../../backend/fixtures/pdf/README.md) for
those decisions, including later `acceptance02` evidence. The final New chat
behavior change did not change layout; the existing visual disposition remains
scoped to the UI.
