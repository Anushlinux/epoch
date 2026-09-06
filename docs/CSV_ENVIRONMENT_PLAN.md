# CSV import investigation sandbox

Assigned September 6: create the proposed CSV failure environment so the user can
exercise the current chat and explicit debugger against real simulated tool calls.

1. Add an isolated per-conversation customer store with an immutable sample CSV
   and host-owned expected results. Keep release tools and criteria unchanged.
2. Expose sample reading, CSV import, customer listing and import-status tools
   through the existing three-function MCP discovery interface. A broken adapter
   maps `email` to `emailAddress`; a strict simulated service rejects the payload
   atomically. A separately selected healthy control uses the correct mapping.
3. Preserve inputs, outgoing payloads, errors, import receipts, stored customers
   and trusted checks. Runtime tools cannot change their environment or criteria.
4. Add explicit environment selection for a new chat, a sample task, and an
   inspectable result panel. Debugger receives the actual CSV evidence only when
   the user requests investigation. Neither selection nor opening a page executes
   Hermes or Luna.
5. Verify failure, healthy control, invalid inputs, duplicate/idempotency handling,
   persistence, MCP scope, chat/debugger evidence and browser interaction. Record
   local tests separately from live model proof.

The healthy adapter is a developer-provided control, not a generated repair.
Automatic CSV repair/publication was outside this initial assignment; the later
[verified CSV repair assignment](CSV_REPAIR_PLAN.md) adds bounded repair when
Debugger is explicitly invoked. No credentials,
external customer services, global settings or arbitrary file access are added.
