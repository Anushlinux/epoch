# Chat-to-traces integration

Assigned scope: make normal Hermes conversations produce local Neatlogs traces,
link conversations and individual responses to their evidence, and correct direct
frontend navigation. Preserve the current executor, prompts, tools, settings,
databases, debugger and repair boundaries. No later investigation/repair phases.

1. Observe the existing public Hermes bridge callbacks using an isolated Neatlogs
   client. Store original OTLP through the existing collector, then let its durable
   cursor build the searchable projection. Never forward these chat spans to cloud.
2. Persist the trace identity and capture outcome on each chat operation. Keep
   capture failures separate from business results and expose incomplete evidence.
3. Link each conversation and message to its traces, preserve conversation context
   in URLs, provide a return link, and explain pending/absent historical evidence.
4. Canonicalize the development host's filesystem boundary and route aliases; use
   Node watch mode so edits to the host reload its route table.
5. Update setup, contracts and status with manual acceptance steps. Review source
   and diff formatting only; do not run tests, probes, examples, servers or models.

Delivery status: implemented but unverified; user performs runtime acceptance.
