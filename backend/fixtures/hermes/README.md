# Actual Hermes execution evidence

These are saved observations from the installed Hermes executor on September 6,
2026. They are not development UI fixtures or scripted executor responses. Model
inference used the existing `openai-codex` / `gpt-6-astra` route; all business effects
were local simulations. Full setup, credential handling and compatibility limits
are in [Hermes setup](../../docs/HERMES_SETUP.md).

## Final Phase 3 acceptance

[phase3_acceptance.json](phase3_acceptance.json) contains the two complete run
records, saved state, correlated events, and baseline comparisons.

| Scenario | Actual run ID | Saved effects | Trusted outcome |
| --- | --- | --- | --- |
| Control | `c9a1bcca-22ad-462a-b5a7-d185dad64ba1` | 1 ticket, 1 checklist, 1 QA message | All three checks pass; run completed |
| Broken checklist adapter | `aae4ba66-dbc7-43b4-993f-996554f1d0d1` | 1 ticket, 0 checklists, 0 messages | Ticket passes; checklist and QA notice fail; run failed |

The healthy and defective runs have 69 and 62 persisted events respectively. Both
finished their executor conversation, but only the control achieved the task.
The defective adapter serializes checklist items as a string, which the service
rejects without creating a checklist. No repair occurred.

All 12 compared baseline fields are present and equal: Hermes commit/source,
model configuration, initial/full/static system prompts, discovery interface,
bridge source, evaluator, grants, criteria and initial brief. Both runs report
unchanged Hermes source, prompt and personal settings, fresh empty homes with
memory disabled, and no missing evidence. The only granted model tools are the
three Epoch MCP facade functions. The evaluator is `release-state-v2`.

After execution, the local HTTP run/state/trace endpoints and SSE replay were
checked against these saved records. SSE retained the final event and supported
the sequence cursor. No second inference was performed for that readback.

## Reproduction

From `backend/`, after completing the normal setup:

```powershell
uv run --frozen epoch-backend hermes-info
uv run --frozen epoch-backend run-release --release 2.4 --scenario control --timeout 180 --max-turns 16
uv run --frozen epoch-backend run-release --release 2.4 --scenario broken_checklist --timeout 180 --max-turns 16
```

The second workflow is expected to exit with code 1 because its task is incomplete.
Each invocation creates a fresh run/sandbox. Availability and the configured model
route must work on the host; model output and timing are not deterministic.

The final observations used separate ignored data directories. Export their saved
records without invoking a model or changing outcomes:

```powershell
uv run --frozen python scripts/export_run_evidence.py --data-dir data/final-control --data-dir data/final-broken_checklist --output fixtures/hermes/phase3_acceptance.json
```

Those runtime directories are local verification data and are not distributed in
Git. The JSON artifact is the portable evidence; reproduction creates new identities.

## Preserved development attempts

[development_attempts.json](development_attempts.json) retains four earlier runs;
their original outcomes and missing evidence were not rewritten:

| Run | Observed outcome and subsequent developer change |
| --- | --- |
| `51d96d37-2e6c-4b26-bf29-89920c9d1061` | Bridge guard stopped before inference because installed Hermes added tool-search/resource wrappers. Supported per-run configuration now exposes exactly the allowed facade. |
| `2689138a-be84-4327-ab10-517e8021f6c9` | Hermes created the required objects, but evaluator v1 incorrectly rejected release `2.4` followed by a sentence-ending period. The recorded run remains failed. A developer fixed token-boundary handling, added regression cases, and versioned the evaluator as v2. |
| `c12093d9-a78e-478e-a831-bb98fe7e8c62` | Control passed v2, but its complete prompt differed from the paired defective run because run paths and Git status entered the prompt. This pair was not accepted as a fixed-baseline comparison. |
| `98483057-2018-4a38-8f5f-bcbccf002520` | Defective run failed the expected checks under v2; same prompt-baseline limitation as its control. Supported settings subsequently stabilized the prompt before the final pair above. |

These are normal implementation corrections, not autonomous environment learning.
The historical artifact intentionally reports incomplete or unequal baselines.
No token, personal conversation, private reasoning or raw console transcript is
included. Personal configuration/credential files are represented by hashes only.

Phase 4 supervision and Phase 5 generated repair remain unimplemented. These two
acceptance runs prove the current narrow installed-Hermes path, not compatibility
with other providers, future Hermes versions, live business APIs or secure execution
of generated code.
