# Current implementation status

## PDF batch selection and Docker recovery - September 12, 2026

The user reported a one-file picker and **PDF container cleanup could not be confirmed**
while Docker may have been stopped. Static inspection found no `multiple` attribute,
only the first selected file being handled, and cleanup errors masking failed container
creation. Actual Docker state was not probed during this delivery.

**Implemented but unverified:** up to 20 PDFs per selection, 10 MiB each, validated
before submission; serial uploads to a fixed conversation with per-file progress;
explicit remaining-file retries; saved chat URL as soon as the destination is known;
and bounded file controls in the composer. Success acknowledgements check chat/asset
identity and content hash. Completed uploads keep their receipts; uncertain responses
reuse the original request identity.

PDF runtime preflight checks the selected local Linux engine, seccomp and immutable
image before container creation. Confirmed no-effect upload failures carry an explicit
preflight retry hint. Uncertain cleanup retains the container name, endpoint and original
failure where available. An idle-only upload reconciliation route checks absence of all
tagged PDF containers and records separate audit evidence before permitting an explicit
new request. Old records without an endpoint require user confirmation of the same Docker
setup; recorded endpoint mismatches are refused. No containers or old receipts are deleted.

Static source review and diff formatting only. No tests, syntax/lint checks, Docker
probes, servers, browser acceptance, SDK or model calls. No dependencies, credentials,
data-directory changes or migrations. Existing app-file and process-only settings,
procurement PDF artifacts, chat/repair behaviour, and original direction bytes/hard
breaks are preserved. See [setup and unexecuted manual checks](../backend/docs/PDF_UPLOADS.md).

## User-reviewed document cleanup — September 11, 2026

The user reported a working, cited tool-defect investigation and requested a genuine
data-noise example plus an Apply button. They explicitly selected application after
source review rather than requiring four trials. The screenshot demonstrates a returned
investigation result; it does not independently prove the diagnosis or noise prevention.

**Implemented but unverified:** Documents now has Review cleanup, a source-selection
table, Apply filter and Undo filter. New HTTP/CLI actions record the review, retained
replacements, new exclusions and project/environment scope. Apply rechecks the exact
source/metadata snapshot and revision, requires idle execution, invalidates the warm
worker, merges existing rules, and atomically writes policy/activation/revision records.
Exact retries return the original receipt. Empty/no-effect reviews and changed snapshots
cannot be applied. Active activation receipts remain available beyond recent-history
limits. Approvals are labeled `user_approved_filter`, not verified task acceptance.

The original four-trial policy route remains available; generated-code repair gates,
Hermes prompts/configuration, original sources/logs, historical/explicit reads and old
chat messages are unchanged. Filtering affects new current retrievals across the same
project and Documents environment; existing chat history can still contain prior noise.
No automatic task replay or model call accompanies review, apply or undo.

Only static source review and diff formatting were performed. No tests, syntax/lint
checks, servers, model/SDK calls, sample execution or browser acceptance. No new setting,
dependency, credential or migration; existing app-file and process-only settings remain.
See [setup and API](../backend/docs/NOISE_WORKFLOW.md) and the unexecuted
[duplicate-PDF walkthrough](../backend/docs/DATA_NOISE_DEMO.md). Original direction
bytes and its three Markdown hard breaks remain preserved.

## Noise outcome/action consistency — September 11, 2026

The user's latest screenshot reports `invalid_policy_proposal`: the generated outcome
was `tool_defect` but its rule list was nonempty. Implemented but unverified: complete
generation-schema alternatives now couple context-noise outcomes to supported rules
and all other outcomes to exactly an empty list. Root definitions, citation constraints
and the earlier grammar workaround remain; prompt size is bounded by keeping the flat
schema in the prompt. One request, no automatic retry or altered historical result.

Existing host validation and publication checks remain intact. Valid tool-defect
answers display cited findings plus a link to the conversation's existing Debugger;
the link is read-only navigation and does not start repair. Other non-policy outcomes
display appropriate evidence-gap/no-issue notices. Static source review and diff
formatting only; no tests, syntax checks, servers, browser checks or model calls.
No new environment setting, dependency or migration. See [manual retry](../backend/docs/NOISE_WORKFLOW.md#if-the-local-investigation-fails).

## Local answer parsing and diagnostics — September 11, 2026

The user's next screenshot showed `invalid_model_answer`. Read-only inspection of the
two latest analysis records found no saved response or validation detail. Their matching
Ollama log entries returned HTTP 200 with generation activity, so the prior grammar
rejection was cleared for those requests; successful answer validation is still unproven.
The precise old validation failures cannot be reconstructed from the retained evidence.

Implemented but unverified: shared completion/JSON/Pydantic validation diagnostics,
single JSON-code-fence handling, snapshot-specific citation enums and existing host
citation checks, explicit invalid-policy-proposal errors, and Failure details in both
local investigation interfaces. New failures retain structural metadata and failing
field/type information, without raw rejected text or thinking. No silent answer repair,
citation remapping, weakened acceptance, automatic retry or model/configuration change.
No migration or dependency changes. Only read-only log/SQLite/source inspection and
diff formatting; no tests, syntax checks, servers, browser acceptance or model calls.
See [manual retry](../backend/docs/NOISE_WORKFLOW.md#if-the-local-investigation-fails).

## Ollama bounded-string grammar fix — September 11, 2026

The user's retry supplied HTTP 400 with a sampler grammar parse error. The now-available
desktop server log contains the repetition-complexity rejection and `char{1,2000}` rules
generated from noise-answer string limits. This identifies the request's grammar failure;
it is not evidence of PDF content noise or a model-memory shortage.

Implemented but unverified: noise analysis and trace questions now pass a separate
sampling schema without string-length bounds, while providing the full schema in the
prompt and retaining unchanged Pydantic/citation/rule validation. Structural constraints,
array limits, output budgets, the existing model and publication gates are preserved.
Prompt/schema versions identify new requests. No automatic retries or provider fallback.
No environment/dependency changes or migration. Static source/log review and diff
formatting only; no tests, syntax checks, servers, browser acceptance or model calls.
See [manual retry and rationale](../backend/docs/NOISE_WORKFLOW.md#if-the-local-investigation-fails).

## Ollama rejection diagnostics — September 11, 2026

The user reported a failed local noise investigation. Static inspection confirmed that
the shared client discarded non-success response bodies and always displayed a generic
memory hint. At that point, available desktop logs did not contain the reported failed
request, so its cause was unknown. Older logs contain successful inference; they do not
validate the reported request or the current integration.

Implemented but unverified: bounded JSON provider diagnostics with status/endpoint,
distinct noise transport/timeout/answer errors, persisted diagnostic fields for noise
analysis and trace questions, and explicit retry of a failed noise investigation with a
new request identity. Failed records remain intact; no automatic inference retry, model
fallback, schema relaxation, configuration change or policy publication was added.
Only source/log review and diff formatting were performed. No tests, syntax checks,
servers, browser acceptance or model calls were run. The subsequent user retry identified
the grammar failure addressed above. See [manual troubleshooting](../backend/docs/NOISE_WORKFLOW.md#if-the-local-investigation-fails).

## Noise investigation and context policies — September 11, 2026

**Implemented but unverified.** The user assigned the proposed noise workflow.
Explicit local Ollama analysis now produces cited findings and bounded policy proposals.
The UI presents relevant evidence, retains the full trace tree, and provides source
annotations, draft previews, trial links, recorded assessments, activation and rollback.
HTTP/CLI entrypoints support the same actions. The model does not authorize publication.

The new declarative selector supports exact duplicate consolidation, explicit approved
current-version preference and requested-topic filtering. Unknown metadata, conflicting
approvals, protected sources and historical/explicit reads are preserved. No paragraph
deletion, hard-coded source IDs, automatic root-cause proof or future-success guarantee.
PDF and normal-chat runbook tool paths record the candidate sources, policy/revision,
selection and actual delivered content. Existing generated runbook repair retains its
own path; release/repair sessions without a chat policy pin remain separate.

In the original trial route, four distinct preview-bound trial traces and user-recorded
passing assessments gate activation, along with required-source retention, observed selection, actual exclusions
in original/fresh cases, unchanged snapshots and an idle executor. This is manual
acceptance evidence, not independently verified business-task correctness. Policies,
annotations, decisions and rejected/failed assessments remain in a new SQLite database
inside the existing data directory. Metadata changes deactivate the scope's policy;
policy changes close the warm worker and revisions pin subsequent operations.

No tests, syntax/lint checks, servers, SDK probes, browser acceptance or model calls
were run. Only static source review and diff formatting were performed. Existing app-file
values, model connections, original databases and direction bytes/hard breaks were
preserved. No dependency or new environment setting was added. See [setup and manual
checks](../backend/docs/NOISE_WORKFLOW.md) for unexecuted validation and scope limits.

## Conversation workers and live answers — September 10, 2026

**Implemented but unverified, at the user's request.** Normal chat retains at most
one initialized Hermes worker per local workspace. Same-chat reuse requires matching
workspace/project/environment, grants and version manifests, authoritative visible
history, source/settings/model and credential identities. The worker is discarded on
cancellation, failure, idle expiry, unavailable integrity evidence or uncertain final
persistence. Cleanup uncertainty blocks further execution. Each new chat submission
keeps its 20-request/600-second allowance; release and repair continuations retain their
existing lifetime budget and integrity behavior. Installed Hermes source is unchanged.

The installed public text callback now feeds a bounded operation-scoped SSE preview,
with snapshot reconnect, response-block resets and actual stages. The frontend replaces
provisional text with the canonical saved message. Chat reads render before independent
runtime, list and PDF metadata requests finish; stream updates touch only live text/stage,
and ordinary renders retain unchanged preview images. Polling remains the saved-result
fallback. Existing per-message local Neatlogs capture remains additive.

Optional `EPOCH_CHAT_WORKER_IDLE_SECONDS` defaults to 300; zero disables reuse. It is an
app-file setting with process precedence. Existing app-file values, data, credentials and
direction source were preserved; no dependency or manual database migration was added.
The API remains local and unauthenticated; multi-user isolation is not claimed.

Only static source review and diff formatting were performed. All tests, syntax/lint
checks, servers, SDK probes, sample/browser/model executions, reuse and isolation
acceptance, and performance measurements remain unexecuted. Original direction Markdown
hard breaks are preserved. See [setup and manual checks](../backend/docs/CHAT_LATENCY.md).

## Hermes chat to local traces — September 10, 2026

**Implemented but unverified.** The user's screenshot shows `/traces` returning
“Frontend resource not found.” Static inspection found an existing route plus a
case-sensitive filesystem prefix check that can reject canonical Windows paths.
The host now compares canonical paths using platform semantics, redirects page
trailing slashes, and uses Node watch mode. An older running route table is another
possible cause; no browser/server reproduction was attempted. Both processes need
a restart to load the integration.

Normal `ChatService.run` now observes public Hermes bridge callbacks using a private
Neatlogs client, a workflow root per message and tool children paired by callback
IDs. The SDK's local exporter writes through original OTLP collection into the
existing SQLite database; background indexing preserves the existing cursor path.
Chat span delivery is permanently `local_only`, including across cloud-setting
changes. External HTTP token authorization and existing forwarding remain intact.
Neatlogs moves to runtime dependencies at the existing locked version.

Chat operations persist trace identities, capture states and warnings. Conversation
and per-request links open filtered traces; the explorer retains context and links
back. A read-only trace-context endpoint exposes capture summaries without message
bodies. Restart marks interrupted capture incomplete. No historical runs are
fabricated. Provider internals and unmatched callbacks remain explicit evidence gaps.

No Hermes implementation, prompt, model configuration, discovery interface, repair
behavior, app-file value or database was changed. The direction document and its
original Markdown hard breaks remain unchanged. Development used static source
review and diff formatting only; dependency sync, tests, lint/syntax checks, SDK
probes, sample execution, browser acceptance and all model calls remain unexecuted.
See [setup and manual acceptance](../backend/docs/CHAT_TRACES.md).

## Combined workspace startup correction — September 10, 2026

The user clarified that new Neatlogs/Ollama features must extend existing workflows.
The normal application already registers chat, execution/debugger, incidents,
telemetry, trace reads and trace questions together. The supplied startup command
selected the separate trace-only profile, causing the user's `/api/chats` and
`/api/runtime` requests to return 404. It also set a temporary `data/trace-explorer`
override while the user's app file selected `data`. Neither observation proves
deletion of chat code or the original database.

Corrected setup guides, README entrypoints, CLI help/error hints and trace connection
instructions to use normal `epoch-backend --env-file .env serve` with the original
workspace directory. The optional standalone profile now prints a clear startup
notice. Traces inherits the tab's chat API origin and shares explicit connection
changes through the existing preference key. No chat/executor/repair behavior or
data was rewritten; the app file itself was not edited. Recovery instructions remove
only the terminal's temporary data-directory override; directories are not merged.

The user's log demonstrates standalone server startup and the three 404 responses.
Combined runtime behavior remains unverified. This correction used static source
review and diff formatting only; no test, server, browser or model execution.
The direction document and its original Markdown hard breaks remain unchanged.

## Local trace questions, feature Phase 3 — September 10, 2026

**Implemented but unverified, at the user's request.** The user assigned the next
trace-debugger feature phase and supplied an installed Ollama model:
`qwen3:4b-instruct-2507-q4_K_M`. The selected scope is questions over one trace, not
the older repair Phase 3 or the different numbering in the attached source brief.
See the [assignment plan](../backend/docs/TRACE_QA_PLAN.md) and
[setup/manual acceptance guide](../backend/docs/TRACE_QUESTIONS.md).

Added deterministic trace-scoped retrieval, bounded evidence snapshots, a local
Ollama adapter, structured answer/citation-ID validation, durable question/result
history, explicit asynchronous POST and read APIs, CLI submission/inspection, and
an Ask about this trace panel. Model calls have a configured total deadline and
one-request concurrency; repeated request IDs do not automatically regenerate.
GET requests and page refreshes do not contact Ollama. No model download, code
execution, repair, comparison, cross-run investigation or incident enhancement was
implemented. Citation IDs are validated; factual correctness remains a human check.

New optional app-file/process settings: `EPOCH_OLLAMA_BASE_URL`, `EPOCH_TRACE_MODEL`,
`EPOCH_TRACE_QUESTION_TIMEOUT_SECONDS`. Defaults match the user's installed model
and standard local Ollama port. Existing process-only `EPOCH_TELEMETRY_TOKEN` stays
the SDK ingestion credential. No new secret is needed. Startup adds the question
table/index in `telemetry.sqlite3`; reuse the existing data directory. HTTPX 0.28.1
was declared directly using its already locked version; no package was upgraded.

Development used source review and official Ollama API documentation. No test suite,
syntax/lint check, local API probe, sample execution, model call, server startup or
browser acceptance was run. The handoff supplies manual commands and expected
results for the user. Runtime, answer quality and persistence acceptance are pending.
The original direction and its three Markdown hard breaks remain unchanged.
`git diff --check` passed; new files passed the same formatting check with `--no-index`.

## Neatlogs local trace explorer, feature Phases 1–2 — September 10, 2026

**Implemented but unverified, by explicit user request.** This is a separate feature
assignment, not completion of the older backend repair phases. Branch:
`codex/neatlogs-local-debugger`. See [setup and contracts](../backend/docs/TRACE_EXPLORER.md)
and the [bounded assignment](../backend/docs/TRACE_EXPLORER_PLAN.md).

Added a local-only collector profile, normalized SQLite span/search projection,
restartable backfill, immutable-ID conflict receipts, trace list/detail APIs, CLI
inspection and `/traces` UI with filtering, hierarchy, original evidence and visible
collection/indexing gaps. The SDK example executes synthetic invoice tools without
a model or live refund. The example was authored but not executed. Existing raw
telemetry and task/repair databases are preserved.

`uv sync --frozen --cache-dir .uv-cache` completed successfully without changing the
lockfile. Changes were reviewed statically and diff formatting checked. No tests,
syntax/lint commands, SDK probes, example executions, server/browser acceptance or
model calls were run. No runtime compatibility, persistence or UI acceptance claim
is made. Full validation remains pending.

The original direction document remains byte-for-byte unchanged, including its
three existing Markdown hard breaks. `git diff --check` passed for tracked changes;
the same formatting check passed against new files using `--no-index`.

Required setup: synchronize locked dependencies and provide process-only
`EPOCH_TELEMETRY_TOKEN` to both collector and SDK. The `trace-debugger` CLI profile
requires cloud forwarding disabled. An isolated `EPOCH_DATA_DIR` is recommended;
schema additions are automatic and preserve old evidence. No new credential, Docker
or model setup is required. AI questions, similar-run search, comparison, MCP,
replay, repairs and incident enhancements require later explicit authorization.

## Inline chat activity restored — September 7, 2026

User feedback reversed the separate activity panel. Hermes now shows its working
indicator inline at the end of the transcript; Debugger uses the same unboxed row.
Chat replies remain full text. The duplicated latest-file card is removed from chat,
with all assets available under Files; scrolling follows the latest message rather
than the file controls. The compact composer, Northstar shortcut and collapsed
technical controls remain. Backend results and execution logic are unchanged.
Verification is limited to syntax/diff checks and a read-only local browser check;
no model runs or full test suites were requested for this refinement.

## Simplified chat and debugger — September 7, 2026

The chat composer now uses a compact options control. One Northstar example button
adds the bundled files and fills the draft without starting a model call. Source
files/uploads and tool versions are collapsed; the latest generated result retains
visible success/failure, preview and download controls. Debugger puts current work
and its eligible action first, with context and historical evidence underneath.
Activity uses recorded operation progress and scoped tool events, never fabricated
thoughts. Agent execution, repair gates and request identity handling are unchanged.

At the user's request, verification was limited to JavaScript syntax, diff checks
and a single read-only desktop/mobile visual pass (no browser errors or horizontal
overflow). No full test suite or new live model run was performed for this UI update.

## Direct PDF debugger action — September 7, 2026

The PDF debugger now places its eligible repair/creation action first and removes
the optional question form and separate investigation button. It uses the existing
saved conversation, captured tool input and trusted findings; no backend repair logic
changed. Requirements remain expandable, prior evidence is preserved, and running
operations retain Stop. Debugger no longer scrolls to the bottom when messages load.
Standard-chat investigation and the read-only API remain available. Frontend unit
checks passed **74 tests**; real HTTP desktop/mobile checks verify that the action is
visible without a context form or any model-triggering POST request.

## PDF executor response boundary — September 7, 2026

Hermes now receives a fixed PDF-only system instruction to report actions, output
files and observed failures, without diagnosing causes or suggesting repairs or
next steps. Debugger remains responsible for that work. Original execution,
verification and recovery use the same instruction through the existing Hermes
system-message parameter; task text, tool checks and historical evidence are unchanged.
No configuration or credential change is required. Re-run a task after this bridge
update before repairing it so its executor baseline reflects the current instructions.

Focused checks: **53 passed, 3 Docker-only tests skipped**, including PDF continuation
and probe instructions and unchanged standard-chat behavior. A real Hermes baseline
run in `backend/data/pdf-response-acceptance-01` produced the one-page clipped PDF,
reported missing content and 2,436 out-of-bounds characters, linked the actual file,
and gave no repair recommendation. Its prompt invariants passed. This follow-up
verified the failure response, not a new full repair/merge acceptance sequence.

## PDF workshop — September 7, 2026

Active CSV routing is retired. New chat defaults to the PDF workshop; standard chat
and release evaluation remain available. Historical CSV records, fixtures and
evidence are retained. The CSV sections below describe historical results, not the
currently selectable environment. Work is on `testing`, preserving the dirty checkout
and the original direction document unchanged.

Implemented: conversation-scoped immutable PDF storage, bounded uploads, source
packs, actual page previews and downloads, an intentionally defective ReportLab
renderer, generated renderer repair, and constrained generation/registration of
`pdf.merge`. Investigation stays read-only. Explicit actions gate code generation,
five verification stages, publication and separately recorded Hermes recovery.
Published bundles are project-scoped and retain the prior renderer when adding a
tool. Rollback uses expected-version checks and durable retry receipts.

The separate PDF image runs without network, credentials, host mounts or a Docker
socket; non-root/read-only filesystem, 1 GiB memory, one CPU, 60-second invocation,
bounded temporary storage and 25 MiB output limits are enforced by the host. The
immutable image and actual installed dependency/worker versions are recorded by
setup. Existing release configuration and model credentials are unchanged.

Demonstrated validation:

- Focused backend tests: **47 passed, 3 opt-in Docker tests skipped**.
- Explicit real Docker PDF tests: **13 passed**, including baseline clipping,
  short controls, invalid/encrypted/interactive/signed files, timeout, cancellation,
  isolation and asset integrity.
- Full backend run: **337 passed, 12 skipped,
  1 failed**. The failure is the unchanged release test
  `test_updates_cannot_override_scope_links_identity_or_criteria_through_registry`:
  existing code returns `access_denied` where its older test expects
  `invalid_arguments`. Its registry/service/test files were not changed by this work.
- Frontend unit suite: **74 passed**. Real HTTP desktop/mobile file tests: **2 passed**;
  loaded live-evidence/page-navigation captures: **2 passed**. Browser tests disable
  models explicitly. [Scoped UI review](../frontend/evidence/PDF_UI_REVIEW.md) approved
  the presentation; this is not backend acceptance.
- Acceptance project `backend/data/pdf-acceptance-01` proved real Hermes clipping,
  a real Luna renderer repair, real Hermes recovery and fresh-chat reuse. Both
  corrected documents contain two readable pages. Its merge metadata attempts were
  rejected and exhausted; no merger was published there. All attempts remain saved.
- The complete required sequence passed in `backend/data/pdf-acceptance-02`:
  actual Hermes clipping, Luna-generated renderer repair, Hermes recovery, a fresh
  two-page festival document, missing-capability discovery, a Luna-generated merger,
  and a four-page retreat pack. The merger retained the repaired renderer.
- A backend restart and an additional entirely new Python process each reused the
  published merger in a fresh chat, producing a three-page event pack in a different
  order. Two rollback steps in an isolated copy removed merging while retaining the
  renderer repair, then restored the original clipping defect. Source-brief coverage
  passed, and every main output page was rendered and visually inspected.
- Failed attempts remain evidence. A provider rejected quoted JSON in a strict
  string-enum schema; generating constrained structured metadata resolved it without
  a fallback tool or reset of the attempt counter. See the [actual acceptance
  record and PDFs](../backend/fixtures/pdf/README.md) for generated source, gate
  results, hashes, restart and rollback evidence.

The normal local backend was restarted with its same `.env` configuration and
preserved databases. See [PDF setup, migration and commands](../backend/docs/PDF_WORKSHOP.md).
Required setup is the local PDF image plus backend restart. `EPOCH_PDF_IMAGE_ID` is
optional in the explicitly loaded app file or process environment; no new credential
is needed. `create_pdf_demo.py` creates a fresh project without any model calls or
deletion. No push, merge or video was performed.

## Explicit CSV repair control — September 7, 2026

The reported frontend showed updated repair copy while the running Python server
still exposed no CSV repair routes. Its saved investigation explicitly came from
the earlier diagnosis-only implementation. The idle local backend was gracefully
restarted with its existing `.env` command; all **4** conversations and runtime
enablement settings were retained. The real connected conversation now reports
repair support and eligibility, and its **Verify and apply fix** button was
confirmed enabled in Helium. No new model repair was executed on that conversation
during this UI follow-up; the previous live repair proof remains below.

Investigation and execution are now separate actions. `/debugger` saves analysis
without applying a candidate; the new `/csv-repair` route starts the bounded
verification/publication/recovery loop. Operations retain `kind: debugger` and
add `action: repair`. Lost acknowledgements retain the exact endpoint and request
identity, including across browser reloads. The server enforces eligibility and
rejects conflicting IDs or unsupported repair scope. Existing operation records
load without manual migration.

The repair panel shows current activity even when diagnosis text is already
available, proposed mapping, verification results, publication and recovery
separately. Older servers lacking `repair_capability` show an explicit restart
message and disabled repair button. Host eligibility reasons explain other blocked
states. Historical diagnoses remain unchanged.

Checks: **74 backend tests passed** across `test_csv_repair.py`, `test_csv_chat.py`,
`test_chat.py`, `test_csv_sandbox.py` and `test_api.py`; **77 frontend state tests
passed**; **12 desktop/mobile chat browser tests passed**. Model calls in these
tests are explicit doubles and browser HTTP is mocked. Desktop/mobile action
screenshots were inspected; the Impeccable detector reported no findings. The
real local backend route, saved-chat continuity and enabled browser control were
also inspected. No new settings, credentials or dependencies were introduced.

The interaction described below is historical: automatic repair within
Investigate is superseded by the separate execution control above.

## CSV verified repair follow-up — September 6, 2026

The [repair assignment](CSV_REPAIR_PLAN.md) extends explicit CSV investigation
into a bounded repair loop. Luna may propose outgoing field names based on an
observed sample `missing_email` failure. Host code interprets that mapping; there
is no generated-code execution, healthy-control switch, source rewrite, or
candidate access to criteria. Semantically identical CSV quoting/line-ending
retries are eligible; different customer data and unsupported failures are not.

The host stages each candidate separately, checks original/fresh mappings,
invalid-input atomicity, deduplication and the healthy control, then has Hermes
verify original and fresh tasks against protected state expectations. Recorded
executor implementation, settings, model configuration, static prompt and discovery
hashes must match the original run. Only the verified artifact is published per
project. A separately recorded continuation lets Hermes retry; rejected receipts
remain immutable. Repair publication and live recovery are distinct outcomes.

Published/rejected artifacts and evidence persist in `csv-repairs/`; new broken
CSV chats load the active version through normal discovery. Existing broken chats
select it on their next send. Healthy controls and unrelated projects remain
independent. The host rollback endpoint requires an idle controller and the exact
expected active version; it preserves prior versions, customers and receipts.
See [setup and limits](../backend/fixtures/csv/README.md).

Validation completed:

- From `backend/`, `.venv/bin/python -m pytest tests/test_csv_repair.py
  tests/test_csv_sandbox.py tests/test_csv_chat.py tests/test_chat.py
  tests/test_mcp_server.py tests/test_api.py -q`: **76 passed**, two upstream
  deprecation warnings. Model calls are explicit doubles in these tests. The
  formatting-retry correction subsequently passed all **10 repair tests**.
- `npm test --prefix frontend`: **75 passed**.
- From `frontend/`, `npx playwright test tests/chat.browser.mjs`: **10 passed**
  on desktop/mobile after allowing Chromium outside the macOS sandbox. Browser
  HTTP is mocked; these checks do not prove provider behavior.
- Focused Ruff lint, JavaScript syntax and `git diff --check` passed. All **82**
  local links in the edited guides resolve. The direction file matches its
  original SHA-256; its three original Markdown hard breaks remain untouched.
  AO preview is unavailable in this terminal; no dependency was added.

Actual live acceptance passed with `.venv/bin/python scripts/verify_csv_repair.py
--live --data-dir data/csv-repair-live-20260906-c` (from `backend/`, with network
access). [Retained evidence](../backend/fixtures/csv/repair-live-evidence.json)
records actual `gpt-5.6-luna` proposal generation and configured `gpt-6-astra`
Hermes execution. The initial failed import saved **0** customers. All **9**
candidate gates passed, including the original three-customer task and a fresh
two-customer CSV with quoted/non-ASCII names. Both Hermes verification runs used
**6 turns** and matched the original executor baseline. Luna used **2,866 input /
508 output tokens**. The exact mapping was published as version
`6d87af27-1bbf-4a4d-804a-128aac664583`.

Hermes recovery used **6 turns**, saved **3** customers and passed the original
checks while retaining the earlier rejected receipts. A separate new chat loaded
the persisted version, saved **3** customers and passed the same checks with
**zero debugger operations**. Full records remain in the separate ignored
acceptance directory; this did not modify the user's ordinary runtime database.
Business effects were local simulations. General-purpose repair, model training,
live customer services and a live-model browser walkthrough are not claimed.

The first restricted-network attempt could not reach the model provider. The
second real attempt exposed the raw-text eligibility bug: Hermes changed CSV
formatting while preserving customers, so repair was incorrectly skipped. Both
remain under `backend/data/csv-repair-live-20260906-{a,b}/`; neither published a
repair. The passing run uses the corrected parsed-customer comparison.

Required setup: restart the backend and refresh the frontend. Optional: run the
explicit `--live` acceptance harness in a new data directory. No new environment
variables, credentials, dependencies, Docker setup or manual migration are needed;
existing app-file and process-only settings retain their meanings. Triggering
remains explicit through Investigate. This is scoped environment adaptation,
not unrestricted self-modification or model training.

## CSV import test environment — September 6, 2026

Historical initial assignment below; its diagnosis-only limitation is superseded
by the verified repair follow-up above.

The user-assigned [CSV plan](CSV_ENVIRONMENT_PLAN.md) is implemented. New chats can
select a broken CSV adapter or a healthy control. Each uses a separate customer
SQLite database and four customer tools through the unchanged three-function MCP
facade. Release tools are absent from this environment. Existing chats default to
standard tools and retain their original state.

The broken adapter actually maps `email` to `emailAddress`. The strict simulated
service rejects the resulting request and saves zero customers. The healthy
control saves the three original sample customers. Input validation, atomic rejected
imports, case-insensitive email deduplication, exact retry receipts and conflicting
retry rejection are implemented. Mode and trusted criteria are immutable to runtime
tools. Healthy control is developer-written; no generated CSV repair is claimed.

The UI includes an explicit environment selector, a sample-task button and actual
customer/check/evidence panels in chat and debugger. Only Send starts Hermes; only
Investigate starts Luna. The host supplies immutable sample criteria and actual
verification to debugger analysis, retaining the last service failures even after
subsequent inspection calls. It does not expose the seeded mode as a diagnosis to
Luna. Recorded request payloads and required service fields provide the evidence.

Validation:

- From `backend/`, `.venv/bin/python -m pytest tests/test_csv_sandbox.py
  tests/test_csv_chat.py tests/test_chat.py tests/test_mcp_server.py tests/test_api.py
  -q` passed **66 tests**. These include real MCP subprocess calls and restart,
  default release regression, CSV isolation, API creation identity and debugger
  evidence. Hermes/Luna are replaced only in the chat orchestration tests.
- `.venv/bin/python scripts/verify_csv_environment.py --output
  fixtures/csv/local-evidence.json` reproduced **broken: 0 saved; healthy: 3 saved**
  with exact retry identities preserved. The [retained JSON](../backend/fixtures/csv/local-evidence.json)
  contains actual simulated tool effects and traces, not a prerecorded diagnosis.
- `npm test --prefix frontend` passed **75 tests**. From `frontend/`,
  `npx playwright test tests/chat.browser.mjs` passed **10 desktop/mobile tests**;
  the four CSV cases passed again after the mobile inset fix and adoption of the
  actual sandbox snapshots. Browser transport remains mocked; these are UI checks,
  not live provider acceptance.
- Ruff lint/format, JavaScript syntax, the Impeccable detector and
  `git diff --check` passed. Desktop/mobile screenshots were inspected. The preserved
  direction is unchanged, including its original Markdown hard breaks.

[Testing instructions](../backend/fixtures/csv/README.md) and the supplied
[customer CSV](../backend/fixtures/csv/customers.csv) are available. Restart the
backend and refresh the frontend; no new settings, dependencies, credentials,
Docker setup or manual migration are required. Existing app/process settings keep
working unchanged. No live model calls or new automatic repair acceptance were
performed for this assignment.


## Hermes startup and polling correction — September 6, 2026

The reported chat RuntimeError occurred during installed Hermes initialization,
before model inference. With an omitted configured base URL, Epoch passed an
explicit credential but `base_url=None`. The installed Hermes initializer requires
both values to use that credential; otherwise it attempts credential discovery in
the deliberately empty isolated home. The bridge now supplies the standard Codex
endpoint when omitted, preserves explicit URLs and records the effective endpoint.
Initialization failures now have a sanitized stage-specific diagnostic.

The chat controller also unconditionally refreshed chat list/detail/runtime every
1.5 seconds after failures. Runtime inspection checks both agent installations.
It now polls only selected chat detail while running, refreshes runtime once at
completion/failure, and stops while idle. If another operation is active, shared
availability is checked at five-second intervals. Hidden tabs pause polling;
returning to the page reads current state once. Failed active reads back off up to
30 seconds, and overlapping refreshes share or serialize requests. No write retry
or model execution is caused by polling.

Validation: **54 focused backend tests** (Hermes bridge, chat and operation budget),
Ruff, **71 frontend unit tests**, and **6 desktop/mobile chat browser tests** passed.
A probe against the actual installed Hermes passed initialization and discovered
exactly the three permitted Epoch MCP tools. It used a placeholder credential,
blocked outbound non-loopback sockets, and exited before inference. Local probe
output is retained at `/private/tmp/epoch-chat-startup-probe.txt`.
This establishes startup/discovery, not authenticated live model completion.
`git diff --check` passes. Existing failure records remain unchanged.

Restart the backend and refresh the frontend to load the fixes. No environment
settings, credentials, database migration or personal Hermes changes are needed.


## Hermes chat and manual debugger — September 6, 2026

The latest user correction replaces release intake as the default conversation.
Ordinary messages use durable `/api/chats` operations and call Hermes directly.
Opening Debugger only reads the selected conversation; **Investigate conversation**
explicitly invokes one bounded Luna analysis. Original user requests remain
verbatim requirements evidence. The debugger retains citations, observations,
hypotheses and missing information. It neither starts a release run nor replays
Hermes, changes trusted criteria or publishes repairs. Debugger findings are labeled
separately and excluded from Hermes's subsequent visible history.

Release evaluation remains a separate example at `/debugger?mode=release`, with
historical `/debugger?task=UUID` links retained. The original release evaluator and
repair controller remain limited to their supported workflows. A general
conversation investigation is not a generic trusted outcome checker or arbitrary
repair implementation. No new live-service or Phase 6/7 acceptance is claimed.

Implemented with the [assigned plan](CHAT_DEBUGGER_PLAN.md). Existing uncommitted
chat work and unrelated telemetry configuration changes were preserved. Restart
the backend and refresh the frontend to use the new routes; no new settings or
manual migration are needed. A separate `chats.sqlite3` is initialized under the
configured data directory. Existing task/run data remains intact.

Validation:

- From `backend/`, `.venv/bin/python -m pytest tests/test_chat.py
  tests/test_hermes_bridge.py tests/test_incidents.py tests/test_api.py -q` passed
  **74 tests** using local bridge doubles; Ruff checks passed. These cover isolated
  chat, explicit investigation, citations, retained requirements, request identity,
  interruption/cancellation and strict visible-history boundaries.
- `npm test --prefix frontend` passed **69 tests**, including an exact debugger
  retry after reload with an optional blank question.
- From `frontend/`, `npx playwright test tests/chat.browser.mjs
  tests/workspace.browser.mjs` passed **38 desktop/mobile tests** initially; a
  final focused rerun passed all **6 chat tests**, bringing coverage to **40 unique
  desktop/mobile tests** with the unchanged 34 fixture cases. These use intercepted
  API responses. New chat/manual-debugger screenshots were visually inspected;
  see [desktop debugger](../frontend/evidence/manual-debugger-desktop.png) and
  [mobile debugger](../frontend/evidence/manual-debugger-mobile.png).
- `npm run test:execution --prefix frontend`, filtered to desktop and
  `explicit release, named SSE`, passed the selected direct-release
  HTTP/browser case with an explicit test executor. The runner also checked
  intake request identity, error responses, CORS and restart persistence.
  Remaining historical execution/supervision/incident HTTP browser cases were
  not rerun.
- JavaScript syntax, `git diff --check` and the Impeccable mechanical detector
  passed. Documentation paths resolve and `docs/direction.md` remains byte-for-byte
  identical to HEAD, SHA-256
  `791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`.
  Its original Markdown hard breaks remain intact. AO preview is unavailable;
  no preview dependency was added.

No live Hermes/Luna calls were made for this change. The historical intake browser
suite expects the removed one-request release-chat form and was not run; the new
chat browser coverage verifies the replacement interaction.


## Neatlogs configuration fix — September 6, 2026

The backend now accepts optional `NEATLOGS_API_KEY` in an explicitly loaded `.env`
file as well as the process environment. Process values take precedence; the key
is excluded from settings serialization and representation. Telemetry consumes the
resolved key. Unknown file settings remain rejected, and cloud forwarding remains
explicitly opt-in. Existing setups need no database migration; see
[setup and restart instructions](../backend/docs/INCIDENTS_SETUP.md).

Validation from `backend/`: `.venv/bin/python -m pytest tests/test_config_cli.py
tests/test_telemetry.py -q` passed **25 tests** with two dependency deprecation
warnings. Ruff lint and format checks passed for the changed Python files. The
existing local `.env` also validated without displaying credentials. These checks
do not establish authenticated Neatlogs cloud delivery or new model execution.

**Current integration connects the frontend to Phase 7 and adds incidents plus Neatlogs.**
Focused integration checks are recorded below. Full Phase 6/7 live repair acceptance
remains pending; earlier Phase 5 results do not validate those paths. API health/runtime
still report phase 7. See [incident setup](../backend/docs/INCIDENTS_SETUP.md) and the
[Phase 6/7 handoff](../backend/docs/PHASES_6_7_HANDOFF.md).


As of September 6, 2026, **backend Phases 1–5 are implemented and verified**. The release supervisor uses OpenAI `gpt-5.6-luna` for sourced plans and corrective instructions. Existing Hermes performs the business work through local MCP simulations. Opt-in Phase 5 repairs the checklist serializer through actual Luna generation, Docker isolation, trusted verification and durable project versions.

## Implemented facts

- The [backend API/CLI](../backend/README.md) persists tasks and explicit release runs in SQLite. Intake alone stays pending. Existing direct runs remain available; `supervised: true` enables Luna planning, checkpoint checks and bounded continuations.
- Supported feedback adds checklist items or exact QA-message phrases. The host validates quoted provenance, retains all earlier requirements and invokes a fixed trusted evaluator. Unsupported/removal/subjective changes require clarification. This is a narrow release workflow, not general-purpose task verification.
- Hermes retains one actual conversation across automatic continuations. A separately submitted feedback/clarification operation starts a new conversation over the same saved sandbox. Updates preserve object IDs and links, and previous operation snapshots/results remain available.
- Every ordinary explicit operation shares at most **20 authorized model requests and 600 seconds** across the debugger and Hermes. Opt-in repair gives each isolated verification its own 20/600 limit, with a 60-request/1,800-second overall ceiling and at most two candidates; primary work retains 20 requests/600 active seconds. The parent admits each executor request before network dispatch, including summaries/retries. Continuations cannot reset the budget. A new user operation has a new budget. Cancellation, deadline and baseline failures prevent completion.
- The debugger uses structured output without tools. Trusted checks inspect saved outcomes after meaningful tool completions and pass boundaries. Plans, public activity, checks, interventions, user revisions and errors are retained; private reasoning is not exported.
- The MCP facade exposes scoped simulations, including in-place checklist/message updates. Additive trusted criteria are administered by host code and excluded from MCP discovery. The evaluator is `release-state-v3`; historical Phase 3 artifacts keep their original criteria and outcomes. The opt-in Phase 5 controller can repair the checklist serializer; generated missing-tool/context paths are now developed but untested.
- HTTP provides run/status/state/trace/SSE, feedback, clarifications and revision history. Request IDs and expected revision IDs prevent duplicate/stale submissions. Restart marks incomplete operations interrupted and keeps partial effects; there is no automatic replay.
- Locked dependencies, schemas, test doubles and real local MCP/server checks are included. Actual model evidence is recorded separately. The [frontend handoff](../backend/docs/FRONTEND_HANDOFF.md) and [supervision schemas](../backend/contracts/supervision-schemas.json) define Anushrut's integration surface.

[README](../README.md), [architecture](architecture.md), [integration checklist](integrations.md), [backend phases](../backend/PHASES.md) and [task briefs](tasks/README.md) define scope. [AGENTS.md](../AGENTS.md) remains canonical through [Claude](../CLAUDE.md) and [Copilot](../.github/copilot-instructions.md). The [direction](direction.md) remains unchanged historical product intent.

The [frontend workspace](../frontend/README.md) now accepts Phase 3 health and published task states. It connects task intake to explicit release requests, runtime availability, run history, checkpoints, trusted results, simulated state, persisted trace/SSE and asynchronous cancellation. Exact run submissions survive uncertain acknowledgements; reconnect/navigation do not replay work. The [verification record](../frontend/evidence/README.md) distinguishes actual HTTP/storage checks from the explicitly substituted test executor used in browser execution tests. This integration did not run a new Hermes/model acceptance test.

## Approved decisions

The user's Phase 4 assignment selected OpenAI `gpt-5.6-luna`, a maximum of 20 agent turns and a maximum time of 10 minutes, with a full report before push. The [Phase 4 plan](../backend/PHASE_4_PLAN.md) records the shared-budget interpretation, opt-in compatibility, additive scope and parallel ownership. Rajdeep owns backend/supervision; Anushrut owns UI. Python 3.12, uv, FastAPI/Pydantic, SQLite, MCP SDK 1.29.1, pytest and Ruff remain selected. JSON Schema validation is an explicit locked dependency.

## Requirements awaiting implementation

Missing-tool and context code awaits live acceptance. Supervision/repair UI, incident construction and Neatlogs local ingestion are integrated; authenticated cloud delivery and Workshop remain unverified/deferred respectively. Phase 5 uses restricted Linux Docker for generated Python; ordinary simulated services alone are not a secure execution boundary. The saved adapter and later-session benefit below establish narrow persistent environment repair, not general-purpose learning.

## Verified scope and remaining assumptions

Actual Hermes compatibility is specific to installed commit `7166071fcaadb36df26f6d753dda97da6b5d699e`, configured `openai-codex` / `gpt-6-astra`, and its existing medium reasoning setting. Luna is a separate debugger request through the observed existing OpenAI/Codex route. Neither Hermes source nor personal settings/credentials are changed. The official API-key debugger route is implemented and tested with doubles; no API key was available for live validation. See [Hermes setup](../backend/docs/HERMES_SETUP.md) and [debugger setup](../backend/docs/DEBUGGER_SETUP.md).

Synthetic requests, supplied tool evidence and feedback go to the configured OpenAI endpoint. Business effects stay local. The subscription route does not accept an output-token cap; request and wall-time limits apply, but no monetary spend cap is claimed. Availability checks prove credential/configuration presence only. Provider failures preserve partial state and need an explicit user retry. Other Hermes versions/accounts/providers require their own evidence.

The server has no authentication, multi-user isolation or distributed workers. Normal cancellation/process cleanup and durable restart handling are tested; abrupt backend-crash containment against real inference remains unverified. Live Jira/Notion/Slack, production deployment, remote CI and browser sign-off remain outside this handoff.

## Runtime capability inventory

| Capability | Current status | Remaining work |
| --- | --- | --- |
| Intake API/CLI, config, durable tasks and contracts | Implemented and tested | Phase 1 complete |
| Stateful simulations, permissions, discovery, invocation and trusted outcomes | Implemented; official SDK MCP round trips tested | Phase 2 complete |
| Seeded checklist, lookup and context failure scenarios | Implemented in local sandbox | Repairs in Phases 5–7 |
| Actual installed Hermes, explicit release briefs and correlated evidence | Implemented; control and defect executions recorded below | Phases 3–4 complete |
| Run status/state/trace, SSE, cancellation and restart handling | Implemented and tested; consuming UI connected | New model-backed browser acceptance remains unexecuted |
| Frontend intake, supervision/repair and incident views | Phase 7 HTTP/browser smoke with real storage/checks and explicit test actors | Full live-model and mobile workflow acceptance remains pending |
| Automatic checkpoint planning, continuations and feedback revisions | Implemented; actual-model evidence retained | Phase 4 complete |
| Debugger, isolated generated checklist repair, publication and rollback | Implemented; actual Docker/Luna/Hermes acceptance below | Phase 5 complete |
| Generated missing tools and scoped context repairs | Development delivered, untested | Phases 6–7 acceptance pending |
| Incidents and Neatlogs | Local collector, source inspection, grouping/imports, on-demand Luna and optional cloud export implemented | Actual SDK local smoke passed; live cloud/model incident acceptance pending; Workshop deferred |
| Live business-service connections and production operation | Deferred | Separate future scope |

The narrow checklist repair has saved executable and later-session evidence. No agent benchmark, broader learning result or current UI sign-off is claimed. A successful executor conversation is recorded separately from trusted task success.

## Documentation validation

The original documentation foundation used the following checks; implementation handoffs additionally verify their assigned source/runtime scope:

1. Compare `docs/direction.md` byte-for-byte with the supplied source file. Record matching SHA-256 hashes. The source used for this foundation is `/Users/bhaskarpandit/.ao/electron/terminal-drops/1788694360022-direction_1_.md`; this is provenance, not a portable dependency or setup path.
2. Resolve every relative Markdown link and fragment to an existing file and heading. Check preserved footnote references separately. This does not verify remote URLs or installed integration behavior.
3. Confirm the README leads to the canonical instructions and all planning documents. Confirm the Claude and Copilot files resolve to the same AGENTS.md and do not duplicate its policies.
4. Check that the seven ordered backend briefs each contain goal, prerequisites, owned area, exclusions, acceptance checks, evidence, and a copy-paste prompt. Check that the UI lane in the task README identifies Anushrut's ownership, dependencies, acceptance and handoff separately.
5. Inspect all changed and untracked files against the base commit: only the intended Markdown documentation and agent entry files may be added or changed. Run `git diff --check` and the corresponding staged check before committing.
6. Follow the AO preview guide and open `ao preview README.md` when working in AO. Inspect the rendered primary handoff without introducing a server, dependencies, or launch configuration.

These checks validate documentation integrity and navigation only. Update the runtime inventory only when implementation has matching execution evidence; record partial or blocked results explicitly.

### Foundation validation record

The source copy was compared byte-for-byte during this handoff. Both files have SHA-256 `791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`. Checks passed for 88 local Markdown links, two heading fragments and five footnotes across 16 Markdown files. The Claude import target and Copilot pointer resolve to the canonical AGENTS.md. All seven briefs have the required goal, prerequisites, owned area, exclusions, acceptance checks, evidence and prompt sections. The change inventory contains only the intended Markdown files, with no tracked validation scripts. The README was opened with AO preview and its rendered content inspected. No nonexistent application command is presented as runnable; future commands must be established and tested during implementation.

The full staged `git diff --check` reports three trailing-whitespace findings in the unchanged source at `docs/direction.md` lines 3–5. Those original two-space Markdown hard breaks are intentionally preserved. Strict checking of all authored files passes with `git diff --cached --check -- . ':!docs/direction.md'`. A separate `git -c core.whitespace=-blank-at-eol diff --cached --check` also passes; the override applies only to that invocation and changes no repository or global settings. This exception does not waive whitespace checking for authored documentation.

### Supervisor and ownership documentation update

Pulled the documentation foundation at `d681128` before updating the supervisor flow and Anushrut/Rajdeep assignments. Checked 91 local links including four heading fragments, all seven backend brief structures, and the shared agent entrypoints. The original direction Git blob retains SHA-256 `791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`, and its working file has no Git diff. The source's original Markdown hard breaks remain preserved. All ten changed files are Markdown and the authored diff passes `git diff --check`. AO preview is unavailable on this host; no runtime or preview dependency was added. Runtime and integration checks remain unexecuted because no application code is part of this change.

### Phase 1 validation record

Implemented on a feature branch from `e1395bc` using parallel contract, storage and integration-test agents with separate file ownership. Technical selections were recorded before coding. Validation used Python 3.12.10 and uv 0.8.15 on Windows; dependencies are pinned in `backend/uv.lock`.

Initial `uv sync` downloaded dependencies into a repository-local cache. Copied only Git-visible backend source files into a fresh temporary directory, created a new virtual environment, and ran the following commands there with that warmed cache. This verifies clean installation from source with a frozen lock; it is not a claim of installation without previously downloaded dependencies.

| Command (from `backend/`) | Observed result |
| --- | --- |
| `uv sync --frozen --offline` | Clean environment created; 26 packages installed |
| `uv run --frozen --offline epoch-backend check-config` | Valid local configuration; no database side effects |
| `uv run --frozen --offline pytest -q` | 66 passed; two dependency deprecation warnings |
| `uv run --frozen --offline ruff check .` | Passed |
| `uv run --frozen --offline ruff format --check .` | Passed |
| `uv run --frozen --offline python scripts/export_contracts.py --check` | Schema and fixture exports match their source |
| `uv run --frozen --offline python scripts/smoke_test.py` | Actual CLI server health, HTTP intake, idempotent retry and persisted task after process restart passed |

Tests include 16 storage checks, 40 API/config/CLI checks and 10 contract checks. They cover concurrent retry idempotency, conflicting request IDs, pagination, corrupted storage, schema-version refusal, field validation, CORS, sanitized errors, explicit environment files and source/evidence invariants. SQLite `user_version=1` guards the intake schema; environment-version records have contracts only, with publication/storage deferred to Phase 5.

Windows sandbox ACLs blocked pytest temporary-directory access, so the successful test and smoke executions ran with the approved local escalation. The two remaining warnings are from Starlette's HTTPX compatibility and its AnyIO portal alias; all tests pass with the locked dependencies. The workflow uses Python 3.12 on Linux and is configured to run tests, formatting, exports and the smoke script; no remote CI result is claimed here.

Documentation checks passed for 135 local links, six heading fragments, seven task brief structures and the canonical agent entrypoints. The direction Git blob still hashes to `791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`; its Windows worktree remains unchanged at SHA-256 `714c89515b81ad887935de309d5b69ec43a77ee623c13fbff6fadc56f371a9a7`, including the original Markdown hard breaks. Authored changes pass `git diff --check`. AO preview remains unavailable on this host.

Anushrut has the published HTTP/error contracts and fixture states; this does not claim a completed UI integration or personal sign-off. At the Phase 1 handoff, Phase 2 onward remained unstarted and Hermes/integration/repair checks were outside scope. The later Phase 2–3 record below supersedes that implementation inventory while preserving the historical results.

### Frontend fixture implementation

The following frontend evidence was recorded before the Phase 3 merge. It is retained as Phase 1/fixture validation, not proof of compatibility with the current backend.

The UI preserves original requests and clarifications, displays all six sourced checkpoint states, keeps task and repair outcomes separate, retains rejected candidates and partial artifacts, and records feedback as explicit revisions with previous results retained. Local tests cover evidence/identity guards, stale and duplicate events, stream gaps, uncertain submissions, retry/reconnect, forms, keyboard navigation, mobile layout and text escaping. See the [verification record](../frontend/evidence/README.md) for actual commands, outcomes, screenshots and limitations.

The [frontend-local contract proposal](../frontend/CONTRACT-PROPOSAL.md) is **PROPOSED, not agreed**. At this historical handoff, the backend published Phase 1 intake endpoints and future data contracts. The primary UI consumed those intake models directly; the future fixture proposal remained separate and unagreed. Execution, streaming, feedback and repair endpoints were unimplemented at that point. The current [backend handoff](../backend/docs/FRONTEND_HANDOFF.md) now includes Phase 3 execution and SSE; supervision, feedback and repair remain unimplemented, and the later frontend integration record below documents its Phase 3 adaptation. The fixture adapter stores data only in page memory and cannot establish durable duplicate prevention, secure repair isolation, trusted evaluation or backend compatibility.

### Frontend Phase 1 intake integration

Against the unchanged Phase 1 backend at `0a062dd`, the frontend verified actual health/create/list/detail, 201 intake, 200 identical/normalized retry, 409 conflict, 422 validation, 404 missing records, 403 disallowed origin, explicit allowed CORS and SQLite record/ID persistence across restart. Tasks stayed pending and health reported execution disabled. Temporary test data was isolated and removed; no backend source, configuration defaults or evaluator logic changed.

`npm run test:all --prefix frontend` passed 41 state tests and 30 fixture browser tests. `npm run test:integration --prefix frontend` passed HTTP checks and 12 desktop/mobile browser cases using actual API requests. Transport fault injection tests are labeled separately. Full evidence and screenshots are in the frontend verification record.

The frontend added `npm run dev --prefix frontend`, a minimal Node HTTP host at `http://127.0.0.1:5173`, already supported by backend CORS. Actual normal-page browser tests and AO intake use this origin without backend changes, a proxy, source interception or special browser permissions. The older generated-origin static-file preview remains unsuitable for API integration. No SSE, checkpoints, execution, feedback or repair endpoint was added or claimed. Actual supervised repair remains blocked on later phases.

Final fixture remediation rejects duplicate/dropped checkpoint identities and unsourced failed/needs-input snapshots, blocks disconnected request dispatch, and hides stale delivery labels after checkpoint updates without rewriting the supplied task verdict. The new state and desktop/mobile regressions pass.

### Phases 2 and 3 validation record

Implemented together at the user's request on `codex/backend-phases-2-3`, based on Phase 1 commit `0a062dd`. Three parallel agents owned sandbox/checks, registry/MCP, and Hermes integration; the primary agent owned execution persistence/API/SSE/CLI and coordinated review. Decisions were recorded before coding in the [combined plan](../backend/PHASES_2_3_PLAN.md). Anushrut's UI work and the original direction were not changed.

The installed Windows Hermes checkout is `7166071fcaadb36df26f6d753dda97da6b5d699e`. Actual inference retained `openai-codex`, `gpt-6-astra`, medium reasoning and the existing endpoint/credential. No global Hermes settings, source or personal credentials were rewritten. MCP SDK 1.29.1 is locked in the backend environment. Compatibility is demonstrated for this installation/route only.

#### Actual executor acceptance

The [portable evidence and reproduction guide](../backend/fixtures/hermes/README.md) links full saved run/state/event JSON and preserved earlier attempts. The final pair ran with the same explicit release `2.4` brief, fixed grants, v2 trusted criteria and fresh empty memory homes.

| Scenario | Run | Observed result |
| --- | --- | --- |
| Healthy control | `c9a1bcca-22ad-462a-b5a7-d185dad64ba1` | Hermes completed; one ticket, one linked checklist and one QA message; all three trusted checks pass; 69 correlated events |
| Broken checklist adapter | `aae4ba66-dbc7-43b4-993f-996554f1d0d1` | Hermes completed its conversation; one ticket remains, no checklist or QA message; ticket check passes and the two missing outcomes fail; 62 correlated events |

All 12 compared fields are present and equal across these runs: Hermes commit/source, model configuration, initial/full/static system prompts, discovery definitions, bridge source, evaluator, grants, criteria and brief. Both record unchanged Hermes source, prompt and personal settings, and no missing evidence. The actual advertised tool surface contains only the three Epoch MCP facade functions. Full prompts include the date, so this is a same-date comparison, not a promise of identical prompts on different dates.

Readback through the local HTTP API verified both saved run records, object counts and task/run correlation. SSE replay with `Last-Event-ID: 1` included each final event and closed. These readback checks invoked no model. The genuine control/failure execution satisfies Phase 3; there was no automatic continuation or repair.

Earlier attempts are preserved without rewriting outcomes: the bridge initially stopped on unexpected installed-Hermes tool-search wrappers; supported per-run settings removed them. A real control then exposed a verifier v1 false-negative for a release number followed by a sentence-ending period. Normal developer correction added token-boundary regressions and versioned the evaluator as `release-state-v2`; the old failed result remains intact. Another pair achieved expected business outcomes but had differing prompts due to temporary paths/Git context, so it was not accepted as a fixed-baseline comparison. Supported configuration stabilized the prompts, proven first by two no-inference probes and then by the final actual pair above. These are development corrections, not autonomous learning.

#### Automated and clean-source validation

Validation used Python 3.12.10 and uv 0.8.15 on Windows. The fresh-source check copied only Git-visible backend files into a temporary directory, created a new virtual environment, and used the already downloaded repository-local uv cache. It verifies frozen installation from source with a warmed cache, not a network-free first installation.

| Command (from `backend/`) | Observed result |
| --- | --- |
| `uv sync --frozen --offline` | New environment; 40 packages installed |
| `uv run --frozen --offline epoch-backend check-config` | Valid local configuration |
| `uv run --frozen --offline pytest -q` | 156 passed; two upstream dependency deprecation warnings |
| `uv run --frozen --offline ruff check .` | Passed |
| `uv run --frozen --offline ruff format --check .` | Passed |
| `uv run --frozen --offline python scripts/export_contracts.py --check` | Shared and execution schemas/fixtures match source |
| `uv run --frozen --offline python scripts/smoke_test.py` | Actual local CLI server, HTTP intake, retry and restart persistence passed; model execution disabled |

Coverage includes stateful sandbox invariants, serialization failure effects, permission-filtered discovery/invocation, invalid MCP envelopes and actual SDK stdio subprocess calls, idempotent retries, cross-run isolation, source provenance, trusted token matching, executor cancellation/timeouts, status persistence, failed admission/finalization and SSE final-event races. Review found and fixed failed admission leaving a running record without a worker; regression tests verify terminal retries or an explicit unresolved-state block. Bridge/orchestration tests use declared doubles. Actual installed model runs above establish the executor acceptance separately.

Local escalation was required for Windows temporary-directory ACLs and actual subprocess/model execution. Starlette's HTTPX compatibility and AnyIO portal alias emit the two remaining warnings; there are no test failures. The configured Linux GitHub workflow was not executed remotely during this handoff.

The fresh-copy smoke initially passed its HTTP assertions but failed cleanup because a Windows virtual-environment launcher left its server child holding the execution lease. The harness now terminates its own launched process tree before temporary-data cleanup; this is test-harness cleanup, not a claim of stronger production process isolation.

#### Boundaries and handoff

Rajdeep's Phase 2 and Phase 3 pass conditions are met. The [frontend handoff](../backend/docs/FRONTEND_HANDOFF.md) documents actual run/status/state/trace/SSE routes and separates them from future repair contracts; Anushrut's Phase 3 UI consumption/sign-off is not claimed; the existing frontend health and task-status parsers reject the current backend contract. Use the CLI/API until that separately owned integration is updated. Automatic supervision and feedback (Phase 4), generated repair and secure candidate isolation (Phase 5), tool/context repair, Neatlogs/Workshop and live business services remain unimplemented. Normal timeout/cancellation is tested; abrupt backend crash containment against a real model and stronger process isolation remain unverified.

Documentation integrity checks passed for 168 local links, five heading fragments, seven backend task brief structures and both canonical agent entrypoints across 24 Markdown files. The direction Git blob and Windows worktree retain the SHA-256 values recorded under Phase 1; there is no source diff, and its original Markdown hard breaks remain intact. The assigned change inventory contains backend work, shared handoff documentation and the backend CI workflow; runtime databases, caches and credentials are excluded. Authored `git diff --check` passes. AO preview remains unavailable on this host.

### Main-branch integration validation

Pulled main at `4bfb841d4c2a5b931d7e5238a30cd11b41d2db1c` before merging Phase 2–3 commit `e6735b4` in an isolated checkout. Shared documentation reconciles both histories; backend source remains identical to that Phase 3 commit, and the complete frontend tree remains identical to pulled main. The original workspace and its in-progress frontend changes were preserved.

Against the merged checkout, 156 backend tests passed with the same two dependency warnings. Ruff checks and formatting passed for 39 files; exported contracts matched source; the actual CLI HTTP/restart smoke passed. No new model inference was invoked; the existing genuine Hermes acceptance evidence above remains the executor proof. The committed frontend still rejects Phase 3 health and non-pending task states, so current release execution uses the CLI/API pending Anushrut's separate frontend adaptation. No Phase 3 browser integration or remote CI result is claimed.

### Phase 3 frontend connection validation

Connected the existing chat/debugger to current intake, runtime, explicit release
runs, run history, checkpoints, trusted results, simulated state, trace/SSE and
cancellation. New runs require explicit submission; unresolved acknowledgements
retain their exact identity and payload across reload. Read-only reconnect uses
persisted evidence and never replays execution. Stale task responses and unrelated
run/event identities cannot replace the selected record.

Validation passed: 50 frontend unit/state tests; 34 fixture browser tests; 14
actual Phase 3 intake browser cases; 8 execution browser cases using real HTTP,
SSE, SQLite, simulated tools and trusted checks with an explicitly substituted test
executor; and 156 backend tests. Ruff and schema-export checks passed. Exact
commands, screenshots and saved run/state/trace records are in the [frontend
verification record](../frontend/evidence/README.md#phase-3-frontendbackend-connection--september-6-2026).
No new Hermes/model execution is claimed. Production backend source and trusted
checks remain unchanged; the new Python harness lives only under backend tests.

The current host's existing port-8000 server still reports Phase 1. It was left
untouched; a current Phase 3 server runs on port 8002. That server reports Hermes
unavailable because local model configuration cannot be read safely. Browser
execution tests therefore establish frontend/API behavior with a test executor,
not provider readiness. The new UI reflects this unavailable state honestly.

The original direction retains SHA-256
`791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`, including its
original Markdown hard breaks. Authored changes pass `git diff --check`.
AO preview is unavailable on this host; no preview dependency was added.

### Phase 4 validation record

Implemented on local branch `codex/backend-phase-4` from pulled main `948ea47f1230ab16f960db3435dd0260f21cee37`, in an isolated worktree. The original checkout has an unfinished merge and frontend changes, so it was preserved. Three parallel agents owned the OpenAI transport, Hermes session/request gate, and state/criteria revisions; the primary agent integrated supervision/persistence and coordinated independent review. The [plan](../backend/PHASE_4_PLAN.md) preceded implementation. The user requested a report before push; the initial report was delivered while the handoff was unpublished. Publication was authorized in the subsequent request.

#### Actual Luna and Hermes acceptance

The [portable evidence guide](../backend/fixtures/supervision/README.md) links full run/state/event JSON, failed attempts, initial transport probes and HTTP readback. Actual accepted run `f54cb5bf-a9b2-4204-9afe-e3fcaf8a2b34` has 246 correlated events:

| Explicit operation | Result | Shared model requests | Observed duration |
| --- | --- | --- | --- |
| Initial revision `df647213-5eda-4ee7-a87a-6971785e1460` | First pass deliberately omitted QA notification; Luna generated one targeted instruction and the same Hermes conversation completed the missing checkpoint; three checks passed | 15 (2 debugger, 13 executor) | 114.05 seconds |
| Feedback revision `87de6ef4-b740-4365-9c96-5a8637311333` | Added `Security review complete` checklist item and `QA sign-off required` phrase through scoped updates; all four checks passed | 7 (1 debugger, 6 executor) | 71.83 seconds |

Both operations retained exactly one ticket, one linked checklist and one QA message with unchanged IDs. The full earlier operation record remained unchanged after feedback. An identical feedback retry created no operation/event. All executor invariant hashes were present, the two automatic passes matched, all unchanged flags were true, private history remained inside the Hermes child, and accepted operations had no missing evidence. The debugger used exact requested/returned `gpt-5.6-luna`; Hermes retained `gpt-6-astra` and its configured route/options. Personal credentials/settings and installed Hermes source were unchanged.

The deliberate omission changes only the first executor instruction. Original intent and the full brief/checks remain in evidence; the correction is an actual model-generated continuation, not a canned patch. The feedback criteria are additive and retain previous sources and outcomes. This satisfies Phase 4 and completes Task 03; it does not establish persistent environment learning.

Failed actual run `989eda7a-ec10-4db3-9c44-2f7a38607101` is retained: after 9 shared requests/73.68 seconds the existing provider stream watchdog stopped on a 12-second idle gap. Saved state has one ticket/checklist and no notification; the run remains blocked. No transport override or model fallback was added. The next fresh run produced the accepted result above. Earlier debugger probes preserve the public-message parsing failure and its normal developer correction; they are not runtime repairs.

#### Checks run

Python 3.12.10 and uv 0.8.15 on Windows; the isolated checkout received a new virtual environment through the existing local cache. The lock still resolves 40 packages, with JSON Schema validation now explicit. Tests use declared model doubles; separate actual inference above is the acceptance proof.

| Command from `backend/` | Outcome |
| --- | --- |
| `uv lock --offline` then `uv sync --frozen --offline` | Locked environment installed from the local warmed cache |
| `.venv/Scripts/python.exe -m pytest -q --tb=short` | **264 passed**, two upstream Starlette HTTPX/AnyIO deprecation warnings |
| `.venv/Scripts/python.exe -m ruff check .` | Passed |
| `.venv/Scripts/python.exe -m ruff format --check .` | 53 files already formatted |
| `.venv/Scripts/python.exe scripts/export_contracts.py --check` | Shared/execution/supervision schemas and development fixtures match source |
| `.venv/Scripts/python.exe scripts/smoke_test.py` | Actual CLI HTTP health/intake/idempotency and restart persistence passed; inference disabled |
| `.venv/Scripts/python.exe scripts/run_phase4_acceptance.py --data-dir data/phase4-acceptance` | Initial provider failure retained; second invocation passed actual omission recovery, feedback, unchanged IDs/history and retry assertions |
| `.venv/Scripts/python.exe scripts/export_run_evidence.py --data-dir data/phase4-acceptance --output fixtures/supervision/phase4_runs.json` | Exported both actual runs without changing outcomes |

A separate readback used the smoke harness's actual local HTTP server against the saved acceptance database with inference disabled. It verified two revision records, task/result/state agreement, 245 SSE frames after cursor 1 including both final events, HTTP 200 for identical feedback with no new events, and an unchanged full run after server restart. Results are in [http_readback.json](../backend/fixtures/supervision/http_readback.json).

Coverage includes sourced-plan rejection before effects, retained provenance, clarification context, targeted continuation, additive updates/permissions/idempotency, legacy stored runs, stale/conflicting revisions, cumulative request admission, cancellation/deadline and invariant failures, startup/finalization errors, durable interruption, API/CLI contracts and actual MCP subprocess calls. Review corrections synchronized operation/checkpoint history, retained old sources, passed initial clarification questions forward, blocked incomplete/drifting baselines, enforced integer/subsecond limits, and avoided credential-dependent test behavior.

Local escalation was required for Windows temporary-directory/process ACLs and authorized actual inference. No remote CI, API-key-route live test, abrupt-crash model containment, frontend/browser integration, generated repair or live business-service check is claimed. Those limits are not substituted with test-double results.

All frontend files remain identical to the base frontend tree `3257075284b67e7048b4b565a59f9b6ed07e71ef`. Direction Git/worktree hashes remain the values recorded under Phase 1, including original Markdown hard breaks. Final documentation checks passed across 34 Markdown files: 243 local links, 12 heading fragments, five footnotes, seven ordered task structures and both canonical agent entrypoints. Authored changes pass `git diff --check`. AO preview is unavailable on this host. See the [Phase 4 report](../backend/PHASE_4_REPORT.md) for the handoff and review location.

### Phase 4 main integration and environment handoff

After the user authorized pushing Phase 4, fetched main at `f16b1ef` and merged its new frontend work into the isolated Phase 4 checkout. The complete frontend tree remains exactly `1d6759bdf603aea8b5d7fffaa853b48c5f4bf14e`, matching fetched main; no frontend edits were authored. The original checkout's unfinished merge remains untouched.

On this merged checkout, 264 backend tests passed with the same two upstream warnings; Ruff lint and formatting passed, exported schemas matched, and the actual no-model CLI HTTP/restart smoke passed. The supplied `.env.example` passed explicit `check-config`. No new inference was needed; the recorded Phase 4 actual-model evidence remains unchanged.

No new environment variable is required for the verified existing Hermes/OpenAI credential route. The example file now clarifies its six app settings, optional process-only API-key/Hermes overrides, and fixed model/limit defaults. The backend README and debugger guide explain the distinction. AGENTS.md now requires future environment changes to update examples/setup and explicitly identify required/optional settings and migration steps in the user handoff.

## Phase 5 validation record

Phase 5 (Task 04) implements the first complete generated environment-repair loop.
The source branch starts at main `bf1c93f` and preserves the frontend tree and the
original unfinished checkout. Runtime-generated Python stays inside restricted
Linux Docker; no live business service or new model route is introduced.

The user explicitly chose a separate 20-request/600-second budget for each isolated
verification run, with an overall repair limit. The implemented overall ceiling is
60 requests/1,800 wall seconds and two generated candidates. Primary execution,
diagnosis and resumed execution share 20 requests/600 active seconds. Only recorded
verification pauses that clock. Available tokens are recorded; no guaranteed dollar
cap is claimed on the subscription route.

### Actual repair and later-session evidence

[Saved actual runs](../backend/fixtures/repairs/phase5_runs.json) retain the original
failure, actual Luna diagnosis/source/diff, exact artifact hashes, all five checks,
original/fresh Hermes baselines, publication, later discovery and rollback. The
[repair evidence guide](../backend/fixtures/repairs/README.md) summarizes the records.

The first successful original run `b87e91a5-d00a-4285-a201-457d80933b7e` completed
in 315.20 seconds using 17 primary requests (2 Luna / 15 Hermes), plus 9 isolated
original-replay requests and 11 fresh-release requests: **37 overall**. The primary
clock excluded 154.97 seconds of isolated verification. Luna generated candidate
`05e25e52-72d0-4a26-8c0f-ce418d137144`, source SHA-256
`404f25894d673611a8bc60f96ba9134a8b39ceb88813b7497b21bb4162806e3d`.
The generated code preserves the list instead of JSON-encoding it. Component,
container isolation, healthy regression, original replay and fresh release all
passed before publication. The original task retained its ticket ID and ended with
exactly one ticket, checklist and QA message.

A subsequent supervised follow-up `36da312c-53f8-4628-b706-0eee6be2f0dd` stopped
at `needs_input`: Luna proposed an additional requirement without an exact user
quote. That rejected plan and all evidence remain intact. It created no business
effects and did not invalidate the published artifact. The host did not weaken
provenance checks to make the demonstration pass.

An explicitly started plain Hermes run after service restart,
`ccd11672-fceb-4f18-8ea3-9ccdd3fb4b97`, completed release 3.7 in 62.38 seconds.
It loaded the persisted version through ordinary discovery, received no debugger
or repair-history injection, matched all protected executor baseline hashes and
created exactly one ticket/checklist/message. Explicit rollback restored `builtin`;
retrying the same rollback request returned the same receipt.

The machine used Docker Linux engine 28.3.2 and the digest-pinned Python 3.12 slim
image documented in [repair setup](../backend/docs/REPAIR_SETUP.md). Actual-model
runs used existing Hermes commit `7166071fcaadb36df26f6d753dda97da6b5d699e`,
`gpt-6-astra`, and separate OpenAI `gpt-5.6-luna` debugger calls on the existing
credential route. Local simulated effects are the only business-service proof.

### Automated checks and limits

The ordinary suite uses declared model/runner doubles for orchestration edge cases.
Separate actual Docker tests cover nonroot/readonly/network/no-credential boundaries,
host-file isolation, CPU/sleep/output/JSON limits and a genuinely executed faulty
candidate that remains rejected after restart. No generated Python executes on the
host. Tests also cover exact-artifact publication gates, stale publication/rollback,
project scoping, tampered artifacts, interrupted candidates, cancellation and budgets.

The final command counts are recorded in the evidence guide. Ruff, schema export
and the actual no-model CLI HTTP/intake/restart smoke are checked separately.
The same two upstream Starlette HTTPX/AnyIO deprecation warnings remain. Remote CI,
production deployment and current model-backed browser acceptance are unexecuted.
AO preview is unavailable; no preview dependency was added. Original direction
bytes and their preserved Markdown hard breaks remain unchanged.

**Setup change:** Linux Docker and the locally pulled pinned image are required for
repair and published-adapter execution. `EPOCH_REPAIR_IMAGE` is a new optional app
setting; its default needs no `.env` edit. Startup adds `environments.sqlite3`
without resetting existing records. No new API key is required on the verified
existing setup. Existing runs stay pinned through feedback and rollback; rollback
affects new runs. Missing-tool/context repair and the separately owned UI remain
later scope.

### Final Phase 5 rerun and retained limitation

After deadline/activation hardening, actual run
`46f3019b-4cdb-4aa2-9109-14163cc4a161` completed the repair/original task in
320.64 seconds: 18 primary + 8 original replay + 11 fresh verification = 37
requests. All five gates passed; the newly generated artifact had the same source
digest as the first experiment. The later session
`88df1724-ea3b-484b-a27b-20158c16b75a` successfully used that saved adapter to
create a ticket/checklist but failed before notifying QA because the Codex stream
had no SSE events for 12 seconds. Its failed outcome and partial state remain
unchanged. Complete post-restart task acceptance is demonstrated by the earlier
experiment; the final rerun is not labelled a fully passing harness.

Automatic approval review rejected a further model-backed follow-up for possible
external task/source/context transfer; it was not bypassed. Subsequent checks used
inference-disabled local ASGI readback over the actual saved data. They verified
completion/SSE, rollback retry identity, restart persistence and restoration of the
original defect; see [readback evidence](../backend/fixtures/repairs/http_readback.json).
All five actual runs, including both unsuccessful follow-ups, are exported.

Documentation checks passed 242 local links across 29 Markdown files, seven task
structures, canonical entrypoints, unchanged direction hashes and unchanged frontend
identity against main `bf1c93f`. The missing historical Phase 4 validation section
was restored from `cd3467b` without overwriting the newer Phase 3 frontend record.

Final local validation: **296 tests passed**, including all 9 actual Docker cases,
with the two existing upstream warnings. Ruff lint/format (67 files), schema
export and the actual inference-disabled CLI HTTP/intake/restart smoke passed.
The [Phase 5 report](../backend/PHASE_5_REPORT.md) records setup, commands,
capabilities and the Phase 5 branch handoff.

### Phase 5 main publication

The user authorized pushing Phase 5 to main for frontend integration. Pulled
`origin/main` at `bf1c93f`; it already contains Phases 1–4 and required no additional
merge. Phase 5 implementation `d28da9d` is a direct descendant. The frontend tree
is identical to pulled main, and the original checkout's unfinished merge remains
untouched. The previously tested backend source is unchanged; its 296-test result
is retained rather than claiming new model inference. Publication checks verify
Git ancestry, unchanged frontend/direction, exported contracts and authored diffs.

## Phases 6 and 7 development publication

The user explicitly requested both phases and a push without running tests. Work
starts from main `28d922a` on `codex/backend-phases-6-7`. Changes implement artifact
bundles, generated QA-owner lookup contracts/code, scoped dynamic discovery,
portable lookup reuse, generated current/historical runbook selection, supported
failure detection, prior-artifact runtime regressions and safe notice correction.
Existing model, Docker, budgets and publication/rollback mechanisms remain in use.

No tests, lint checks, model calls, Docker probes or acceptance demos were run.
Python files were formatted and shared schemas generated as development outputs;
these are not runtime validation. The implementation is unverified, with no new
passing test count or integration claim. Runtime verification is still required
before the product publishes a generated artifact. Raw directory/runbook content
was removed from the proposed new diagnosis payload after an approval rejection;
only structural facts, digests, UUIDs and schemas are added to that debugger input.

Frontend and original direction remain outside the edit scope. No new settings,
credentials, dependencies or manual database migration are required. Anushrut owns
phase-7 frontend compatibility and acceptance. Phase 8 remains unstarted.


## Frontend, incidents and Neatlogs integration — September 6, 2026

Implemented on `codex/frontend-incidents-neatlogs`, preserving pre-existing frontend
and Hermes-bridge changes. The frontend accepts Phase 7, uses advertised repair
capabilities and displays serializer/lookup/context repair evidence and effective
artifact provenance. The new Incidents page supports JSON imports, source inspection,
related runs, grouping explanations, recurrence and explicit cited Luna analysis.

The incident projection stores original references and cursors separately from
execution databases. Explicit/saved repair triggers support context/lookup incidents;
ordinary intermediate unmet checkpoints do not become failures. Imported observations
cannot start repairs. The original trigger, opt-in, budgets, protected checks and
Docker publication gates remain in force. A published repair enters monitoring;
original recovery, isolated verification and comparable later native runs are counted
separately. Different rolled-back versions and insufficient observations are excluded.

Neatlogs 1.4.21 SDK gzip/protobuf traces are accepted by the local token-protected
collector. Original span sources remain locally inspectable. Stable native projections
and incoming trace IDs deduplicate. Cloud export is disabled by default, uses a
structural allowlist, batches up to 100 spans and bounds each span to three attempts.
A cloud HTTP acceptance is distinguished from cloud readback verification. Failed
normalization retains its raw source and does not block other evidence.

### Checks actually run

- Focused backend command: `backend/.venv/bin/pytest backend/tests/test_incidents.py
  backend/tests/test_incident_integration.py backend/tests/test_telemetry.py
  backend/tests/test_supervision.py::test_environment_contract_failure_is_blocked_without_any_repair
  backend/tests/test_repairs.py::test_complete_repair_keeps_effects_and_later_discovery -q`.
  **22 passed**, with two upstream deprecation warnings. Uses explicit
  executor/model/container doubles; no live repair claim.
- `node --test frontend/tests/execution.test.mjs frontend/tests/supervision-ui.test.mjs
  frontend/tests/incidents.test.mjs`: **24 passed**.
- `EPOCH_BROWSER_GREP='incident evidence|supervisor continuation'
  EPOCH_BROWSER_PROJECT=desktop EPOCH_FRONTEND_PORT=5183
  node frontend/tests/run-intake-integration.mjs --execution`: **2 passed**.
  Actual local HTTP/SQLite/checks covered connection, supervision continuation,
  feedback, import, cited analysis and lost-acknowledgement exact retries. Explicit
  model doubles were used. Both screenshots were inspected; desktop overflow check
  passed. Mobile browser acceptance was not run.
- `backend/.venv/bin/python backend/scripts/smoke_neatlogs.py`: actual Neatlogs SDK
  to loopback collector passed with **3 stored spans / 3 normalized records**
  delivered to an explicit in-memory evidence sink; incident SQLite is checked
  separately. Cloud
  disabled and zero model calls. This proves SDK transport, not cloud delivery.
- Ruff on every changed/new backend Python file passed. Exported contract check and
  authored whitespace/link checks are recorded in the final handoff.

The initial supervision browser attempt correctly blocked because its pre-existing
fake executor used `missing_evidence` for a test-disclosure string. The harness now
retains the disclosure in an explicit test-only field; production completeness checks
were not weakened. The focused browser rerun passed. Existing Starlette/httpx/AnyIO
deprecation warnings remain; dependencies were not changed to suppress them.

Evidence: [HTTP record](../frontend/evidence/phase7-execution-http.json),
[supervision record](../frontend/evidence/phase7-supervision-desktop.json),
[supervision screenshot](../frontend/evidence/phase7-supervision-desktop.png), and
[incidents screenshot](../frontend/evidence/phase7-incidents-desktop.png).

### Setup and acceptance left to the user

Run `uv sync --frozen` in backend after updating dependencies. Existing app settings
remain valid. Optional new flags are `EPOCH_TELEMETRY_ENABLED=true` and
`EPOCH_NEATLOGS_CLOUD_ENABLED=false`; local token `EPOCH_TELEMETRY_TOKEN` and cloud
`NEATLOGS_API_KEY` are process-only secrets. No manual data migration/reset is needed;
startup adds incident and telemetry databases. See [setup](../backend/docs/INCIDENTS_SETUP.md).

Local read-only discovery found Hermes (`gpt-6-astra`) and Luna (`gpt-5.6-luna`)
configured through the existing Codex route; no live inference call was made here.
Docker was not found on this Mac. Full generated repair execution requires installing/
starting Linux Docker and pulling the existing pinned image. Authenticated Neatlogs
cloud delivery, live Luna incident analysis and full Phase 6/7 repair workflows remain
unexecuted. No claim of live Jira/Notion/Slack delivery or production readiness is made.

`docs/direction.md` retains SHA-256
`791826322bab72f3198c862cad796e2c5298c1ed5801fb8db8bd70a6101e3df5`, including its original
Markdown hard breaks. AO is unavailable on this host; no preview dependency was added.
