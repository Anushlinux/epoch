# Conversation workers and live answers

Assigned scope: retain the initialized Hermes agent/MCP connection for the active
conversation, stream public answer text, report actual stages, and render chat
results independently of runtime/PDF panels. Preserve existing trace capture,
execution grants, repair experiments and saved conversations. No later trace phases.

1. Add a single conversation-scoped warm-worker slot per local workspace. Reuse
   requires the same chat/project/environment, authoritative visible history and
   unchanged tools, implementation, model/settings and credential identities.
   Release/repair sessions retain their existing lifetime budgets. Chat messages
   get independent 20-request/600-second grants; no retry of uncertain execution.
2. Invalidate on cancellation, failure, missing integrity evidence, changed scope
   or failed persistence. Reap idle workers after an optional app-file timeout
   (default 300 seconds; zero disables reuse). Close workers during app shutdown.
3. Connect the installed text-delta callback to operation-scoped SSE, with bounded
   live snapshots, sequence IDs, reconnect recovery and public-text redaction.
   Provisional text is replaced by the final saved message. Streaming never exposes
   private model history or reasoning and disconnecting never cancels execution.
4. Render returned chat immediately. Refresh conversation lists, runtime and PDF
   metadata independently, with identity guards, separate errors and polling fallback.
5. Update settings, setup, API notes, status and manual checks. Static source review
   and diff formatting only: no tests, syntax/lint checks, servers, SDK probes or models.

Isolation boundary: this remains the existing local single-user API. Workers are
never shared across conversations or server instances; multi-user authentication
is not added or claimed by this change.
