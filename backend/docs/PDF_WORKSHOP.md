# Local PDF workshop

**September 12 upload update:** **Upload PDFs** accepts up to 20 files per selection,
10 MiB each, with per-file progress and explicit recovery. Start Docker Desktop's local
Linux engine before uploading. See [Docker recovery and manual checks](PDF_UPLOADS.md)
for the previously ambiguous cleanup error. Implemented but unverified; no new settings.

The PDF workshop uses real PDFs and the existing Hermes/Luna connection. The initial
renderer draws past the bottom of its first page. There is initially no merge tool.
The PDF debugger opens directly on **Fix PDF tool** or **Create merge tool**, using
the selected conversation's saved evidence. No context entry or separate investigation
step is required. Clicking the action authorizes diagnosis, generated code, isolated
verification, publication and Hermes continuation. Opening Debugger makes no model call.
The separate investigation API remains read-only; standard chat retains its investigation form.

## Setup

From the repository root, after the existing backend dependency setup:

```sh
backend/.venv/bin/python backend/scripts/setup_pdf_runtime.py
backend/.venv/bin/epoch-backend --env-file backend/.env serve
```

Linux Docker must be running. Setup downloads the pinned Python base and PDF
dependencies, builds the local image, and saves its immutable identity under
`backend/data/pdf/runtime.json`. Runtime never pulls an image. ReportLab, pypdf,
pdfplumber, Poppler and DejaVu fonts run inside this image, not in the backend Python
environment. Font licensing remains available inside the distribution's copyright
files. Candidate execution has no network, host mounts, Docker socket or credentials.

**Required:** build the PDF image and restart the backend. **Optional:**
`EPOCH_PDF_IMAGE_ID` in the explicitly loaded app `.env` file or process environment
overrides the recorded image identity. Existing model credentials and
`EPOCH_REPAIR_IMAGE` remain unchanged. Existing process-only model settings remain
process-only. For a custom data directory, pass it to setup with `--data-dir` as well.
No database reset or manual migration is needed. Startup adds PDF storage separately.

The frontend defaults to document tools for new chats. **Try Northstar example**
adds the retreat files and fills the message draft; press Send to start Hermes.
Other examples and options are under the composer's plus control. In a saved chat,
expand **Files** to upload PDFs or view all previous outputs. File selection,
preview and opening Debugger make no model calls.
The sample prompt asks Hermes to create the document from the supplied brief. Preview
images are rendered from the saved PDF bytes. Failed outputs remain downloadable.
Files are scoped to their conversation; published tools are shared within a project.

Hermes reports its actions, resulting files and observed check failures. It does not
diagnose causes, suggest code fixes or prescribe next steps; those belong to Debugger.
This PDF-only response instruction is supplied through Hermes's existing system-message
parameter and stays identical for original execution, verification and recovery.
Standard chat and release execution do not receive it. No new setting is required.
After an instruction/bridge update, run the task again to capture a current baseline
before asking Debugger to repair it; historical messages and evidence remain unchanged.

To create a fresh project and add source files without making model calls, while the
backend is running:

```sh
backend/.venv/bin/python backend/scripts/create_pdf_demo.py
```

This prints a new conversation URL and a retry identity. It preserves every prior
project. Use `--pack festival` for the other source pack.

Uploads are limited to 10 MiB. Merges accept two to five inputs, up to 20 MiB and
100 pages combined. Encrypted, signed, interactive or malformed PDFs are rejected.
Static scans can be merged without OCR. Identical retries use saved receipts;
interrupted operations require an explicit new action. Publication and recovery have
separate recorded outcomes. Rollback is available only when the environment is idle.

## Acceptance and evidence

```sh
backend/.venv/bin/pytest backend/tests/test_pdf_workshop.py -q
EPOCH_TEST_DOCKER=1 backend/.venv/bin/pytest backend/tests/test_pdf_workshop.py -q
backend/.venv/bin/python backend/scripts/verify_pdf_workshop.py --live --data-dir backend/data/pdf-demo-NEW
```

The last command creates a fresh demonstration environment with its own project and
stores; choose a new directory each time. It never deletes prior evidence. `--resume`
continues the same evidence record without resetting candidate attempts. `--stage`
allows bounded checkpoints. `--live` makes real configured provider calls.

After a successful run, this separate command starts a new Python process and
proves another fresh chat can use the persisted merger with different ordered inputs:

```sh
backend/.venv/bin/python backend/scripts/verify_pdf_workshop.py --live --data-dir backend/data/pdf-demo-NEW --resume --stage reuse --fresh-reuse
```

Each explicit action has at most two candidates for its evidence-backed failure,
60 model requests and 1,800 seconds. Publication requires isolation, component,
original-task, fresh-task and regression proofs. Source, bundle, container image and
protected verifier hashes bind these proofs. Fresh conversations receive ordinary
discovery with no debugger history. Generation checks preserve the captured content;
fixture checks separately assess source-brief coverage.

See the repository [status](../../docs/status.md) and [retained live acceptance
evidence](../fixtures/pdf/README.md) for actual results and limitations.
Implementation or unit tests are not a substitute for live acceptance.

## Retired CSV environment

CSV chats are filtered before pagination. Historical URLs and CSV action endpoints
return a retired-environment response; CSV cannot be selected or executed. Existing
databases, source fixtures and evidence remain on disk. Old browser pending requests
are archived locally and never translated into PDF requests. Historical CSV execution
tests are preserved in `backend/fixtures/csv/legacy_*_tests.py` and
`frontend/evidence/retired-csv/`; they are no longer active product tests.
