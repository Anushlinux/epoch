# Phases 6 and 7: development handoff

**Implemented, untested.** The user explicitly requested development and a push
without running tests. No pytest, lint check, Docker probe, model call, smoke test
or acceptance demo was run for this change. Earlier Phase 5 results do not validate
these additions. Runtime verification remains mandatory before an artifact can be
published; its implementation has not received development acceptance.

## Phase 6: generated missing lookup

For an observed failed QA-owner checkpoint, the controller requires an actual
scoped discovery result with the lookup absent and an existing `directory.read`
grant. An installed or denied capability is not treated as missing. Luna generates
`qa_lookup.py` plus its discoverable description and input/output schemas. There is
no prewritten lookup algorithm used as a fallback.

After activation, normal discovery exposes `directory.lookup_qa_owner`. Input is
`{"project_id":"demo"}`. Output contains `status` (`found`, `missing`, `ambiguous`),
`project_id`, and the exact directory `owner` record or null. The host rejects
foreign-project queries, malformed arguments, fabricated records and guessed
answers. It supplies only current-project records to the isolated function.

Runtime gates include valid/missing/ambiguous owners, unrelated projects, another
owner, invalid arguments, denied discovery/invocation and actual original/fresh
Hermes execution. The fresh lookup verification uses a different project with a
different seeded owner. Publication must pass the existing five proof gates.

Verified lookup code is portable within the same local data directory. New runs
can discover a published lookup from an active environment in another project,
while directory data and grants remain local to the new run. Only this lookup
artifact is shared; serializer and retrieval changes remain project-specific.
Copied/pinned artifacts retain their origin and source digest. Rolling back an
origin does not revoke copies already pinned or retained in other active versions.

## Phase 7: generated retrieval rule

Investigation requires an actual current-context request that returned old guidance,
a failed trusted QA-notification check, and a saved message to the old destination
mentioned in that guidance. A scenario label or document presence alone cannot
start this repair. Luna generates `runbook_selector.py`, selecting existing source
IDs according to scope, current status and explicit version requests.

The host preserves source documents and rejects missing, ambiguous, foreign or
inappropriate selections. Runtime gates cover current and historical requests,
explicit versions, missing/ambiguous guidance, unrelated scope, prior artifacts,
and original/fresh Hermes tasks. Old source bodies and retrieval evidence remain
available. Successful replay is required before treating the context hypothesis
as an accepted improvement.

`messages.update` now accepts optional `channel` to correct an existing notice to
the task's authoritative QA channel while retaining its ID and links. Other
destination changes are denied. Hermes performs the correction; the debugger
cannot mutate the business state itself.

## Shared lifecycle and budget

Environment versions now contain a hash-checked artifact bundle. Adding one surface
retains earlier repairs; rejection, publication, safe activation, restart and
rollback use the existing store. Older serializer-only records remain readable.
New lookup grants apply only to newly initialized runs; existing grants are never
silently expanded.

Each repair operation still allows two candidate attempts, 20 primary model
requests/600 active seconds, separate 20-request/600-second verification runs, and
60 requests/1,800 wall seconds overall. Runtime component gates execute generated
Python only in the existing restricted Docker runner. No dollar-cap guarantee is
added. A verification failure or exhausted budget blocks publication.

The new diagnosis payload sends fixed schemas, evidence UUIDs, source digests and
structural failure facts to the existing Luna route. Raw directory rows, names,
channels and document bodies are retained locally rather than newly added to that
debugger payload. Existing Hermes execution still receives its authorized task/tool
context through the established provider route. An approval rejection of broader
raw-context wiring was resolved by implementing this narrower payload.

## Frontend integration

Frontend files are unchanged. Health and runtime now report **phase 7**.
`RuntimeInfo.repair_targets` lists all three allowed files and
`development_validation` is `phases_6_7_untested`.

Existing routes and run input remain available. Set `supervised: true` and
`repair_enabled: true`, choosing scenario `missing_lookup` or `outdated_context`.
`ExecutionRecord.environment_artifacts` maps target files to origin versions or
source digests. Environment inspection adds `effective_artifacts`, including origin
project/version and source digest, so a shared lookup is visible even when the
project's local active version is `builtin`.

Render existing repair events, `editable_target`, `investigation`, generated
`tool_contract`, source/diff, proof cases and `fresh_release.verification_project`.
The discovery result and tool trace include the actual artifact implementation
version. Show failed or unsupported diagnosis honestly; do not infer task completion
from an active artifact or an assistant's text.

Suggested commands for the teammate to exercise after integration (not run here):

```powershell
uv run --frozen epoch-backend run-release --release 2.4 --scenario missing_lookup --repair
uv run --frozen epoch-backend run-release --release 3.1 --scenario outdated_context --repair
```

The context scenario only triggers repair if the executor actually makes the
context-related mistake; an already-correct task needs no manufactured failure.

## Environment and remaining work

No new environment variable, credential, package or external integration is added.
Keep the Phase 5 Linux Docker/image setup and existing Hermes/OpenAI route. No manual
database migration is required; artifact bundles use additional JSON record fields.
The `.env.example` settings remain the same. Exported JSON schemas are updated.

All business services remain local simulations. Phase 6/7 runtime behavior and
compatibility still need acceptance testing by the integration team. Phase 8
reliability/demo/vendor integration work has not started.
