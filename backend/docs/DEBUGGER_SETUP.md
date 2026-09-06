# OpenAI debugger setup

Phase 4 uses **`gpt-5.6-luna`** for the debugger's structured planning, continuation and feedback decisions. Hermes remains the executor that invokes business tools. A debugger response is a proposal; trusted application code validates it and determines checkpoint success. The debugger has no tools, shell, filesystem-edit action or environment-repair action.

The supervisor enforces the user's shared **20 agent turns and 600 seconds** per run/revision outside both agents. One debugger request consumes one turn; the remaining budget is shared with Hermes. The transport also terminates its own network worker when the supplied remaining timeout expires or cancellation is requested. It performs no hidden retry and never substitutes another model.

## Credentials and route selection

1. When `OPENAI_API_KEY` is present in the backend process environment, use the official OpenAI Responses API at `https://api.openai.com/v1/responses`.
2. Otherwise, inspect the existing Hermes installation. If its configured provider is `openai-codex` at the official Codex endpoint and it has an existing access token, use `https://chatgpt.com/backend-api/codex/responses`.
3. If neither route is configured, report `debugger_unavailable`. An error from the selected route never causes a switch to another route or model.

Use the existing backend environment-variable setup for an API key; do not commit it. `OPENAI_BASE_URL` and model/endpoint values supplied in task text are not accepted as transport overrides. The debugger reads the selected credential only in the child process, does not refresh or copy tokens, and does not alter the user's Hermes or Codex settings. Authentication failures require the user to restore their existing credentials through their usual application.

`detect_debugger()` checks local configuration and credential presence. Its `available` flag does not prove network connectivity, model entitlement or remaining account usage. Importing the module and checking availability never invoke the model.

## Request and result contract

The backend calls `complete(request, on_event, cancel_event)` with:

- `instructions`: trusted debugger instructions.
- `input`: task, feedback and observable evidence as structured data.
- `schema`: trusted JSON Schema for the requested decision; remote schema references are rejected.
- `timeout_seconds`: remaining wall time, from 1 to 600 seconds.
- `max_output_tokens`: optional output cap, from 256 to 16384; defaults to 4096.

The transport requests strict structured output and validates the returned object again locally. It records the exact requested/returned model, route, prompt/input/schema hashes, bridge hash, token usage when present, and whether the route supports the requested output cap. Credential values, private reasoning and raw console logs are excluded. Public `debugger.started` and `debugger.completed` events expose route/usage metadata; the caller records the validated decision and any failure.

**The Codex route does not support this output-token cap in the installed Hermes transport.** Epoch omits that parameter and records `output_token_limit_supported: false`; the shared turn and wall-time limits still apply. The API-key route sends `max_output_tokens`. There is no claim of an exact monetary cost limit for subscription-backed requests.

## Demonstrated compatibility

On September 6, 2026, a real request on this machine using the existing Hermes Codex credential returned `{"status":"ready"}` with response model `gpt-5.6-luna`, 77 input tokens and 16 output tokens. The credential file was unchanged and no evidence field was missing. This proves the exact model and route for the configured account at that time; it does not establish compatibility for every ChatGPT account or a stable public third-party Codex API contract.

The first transport attempt retained only `response.completed`, whose output array was empty on the configured Codex route. That attempt failed safely. The corrected transport reconstructs completed public messages from `response.output_item.done` events and requires `response.completed` before accepting them. It ignores private reasoning and partial deltas. The failed attempts and corrected probe remain in ignored runtime data under `backend/data/phase4-debugger-probe/`; supervision acceptance evidence is reported in the [implementation status](../../docs/status.md).

The API-key route has transport tests but was not exercised with an actual API key on this machine because none was configured. Unit tests use explicitly fake responses and do not stand in for live model evidence.

## Source basis

Official [GPT-5.6 Luna documentation](https://developers.openai.com/api/docs/models/gpt-5.6-luna) establishes the exact model and support for Responses and structured output. The [structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs) describes JSON Schema constrained responses and handling incomplete or refused responses. [Codex authentication documentation](https://learn.chatgpt.com/docs/auth) distinguishes account sign-in from API-key authentication; it does not guarantee this custom transport's compatibility.

The configured consumer-route behavior was additionally checked against the installed Hermes source (`agent/codex_headers.py`, `agent/transports/codex.py`, and `agent/codex_runtime.py`) and the actual request above. No Hermes implementation was changed to enable the debugger.
