// Presentation guards only. This module does not evaluate business outcomes.
export const CHECKPOINT_STATES = [
  "planned",
  "running",
  "checking",
  "passed",
  "failed",
  "needs-input",
];
export const copy = (value) => structuredClone(value);
const scoped = (state, record) =>
  record &&
  record.taskId === state.taskId &&
  record.runId === state.runId &&
  record.revision === state.revision &&
  record.category === "fixture";
export const checkpointEvidence = (state, cp) =>
  (cp.evidenceIds || [])
    .map((id) => state.evidence.find((e) => e.id === id))
    .filter(Boolean);
export function hasPassEvidence(state, cp) {
  return checkpointEvidence(state, cp).some(
    (e) =>
      scoped(state, e) &&
      e.checkpointId === cp.id &&
      e.criterionVersion === cp.criterionVersion &&
      e.verdict === "passed" &&
      e.observed &&
      e.expected,
  );
}
export function canDeliver(state, result) {
  return (
    state.checkpoints.length > 0 &&
    state.checkpoints.every(
      (cp) => cp.status === "passed" && hasPassEvidence(state, cp),
    ) &&
    result?.artifactIds?.length > 0 &&
    result.artifactIds.every((id) =>
      state.evidence.some((e) => e.id === id && scoped(state, e) && e.object),
    )
  );
}
export function acceptEvent(state, event) {
  if (!scoped(state, event)) return state;
  if (state.seen.includes(event.eventId) || event.seq <= state.seq)
    return state;
  if (state.connection !== "connected") return state;
  if (
    !event.eventId ||
    !Number.isInteger(event.seq) ||
    event.seq !== state.seq + 1
  )
    return {
      ...state,
      connection: "gap",
      notice:
        "Fixture event gap. Reconnect to restore a complete snapshot; no work will be resubmitted.",
    };
  const next = copy(state);
  const reject = (message) => ({
    ...state,
    connection: "gap",
    notice: `Incomplete fixture evidence: ${message} Reconnect to inspect the last complete state.`,
  });
  const data = event.data;
  if (!data || typeof data !== "object")
    return reject("event payload is missing.");
  switch (event.kind) {
    case "evidence":
      if (
        !scoped(state, data) ||
        !data.id ||
        next.evidence.some((e) => e.id === data.id)
      )
        return reject("evidence identity is invalid.");
      next.evidence.push(copy(data));
      break;
    case "checkpoint": {
      const cp = next.checkpoints.find((c) => c.id === data.id);
      if (
        !cp ||
        !CHECKPOINT_STATES.includes(data.status) ||
        data.criterionVersion !== cp.criterionVersion ||
        !Array.isArray(data.evidenceIds)
      )
        return reject("checkpoint identity or criterion changed.");
      // Only display fields may change; source, criteria and dependencies are immutable.
      cp.status = data.status;
      cp.evidenceIds = copy(data.evidenceIds);
      if (
        cp.evidenceIds.some(
          (id) => !next.evidence.some((e) => e.id === id && scoped(next, e)),
        )
      )
        return reject("a referenced record is unavailable.");
      if (cp.status === "passed" && !hasPassEvidence(next, cp))
        return reject("a passing checkpoint needs matching outcome evidence.");
      if (
        ["failed", "needs-input"].includes(cp.status) &&
        !checkpointEvidence(next, cp).some(
          (e) =>
            e.checkpointId === cp.id &&
            e.criterionVersion === cp.criterionVersion &&
            e.verdict === cp.status,
        )
      )
        return reject("the checkpoint outcome has no matching evidence.");
      break;
    }
    case "activity":
      if (
        !data.id ||
        ![
          "tool-call",
          "tool-result",
          "context",
          "supervisor",
          "observation",
        ].includes(data.type)
      )
        return reject("unsupported activity category.");
      next.activity.push(copy(data));
      break;
    case "repair":
      if (
        !data.id ||
        !["rejected", "verifying", "active"].includes(data.status)
      )
        return reject("repair record is invalid.");
      // Records are append-only; task status is deliberately untouched.
      next.repairs.push(copy(data));
      break;
    case "task-outcome":
      if (!["incomplete", "delivered"].includes(data.status))
        return reject("unknown task outcome.");
      if (data.status === "delivered" && !canDeliver(next, data.result))
        return reject("delivery has unresolved checks or missing artifacts.");
      next.status = data.status;
      next.result = copy(data.result || null);
      break;
    default:
      return reject("unknown event kind.");
  }
  next.seq = event.seq;
  next.seen.push(event.eventId);
  next.notice = "";
  return next;
}
export function reconnectState(current, snapshot) {
  if (!scoped(current, snapshot) || snapshot.seq < current.seq)
    return {
      ...current,
      connection: "gap",
      notice:
        "Reconnect returned stale or unrelated fixture state. The current task was retained.",
    };
  if (
    !Number.isInteger(snapshot.seq) ||
    !Array.isArray(snapshot.checkpoints) ||
    !Array.isArray(snapshot.evidence)
  )
    return {
      ...current,
      connection: "gap",
      notice:
        "Reconnect returned incomplete fixture state. The current task was retained.",
    };
  // A reconnect cannot erase retained history or already observed immutable records.
  for (const key of ["history", "evidence", "activity", "repairs"]) {
    if (
      !Array.isArray(snapshot[key]) ||
      !current[key].every((record) =>
        snapshot[key].some(
          (other) => JSON.stringify(record) === JSON.stringify(other),
        ),
      )
    )
      return {
        ...current,
        connection: "gap",
        notice:
          "Reconnect omitted known fixture history. The current task was retained.",
      };
  }
  if (
    JSON.stringify(snapshot.intent) !== JSON.stringify(current.intent) ||
    snapshot.checkpoints.length !== current.checkpoints.length ||
    snapshot.checkpoints.some((cp) => {
      const prior = current.checkpoints.find((c) => c.id === cp.id);
      return (
        !prior ||
        !CHECKPOINT_STATES.includes(cp.status) ||
        cp.criterionVersion !== prior.criterionVersion ||
        cp.text !== prior.text ||
        JSON.stringify(cp.source) !== JSON.stringify(prior.source) ||
        JSON.stringify(cp.dependencies) !==
          JSON.stringify(prior.dependencies) ||
        (cp.status === "passed" && !hasPassEvidence(snapshot, cp))
      );
    }) ||
    (snapshot.status === "delivered" && !canDeliver(snapshot, snapshot.result))
  )
    return {
      ...current,
      connection: "gap",
      notice:
        "Reconnect contains incomplete fixture criteria or outcomes. The current task was retained.",
    };
  return {
    ...copy(snapshot),
    connection: "connected",
    notice:
      "Fixture connection restored. Existing work was retained; no command was resubmitted.",
  };
}
export function revise(state, feedback, commandId) {
  if (!feedback.text?.trim()) throw new Error("Describe the change you want.");
  const previous = copy(state);
  delete previous.history;
  const revision = state.revision + 1;
  return {
    ...copy(state),
    revision,
    runId: `${state.taskId}-r${revision}`,
    seq: 0,
    seen: [],
    status: "planned",
    result: null,
    intent: {
      ...copy(state.intent),
      feedback: [
        ...state.intent.feedback,
        {
          text: feedback.text.trim(),
          kind: feedback.kind,
          fromRevision: state.revision,
          commandId,
        },
      ],
    },
    checkpoints: [
      ...state.checkpoints.map((cp) => ({
        ...copy(cp),
        status: "planned",
        evidenceIds: [],
      })),
      {
        id: `feedback-${revision}`,
        text: feedback.text.trim(),
        criterionVersion: 1,
        dependencies: [],
        source: {
          kind: "explicit",
          label: `Revision ${revision} feedback`,
          quote: feedback.text.trim(),
        },
        status: "planned",
        evidenceIds: [],
      },
    ],
    evidence: [],
    activity: [],
    repairs: [],
    history: [...state.history, previous],
    connection: "connected",
    notice:
      "Revision recorded in this fixture session. Previous requirements and results remain in history. No execution started.",
  };
}
