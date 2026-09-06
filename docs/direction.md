# Direction: An agent debugger that improves the environment

**Project:** Syndicate hackathon, Track 1: Automated Agent Engineering  
**Build window:** 10 hours  
**Status:** Product direction, not a claim that these capabilities are already implemented  
**Updated:** September 6, 2026

## 1. What we are building

We are building a debugger agent that attaches to a working agent environment, observes what happens, identifies why a task failed, and makes a verified, persistent improvement to that environment.

The user interacts with **Hermes**, the agent doing their work. Hermes discovers available tools, understands how to use them, calls them, and responds to the user. Our debugger observes the conversation and the execution behind it. When it has evidence of a failure, it investigates and repairs the tools or context that Hermes depends on.

The central product promise is:

> The agent fails at a real task. The debugger finds the cause, changes the environment, verifies the repair, and makes that improvement available to future runs without rewriting the agent.

The debugger has three responsibilities:

1. **Repair existing tools and execution problems.** Fix a faulty tool implementation, interface, or environment-controlled execution behavior.
2. **Create missing tools.** Generate, test, and publish a capability that the task needs but the agent cannot currently access.
3. **Improve the context supplied to the agent.** Correct retrieval and filtering so irrelevant, outdated, or incorrectly scoped information does not keep causing the same failure.

These are three possible responses within one debugging loop, not three unrelated products.

## 2. Why this fits the track

The organizers' guidance shared in our discussion emphasizes agents that improve over time through tool use, reflection, memory, and learning complex contextual logic. The broader track description also asks for measurable improvements in accuracy, reliability, cost, and speed, with demonstrations across distinct domains.

Our chosen focus is the improvement loop: a fixed executor becomes more capable and reliable because the environment around it changes in response to observed failures.

For this build, we will demonstrate one coherent workflow with multiple failure types and fresh task variations. We should not describe three failures in one workflow as three separate domains, or claim automatic agent-architecture generation when we have only implemented environment repair.

The strongest evidence is not a paragraph saying the system learned. It is a changed tool or context policy, passing verification, and a later task that benefits from the change.

## 3. The product boundary

### Hermes is the executor

Hermes is the agent the user talks to. It interprets the request, plans the task, discovers capabilities, uses tools, and reports results. It remains responsible for performing the business workflow after a repair.

We do not replace Hermes with the debugger whenever a task gets difficult. Otherwise, we would demonstrate a second agent doing the work, not the original agent improving through a repaired environment.

### The debugger is an attached maintenance agent

The debugger observes the instrumented environment and has permission to inspect and repair a limited part of it. It can inspect traces, read editable tool code and API documentation, propose changes, execute isolated tests, and publish approved repairs.

It may run Hermes in a test environment to verify a candidate. It should not independently complete the user's business task and present that as evidence that Hermes improved.

### The environment owns the business tools

Tools live in a shared registry within the authorized workspace. They are not individually embedded into each agent's prompt or copied into each agent's implementation.

Every executor has four basic abilities: discover which tools are available, read what each tool does, inspect its invocation requirements, and call it. The exact number of functions exposing these abilities belongs in the technical plan.

After the debugger publishes a tool, Hermes discovers it through the same interface it already uses. No per-tool patch to Hermes is required.

“Shared” does not mean unrestricted access across users or organizations. Discovery and execution remain permission-scoped. The debugger uses the same general access pattern but has additional, restricted maintenance permissions.

## 4. What stays fixed and what can change

During a repair experiment, keep the Hermes implementation, system prompt, model configuration, and baseline discovery interface unchanged. One-time integration and permission configuration are allowed; repeated edits to the executor are not the learning mechanism being demonstrated.

The debugger may change tool implementation code, tool descriptions and schemas, bounded tool-side execution behavior, the set of registered tools, retrieval/filtering rules, and persistent repair records.

It must not change the user's request, silently weaken success criteria, rewrite the evaluator to accept its patch, conceal failed traces, or grant itself new permissions.

A tool-side workflow repair is in scope when the environment genuinely owns that behavior. An error entirely inside Hermes' planning logic may be diagnosed as outside the current repair boundary. We should report that honestly rather than quietly editing Hermes and claiming otherwise.

The intended flow is:

```text
User <--> Hermes <--> Shared tools <--> Connected apps / sandbox services
             |             |
             +------ Instrumented execution ------+
                                                  |
                                      Debugger investigation
                                                  |
                              Candidate tool / context change
                                                  |
                               Isolated tests + Hermes rerun
                                                  |
                                Publish verified environment
                                                  |
                                     Future Hermes tasks
```

The debugger is logically separate from task execution. It is not an unrestricted process above all security boundaries.

## 5. How the debugger knows what should have happened

The debugger needs a standard for success. It does not necessarily need an exact, prewritten final answer.

That standard comes from the user's request, explicit conversation constraints, authoritative workspace information, tool contracts, observable application state, and any later user correction.

For example, “Create the release ticket, add its checklist to Notion, and notify QA with both links” supplies concrete expectations. We can check whether those objects exist, whether their contents match the requested release, whether the notification reached the right destination, and whether it contains the actual links.

The system should form a compact set of success conditions before checking the outcome. Each condition should retain its source: the user, an identified policy document, or a tool contract. Inferred requirements remain distinguishable from explicit ones.

For the hackathon, known test cases may have manually authored acceptance checks. That is a controlled evaluation setup, not a hardcoded repair. The debugger must still inspect the actual failure and produce the environment change.

User feedback can supply missing information. If the user tells Hermes, “You notified the release channel; I asked for the QA owner,” the debugger can associate that correction with the preceding run. The user does not need to reconstruct the trace or talk to a separate debugger persona.

A correction is evidence to investigate, not proof of a code defect. The user may be changing the goal, expressing a preference, or referring to information the system never had. When the intended outcome cannot be established, report that uncertainty or ask through Hermes. Do not invent a requirement and repair against it.

## 6. How debugging starts

The target demonstration is **automatic triggering followed by a bounded repair loop**. The user should not have to open a debugger and manually describe every failed step.

Triggers can include a tool error, a failed acceptance check, a missing required capability, a contradiction between claimed success and application state, or an explicit correction in the user–Hermes conversation.

A lightweight detector can watch these signals while the more expensive debugger runs only when needed. We do not need to continuously analyze every token.

Under the time constraint, deterministic triggers are acceptable. A tool error or a phrase such as “that is not what I asked for” can initiate an investigation. Such rules detect a possible problem; they must not select a prerecorded diagnosis, install a fixed answer, or manufacture a passing result.

Do not build the product around detecting whether the user is angry. Objective failure signals and explicit corrections are more useful than assumptions about emotional state.

A manual “Investigate this run” control can remain available, but the main demo should show at least one investigation starting without that click. The autonomy claim applies only to the configured environment, supported triggers, and permitted repairs.

## 7. The complete learning loop

### Observe

Record the request, relevant conversation, tools visible to Hermes, tool descriptions and versions, calls and arguments, results and errors, retrieved context, final response, and available application-state evidence. Associate them with the same task and run.

Capture observable inputs and outputs. Do not assume access to private model reasoning or uninstrumented activity. When evidence is missing, the diagnosis should say so.

### Evaluate and investigate

Compare the result with the success conditions. Trace a failed condition back through the relevant calls and context. Separate the immediate error from its likely cause.

“Notion was not updated” is an observed failure. “The adapter converted valid inputs into an invalid request body” is a candidate explanation supported by the tool trace and implementation.

### Choose and stage a repair

Decide whether this is an existing-tool repair, missing-tool creation, context repair, or something outside the current scope. Prefer a small, evidence-backed change over changing several unrelated parts at once.

Create the candidate in an isolated version of the environment. Record what changed and why.

### Verify

Check the changed component, rerun the failed task safely, and test a fresh variation. Check that previously passing behavior still works.

Use application state and tool results where possible, not only a model's opinion of its own answer. The debugger can propose additional tests, but cannot alter the trusted checks used to decide whether its repair succeeded.

### Publish and retain

Only a verified candidate becomes active. Preserve the previous version for rollback and record which version each run used. Activate changes at a safe execution boundary rather than silently replacing code during an in-flight call.

Persist the actual repair and its evidence. Later tasks must use it through normal discovery or retrieval, not because the entire debugging conversation is pasted into their prompts.

### Stop when necessary

Bound repair attempts, time, and cost. A failed patch stays rejected. Missing permissions, unavailable evidence, or unresolved ambiguity produce a clear limitation report rather than an endless retry loop.

## 8. Responsibility one: repair an existing tool

This is the technical repair demonstration. It must be stronger than remembering to perform a forgotten step.

The debugger should be able to inspect a failing tool implementation, identify the mismatch between the intended operation and actual request or result, produce an executable correction, test it, and publish a new version.

Potential repair surfaces include request serialization, response parsing, incorrect argument schemas, stale field mappings, and bounded execution behavior owned by the tool layer.

The tool must still perform the real operation. Replacing an error with a successful-looking response is not a repair.

The durable outcome is a corrected tool available to future calls. A written reminder such as “be careful when using Notion” is not sufficient.

## 9. Responsibility two: create a missing tool

Sometimes the available tools cannot perform an operation the task requires. The debugger should first check that the capability is genuinely absent, rather than merely undiscovered or poorly described.

Tool generation requires an underlying resource: an existing API, an authorized service, a library, or a permitted composition of existing operations. The debugger cannot create credentials, permission scopes, unavailable data, or a third-party capability that does not exist.

Within that boundary, it can write a small adapter, define its description and input/output contract, test it, and register it. The executor then discovers and uses it normally.

The demonstration must distinguish generating an executable adapter from simply enabling a prewritten hidden tool. Existing scaffolding is acceptable, but we should show what code and contract the debugger actually produced.

A published tool should handle missing or ambiguous results honestly. It must not guess an identity or fabricate data merely to complete the task.

## 10. Responsibility three: improve the supplied context

A run may use functioning tools and still fail because its retrieved information is outdated, irrelevant, or scoped to the wrong team or workflow.

The debugger should inspect the context Hermes actually received, identify evidence that it was unsuitable, and test a change to the environment's retrieval or context assembly.

For this build, that can mean prioritizing current approved documents, respecting workspace and workflow scope, excluding unrelated results, deduplicating repeated information, or exposing source/version metadata more clearly.

Do not permanently delete source documents just because they were unhelpful for one request. An old runbook may be necessary for a historical question. Change what gets supplied for the current task while retaining original evidence.

Do not claim that a document caused a failure merely because it appeared in the prompt. Treat that as a hypothesis and compare behavior after a targeted change. Preserve required constraints and regression-check questions that still need the excluded material.

The objective is correct task-relevant context. Fewer tokens are a possible secondary benefit, not proof of improvement by themselves.

## 11. The concrete demonstration

### Shared business workflow

Use a release-preparation task that a nontechnical observer can understand:

> Prepare release v1.4 for QA. Create its Jira ticket, add the release checklist to Notion, and notify QA with links to both.

The user expects the right ticket, the right checklist, the right notification, and an accurate completion report. They should not need to understand API payloads or registries to see whether the workflow succeeded.

Use three controlled scenarios around this workflow. Initially isolate the failure types so the audience can understand each cause and repair. These are proposed demonstration fixtures, not results we have already achieved.

### Scenario A: the tool exists but its implementation is broken

**Run one:** Hermes creates the Jira ticket. It calls the Notion tool with valid business inputs, but the adapter constructs an invalid page-property payload. The Notion step fails and the checklist does not exist. Changing the release title in the prompt cannot fix a defect inside the adapter.

Notion's API uses typed page-property values, and pages within a data source must conform to that source's property schema. This is the real interface constraint behind the proposed fixture; the exact payload and API version belong in the technical plan.[^notion]

**Debugger action:** A tool error or failed outcome check triggers investigation. The debugger inspects the adapter and returned validation evidence, corrects the serialization, and tests it. It does not modify Hermes' prompt or hardcode the current release title.

**Run two:** In an isolated rerun, the same task produces the ticket, Notion checklist, and notification correctly. For a live continuation, reuse already completed work rather than creating duplicate tickets or notifications.

**Run three:** A fresh request for release v1.5 uses the corrected adapter and succeeds without another repair.

**What the audience sees:** A failed Notion step, the actual code change, verification evidence, and a later release succeeding with unchanged Hermes configuration.

### Scenario B: the required capability is missing

**New request:** “Prepare release v1.6, and send the handoff directly to the QA owner assigned to this project.”

**First attempt:** Hermes can send a Slack message when supplied with a user ID. However, no exposed tool can resolve the project's QA owner to that ID. An authorized workspace directory service exists, but Hermes has no adapter for querying it. The run cannot satisfy the request without guessing or asking the user to do the lookup.

**Debugger action:** It verifies that owner lookup is absent from the available tools, reads the directory service contract, and generates a small lookup adapter. It tests successful, missing, and ambiguous matches, then publishes the new tool with a usable description and schema.

**Next attempt:** Hermes discovers the added tool, looks up the project's current QA owner, and uses the existing Slack tool to send the handoff.

**Later task:** Another project has a different owner. The same generated tool resolves that owner from directory data, demonstrating that the first person's identity was not hardcoded.

**What the audience sees:** The missing capability, generated adapter, changed tool list, and Hermes selecting and using the new tool without an executor edit.

### Scenario C: the tools work, but the context is misleading

**New task:** Prepare another release and notify the appropriate QA destination under the current workflow.

**First attempt:** Retrieval returns an outdated release runbook alongside the current approved one. The old runbook points to a previous notification channel. Hermes follows it, and the message is delivered successfully to the wrong destination. No API exception is required for this failure.

**Debugger action:** A trusted outcome check or user correction identifies the mismatch. The debugger examines the supplied documents and their metadata, proposes a scoped retrieval change that prefers the current approved runbook, and verifies the new behavior.

**Next attempt:** Hermes receives the appropriate current guidance and sends the notification to the correct destination.

**Later task:** A historical question still retrieves the older runbook when it is relevant. This checks that the system learned a scoped retrieval rule rather than deleting all old information.

**What the audience sees:** The misleading context, the retrieval-policy change, and correct behavior on both a new release and a historical question.

## 12. What qualifies as learning

A successful rerun is necessary but insufficient. It might result from chance, leftover application state, or an answer specific to the original input.

For this product, learning means an evidence-backed environment change persists and improves later behavior. The baseline and repaired comparisons should use equivalent starting state and the same executor configuration. Fresh-task tests should change meaningful inputs, not just repeat the original prompt.

Start later demonstrations in a fresh executor session where practical. Keep unrelated Hermes memory and skill updates controlled during evaluation so they do not confound the claimed effect of our debugger.

Repair records should preserve the triggering task, failed condition, supporting trace steps, diagnosis, changed component, scope, verification results, and active version. Store rejected attempts as failed attempts, not successful lessons.

The executable tool or retrieval rule is what changes future behavior. The repair record explains and audits that change.

We should say “this failure did not recur in the tested variations,” not promise that it can never happen again.

## 13. Expected product experience and outputs

The user remains in the Hermes conversation. A visible activity panel can show that a failure was detected, what is being investigated, which change is under test, and whether verification passed. A developer can expand the underlying trace and diff.

The main screen should make three things easy to compare: the requested outcome, what actually happened, and what changed between runs. Do not hide the technical repair; put its plain-English explanation first and the executable evidence one level deeper.

After an investigation, the debugger should produce a concise repair report covering the failed expectation, supporting evidence, proposed cause, exact environment change, verification outcome, and persistence or rollback status.

A successful task should show real object links or inspectable sandbox state. A failed or incomplete task should say which condition remains unmet.

The final demo should visibly connect:

> Failed outcome → diagnosis → actual environment change → verified rerun → success on a fresh task.

An animated sequence without the corresponding executions and artifacts is not the product.

## 14. Light technical direction and integration roles

The minimum system needs an executor integration, a shared tool registry, trace capture, an event-triggered debugger, isolated candidate testing, outcome evaluation, persistent environment versions, and a small interface showing the loop. Detailed frameworks, schemas, routes, and repository layout belong in a separate technical plan.

### Hermes

Hermes is the initial executor, not a new agent framework we are building. Its documentation describes a central tool registry and dispatch system.[^hermes-tools]

Its MCP documentation also describes runtime tool-list updates through server notifications.[^hermes-mcp] That supports the direction, but dynamic discovery must still be tested with the installed version and our registry bridge. Adding a file is not enough unless the new capability actually becomes visible and callable to Hermes.

The desired contract is an unchanged discovery interface connected once to our environment. Whether that uses generic discovery functions, MCP, or a thin adapter is an implementation decision.

### Neatlogs

Neatlogs is the intended tracing/instrumentation integration. Its SDK supports wrapping model clients and adding spans to custom functions; custom tool and retrieval boundaries still need deliberate instrumentation.[^neatlogs]

Use captured execution evidence to support diagnosis and inspection. Do not assume that adding an SDK automatically exposes every relevant part of Hermes or our environment.

### Raindrop Workshop

The local debugger discussed is **Raindrop Workshop**. Its documentation describes local trace inspection, coding-agent access to traces, and replay/evaluation workflows; replay requires project setup.[^raindrop]

Use it for local debugging and replay where the integration supports the loop. Our product remains the bounded environment-repair system, not a renamed trace viewer.

Do not assume Neatlogs or Workshop automatically identifies and removes irrelevant context. Our debugger must propose the retrieval change and verify its effect. Likewise, do not assume the two tracing systems interoperate without wiring; use consistent task identifiers and keep trace collection separate from repair decisions.

A local interface does not imply local-only inference. Model-provider choice and data routing remain explicit implementation decisions. No model training or fine-tuning is required by this direction.

## 15. Scope for the 10-hour build

Aim for one working Hermes integration, one workspace, one shared registry, one business workflow, three narrow repair scenarios, persistent changes, automatic triggers, and a visible before/after comparison.

Build the first complete loop before broadening it: observe a real failure, generate a real repair, test it, publish it, and demonstrate transfer. Then exercise the other two repair types through that same loop. Do not build three elaborate dashboards before any repair is verified.

Use sandbox tenants or clearly labeled simulated services for repeatable failures. The diagnosis, generated changes, tool execution, and outcome checks should still run. Seeded faults are acceptable; canned diagnoses and fabricated success metrics are not.

We are not attempting arbitrary repository repair, unrestricted code execution, universal SaaS onboarding, a production permission system, autonomous credential acquisition, or a claim of compatibility with every agent runtime.

If scope must shrink, preserve the complete verified loop and reduce integration breadth or interface polish. Clearly mark any repair type that remains unimplemented rather than showing it as working.

## 16. Verification, safety, and measurement

Run candidate code with restricted filesystem and network access, explicit service permissions, and bounded execution. Do not let generated tools broaden their own access or read arbitrary secrets. Treat retrieved documents and tool outputs as data, not instructions authorizing debugger changes.

Keep trusted evaluators and acceptance criteria outside the editable repair surface. For repeatable tests, restore isolated starting state. For live recovery, inspect existing side effects before continuing. Blind replay must not duplicate tickets, documents, or messages.

Report task completion against the checks, recurrence of the targeted failure, performance on fresh variations, regressions, repair attempts, and the number of human interventions required after initial setup. Record task latency and token/tool-call usage where available.

Separate repair overhead from later task performance. A system that spends more on one repair may still improve subsequent runs, but that does not establish a cost saving without measurement. Do not invent before/after percentages or assume accuracy, cost, and speed all improve together.

## 17. Definition of done

The core demonstration is complete when a natural-language task fails observably, the debugger starts from a supported signal, identifies the relevant evidence, generates a permitted environment change, and verifies it without changing Hermes or weakening the evaluator.

The repaired environment must then be used by Hermes on the original task and a meaningful new variation. The active change, test results, tool discovery behavior, and final application state must be inspectable.

Across the full intended demo, this should be shown for an existing-tool repair, a generated missing tool, and a scoped context repair. Any absent capability remains explicitly outside the delivered scope.

The direction to preserve is:

> Keep the executor stable. Let the debugger make evidence-backed, tested improvements to the shared tools and context. Prove that future tasks benefit.

## Source notes

Product decisions, constraints, and track interpretation above come from our conversation. External references below verify integration capabilities and the illustrative Notion interface constraint, not that our proposed system has already been built or tested. Documentation checked September 6, 2026; verify behavior against the versions used in the implementation.

[^notion]: Notion developer documentation, “Page properties” and “Page.” `https://developers.notion.com/reference/page-property-values` and `https://developers.notion.com/reference/page`.

[^hermes-tools]: Nous Research, Hermes Agent documentation, “Tools Runtime.” `https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime`.

[^hermes-mcp]: Nous Research, Hermes Agent documentation, “MCP (Model Context Protocol),” especially runtime behavior and dynamic tool discovery. `https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp`.

[^neatlogs]: Neatlogs official documentation, “Python SDK” and “Integrations.” `https://docs.neatlogs.com/sdk/python` and `https://docs.neatlogs.com/integrations`.

[^raindrop]: Raindrop official documentation, “Workshop,” including replay setup and the local evaluation workflow. `https://www.raindrop.ai/docs/workshop/overview/`.
