# Integration verification and remaining checks

**Local sandbox services, MCP, actual Hermes and opt-in OpenAI Luna supervision are implemented.** Installed Hermes has executed both the healthy release workflow and the deliberately broken checklist workflow. Trusted checks inspect simulated application state independently of Hermes's completion message. The [status record](status.md) records final acceptance, run identifiers and remaining limitations; checked items below describe only demonstrated scope.

Neatlogs, Raindrop Workshop and live Jira/Notion/Slack connections remain unimplemented and unverified. Phase 5 generated checklist repair uses the local Linux Docker runner; see [repair setup](../backend/docs/REPAIR_SETUP.md) and [validation](status.md). Anushrut owns the separate UI. Backend setup, simulation commands and execution entrypoints are in the [backend README](../backend/README.md); provider isolation and installed-source verification are in [Hermes setup](../backend/docs/HERMES_SETUP.md).

## Dated official references from the direction

The supplied direction records these official sources as checked on **September 6, 2026**. That historical reference list is preserved here; links alone do not establish Epoch compatibility. Phase 3 additionally inspected the installed Hermes source and exercised its actual MCP client and executor. The other vendor integrations still require installed-version verification.

| Intended area | Official sources cited in the supplied direction | Pending verification |
| --- | --- | --- |
| Hermes tool access | [Tools Runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime) | Initial scoped MCP connection verified; broader versions/providers remain unverified |
| Hermes capability updates | [MCP documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp) | Fresh-process discovery verified; publication, refresh notifications and newly generated capabilities remain unimplemented |
| Neatlogs capture | [Python SDK](https://docs.neatlogs.com/sdk/python), [Integrations](https://docs.neatlogs.com/integrations) | Actual model/tool/context coverage, correlation and data routing |
| Raindrop Workshop | [Workshop overview](https://www.raindrop.ai/docs/workshop/overview/) | Trace access, explicit interoperability and configured safe replay |
| Illustrative Notion adapter constraint | [Page property values](https://developers.notion.com/reference/page-property-values), [Page](https://developers.notion.com/reference/page) | Selected contract/version and simulation fidelity; live adapter deferred |

Task 02 now supplies local traces and trusted checks. Phase 3 covers the actual-executor portion of Task 03; Phase 4 adds supervision and additive feedback; see the current status for actual acceptance. Task 07 still owns future Neatlogs/Workshop wiring. Local traces do not satisfy those vendors' integration acceptance.

## Current installed execution record

- **Executor:** native Windows Hermes checkout `7166071fcaadb36df26f6d753dda97da6b5d699e`, using its existing Python environment through `run_agent.AIAgent`. No Hermes source, global configuration or credentials were changed by Epoch.
- **Connection:** MCP Python SDK `1.29.1`, stdio transport. Hermes is granted only `mcp__epoch__discover_tools`, `mcp__epoch__describe_tool` and `mcp__epoch__invoke_tool`. Supported per-run configuration disables Hermes's optional tool-search wrapping and MCP resource/prompt utilities.
- **Provider:** the user's existing `openai-codex` route, `gpt-6-astra`, `https://chatgpt.com/backend-api/codex`, retaining configured inference options. Synthetic briefs, tool schemas, tool results and visible assistant messages go to this remote provider. Business writes remain in local SQLite simulations.
- **Credentials:** the worker reads the existing selected access token into memory; no token is placed in Epoch config, request JSON or emitted events. It performs no login or token refresh. The current route has installed execution evidence; the adapter's other supported API-key routes remain unverified.
- **Evidence:** [recorded Phase 2 simulation results](../backend/fixtures/sandbox/phase2_evidence.json), [real stdio protocol tests](../backend/tests/test_mcp_server.py), [registry checks](../backend/tests/test_tool_registry.py), [bridge tests](../backend/tests/test_hermes_bridge.py), and the [final runtime validation record](status.md). Bridge tests use an explicit test double and cannot substitute for the actual model runs.
- **Debugger:** exact `gpt-5.6-luna`, structured output, no business tools. The existing Codex route has an actual probe; the API-key route has transport tests only. See [debugger setup](../backend/docs/DEBUGGER_SETUP.md).
- **Limits:** at most 20 shared debugger/executor provider requests and 600 seconds per explicitly submitted operation; parent admission precedes every Hermes request, including retries and final summaries. Cancellation and process cleanup preserve partial state. Phase 5 adds opt-in Docker-isolated serializer repair with separately bounded verification runs and an overall 60-request/1,800-second ceiling. There is no guaranteed monetary spend cap or claim of full model-provider telemetry.

The original acceptance pair performed the expected business operations but exposed prompt differences caused by run paths and Git-status snapshots. Supported configuration was corrected before final acceptance. Two discovery-only probes with separate fresh homes then produced byte-identical full prompts. The [final actual-run evidence](../backend/fixtures/hermes/README.md) records passing control and expected defective outcomes with all 12 compared baselines present and equal, including initial/full/static prompt hashes, model settings, implementation, discovery and initial briefs. Earlier failed or unequal-baseline attempts are preserved separately.

## Verification record for every integration

Apply this template separately to each future integration; it is not a claim that all integrations below are complete. The current Hermes/MCP record is above.

- [ ] Record the exact package/tool version or commit, documentation URL and access date, configuration, and environment used.
- [ ] Identify what data leaves the machine, which endpoint receives it, and what access is granted. Keep secrets out of committed artifacts and traces.
- [ ] Define success, expected failure, timeout, denied-access, and missing-evidence checks before executing them.
- [ ] Retain reproduction commands, run/task identifiers, relevant sanitized inputs/outputs, and inspectable effect evidence.
- [ ] State whether the result is documentation review, local simulation, installed-version execution, or a live provider test. Mark every unchecked item unverified.
- [ ] Record unavailable capabilities and a bounded fallback. Do not silently substitute a different executor or tracing system and retain the original claim.

## Hermes executor and discovery

- [x] Connect the installed Hermes executor through the selected stdio MCP interface and perform actual simulated business operations.
- [x] Verify permission-scoped discovery, descriptions/schemas, successful invocation, invalid arguments and denied access through registry/real-stdio tests. Actual Hermes runs additionally demonstrate the healthy workflow and seeded failure; no claim is made that Hermes itself exercised every denied-access case.
- [x] Record implementation, model/inference options, discovery definitions, fresh memory state and initial/final effective prompt hashes. Flag implementation, user-setting or prompt changes during execution.
- [x] Prove those executor/configuration boundaries remain fixed across a generated repair and later-session publication. Actual Phase 5 original/fresh/later comparisons are retained in [status](status.md#phase-5-validation-record).
- [x] Deliver an explicit developer-authored structured brief and capture observable messages, tool calls/results and errors under correlated task/run identities. Private reasoning is not exported.
- [ ] Implement and verify automatic checkpoint planning, bounded targeted continuation and user-feedback revisions. Record those interventions separately and retain equivalent initial briefs/checks for environment comparisons.
- [ ] Publish a verified new capability and show Hermes discovers and invokes it through the same interface, without an executor or per-tool prompt edit. Test in a fresh executor session as well.
- [ ] Verify version selection and activation at a safe boundary. If runtime tool-list notifications are selected, test their actual delivery, cache refresh, and callable results; a new file or notification alone is insufficient.
- [x] Report unavailable Hermes and incomplete execution explicitly; never substitute a fake executor in the live execution path. Test doubles remain limited to component tests.

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

- [x] Persist inspectable local tickets, checklists, messages, directory records and runbooks. Returned references and reports are explicitly simulated.
- [x] Seed a checklist adapter with a real service-contract shape violation. Verify that the failed call creates no checklist, preserves the already-created ticket and fails trusted outcome checks.
- [ ] Implement generated QA-owner lookup and exercise successful, absent and ambiguous owner outcomes. Directory fixtures and a missing-capability scenario exist; the lookup tool intentionally does not.
- [x] Preserve current/historical runbooks, project/version/approval metadata and the actual supplied documents. Test current and historical selection plus the deliberately outdated-context scenario.
- [x] Reset equivalent fixture state, retain earlier trace evidence, reject cross-run access, and prevent duplicate ticket/checklist/message effects on repeated operations. Generated-candidate replay remains future work.
- [x] Keep fault selection and trusted expected outcomes out of the business tool surface. Tests reject administrative tools and verify that business outputs do not expose fixture selection or trusted answers.
- [ ] Validate the future debugger's investigation grants and candidate filesystem isolation. Current simulators are not secure arbitrary-code isolation.

## Future live services and model routing

Live business-service checks require a separately authorized scope and are not needed to claim local simulated effects. Model inference already uses the existing configured remote provider as described above.

- [ ] For Jira, Notion, Slack and a directory service, verify actual tenant permissions, API versions, tool contracts, identity resolution and failure behavior. The illustrative Notion constraint in the direction is not an implemented adapter contract.
- [ ] Before a live write or continuation, define and test how completed side effects are identified, reconciled and protected from duplicates after timeouts or retries.
- [ ] Verify provider state and actual returned object references before claiming a ticket, page or message was delivered. Do not substitute simulated URLs.
- [x] Document the current model-provider choice, data routing, available call-count evidence, usage-measurement gaps and credential handling before actual inference. Generated repairs cannot acquire credentials or enlarge access.

## Completion rule

Only checked items with reproducible execution evidence can support runtime compatibility claims. Partial integrations stay partial in [status](status.md). Preserve the complete verified local loop if integration breadth must shrink, and state exactly what was omitted.

## Phase 6/7 development status

Generated directory/retrieval code and runtime verification gates are implemented
but untested by explicit user instruction. They use the same local simulations,
Docker image and existing Luna/Hermes route; no new live integration is claimed.
See [handoff](../backend/docs/PHASES_6_7_HANDOFF.md) before integration.
