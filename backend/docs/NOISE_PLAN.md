# Assigned noise workflow — September 11, 2026

Implement issue-focused trace investigation with the existing local Ollama model,
reviewable context policies, source metadata, previews, manual validation records,
versioned activation/rollback and ordinary document-tool integration. Preserve raw
traces, sources, historical reads, Hermes configuration and existing repair workflows.

1. Add a bounded declarative selector: exact duplicate consolidation, explicitly
   approved/current document preference, and topic filtering when retrieval specifies
   a topic. Retain unknown metadata and conflicts; never remove document sections.
2. Store source metadata separately, scoped to project/environment/chat/source hash.
   Snapshot policy/metadata at each admitted chat operation; record selection decisions
   and delivered content. Never edit original assets or OTLP evidence.
3. Add local issue analysis with cited relevant spans, noise hypotheses, unsupported
   tool defects and proposed rule types. Keep model proposals separate from authority.
4. Add draft previews and four user-recorded acceptance cases. Activation requires
   recorded passing cases against the same policy/source snapshot and an idle executor.
   Mark this manual acceptance, not automated proof. Retain history and rollback.
5. Add the workflow to Traces, source metadata editing, focused evidence links, policy
   controls, HTTP/CLI access and setup/manual-check documentation.

No tests, syntax/lint checks, SDK/model calls, servers or browser acceptance are run
during development. Delivery is implemented but unverified. Existing generated-code
repair gates remain unchanged. No new cloud/model configuration or data-folder change.

## Ollama rejection follow-up

The reported investigation displayed a generic memory hint for an unspecified HTTP
rejection. Inspect available logs without model calls, preserve bounded Ollama error
details through the shared client, and provide an explicit new-analysis retry action.
Keep historical failures and the existing model/schema/configuration unchanged. Update
manual troubleshooting and review the diff only; the user performs the next live retry.

## Grammar rejection fix

The subsequent user retry and available Ollama log identify a grammar repetition limit:
the generated noise schema contains `char{1,2000}` string rules. Separate the sampler
schema from host validation, omitting string-length bounds only from the former for
noise analysis and trace questions. Supply the complete schema in the prompt, preserve
all acceptance constraints and budgets, record the new schema/prompt version, and update
the manual retry instructions. No installed runtime changes, tests or model calls.

## Rejected-answer follow-up

The user's next attempts reached HTTP 200 but failed host answer validation; the old
record did not retain the precise check. Read existing logs/records only. Add distinct
completion/JSON/schema/citation/policy diagnostics, accept only a single complete JSON
Markdown wrapper, and bind citation choices to the supplied snapshot in the sampling
schema. Keep every host validation gate, preserve failed records and display failure
details. Do not guess the old rejection's cause or run tests/model calls.

## Outcome and proposed-action consistency

The user now supplied `invalid_policy_proposal`: a tool-defect answer also contained
filter rules. Constrain generation to mutually exclusive complete response alternatives:
context noise may suggest rules; every other outcome must contain exactly `rules: []`.
Keep the existing post-generation rejection and draft/publication gates. A valid tool
defect should show its cited explanation and open the conversation's existing Debugger
without starting a repair. Use one inference request and existing settings; static review
and diff formatting only. Preserve older failures.

## User-reviewed data-noise cleanup

The user requests a data-noise example and an explicit button to remove suggested noise.
They explicitly chose Apply after source review, without requiring four trial runs.
For the current Documents environment, implement review of a suggested filter followed
by manual Apply and existing rollback. Label it user-approved, without claiming four-trial
acceptance. Preserve the existing trial-based activation route for other use and keep
generated-code repair gates intact. Apply changes future retrieval; source files, logs,
historical/explicit reads and saved chat history remain preserved. Review snapshots,
source hashes, project/environment scope, revision checks, exact retry receipts and idle
worker invalidation bind the explicit approval. Merge existing rules rather than silently
replace them. No automatic model calls or activation. Provide a duplicate-PDF walkthrough;
development remains static review and diff formatting only.
