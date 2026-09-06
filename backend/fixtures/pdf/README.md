# Actual PDF acceptance evidence

[acceptance.json](acceptance.json) exports real Hermes/Luna results from the isolated
`backend/data/pdf-acceptance-02` project. It includes generated source, publication
proofs, bundle/image hashes, output metadata, restart reuse and rollback history.
The PDFs in `artifacts/` are actual generated outputs copied by their asset IDs.
They are evidence only; the initial tool registry never loads these artifacts.

The real sequence passed:

1. Hermes supplied the full retreat content, but the initial renderer produced one
   clipped page. Independent geometry checks identified text outside the page.
2. Luna generated a renderer. Component, isolation, original replay, fresh replay
   and regression checks passed. Hermes recovered with a complete two-page PDF.
3. A fresh conversation produced the different two-page festival document.
4. Hermes discovered merging was absent and recorded an ordered capability request.
5. Luna generated `pdf.merge`. It passed preservation checks for normal PDFs, maps,
   static scans, rotated pages, different sizes and duplicate inputs. Hermes made
   the four-page retreat pack. The published bundle retained the renderer repair.
6. Backend restart and an additional entirely new Python process both reused the
   saved merger in fresh chats, making the three-page event pack in another order.
7. An isolated copy of the acceptance project's version history rolled back first
   to the renderer repair (merging absent, pagination still correct), then to the
   original renderer (clipping reproduced). The working project remained published.

The first acceptance project remains under `backend/data/pdf-acceptance-01`. Its
renderer succeeded, but two merge metadata proposals failed validation and exhausted
that failure's limit. A fresh project was then used. The second project retained an
HTTP 400 attempt: strict provider schemas rejected quoted JSON inside a string enum.
The final implementation generates schema metadata as a constrained structured
object. Two bounded metadata-only diagnostics are preserved beside the second
project's full report. No failed attempt was overwritten or passed by fallback.

Complete local records also retain captured tool inputs, scoped assets, call events,
protected verifier source snapshots, real executor responses and source diffs. Every
main output page was rendered and visually inspected. The source-brief coverage
audit confirms the created documents included all required brief content. Checks
prove preservation and readable pagination, not general editorial or design quality.

Use [setup and fresh-project commands](../../docs/PDF_WORKSHOP.md) to reproduce this
with the configured providers. Future model runs can fail and remain failed evidence.
