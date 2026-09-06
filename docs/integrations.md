# Intended integration verification checklist

**All integrations are unimplemented and unverified in Epoch.** This is a future checklist, not a record of completed tests. The [preserved source notes](direction.md#source-notes) record vendor documentation references checked for the direction document. This foundation has not repeated those external checks or tested installed versions.

Use Python and local simulated services first. Task 01 selects libraries, schemas, storage, and transport after checking the required contracts. A graphical interface and live business-service connections are deferred. A local interface does not mean model inference is local; provider selection and data routing must be explicit.

## Verification record for every integration

- [ ] Record the exact package/tool version or commit, documentation URL and access date, configuration, and environment used.
- [ ] Identify what data leaves the machine, which endpoint receives it, and what access is granted. Keep secrets out of committed artifacts and traces.
- [ ] Define success, expected failure, timeout, denied-access, and missing-evidence checks before executing them.
- [ ] Retain reproduction commands, run/task identifiers, relevant sanitized inputs/outputs, and inspectable effect evidence.
- [ ] State whether the result is documentation review, local simulation, installed-version execution, or a live provider test. Mark every unchecked item unverified.
- [ ] Record unavailable capabilities and a bounded fallback. Do not silently substitute a different executor or tracing system and retain the original claim.

## Hermes executor and discovery

- [ ] Verify one-time connection to the chosen environment interface with the installed Hermes version. The direction mentions generic discovery functions, Model Context Protocol (MCP), or a thin adapter as options, not selections.
- [ ] Show permission-scoped discovery, tool description and invocation requirements, successful invocation, validation failure, and denied access.
- [ ] Capture executor implementation, system prompt, model configuration, discovery interface and controlled memory state before the experiment; prove they stay fixed across repair.
- [ ] Publish a verified new capability and show Hermes discovers and invokes it through the same interface, without an executor or per-tool prompt edit. Test in a fresh executor session as well.
- [ ] Verify version selection and activation at a safe boundary. If runtime tool-list notifications are selected, test their actual delivery, cache refresh, and callable results; a new file or notification alone is insufficient.
- [ ] If Hermes cannot be used, report the blocker. A test double may validate a component but cannot establish Hermes compatibility or the final repair claim.

## Neatlogs instrumentation

- [ ] Verify the installed Python integration and supported model-client wrapping against the selected provider and version.
- [ ] Deliberately instrument custom tool calls, retrieval and application-state checks; identify uncaptured paths and failed calls.
- [ ] Correlate task/run identities across model activity, tool execution, retrieved context, errors and results without claiming access to private reasoning.
- [ ] Test capture failures, redaction, data routing and retention. Show how missing evidence is surfaced to the debugger and report.
- [ ] Retain an actual trace demonstrating the necessary boundaries; installing an SDK is not complete instrumentation.

## Raindrop Workshop and trace interoperability

- [ ] Verify local setup and the exact trace formats Workshop can inspect. Check how authorized coding-agent access is scoped.
- [ ] Explicitly connect Epoch/Neatlogs task and run identifiers to Workshop evidence. Test whether an adapter is required; do not assume either product automatically imports the other's traces.
- [ ] Configure replay against reset isolated simulated state and verify which inputs, code versions, context and evaluator are reused.
- [ ] Demonstrate that replay actually executes the workflow and retains outcomes, rather than only displaying a recorded trace.
- [ ] Verify permission boundaries and failed replay reporting. If interoperability or replay setup is unavailable, keep it unverified and distinguish any local harness evidence from Workshop evidence.

## Local business simulations

- [ ] Provide inspectable local ticket, checklist/page, message, directory and runbook state. Label reports and object references simulated.
- [ ] Seed the release adapter defect with a meaningful contract violation. Test resulting state, not only an exception string.
- [ ] Exercise successful, missing and ambiguous QA-owner lookup using varied project/owner records.
- [ ] Preserve current and historical runbooks with scope/version/approval metadata. Verify current release behavior and historical questions.
- [ ] Restore equivalent starting state for baseline/candidate comparisons, including partial-success cases; detect duplicate objects and messages.
- [ ] Keep fault seeding and trusted expected outcomes separate from debugger-readable diagnosis inputs. Do not leak a reference patch or fixture-to-repair mapping.

## Future live services and model routing

These checks require a separately authorized scope; none is performed in this foundation or required to claim local simulated effects.

- [ ] For Jira, Notion, Slack and a directory service, verify actual tenant permissions, API versions, tool contracts, identity resolution and failure behavior. The illustrative Notion constraint in the direction is not an implemented adapter contract.
- [ ] Before a live write or continuation, define and test how completed side effects are identified, reconciled and protected from duplicates after timeouts or retries.
- [ ] Verify provider state and actual returned object references before claiming a ticket, page or message was delivered. Do not substitute simulated URLs.
- [ ] Document model-provider choice, data routing, available usage measurements and credential handling before enabling inference. Generated repairs cannot acquire credentials or enlarge access.

## Completion rule

Only checked items with reproducible execution evidence can support runtime compatibility claims. Partial integrations stay partial in [status](status.md). Preserve the complete verified local loop if integration breadth must shrink, and state exactly what was omitted.
