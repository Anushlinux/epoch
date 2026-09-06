import test from "node:test";
import assert from "node:assert/strict";
import {
  acceptEvent,
  reconnectState,
  revise,
  copy,
  CHECKPOINT_STATES,
} from "../src/state.mjs";
import { FixtureAdapter, createTask } from "../src/fixtures.mjs";
const event = (s, kind, data, extra = {}) => ({
  taskId: s.taskId,
  runId: s.runId,
  revision: s.revision,
  category: "fixture",
  seq: s.seq + 1,
  eventId: `event-${s.seq + 1}`,
  kind,
  data,
  ...extra,
});
const complete = () => {
  const a = new FixtureAdapter();
  while (a.frame < 8) a.next();
  return a;
};

test("manual playback contains all six states and explicit result with inspectable fixture objects", () => {
  const a = new FixtureAdapter({ startAtFailure: false });
  const states = new Set(a.state.checkpoints.map((c) => c.status));
  while (a.frame < 8) {
    a.next();
    a.state.checkpoints.forEach((c) => states.add(c.status));
    assert.equal(a.state.connection, "connected");
  }
  assert.deepEqual([...states].sort(), CHECKPOINT_STATES.toSorted());
  assert.equal(a.state.status, "delivered");
  assert.equal(a.state.result.artifactIds.length, 3);
  assert.ok(a.state.evidence.every((e) => e.category === "fixture"));
});

test("default failure preserves partial ticket, rejected candidate and expected/observed evidence", () => {
  const s = new FixtureAdapter().snapshot();
  assert.equal(s.status, "incomplete");
  assert.deepEqual(s.result.artifactIds, ["ticket-passed"]);
  assert.equal(s.repairs[0].status, "rejected");
  assert.ok(s.evidence.find((e) => e.id === "checklist-failed").expected);
});

test("repair verification and activation never complete task or notification", () => {
  const a = new FixtureAdapter();
  a.next();
  a.next();
  assert.equal(a.state.repairs.at(-1).status, "active");
  assert.equal(a.state.status, "incomplete");
  assert.equal(a.state.checkpoints.at(-1).status, "planned");
  assert.equal(a.state.result.artifactIds.length, 1);
});

test("passing without evidence is rejected without optimistic display", () => {
  const s = createTask();
  const next = acceptEvent(
    s,
    event(s, "checkpoint", {
      id: "ticket",
      status: "passed",
      criterionVersion: 1,
      evidenceIds: [],
    }),
  );
  assert.equal(next.checkpoints[0].status, "planned");
  assert.equal(next.connection, "gap");
});

test("matching record must bind run, revision, criterion and actual observed value", () => {
  const base = new FixtureAdapter().snapshot();
  for (const change of [
    { runId: "other" },
    { revision: 2 },
    { criterionVersion: 2 },
    { observed: "" },
    { category: "actual-hermes" },
  ]) {
    const s = copy(base);
    Object.assign(s.evidence[0], change);
    s.checkpoints[0].status = "checking";
    const next = acceptEvent(
      s,
      event(s, "checkpoint", {
        id: "ticket",
        status: "passed",
        criterionVersion: 1,
        evidenceIds: ["ticket-passed"],
      }),
    );
    assert.equal(next.checkpoints[0].status, "checking");
    assert.equal(next.connection, "gap");
  }
});

test("outcome cannot deliver missing artifacts or incomplete checkpoints", () => {
  const s = new FixtureAdapter().snapshot();
  const next = acceptEvent(
    s,
    event(s, "task-outcome", {
      status: "delivered",
      result: { artifactIds: ["ticket-passed"] },
    }),
  );
  assert.equal(next.status, "incomplete");
  const delivered = complete().snapshot();
  delivered.status = "incomplete";
  const missing = acceptEvent(
    delivered,
    event(delivered, "task-outcome", {
      status: "delivered",
      result: { artifactIds: ["missing"] },
    }),
  );
  assert.equal(missing.status, "incomplete");
  assert.equal(missing.connection, "gap");
});

test("events cannot rewrite requirements or dependency/source provenance", () => {
  const s = createTask();
  const next = acceptEvent(
    s,
    event(s, "checkpoint", {
      id: "ticket",
      status: "running",
      criterionVersion: 1,
      evidenceIds: [],
      source: { kind: "inferred" },
      text: "Weakened criterion",
      dependencies: ["fake"],
    }),
  );
  assert.deepEqual(next.checkpoints[0].source, s.checkpoints[0].source);
  assert.equal(next.checkpoints[0].text, s.checkpoints[0].text);
  assert.deepEqual(next.checkpoints[0].dependencies, []);
});

test("duplicate IDs, stale sequences and unrelated task/run/revision/category events are ignored", () => {
  const s = createTask();
  const e = event(s, "checkpoint", {
    id: "ticket",
    status: "running",
    criterionVersion: 1,
    evidenceIds: [],
  });
  const next = acceptEvent(s, e);
  for (const duplicate of [e, { ...e, seq: 2 }, { ...e, eventId: "old" }])
    assert.equal(acceptEvent(next, duplicate), next);
  for (const extra of [
    { taskId: "other" },
    { runId: "other" },
    { revision: 0 },
    { category: "actual-hermes" },
  ])
    assert.equal(acceptEvent(s, { ...e, ...extra }), s);
});

test("gap blocks further events and reconnect restores snapshot without replaying a command", async () => {
  const a = new FixtureAdapter({ startAtFailure: false });
  const before = a.snapshot();
  const frame = a.next();
  const gap = acceptEvent(before, { ...frame.events[0], seq: 4 });
  assert.equal(gap.connection, "gap");
  assert.equal(acceptEvent(gap, frame.events[0]), gap);
  const restored = reconnectState(gap, await a.reconnect());
  assert.equal(restored.connection, "connected");
  assert.equal(restored.seq, a.state.seq);
  assert.equal(a.commands.size, 0);
});

test("disconnected views retain evidence and ignore arriving events", () => {
  const a = new FixtureAdapter();
  const s = { ...a.snapshot(), connection: "disconnected" };
  const frame = a.next();
  assert.equal(acceptEvent(s, frame.events[0]), s);
  assert.equal(s.result.artifactIds[0], "ticket-passed");
});

test("reconnect rejects stale, missing, rewritten criteria, mismatched pass or erased history snapshots", () => {
  const s = complete().snapshot();
  for (const mutate of [
    (x) => x.seq--,
    (x) => (x.evidence = []),
    (x) => (x.checkpoints[0].text = "changed"),
    (x) => (x.evidence[0].verdict = "failed"),
    (x) => (x.intent.original = "changed"),
    (x) => delete x.checkpoints,
  ]) {
    const snapshot = copy(s);
    mutate(snapshot);
    const next = reconnectState(s, snapshot);
    assert.equal(next.connection, "gap");
    assert.deepEqual(next.evidence, s.evidence);
  }
  const revised = revise(
    s,
    { text: "Add owner", kind: "new-preference" },
    "revision-2",
  );
  const missing = copy(revised);
  missing.history = [];
  assert.equal(reconnectState(revised, missing).connection, "gap");
});

test("unknown and malformed event states fail closed with a reconnect path", () => {
  const s = createTask();
  for (const e of [
    event(s, "unknown", {}),
    event(s, "checkpoint", {}),
    event(s, "activity", { id: "thinking", type: "private-reasoning" }),
    event(s, "repair", { id: "x", status: "delivered" }),
    event(s, "evidence", {}),
  ]) {
    assert.equal(acceptEvent(s, e).connection, "gap");
    assert.equal(s.status, "planned");
  }
});

test("uncertain create acknowledgement reuses command ID and creates one task", async () => {
  const a = new FixtureAdapter();
  a.loseNextAcknowledgement = true;
  const command = {
    id: "draft-1",
    kind: "create",
    payload: {
      request: "Keep my exact requirement",
      constraints: "No changes outside it",
      destination: "Just here",
    },
  };
  await assert.rejects(a.command(command), /acknowledgement lost/);
  const accepted = a.snapshot();
  const recovered = await a.command(command);
  assert.equal(a.commands.size, 1);
  assert.deepEqual(recovered, accepted);
  assert.equal(recovered.intent.original, command.payload.request);
  assert.equal(recovered.checkpoints.length, 1);
  assert.equal(recovered.status, "planned");
  assert.equal(a.next().events.length, 0);
});

test("reused command ID with changed input is refused", async () => {
  const a = new FixtureAdapter();
  const command = {
    id: "draft-1",
    kind: "create",
    payload: { request: "A", destination: "Here" },
  };
  await a.command(command);
  await assert.rejects(
    a.command({ ...command, payload: { request: "B", destination: "Here" } }),
    /different input/,
  );
  assert.equal(a.state.intent.original, "A");
});

test("blank requests/clarifications and invalid feedback do not mutate state", async () => {
  const a = new FixtureAdapter();
  const before = a.snapshot();
  for (const payload of [
    { request: " ", destination: "here" },
    { request: "x", destination: " " },
  ])
    await assert.rejects(
      a.command({ id: "bad", kind: "create", payload }),
      /required/,
    );
  assert.throws(() => revise(before, { text: " " }, "bad"), /Describe/);
  assert.deepEqual(a.snapshot(), before);
});

test("feedback retains original intent, constraints, sources, results and rejected repairs without inherited passes", async () => {
  const a = complete();
  const original = a.snapshot();
  const cmd = {
    id: "feedback-1",
    kind: "feedback",
    taskId: original.taskId,
    expectedRevision: 1,
    payload: { text: "Include the rollback owner", kind: "missed-requirement" },
  };
  a.loseNextAcknowledgement = true;
  await assert.rejects(a.command(cmd));
  const result = await a.command(cmd);
  assert.equal(result.revision, 2);
  assert.equal(result.history.length, 1);
  assert.equal(result.intent.original, original.intent.original);
  assert.deepEqual(result.history[0].repairs, original.repairs);
  assert.deepEqual(result.history[0].result, original.result);
  assert.ok(
    result.checkpoints.every(
      (c) => c.status === "planned" && c.evidenceIds.length === 0,
    ),
  );
  assert.equal(result.checkpoints.at(-1).source.label, "Revision 2 feedback");
  assert.equal(result.intent.constraints, original.intent.constraints);
  assert.deepEqual(await a.command(cmd), result);
  assert.equal(a.commands.size, 1);
  await assert.rejects(
    a.command({ ...cmd, id: "stale-feedback" }),
    /older revision/,
  );
});

test("multiple feedback revisions retain the full chain without altering previous objects", () => {
  const original = complete().snapshot();
  const first = revise(
    original,
    { text: "Include owner", kind: "new-preference" },
    "f1",
  );
  const second = revise(
    first,
    { text: "Mention deadline", kind: "new-preference" },
    "f2",
  );
  assert.equal(second.history.length, 2);
  assert.equal(second.intent.feedback.length, 2);
  assert.equal(original.intent.feedback.length, 0);
  assert.equal(first.history.length, 1);
  assert.deepEqual(second.history[0].checkpoints, original.checkpoints);
});

test("a failed reconnect can be retried without changing task state or command count", async () => {
  const a = new FixtureAdapter();
  const previous = a.snapshot();
  a.failNextReconnect = true;
  await assert.rejects(a.reconnect(), /reconnect failed/);
  assert.deepEqual(a.snapshot(), previous);
  assert.deepEqual(await a.reconnect(), previous);
  assert.equal(a.commands.size, 0);
});
