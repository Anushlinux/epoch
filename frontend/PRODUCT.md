# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Provisional plain HTML, CSS and browser JavaScript modules. Node's built-in test runner verifies local state behavior. No production frontend stack selected; joint frontend agreement with Rajdeep remains pending. Backend Phase 1 selections are recorded separately in `backend/DECISIONS.md`. The user authorized minimal provisional tooling, fixture UI and a later Phase 1 intake integration against the published handoff.

## Users

People requesting a task and reviewing its checkpoints, observable execution, artifacts and unresolved requirements.

## Product Purpose

Epoch is intended to supervise task delivery and support verified environment repairs. This frontend saves and reads real Phase 1 tasks, and separately demonstrates future execution interfaces with fixtures. It does not execute work or verify repairs.

## Capabilities and Constraints

Preserve original requests, explicit and inferred requirements, source references and revisions. Task completion and repair activation are separate claims. Every current execution record is visibly a development fixture. Phase 1 backend intake endpoints and a handoff are now published. The primary page connects to published Phase 1 intake/list/detail routes. Future fixture mapping and execution/recovery integration remain unsettled. The minimal frontend dev host uses the backend-supported loopback origin on port 5173. Normal browser and AO intake connect through that URL; generated-origin static-file preview remains for disconnected inspection only. No private reasoning or credentials belong in this browser.

## Evidence on Hand

The UI brief in `docs/tasks/README.md` and architecture are requirements. There is no backend execution evidence. Fixture tests/screenshots establish frontend behavior. The separate Phase 1 integration checks establish actual local task intake and persistence, not task execution.

## Accessibility & Inclusion

Responsive workspace, semantic controls, keyboard access, visible focus, readable contrast, reduced motion and explicit text for states.
