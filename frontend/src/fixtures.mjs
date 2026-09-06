import { acceptEvent, copy, revise } from "./state.mjs";

export const EXAMPLE_REQUEST =
  "Prepare the Atlas 2.4 release: create a release ticket, add a QA checklist, and notify the QA team with both links.";
const commandError = (code, message) =>
  Object.assign(new Error(message), { code });
const scope = (s) => ({
  taskId: s.taskId,
  runId: s.runId,
  revision: s.revision,
  category: "fixture",
});
export function createTask({
  taskId = "fixture-atlas",
  request = EXAMPLE_REQUEST,
  constraints = "Keep the existing release ticket. Do not send duplicate notifications.",
  destination = "#atlas-qa",
  example = true,
} = {}) {
  const requirements = example
    ? [
        ["ticket", "Create the release ticket", "create a release ticket", []],
        [
          "checklist",
          "Attach the QA checklist",
          "add a QA checklist",
          ["ticket"],
        ],
        [
          "notify",
          "Notify QA with both links",
          "notify the QA team with both links",
          ["ticket", "checklist"],
        ],
      ]
    : [["request", request, request, []]];
  return {
    ...scope({ taskId, runId: `${taskId}-r1`, revision: 1 }),
    title: example ? "Prepare the Atlas 2.4 release" : "Your requested task",
    example,
    seq: 0,
    seen: [],
    connection: "connected",
    notice: "",
    status: "planned",
    intent: {
      original: request,
      constraints,
      clarifications: [
        { question: "Where should the result be shared?", answer: destination },
      ],
      defaults: ["Present each outcome with an inspectable evidence record."],
      feedback: [],
    },
    checkpoints: requirements.map(([id, text, quote, dependencies]) => ({
      id,
      text,
      criterionVersion: 1,
      dependencies,
      source: { kind: "explicit", label: "Original request", quote },
      status: "planned",
      evidenceIds: [],
    })),
    evidence: [],
    activity: [],
    repairs: [],
    result: null,
    history: [],
  };
}
function evidence(state, id, extra) {
  return { ...scope(state), id, ...extra };
}
function outcome(state, checkpointId, verdict, observed, object) {
  return evidence(state, `${checkpointId}-${verdict}`, {
    checkpointId,
    criterionVersion: 1,
    verdict,
    expected: state.checkpoints.find((c) => c.id === checkpointId).text,
    observed,
    ...(object ? { object } : {}),
  });
}
const patch =
  '--- fixture/adapter_before.py\n+++ fixture/adapter_after.py\n@@ illustrative serialization only @@\n- "title": release_name\n+ "title": [{"text": {"content": release_name}}]\n';
function repair(id, status) {
  const rejected = status === "rejected";
  return {
    id,
    status,
    title: rejected
      ? "Candidate 01 · retry only"
      : "Candidate 02 · title serialization",
    diagnosis:
      "The sample response rejects the title field. The adapter may be sending a string where a structured value is expected.",
    uncertainty:
      "Authored diagnosis for interface development; no debugger inspected or executed this change.",
    trigger: "checklist-failed",
    scope: "Illustrative checklist adapter only",
    diff: rejected
      ? "--- fixture/adapter_before.py\n+++ fixture/retry_candidate.py\n- attempts = 1\n+ attempts = 3\n"
      : patch,
    reason: rejected
      ? "Repeated the invalid request. The fixture regression record reports duplicate ticket creation."
      : "Display sample for isolated verification; activation is a separate fixture event.",
    tests: [
      {
        name: "Component · title payload",
        status: rejected ? "failed" : "passed",
        detail: rejected
          ? "String still rejected."
          : "Structured title accepted in authored example.",
      },
      {
        name: "Original task replay",
        status: rejected ? "failed" : "passed",
        detail: rejected
          ? "Checklist still absent."
          : "Existing fixture ticket retained.",
      },
      {
        name: "Fresh variation · Atlas 2.5",
        status: rejected ? "not-run" : "passed",
        detail: rejected
          ? "Stopped after component failure."
          : "Authored alternate release record.",
      },
      {
        name: "Regression · duplicate effects",
        status: rejected ? "failed" : "passed",
        detail: rejected
          ? "Authored example contains a second ticket."
          : "Authored example retains one ticket.",
      },
    ],
    limits:
      "Fixture only · example budget: 2 attempts / 60 seconds; not enforced here.",
    versions:
      status === "active"
        ? "Fixture environment v2 active; previous v1 retained. Rollback not executed."
        : "Fixture environment v1 unchanged; candidate staged separately.",
  };
}
export function exampleFrames(state) {
  const cp = (id, status, evidenceIds = []) => [
    "checkpoint",
    { id, status, criterionVersion: 1, evidenceIds },
  ];
  const act = (id, type, title, detail) => [
    "activity",
    { id, type, title, detail, time: `Fixture step ${id.replace("a", "")}` },
  ];
  return [
    {
      label: "Execution started",
      events: [
        cp("ticket", "running"),
        act(
          "a1",
          "tool-call",
          "Hermes → release.create · v1",
          "Fixture input: Atlas 2.4. This is a sample call, not an executed tool.",
        ),
      ],
    },
    {
      label: "Checklist failed · partial result retained",
      events: [
        [
          "evidence",
          outcome(
            state,
            "ticket",
            "passed",
            "Fixture ticket ATLAS-24 exists.",
            {
              type: "ticket",
              id: "ATLAS-24",
              title: "Atlas 2.4 release",
              status: "Open",
              origin: "Authored UI fixture; no Jira object exists.",
            },
          ),
        ],
        cp("ticket", "passed", ["ticket-passed"]),
        [
          "evidence",
          outcome(
            state,
            "checklist",
            "failed",
            "Fixture response: invalid title payload. Checklist is absent.",
          ),
        ],
        cp("checklist", "failed", ["checklist-failed"]),
        act(
          "a2",
          "tool-result",
          "Checklist adapter returned an error",
          "Fixture output: title must be structured text. The ticket already exists; preserve that partial effect.",
        ),
        act(
          "a3",
          "context",
          "Release runbook · fixture version 3",
          "Supplied context example: QA requires a ticket and checklist link. Historical version 2 retained in this record.",
        ),
        [
          "task-outcome",
          {
            status: "incomplete",
            result: {
              artifactIds: ["ticket-passed"],
              limitations: ["Checklist missing.", "QA notification not sent."],
            },
          },
        ],
      ],
    },
    {
      label: "Rejected candidate retained",
      events: [
        ["repair", repair("repair-01", "rejected")],
        act(
          "a4",
          "observation",
          "Candidate 01 rejected",
          "Fixture regression evidence reports duplicate effects. Candidate remains inspectable; no version was activated.",
        ),
      ],
    },
    {
      label: "Candidate verification",
      events: [
        ["repair", repair("repair-02-check", "verifying")],
        cp("checklist", "checking"),
        act(
          "a5",
          "supervisor",
          "Preserve the ticket; retry only the missing checklist",
          "Authored targeted continuation, shown separately from the environment repair. Original criteria are unchanged.",
        ),
      ],
    },
    {
      label: "Repair active · task still incomplete",
      events: [
        ["repair", repair("repair-02-active", "active")],
        act(
          "a6",
          "observation",
          "Fixture environment v2 selected at a safe boundary",
          "Display event only. No repair executed or persisted. Task outcome is still incomplete.",
        ),
      ],
    },
    {
      label: "QA destination needs input",
      events: [
        [
          "evidence",
          outcome(
            state,
            "checklist",
            "passed",
            "Fixture checklist QA-24 links ATLAS-24.",
            {
              type: "checklist",
              id: "QA-24",
              ticket: "ATLAS-24",
              items: ["Verify upgrade", "Run smoke checks"],
              origin: "Authored UI fixture; no Notion page exists.",
            },
          ),
        ],
        cp("checklist", "passed", ["checklist-passed"]),
        [
          "evidence",
          outcome(
            state,
            "notify",
            "needs-input",
            "Fixture destination confirmation is required before notification.",
          ),
        ],
        cp("notify", "needs-input", ["notify-needs-input"]),
      ],
    },
    {
      label: "Notification checking",
      events: [
        cp("notify", "running"),
        act(
          "a7",
          "tool-call",
          "Hermes → qa.notify · v1",
          "Fixture notification references ATLAS-24 and QA-24.",
        ),
        cp("notify", "checking"),
      ],
    },
    {
      label: "Delivered fixture results",
      events: [
        [
          "evidence",
          outcome(
            state,
            "notify",
            "passed",
            "Fixture notification MSG-24 includes both object IDs.",
            {
              type: "message",
              id: "MSG-24",
              channel: state.intent.clarifications[0].answer,
              text: "Atlas 2.4 is ready for QA.",
              links: ["ATLAS-24", "QA-24"],
              origin: "Authored UI fixture; no Slack message was sent.",
            },
          ),
        ],
        cp("notify", "passed", ["notify-passed"]),
        [
          "task-outcome",
          {
            status: "delivered",
            result: {
              artifactIds: [
                "ticket-passed",
                "checklist-passed",
                "notify-passed",
              ],
              limitations: [
                "All artifacts and outcomes are authored fixtures. No real task ran.",
              ],
            },
          },
        ],
      ],
    },
  ];
}
// A replaceable local transport double. No HTTP routes, evaluator, tool or credentials.
export class FixtureAdapter {
  constructor({ startAtFailure = true } = {}) {
    this.state = createTask();
    this.commands = new Map();
    this.frame = 0;
    this.loseNextAcknowledgement = false;
    this.failNextReconnect = false;
    if (startAtFailure) {
      this.next();
      this.next();
      this.next();
    }
  }
  snapshot() {
    return copy(this.state);
  }
  next() {
    if (!this.state.example || this.state.revision !== 1)
      return {
        events: [],
        label:
          "No authored sequence for this request. Backend interpretation is unavailable.",
      };
    const frame = exampleFrames(this.state)[this.frame];
    if (!frame) return { events: [], label: "End of fixture sequence." };
    const events = frame.events.map(([kind, data], index) => ({
      ...scope(this.state),
      eventId: `${this.state.runId}-${this.state.seq + index + 1}`,
      seq: this.state.seq + index + 1,
      kind,
      data,
    }));
    for (const event of events) this.state = acceptEvent(this.state, event);
    this.frame++;
    return { events, label: frame.label };
  }
  async reconnect() {
    if (this.failNextReconnect) {
      this.failNextReconnect = false;
      throw new Error("Fixture reconnect failed.");
    }
    return this.snapshot();
  }
  async command(command) {
    const fingerprint = JSON.stringify(command);
    if (this.commands.has(command.id)) {
      const prior = this.commands.get(command.id);
      if (prior.fingerprint !== fingerprint)
        throw new Error(
          "This command ID belongs to different input. Keep the original request when retrying.",
        );
      return copy(prior.result);
    }
    if (!command.id) throw new Error("A command ID is required.");
    if (
      command.kind !== "create" &&
      (command.taskId !== this.state.taskId ||
        command.expectedRevision !== this.state.revision)
    )
      throw new Error(
        "This request belongs to an older revision. Reconnect before submitting again.",
      );
    if (command.kind === "create") {
      if (
        !command.payload.request?.trim() ||
        !command.payload.destination?.trim()
      )
        throw new Error("A request and sharing destination are required.");
      this.state = createTask({
        taskId: `fixture-${command.id}`,
        ...command.payload,
        example: false,
      });
      this.frame = 0;
    } else if (command.kind === "feedback") {
      this.state = revise(this.state, command.payload, command.id);
      this.frame = 0;
    } else throw new Error("Unknown fixture command.");
    const result = this.snapshot();
    this.commands.set(command.id, { fingerprint, result });
    if (this.loseNextAcknowledgement) {
      this.loseNextAcknowledgement = false;
      throw commandError(
        "acknowledgement-lost",
        "Fixture acknowledgement lost. The command may already be recorded. Retry the same submission to retrieve it safely.",
      );
    }
    return copy(result);
  }
}
