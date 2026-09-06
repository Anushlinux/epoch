# Existing Hermes execution

Epoch uses an existing Hermes checkout and its own Python environment. It does not
install, upgrade or rewrite Hermes. Phase 3 delivers an explicit release brief. Phase 4 adds a persistent private
executor session for bounded supervisor continuations. OpenAI `gpt-5.6-luna` is the
separate debugger; Hermes keeps its existing executor route and model. Generated
environment repairs remain Phase 5 work.

## Installation discovery

On Windows, discovery checks `%LOCALAPPDATA%/hermes/hermes-agent` and the corresponding
`venv/Scripts/python.exe`, then the conventional `~/.hermes` location and a Hermes
executable's parent directory. On other systems it checks `venv/bin/python` or
`.venv/bin/python`. For another checkout, set `EPOCH_HERMES_HOME` and
`EPOCH_HERMES_CHECKOUT` in the backend process environment. These overrides do not
change the user's Hermes settings.

The Windows installation inspected on September 6, 2026 has checkout commit
`7166071fcaadb36df26f6d753dda97da6b5d699e`. Its configured route is `openai-codex`,
model `gpt-6-astra`, endpoint `https://chatgpt.com/backend-api/codex`, with medium
reasoning effort. This is remote model inference using the existing ChatGPT
credential. Synthetic task briefs, tool descriptions, results and assistant messages
go to that configured provider. Tickets, pages and messages remain local simulations.

`detect_installation()` reads only safe configuration metadata. An available result
means the checkout and model configuration were found; it does not establish that
the provider is reachable, the credential is current or the model is available.

## Execution and access

The backend launches a child using Hermes's existing Python and imports its actual
`run_agent.AIAgent`. Each run gets a new `HERMES_HOME` beneath its ignored runtime
directory, containing only a minimal config and empty memory/skill/plugin directories.
The adapter disables context-file injection, memory and background review. It grants
only the Epoch MCP server and checks the actual exposed tool names before inference.
Hermes's personal conversations, skills, integrations and terminal are not included.
The installed version normally wraps MCP tools behind its own tool-search interface;
Epoch disables that optional wrapping through `tools.tool_search.enabled: off` and
disables MCP resource/prompt utilities. The advertised model tool surface is exactly
the three Epoch facade functions. These are per-run configuration choices, not edits
to Hermes source or the user's global tool configuration.

The physical process directory remains unique to each run. `HERMES_HOME` uses the
relative value `hermes-home`, so Hermes stores its state in that run's fresh directory
while its profile description stays identical. `TERMINAL_CWD` pins the logical
workspace to the backend directory, and `agent.coding_context: off` excludes an
irrelevant Git-status snapshot from this business workflow. These supported options
avoid changing the effective prompt when only run IDs or repository edits differ.
Two installed discovery-only probes with different homes produced byte-identical
full prompts after these settings were applied. The comparison files remain under
ignored `data/prompt-stable-a` and `data/prompt-stable-b`.

The MCP server runs with the backend Python and these arguments:

```text
-m epoch_backend.mcp_server --database DATABASE --task-id TASK_UUID --run-id RUN_UUID
```

Its stable interface is `discover_tools`, `describe_tool` and `invoke_tool`. Scoped
registry discovery and service permissions remain authoritative; caller-supplied
tool descriptions cannot grant additional access. The child receives the backend
source path through MCP's explicit environment, without provider credentials.

For the configured `openai-codex` route, the worker reads the existing access token
into its memory and passes it directly to Hermes. It does not copy `auth.json`, write
a token to config, perform login or refresh the user's credentials. An expired token
therefore produces a failed run; refresh/login remains a normal user Hermes operation.
When the Codex base URL is omitted, the bridge passes the standard Codex endpoint
explicitly alongside the in-memory credential. Current Hermes requires both values
to avoid searching the isolated home for credentials. The effective endpoint is
recorded in execution evidence. Initializer failures produce a sanitized stage
message; raw provider exceptions and credential values are never exposed.
The implementation also accepts explicitly configured API-key routes for `openai`,
`anthropic`, `openrouter` and `custom`, but those routes require separate installed
execution evidence before any compatibility claim.

`probe_tools(mcp_command, mcp_args, work_dir)` is a discovery-only diagnostic: it uses
a literal placeholder credential, never reads the existing access token, and returns
before `run_conversation`. Unit tests verify that it cannot invoke inference.

## Supervisor continuation

`Session(request, on_event, cancel_event, before_model_request=callback)` keeps one
actual `AIAgent` and its MCP process alive across `session.run(instruction,
max_turns=remaining_turns, timeout_seconds=remaining_seconds)` calls. Each conversation
passes the previous result's `messages` to Hermes's supported `conversation_history`
argument. Full history, including any provider-internal reasoning, stays inside the
child process and never becomes debugger input or API evidence. The bridge returns
only visible final output, observable events, baselines and request counts. It
refuses another continuation if Hermes did not retain usable history.

The executor cannot change checkpoint decisions. The supervisor inspects trusted
saved sandbox state and records each follow-up instruction separately. Continuation
uses the same sandbox and session; completed effects remain available through
ordinary tools. The one-call `execute` function remains available for Phase 3 callers.

The session baseline spans every continuation. Initial brief identity remains
separate from continuation instruction hashes. Implementation, user settings,
discovery definitions and effective full/static prompts are compared throughout
the session; a changed baseline prevents a success claim or another continuation.

## Evidence and limits

The adapter reports visible assistant messages, tool start/completion callbacks,
tool arguments/results, execution steps and final output. It does not subscribe to
reasoning callbacks or export private reasoning/whole Hermes trajectories. Structured
output redacts credential fields and the actual selected token; arbitrary console
output is discarded. Registry events provide independent task/run correlation and
business-state evidence.

The run baseline records the Hermes Git commit, a hash of tracked Python source
contents, model/inference options, actual discovery definitions, bridge source,
effective system prompt, initial brief and controlled memory state. Personal config,
credential file and identity-file contents are represented by hashes only; before/after
checks flag concurrent changes without replacing those files. Brief hashes are kept
separate from executor/discovery hashes because task inputs differ.
The first pre-inference step captures the initial effective prompt hash; every step
and the final prompt are compared with it. Full and static hashes must both be
compared between controlled runs. Hermes still includes the conversation date, so
comparisons on different dates must disclose that difference instead of claiming
an unchanged complete prompt.

The default and maximum operation allowance is **20 model requests and 600 seconds**.
Phase 4 shares that allowance between debugger calls and Hermes requests. The bridge
also keeps its own cumulative session counter and monotonic deadline; continuation
cannot reset either. Its per-segment allowance can only consume the remaining total.
The root supervisor supplies the current remaining time/requests after debugger work.

Hermes's ordinary iteration counter is insufficient for this guarantee: the installed
version resets it on `run_conversation`, swallows ordinary step-callback exceptions,
and can request an extra summary after exhaustion. Epoch therefore instruments HTTPX
transport inside its child and requires a parent acknowledgment immediately before
each model POST is dispatched. This covers normal, retry and summary requests; the
hook reads no request body or credentials. The parent's `before_model_request`
callback can reject admission when the shared debugger/executor allowance is gone.
No acknowledgment means no request dispatch. `executor.model_request` records an
admitted request, and results return segment `turns_used` and cumulative
`session_turns_used`; progress `executor.step` is not the spending counter.

Per-run `agent.api_max_retries: 1` selects one application attempt, and
`HERMES_STREAM_RETRIES=0` disables stream retries. The installed Hermes request client
sets OpenAI SDK `max_retries=0`; the HTTP gate also counts a future SDK retry if one
occurs. This transport integration is verified only for the inspected installed
HTTPX-based route. Cancellation and timeout terminate only the run worker and its
process descendants. A failed/timed-out run can have partial effects; trusted
state checks and idempotent operations must determine what happened before retry.
These limits do not provide secure arbitrary-code isolation or a guaranteed dollar
spend cap. No generated candidate code runs in Phases 3 or 4.
Abrupt parent/worker crash containment has not been demonstrated against a real
model and is not guaranteed by an OS job or container. Startup recovery records
interrupted runs; stronger process-crash containment remains future work.

Executor completion is not task success. The trusted sandbox evaluator checks saved
business objects after execution. The healthy workflow and deliberately broken
checklist workflow must both be demonstrated using actual Hermes before Phase 3 is
marked complete. See the [validation record](../../docs/status.md), which distinguishes
test doubles, installed execution and unverified integrations.

## Verified source interfaces

This adapter was checked against the local checkout's `run_agent.py`,
`agent/agent_init.py`, `agent/turn_facade.py`, `agent/turn_context.py`,
`agent/turn_iteration_prep.py`, `agent/turn_finalizer.py`,
`agent/client_lifecycle.py`, `agent/chat_completion_helpers.py`, `agent/tool_executor.py`,
`hermes_cli/runtime_provider.py`, `tools/mcp_tool_discovery.py` and
`tools/mcp_tool_registration.py`. Those sources establish the constructor callbacks,
bounded conversation API, explicit credential route and `mcp-epoch` toolset naming.
The upstream [MCP documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)
describes the integration surface; local run evidence establishes compatibility with
the installed commit, not every future Hermes version.
