# General chat and explicit debugger

The September 6 user correction separates ordinary Hermes conversation from the
release demonstration. This is the current assigned scope and supersedes the
earlier default release-intake presentation. The original direction is unchanged.

1. Keep `/chat` as a durable conversation with Hermes. Sending a message must not
   create a release task, run the release supervisor, or invoke the debugger.
2. Open the debugger for the selected conversation. An explicit investigation
   action submits the user's question with the saved conversation and observable
   tool evidence. Preserve the user's original requirements as evidence.
3. Retain release execution and its trusted criteria in a separately labeled
   example. Generic investigation must not claim those checks evaluate arbitrary
   tasks or grant permission to publish arbitrary repairs.
4. Check API isolation, exact retries, navigation and the chat/debugger browser
   flow with local test actors. Record actual results and provider-test limits.

Work is split across backend chat/investigation, frontend interaction, frontend
regression tests, and documentation/integration review. Existing uncommitted work
and unrelated telemetry configuration changes are preserved.

The later [CSV repair assignment](CSV_REPAIR_PLAN.md) extends explicit investigation
for that supported environment to include verified mapping publication and Hermes
recovery. It does not add automatic triggering to ordinary chat.


## Follow-up: startup failure and idle polling

Trace the recorded bridge RuntimeError before changing behavior. Correct only the
integration startup mismatch supported by installed-source evidence, preserving
Hermes and its credentials. Stop unconditional idle/runtime polling; retain active
operation updates, visibility recovery and exact write identities. Verify the
startup boundary without model inference and run focused polling/browser tests.
