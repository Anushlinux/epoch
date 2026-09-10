# Trace explorer implementation assignment

Implement only the newly assigned Neatlogs feature Phases 1 and 2: local SDK
collection, durable original evidence, a rebuildable normalized/search projection,
read-only HTTP/CLI inspection, and the browser trace explorer. Reuse the existing
collector and frontend. A separate `serve --profile trace-debugger` starts without
execution/repair initialization and always disables cloud forwarding.

Order: establish span/read contracts; add indexing and local profile; connect the
CLI and frontend; provide an instrumented example and setup instructions. Preserve
existing data and `docs/direction.md`. No AI questions, inference setup, comparison,
similar-run investigation, MCP additions, replay or repair belong to this assignment.

At the user's explicit request, skip tests, SDK probes, example execution, browser
acceptance and model calls. Review source changes and diff formatting only. Record
the result as implemented but unverified; no acceptance claim follows from delivery.
