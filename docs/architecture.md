# Intended architecture and data flow

**Design only: none of these runtime components exists yet.** Python is the future implementation language. A command-line interface and local simulated services come first. [Task 01](tasks/01-technical-plan.md) chooses libraries, concrete schemas, persistence, transport, and layout; this document specifies responsibilities without selecting those details.

## Core idea

Hermes does the user's work. Epoch observes failures and repairs a limited part of the environment Hermes uses. The executor stays fixed during a repair experiment, so a successful later task can be attributed to an environment change rather than an executor rewrite.

For example, Hermes can submit valid release data to a tool whose adapter serializes it incorrectly. The debugger should change that adapter, then have Hermes use the corrected version to create an inspectable checklist. The debugger sending back a made-up checklist link would fail the product contract.

## Responsibility boundaries

| Component | Owns | Must not do |
| --- | --- | --- |
| CLI / task entry | Submit tasks and corrections; display outcomes, run identifiers, evidence and limitations | Present a scripted animation as an execution |
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

## Execution and repair flow

```text
User request / correction
          |
          v
         CLI <---- outcome and repair report
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

1. Establish success conditions from the user request, explicit constraints, authoritative documents, and tool contracts. Retain each condition's source. Distinguish inferred conditions from explicit ones. Ambiguity is a reason to seek clarification through Hermes or stop, not invent a requirement.
2. Capture the tools and versions visible to Hermes, requests and responses, supplied context and its metadata, and final application state. An absent trace is an evidence gap, not proof that a step did not happen.
3. Evaluate observable outcomes. A tool can succeed while delivering a message to the wrong destination. A user correction opens an investigation but may reflect a changed goal rather than a defect.
4. Diagnose against actual evidence and editable code. Classify the candidate as existing-tool repair, missing-tool creation, scoped context repair, or outside the permitted boundary.
5. Stage the smallest supported change. The candidate cannot write to the executor, evaluator, acceptance criteria, permissions, baseline evidence, or unrelated files. Enforce filesystem, network, service, attempt, time and cost limits outside generated code.
6. Verify the component, rerun from equivalent isolated starting state, exercise a meaningful new input, and check previously passing behavior. Preserve every result, including rejected attempts and missing measurements.
7. Publish only on trusted checks passing. Persist the artifact and evidence, preserve the prior version, and activate at a safe boundary. Each run must identify its environment version. Test rollback and use from a fresh executor session.

## Isolation and replay safety

The first implementation operates only against labeled local simulated services. Each baseline and candidate test needs its own restorable starting state. A rerun must not accidentally benefit from a checklist or message created by the previous run. Include a partial-success case: the ticket exists when checklist creation fails.

A future authorized live recovery has different requirements. It must inspect existing side effects and resume or reconcile completed steps before issuing writes. An uncertain timeout cannot be treated as proof that nothing happened. If duplicate effects cannot be prevented or detected within granted access, stop and report the uncertainty. Local reset tests do not prove live replay safety.

## Fixed and editable surfaces

Before each repair experiment, record the executor implementation, system prompt, model configuration, baseline discovery interface, trusted checks, and permission grants so later verification can establish they remained unchanged. One-time integration configuration happens before that baseline is captured.

The permitted repair surface consists of authorized tool implementations and descriptions/contracts, bounded tool-side behavior, registered capabilities, context selection rules, and repair records. A generated missing tool needs a real authorized underlying resource. A context repair must retain access to an older runbook for a historical question.

The implementation must enforce these restrictions, not merely ask the debugger to obey them. Task 01 chooses the enforcement mechanism. A fixed executor also requires controlling unrelated executor memory or skill updates when comparing baseline and repaired runs.

## Evidence required to support a repair claim

Keep the triggering request and run, failed condition and provenance, trace references, observed outcome, diagnosis and uncertainty, actual artifact diff, permissions and limits, verification results, active and previous versions, and publication or rejection decision. Link the repaired rerun and fresh-task results to those records.

Collect repair attempts, human interventions after setup, latency, and available token/tool-call usage. Separate repair overhead from later execution cost. Mark missing measurements as unavailable. No percentage improvement is justified without a measured baseline and comparable repaired runs.

These are required information categories, not a selected database schema. The [task sequence](tasks/README.md) turns them into concrete contracts and then working behavior.
