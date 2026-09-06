# Phase 4 implementation plan

Requested on September 6, 2026. Implement the release-workflow supervisor and
user-feedback revisions, using OpenAI `gpt-5.6-luna` for the debugger. Preserve
the existing Hermes executor model and all frontend files. Report the finished
implementation and verification before any push; this branch stays local.

## Boundaries and selected interfaces

- Keep direct Phase 3 execution available. `supervised: true` on an explicit
  release-run request enables Phase 4; task intake alone does not start inference.
- Default and maximum operation budgets are 20 model-request turns and 600 seconds.
  Supervisor requests and every Hermes provider request share one host-enforced
  budget. Continuations never reset it. A separately submitted feedback or
  clarification operation receives its own budget and preserves earlier results.
- Use exact OpenAI model `gpt-5.6-luna`, confirmed in the official model reference.
  The debugger performs structured planning and continuation decisions, with no
  business tools or filesystem authority. Prefer an explicitly configured OpenAI
  API key; otherwise use the existing OpenAI/Codex credential route if verified.
  Do not refresh credentials, alter global settings, substitute models or fall
  back to a different route after a failed request. Record route and missing evidence.
- Hermes retains its actual conversation inside a bounded worker during one
  supervised operation. The parent authorizes each model request before dispatch.
  User-visible events contain actions/results and summaries, never private reasoning.
- Planning derives sourced release checkpoints. Trusted code retains the ticket,
  linked checklist and QA-notice requirements. This first supervisor supports
  additional checklist items and required QA-message phrases quoted from user input.
  Unsupported, conflicting or subjective requirements require clarification rather
  than weakening the evaluator or claiming unrestricted workflow support.
- Feedback is an explicit, idempotent operation with an expected prior revision ID.
  Retain its original text, classification, prior/resulting brief, criteria, state,
  verification and interventions. Update existing checklists/messages in place;
  preserve their IDs, links, earlier evidence and all already required outcomes.
- Add developer-controlled additive criteria revisions and two scoped update tools.
  These are ordinary implementation changes, not generated environment repairs.
  Broken adapters and unavailable tools still produce a reported blocker.
- Persist progress/checkpoint events and provide feedback/clarification/revision API
  routes and CLI commands. Preserve old stored runs and explicitly mark unsupported
  legacy feedback operations. No frontend changes, Phase 5 repair, live business
  integration, Neatlogs or Workshop implementation is included.

## Parallel ownership

1. OpenAI agent: debugger transport, schema/redaction/limit checks and route evidence.
2. Hermes agent: persistent conversation, request-budget gate and bridge tests.
3. State agent: additive criteria history, scoped in-place updates and invariants.
4. Primary agent: plan/contracts, aggregate budget, supervisor logic, durable
   operations, HTTP/CLI integration, end-to-end verification and final handoff.

## Acceptance

Run regression and boundary tests for budgets, cancellation, admission/restart,
provenance, ambiguity, immutable history, revision races and duplicate prevention.
Use actual Luna and installed Hermes to demonstrate a deliberately omitted QA
checkpoint followed by a model-generated targeted continuation, then a user-feedback
revision updating existing objects. Preserve failed attempts and exact model/prompt/
discovery baselines. A development omission switch affects the first executor brief
only; the original intent and trusted criteria stay complete and visible in evidence.

References: [OpenAI Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna),
[phase boundaries](PHASES.md), [Task 03](../docs/tasks/03-executor-evidence.md).
