# Intended architecture and data flow

**Design only: none of these runtime components exists yet.** Python is the future backend language and local simulated services come first. Rajdeep builds the backend with a CLI/test harness; Anushrut builds the Epoch UI in parallel after shared contracts are agreed. [Task 01](tasks/01-technical-plan.md) chooses libraries, concrete schemas, persistence, transport, and layout. The current [supervisor flow](../README.md#user-flow) records the later user decision; the original direction remains unchanged.

## Core idea

Epoch supervises delivery: it converts a request into sourced checkpoints and a structured brief, delegates execution to Hermes, evaluates progress, directs targeted continuations, and reports results. Hermes performs the business work. When the cause is environmental, Epoch investigates and repairs the authorized tools or context. The executor stays fixed during a repair experiment; initial briefs/checks remain equivalent and supervisory interventions are recorded separately so a later improvement can be attributed correctly.

For example, Hermes can submit valid release data to a tool whose adapter serializes it incorrectly. The debugger should change that adapter, then have Hermes use the corrected version to create an inspectable checklist. The debugger sending back a made-up checklist link would fail the product contract.

## Responsibility boundaries

| Component | Owns | Must not do |
| --- | --- | --- |
| Epoch UI / CLI harness | Submit requests and feedback; display checkpoints, outcomes, evidence and limitations | Invent checkmarks or present fixture playback as live execution |
| Task supervisor | Form sourced checkpoints and enhanced briefs; monitor observable progress; give bounded corrective instructions; report results and interpret user feedback | Rewrite user intent, silently weaken checks, or perform business operations instead of Hermes |
| Hermes executor | Interpret the request, discover and call tools, use supplied context, report completion | Become an editable repair target during an experiment |
| Shared registry and dispatch | Permission-scoped discovery, descriptions, invocation requirements, calls and version selection | Reveal or run tools outside the caller's grants |
| Business adapters and simulated services | Perform authorized operations and retain inspectable simulated ticket, page, message and directory state | Return success without the corresponding effect |
| Context assembly | Select relevant documents and expose source, version, scope and approval information | Delete original evidence to force a current answer |
| Instrumentation | Capture observable inputs, outputs, errors, context and application-state observations with correlated task/run identities | Claim access to private model reasoning or uncaptured activity |
| Trusted evaluator | Derive checks with requirement provenance; compare actual state with expected outcomes | Let candidate code edit the pass criteria or replace the trusted result |
| Detector | Turn supported errors, failed checks, missing capabilities or corrections into an investigation signal | Map a fixture label directly to a canned diagnosis or patch |
| Debugger | Inspect permitted evidence, form a diagnosis, stage an executable tool or retrieval change | Take over the business workflow or broaden its permissions |
| Candidate runner and publication controller | Isolate tests, enforce limits, evaluate candidates, publish verified versions and support rollback | Activate a failed candidate or change code during an in-flight call |
| Repair and evidence store | Retain actual changed artifacts, provenance, rejected attempts, results and active version history | Treat a narrative lesson alone as a persistent repair |

Neatlogs is intended for tracing; Raindrop Workshop is intended for local inspection and replay where verified. Their adapters must preserve these boundaries. Neither is assumed to provide repair decisions, complete instrumentation, interoperable traces, or ready-to-use replay. See the [integration checklist](integrations.md).

Basic local traces, context boundaries and trusted checks belong in Task 02. Task 03 connects actual Hermes to that existing evidence. Task 07 adds and verifies Neatlogs/Workshop interoperability; the repair tasks must already have inspectable local evidence before then.

## Information needs

These are information requirements, not executable schemas or selected storage formats. Task 01 makes those implementation choices.

| Record | Information it must make available |
| --- | --- |
| Tool contract | Capability and description, inputs and outputs, validation and error behavior, required permissions, side effects, version, and retry/duplicate-effect behavior |
| Run | Request and relevant conversation, task/run identity, executor baseline, visible tools and versions, supplied context and sources, calls/results/errors, final response, state observations, and missing evidence |
| Success condition | Expected outcome, source and whether explicit or inferred, relevant scope, observable check, result and supporting evidence or unresolved ambiguity |
| Repair record | Trigger and failed condition, evidence references, diagnosis and uncertainty, actual changed artifact, permitted scope, attempts and limits, trusted verification results, rejection/publication decision, active/prior versions and rollback history |

## Execution and repair flow

```text
User request / correction
          |
          v
      Epoch UI <---- outcome, checkpoint and repair report
          |
          v
      Supervisor: sourced checkpoints + structured task brief
          |
          v
        Hermes <---- scoped context assembly <---- retained documents
          |
          v
   scoped registry ----> versioned tool ----> local simulated service state
          |                    |                         |
          +---- observable execution evidence ----------+
                               |
                   trusted outcome evaluation
                               |
                    supported failure signal
                               |
                    bounded debugger investigation
                               |
                  isolated candidate environment change
                               |
             component tests + safe Hermes rerun + fresh variation
                               |
                       trusted verification gate
                        /                   \
               reject and retain        publish at safe boundary
                                             |
                               durable environment version
                                             |
                                  future Hermes session
```

1. The supervisor establishes success conditions from the user request, explicit constraints, authoritative documents, and tool contracts, then gives Hermes a structured brief. Retain each condition's source. Distinguish inferred conditions from explicit ones. Material ambiguity prompts a user clarification through the interface; do not invent a requirement.
2. Capture the tools and versions visible to Hermes, requests and responses, supplied context and its metadata, and final application state. An absent trace is an evidence gap, not proof that a step did not happen.
3. Evaluate observable outcomes at meaningful tool/step boundaries. A tool can succeed while delivering a message to the wrong destination. A skipped step can receive a targeted supervisor continuation that reuses completed work. Tool/capability/context defects enter the repair loop below. Do not depend on private thinking or token-by-token inspection.
4. Diagnose against actual evidence and editable code. Classify the candidate as existing-tool repair, missing-tool creation, scoped context repair, or outside the permitted boundary.
5. Stage the smallest supported change. The candidate cannot write to the executor, evaluator, acceptance criteria, permissions, baseline evidence, or unrelated files. Enforce filesystem, network, service, attempt, time and cost limits outside generated code.
6. Verify the component, rerun from equivalent isolated starting state, exercise a meaningful new input, and check previously passing behavior. Preserve every result, including rejected attempts and missing measurements.
7. Publish only on trusted checks passing. Persist the artifact and evidence, preserve the prior version, and activate at a safe boundary. Each run must identify its environment version. Test rollback and use from a fresh executor session.

After checkpoints pass, return the result and evidence to the user. Dissatisfaction can reveal an evaluation mistake, omitted requirement, or new preference. Preserve the prior intent/results, record a new intent revision when appropriate, and delegate the revision to Hermes. A changed preference does not by itself justify changing a shared tool. Bound both task continuations and environment-repair attempts; completion is not guaranteed when evidence, permissions, or budgets are insufficient.

## Isolation and replay safety

The first implementation operates only against labeled local simulated services. Each baseline and candidate test needs its own restorable starting state. A rerun must not accidentally benefit from a checklist or message created by the previous run. Include a partial-success case: the ticket exists when checklist creation fails.

Simulated business services do not securely isolate generated code. A candidate could still access host files or the network unless a separate execution boundary prevents it. Task 01 must select that boundary, and later implementation must test denied access from inside candidate execution. Resettable service state establishes replay conditions, not filesystem or network containment, and neither establishes live-service compatibility.

A future authorized live recovery has different requirements. It must inspect existing side effects and resume or reconcile completed steps before issuing writes. An uncertain timeout cannot be treated as proof that nothing happened. If duplicate effects cannot be prevented or detected within granted access, stop and report the uncertainty. Local reset tests do not prove live replay safety.

## Fixed and editable surfaces

Before each repair experiment, record the executor implementation, system prompt, model configuration, baseline discovery interface, trusted checks, and permission grants so later verification can establish they remained unchanged. One-time integration configuration happens before that baseline is captured.

The permitted repair surface consists of authorized tool implementations and descriptions/contracts, bounded tool-side behavior, registered capabilities, context selection rules, and repair records. A generated missing tool needs a real authorized underlying resource. A context repair must retain access to an older runbook for a historical question.

The implementation must enforce these restrictions, not merely ask the debugger to obey them. Task 01 chooses the enforcement mechanism. A fixed executor also requires controlling unrelated executor memory or skill updates when comparing baseline and repaired runs.

Future developers may improve tests and evaluators through normal reviewed changes. That engineering work establishes a new reviewed baseline where needed; it is distinct from a runtime debugger weakening the evaluator to approve its own candidate. Preserve earlier results and identify the checks used for each experiment.

## Evidence required to support a repair claim

Keep the triggering request and run, failed condition and provenance, trace references, observed outcome, diagnosis and uncertainty, actual artifact diff, permissions and limits, verification results, active and previous versions, and publication or rejection decision. Link the repaired rerun and fresh-task results to those records.

Collect repair attempts, human interventions after setup, latency, and available token/tool-call usage. Separate repair overhead from later execution cost. Mark missing measurements as unavailable. No percentage improvement is justified without a measured baseline and comparable repaired runs.

These are required information categories, not a selected database schema. The [task sequence](tasks/README.md) turns them into concrete contracts and then working behavior.
