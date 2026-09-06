# Phase 3 frontend integration

Scope: connect the existing chat/debugger to the implemented HTTP contract in
`backend/docs/FRONTEND_HANDOFF.md`. Preserve the fixture entrypoint and backend
executor, trusted checks, simulations and later-phase boundaries.

1. Accept Phase 3 health and published task states. Add validated runtime, run,
   state and trace reads, explicit release submission and asynchronous cancellation.
2. Preserve an unresolved run's exact request, task and origin in session storage
   before sending. Reconnect/navigation perform reads only. Recover activity with
   named SSE notifications plus persisted trace and authoritative run polling.
3. Show release configuration, run history, sourced checkpoints, verification,
   partial simulated objects, executor response and missing evidence in the
   existing interface. Keep future repair screens clearly labelled as fixtures.
4. Test contract and recovery boundaries, actual local HTTP intake, and browser
   execution flows with an explicitly labelled test executor. Record exactly what
   ran; do not treat a test executor as installed-Hermes/model acceptance.

Validation: frontend unit and desktop/mobile browser suites; isolated HTTP
integration; backend checks and schema drift; authored diff/links and unchanged
direction hash. No new frontend runtime dependency or live integration is needed.
