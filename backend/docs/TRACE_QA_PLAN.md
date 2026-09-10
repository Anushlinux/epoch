# Trace debugger Phase 3 assignment

The user assigned local trace questions using their already installed Ollama model
`qwen3:4b-instruct-2507-q4_K_M`. This continues feature Phases 1–2; the numbering in
the historical repair roadmap and attached source document is separate.

Later user clarification: these features extend the existing workflow. The primary
entrypoint is the normal `serve` command with the original app file/data directory,
which already registers chat, debugger, telemetry, trace and question routes together.
Correct setup/UI hints to recommend that entrypoint, share the tab's API connection,
and label the trace-only profile as optional. Preserve all existing workflow code
and databases; do not launch servers, merge data directories or run acceptance checks.

1. Define question, evidence snapshot and cited-answer contracts.
2. Retrieve bounded evidence from the selected trace, including the focused span,
   roots, search matches, parents, recorded errors and nearby steps.
3. Call loopback Ollama only after an explicit question. Bound concurrency/time,
   validate structured answers and citations, and retain questions/results locally.
4. Add the question panel, saved history, citation links and CLI commands.
5. Document configuration, limitations and manual acceptance instructions.

No model installation/download, automated tests, probes, sample runs, browser
acceptance or model calls during development. Static review and diff formatting
only. Delivery is implemented but unverified. No cross-run investigation,
comparison, MCP, execution, repair or incident changes are authorized here.
