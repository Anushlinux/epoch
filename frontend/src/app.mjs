import { FixtureAdapter } from "./fixtures.mjs";
import {
  acceptEvent,
  reconnectState,
  checkpointEvidence,
  adoptScope,
  freezeSubmission,
  isDeliveryCurrent,
} from "./state.mjs";
import {
  $,
  escape,
  icon,
  badge,
  empty,
  welcome,
  shell,
  pipeline,
  currentPage,
  urlFor,
  routeLink,
  View,
  installNavigation,
  installInspector,
} from "./ui.mjs";
const root = $("#app");
const view = new View(root);
const inspect = installInspector();
const marker = "epoch.fixture.pending";
function markPending(command) {
  try {
    if (command)
      sessionStorage.setItem(marker, JSON.stringify({ id: command.id }));
    else sessionStorage.removeItem(marker);
    return true;
  } catch {
    return false;
  }
}
function lostSubmission() {
  try {
    return sessionStorage.getItem(marker) !== null;
  } catch {
    return performance.getEntriesByType("navigation")[0]?.type === "reload";
  }
}
let adapter = new FixtureAdapter();
let state = adapter.snapshot();
const ui = {
  composing: false,
  stage: "request",
  draft: { request: "", constraints: "", destination: "" },
  draftId: crypto.randomUUID(),
  feedback: "",
  feedbackKind: "new-preference",
  pending: null,
  submissionStatus: "idle",
  recoveryUnknown: lostSubmission(),
  busy: false,
  error: "",
  tab: "activity",
};
const tabs = [
  ["activity", "Activity"],
  ["checkpoints", "Checkpoints"],
  ["history", "History"],
];
const announce = (text) => {
  $("#announcement").textContent = text;
};
const locked = () =>
  ui.busy ||
  !!ui.pending ||
  ui.recoveryUnknown ||
  state.connection !== "connected";
const delivered = () => isDeliveryCurrent(state);
function label(s = state) {
  return isDeliveryCurrent(s)
    ? "Delivered · fixture"
    : s.status === "delivered"
      ? "Delivery needs confirmation · fixture"
      : s.checkpoints.some((c) => c.status === "failed")
        ? "Needs attention · fixture"
        : s.checkpoints.some((c) => c.status === "needs-input")
          ? "Needs input · fixture"
          : s.checkpoints.some((c) =>
                ["running", "checking"].includes(c.status),
              )
            ? "In progress · fixture"
            : s.revision > 1
              ? "Revision pending · fixture"
              : "Planned · fixture";
}
function matchedTask() {
  const id = new URLSearchParams(location.search).get("task");
  return !id || id === state.taskId;
}
installNavigation(root, routeChanged, newChat);
function navigation() {
  return `<a class="session-item" href="${urlFor(true, "chat", state.taskId)}" data-route ${!ui.composing && matchedTask() ? 'aria-current="page"' : ""}>${icon("chat")}<span><strong>${escape(state.title)}</strong><small>${escape(label())}</small></span></a>`;
}
function checkpointRows() {
  return `<div class="checkpoint-list">${state.checkpoints.map((cp) => `<article class="checkpoint">${badge(cp.status)}<div><h3>${escape(cp.text)}</h3><p>${escape(checkpointEvidence(state, cp).at(-1)?.observed || "No outcome evidence yet.")}</p><button class="text-button" data-action="inspect-checkpoint" data-id="${escape(cp.id)}">${icon("link")} ${cp.evidenceIds.length ? "Inspect evidence & source" : "Inspect requirement source"}</button></div></article>`).join("")}</div>`;
}
function activityList(items) {
  return items.length
    ? `<ol class="activity-list">${items.map((a) => `<li>${icon(a.type === "context" ? "file" : a.type === "supervisor" ? "arrow" : "activity")}<div><h3>${escape(a.title)}</h3><p>${escape(a.detail)}</p><small>${escape(a.time)} · ${escape(a.type)} · fixture</small></div></li>`).join("")}</ol>`
    : empty(
        "No activity recorded",
        "This request has not executed.",
        "activity",
      );
}
function artifacts(owner = state) {
  const records =
    owner.result?.artifactIds
      .map((id) => owner.evidence.find((e) => e.id === id))
      .filter(Boolean) || [];
  return records.length
    ? `<div class="artifact-list">${records.map((e) => `<button class="artifact" data-action="inspect-evidence" data-id="${escape(e.id)}" data-run="${escape(owner.runId)}" data-revision="${owner.revision}">${icon(e.object?.type === "message" ? "chat" : "file")}<span>${escape(e.object?.id || e.id)}<small>${escape(e.object?.type || "record")} · fixture JSON</small></span></button>`).join("")}</div>`
    : '<p class="muted">No result artifacts available.</p>';
}
function diff(record) {
  return `<pre class="diff" tabindex="0" aria-label="Illustrative candidate diff">${record.diff
    .split("\n")
    .map(
      (line) =>
        `<span class="${line.startsWith("+") ? "addition" : line.startsWith("-") ? "deletion" : ""}">${escape(line) || " "}</span>`,
    )
    .join("")}</pre>`;
}
function tests(record) {
  return `<table class="test-table"><caption class="sr-only">Fixture verification records</caption><thead><tr><th>Check</th><th>Recorded result</th></tr></thead><tbody>${record.tests.map((t) => `<tr><td>${escape(t.name)}<p>${escape(t.detail)}</p></td><td>${badge(t.status)}</td></tr>`).join("")}</tbody></table>`;
}
function repairDetails(record, full = false) {
  return `<p>${escape(record.reason)}</p>${full ? `<h3>Diagnosis</h3><p>${escape(record.diagnosis)}</p><p>${escape(record.uncertainty)}</p>` : ""}<h3>Candidate diff</h3>${diff(record)}${full ? `<h3>Verification records · fixtures</h3>${tests(record)}` : ""}<p>${escape(record.versions)}</p><button class="text-button" data-action="inspect-repair" data-id="${escape(record.id)}">Inspect full fixture record ${icon("arrow")}</button>`;
}
function historyContent() {
  return `<div class="current-revision"><h2>Revision ${state.revision} · current</h2><p class="muted">${escape(state.intent.feedback.at(-1)?.text || state.intent.original)}</p></div>${
    state.history.length
      ? [...state.history]
          .reverse()
          .map(
            (previous) =>
              `<details class="history-record" data-key="history-${previous.runId}" open><summary><strong>Revision ${previous.revision}</strong><span>${escape(label(previous))}</span></summary><p>${escape(previous.intent.original)}</p><p>${escape(previous.intent.constraints || "No additional constraints.")}</p>${previous.intent.feedback.map((f) => `<p>${escape(f.text)}</p>`).join("")}<ul>${previous.checkpoints.map((cp) => `<li>${escape(cp.text)} · ${escape(cp.status)} · criterion v${cp.criterionVersion}</li>`).join("")}</ul>${artifacts(previous)}<button class="text-button" data-action="inspect-history" data-run="${escape(previous.runId)}" data-revision="${previous.revision}">Inspect complete revision & repair history ${icon("arrow")}</button></details>`,
          )
          .join("")
      : empty(
          "The original request is intact",
          "Feedback creates a new revision while retaining earlier requirements and evidence.",
          "history",
        )
  }`;
}
function context() {
  return `<aside class="context-column"><h2>Original request</h2><blockquote>${escape(state.intent.original)}</blockquote><button class="text-button" data-action="inspect-intent">Inspect full intent ${icon("arrow")}</button><h3>Constraints</h3><p>${escape(state.intent.constraints || "No additional constraints supplied.")}</p><h3>Clarification</h3>${state.intent.clarifications.map((c) => `<p>${escape(c.question)}</p><p>${escape(c.answer)}</p>`).join("")}<h3>Inferred default</h3>${state.intent.defaults.map((d) => `<p>${escape(d)}</p>`).join("")}<h3>Partial effects & artifacts</h3>${artifacts()}<h3>Evidence boundary</h3><p>Authored UI fixtures. No tool, test, or repair has executed.</p></aside>`;
}
function stageData() {
  const failure = state.evidence.find((e) => e.verdict === "failed");
  const latest = state.repairs.at(-1);
  const active = state.repairs.find((r) => r.status === "active");
  const rejected = state.repairs.filter((r) => r.status === "rejected");
  const stage = (
    status,
    summary,
    body = "",
    tone = "pending",
    open = false,
  ) => ({ status, summary, body, tone, open });
  const resumed =
    state.activity.some((a) => a.id === "a7") ||
    state.checkpoints.some(
      (c) => c.id === "checklist" && c.status === "passed",
    );
  return [
    stage(
      failure ? "Recorded" : "Not recorded",
      failure
        ? "Checklist creation failed after the release ticket was created."
        : "No failed outcome has been recorded.",
      failure
        ? `<h3>Expected</h3><p>${escape(failure.expected)}</p><h3>Observed</h3><p>${escape(failure.observed)}</p><h3>Completed work retained</h3>${artifacts()}<button class="text-button" data-action="inspect-evidence" data-id="${escape(failure.id)}">Inspect failure evidence ${icon("arrow")}</button>`
        : "",
      failure ? "warning" : "pending",
      !!failure && !latest,
    ),
    stage(
      latest ? "Hypothesis recorded" : "Waiting",
      latest
        ? "The checklist adapter may be sending the title in the wrong format."
        : "A diagnosis will appear when supporting evidence is available.",
      latest
        ? `<p>${escape(latest.diagnosis)}</p><h3>Uncertainty</h3><p>${escape(latest.uncertainty)}</p><h3>Permitted surface</h3><p>${escape(latest.scope)}</p><button class="text-button" data-action="inspect-evidence" data-id="${escape(latest.trigger)}">Inspect trigger evidence ${icon("arrow")}</button>`
        : "",
      latest ? "warning" : "pending",
    ),
    stage(
      latest
        ? latest.status === "rejected"
          ? "Rejected"
          : "Candidate recorded"
        : "Waiting",
      latest ? latest.title : "No candidate change has been recorded.",
      latest
        ? `${repairDetails(latest)}${rejected
            .filter((r) => r.id !== latest.id)
            .map(
              (r) =>
                `<details class="attempt" data-key="attempt-${r.id}"><summary>${escape(r.title)} ${badge(r.status)}</summary>${repairDetails(r, true)}</details>`,
            )
            .join("")}`
        : "",
      latest?.status === "rejected"
        ? "rejected"
        : latest
          ? "verifying"
          : "pending",
      latest?.status === "rejected",
    ),
    stage(
      latest
        ? latest.status === "rejected"
          ? "Failed"
          : latest.status === "active"
            ? "Results recorded"
            : "Verifying"
        : "Waiting",
      latest
        ? "Inspect the recorded checks for this exact candidate."
        : "Component, replay, fresh-task, and regression checks have not been recorded.",
      latest
        ? `${tests(latest)}<p>${escape(latest.limits)}</p><p>These are authored test records. No tests run from this interface.</p>`
        : "",
      latest?.status === "rejected"
        ? "rejected"
        : latest?.status === "verifying"
          ? "verifying"
          : latest
            ? "passed"
            : "pending",
      latest?.status === "verifying",
    ),
    stage(
      active
        ? "Active"
        : latest?.status === "rejected"
          ? "Not published"
          : "Waiting",
      active
        ? "The demo records environment v2 as active. The user task has its own outcome."
        : "The current environment remains unchanged until an explicit publication record.",
      active
        ? `<p>${escape(active.versions)}</p><p>Activation is a fixture event. No repair executed or persisted.</p><button class="text-button" data-action="inspect-repair" data-id="${escape(active.id)}">Inspect publication record ${icon("arrow")}</button>`
        : "",
      active ? "active" : "pending",
      !!active && !resumed,
    ),
    stage(
      delivered()
        ? "Delivered"
        : state.status === "delivered"
          ? "Needs confirmation"
          : resumed
            ? "In progress"
            : "Waiting",
      delivered()
        ? "All current checkpoints have matching fixture evidence and an explicit delivery record."
        : resumed
          ? "The executor resumed work. Delivery still requires an explicit task outcome."
          : "Executor continuation and task results appear here independently of repair publication.",
      `${activityList(state.activity.filter((a) => a.type === "supervisor" || a.id === "a7"))}${state.result ? `<h3>Task result</h3>${artifacts()}<p>${escape(state.result.limitations.join(" "))}</p>` : ""}`,
      delivered() ? "passed" : resumed ? "verifying" : "pending",
      resumed,
    ),
  ];
}
function debuggerPage() {
  return `<div class="debugger"><header class="debug-heading"><p class="eyebrow">Epoch / debugger / release preparation</p><h1>${escape(state.title)}</h1><p>${delivered() ? "The release example is delivered. Inspect the repair and the evidence behind each outcome." : !state.evidence.length ? "No execution recorded. This request is preserved, and its pipeline is waiting for evidence." : "Follow the recorded failure, repair decision, and separate task outcome."}</p><div class="debug-meta"><span class="task-state">${escape(label())}</span><span>Revision ${state.revision}</span><span>Fixture environment ${state.repairs.some((r) => r.status === "active") ? "v2" : "v1"}</span></div></header><div class="debug-layout"><div>${pipeline(stageData())}</div>${context()}</div><div class="debug-tabs" role="tablist" aria-label="Evidence sections">${tabs.map(([id, name]) => `<button id="tab-${id}" role="tab" aria-selected="${ui.tab === id}" tabindex="${ui.tab === id ? 0 : -1}" aria-controls="evidence-panel" data-tab="${id}">${name}</button>`).join("")}</div><section id="evidence-panel" class="debug-tab-panel" role="tabpanel" aria-labelledby="tab-${ui.tab}" tabindex="0">${ui.tab === "activity" ? `<h2>Observable activity</h2>${activityList(state.activity)}` : ui.tab === "checkpoints" ? `<h2>Checkpoints</h2><p class="muted">${state.checkpoints.filter((c) => c.status === "passed").length} of ${state.checkpoints.length} fixture passes</p>${checkpointRows()}` : historyContent()}</section></div>`;
}
function assistant(body, name = "Epoch") {
  return `<div class="message assistant"><div class="speaker"><span class="brand-mark">E</span>${name}<small>demo</small></div><div class="message-body">${body}</div></div>`;
}
function chat() {
  if (ui.composing) {
    if (ui.stage === "request")
      return `${welcome()}${ui.error || ui.recoveryUnknown ? `<div class="conversation">${commandError()}</div>` : ""}`;
    return `<div class="conversation"><div class="message user"><div class="message-body"><blockquote>${escape(ui.draft.request)}</blockquote>${ui.draft.constraints ? `<p>${escape(ui.draft.constraints)}</p>` : ""}</div></div>${assistant(`<div class="clarification"><h2>One detail before the brief</h2><p>Where should the result be shared?</p><p class="muted">A fixed demo question. “Just here” is a valid answer.</p></div>`)}${commandError()}</div>`;
  }
  const failure = state.checkpoints.find((c) => c.status === "failed");
  const needsInput = state.checkpoints.find((c) => c.status === "needs-input");
  return `<div class="conversation"><h1>${escape(state.title)}</h1><div class="message user"><div class="message-body"><blockquote>${escape(state.intent.original)}</blockquote></div></div>${assistant(`<p>${!state.example ? "Your request is preserved." : state.revision > 1 ? "Your feedback is recorded as a new revision." : delivered() ? "The release example is ready to inspect." : failure ? "The release ticket is in place. The checklist could not be created, so QA has not been notified." : needsInput ? "The checklist is ready. The QA destination needs confirmation before the notification." : state.activity.length ? "The release example has recorded progress. Inspect the checkpoints below." : "The release request is recorded. Its checkpoints have not started."}</p>${!state.example || state.revision > 1 ? "<p>Execution is pending. Your words are retained without generating an invented plan.</p>" : ""}<details class="disclosure" data-key="brief"><summary>${icon("file")} Task brief & clarification ${icon("down")}</summary><div class="disclosure-body"><p>${escape(state.intent.constraints || "No additional constraints supplied.")}</p>${state.intent.clarifications.map((c) => `<p><strong>${escape(c.question)}</strong><br>${escape(c.answer)}</p>`).join("")}<p class="muted">Inferred: ${escape(state.intent.defaults.join(" "))}</p><button class="text-button" data-action="inspect-intent">Inspect full intent ${icon("arrow")}</button></div></details><details class="disclosure" data-key="chat-checkpoints" open><summary>${icon("check")} Checkpoints <span class="badge">${state.checkpoints.filter((c) => c.status === "passed").length} of ${state.checkpoints.length} fixture passes</span>${icon("down")}</summary><div class="disclosure-body">${checkpointRows()}</div></details>${state.repairs.length ? `<a class="repair-notice" data-route href="${urlFor(true, "debugger", state.taskId, "stage-2")}">${icon("pipeline")}<span><strong>${state.repairs.some((r) => r.status === "active") ? "Repair active · task outcome tracked separately" : "The debugger is investigating"}</strong><small>${state.repairs.at(-1).status === "rejected" ? "First candidate rejected. Review the recorded failure." : "Inspect the candidate, checks, and publication record."}</small></span>${icon("arrow")}</a>` : ""}<details class="disclosure" data-key="chat-activity"><summary>${icon("activity")} Observable activity <span class="badge">${state.activity.length} records</span>${icon("down")}</summary><div class="disclosure-body">${activityList(state.activity)}</div></details>${state.result ? `<h3>${delivered() ? "Delivered fixture results" : "Partial results & gaps"}</h3>${artifacts()}<p class="muted">${escape(state.result.limitations.join(" "))}</p>` : ""}`)}${state.intent.feedback.map((f) => `<div class="message user"><div class="message-body"><p>${escape(f.text)}</p></div></div>`).join("")}${state.history.length ? assistant(`<p>Earlier requirements and results are retained.</p>${routeLink(true, "debugger", state.taskId, "View intent & result history", "history", 'class="back-link"')}`) : ""}<p class="eyebrow task-state">${escape(label())}</p>${commandError()}</div>`;
}
function composer() {
  const formId = ui.composing ? "request-form" : "feedback-form";
  const clarification = ui.composing && ui.stage === "clarification";
  const id = ui.composing
    ? clarification
      ? "destination-text"
      : "request-text"
    : "feedback-text";
  const value = ui.composing
    ? clarification
      ? ui.draft.destination
      : ui.draft.request
    : ui.feedback;
  const title = ui.composing
    ? clarification
      ? "Where should the result be shared?"
      : "Your request"
    : "Your feedback";
  const sendLabel = ui.composing
    ? clarification
      ? "Create fixture task"
      : "Review clarification"
    : "Create fixture revision";
  return `<div class="composer-dock"><form class="composer-box" id="${formId}"><label class="sr-only" for="${id}">${title}</label><textarea id="${id}" data-autogrow data-submit required rows="1" maxlength="${ui.composing ? (clarification ? 200 : 6000) : 4000}" placeholder="${ui.composing ? (clarification ? "A team channel, or just here" : "What should we work on?") : "What would you like to change?"}" ${locked() ? "disabled" : ""}>${escape(value)}</textarea><div class="composer-tools"><div class="composer-tools-left">${
    ui.composing
      ? clarification
        ? `<button class="text-button" data-action="edit-request" ${locked() ? "disabled" : ""}>${icon("back")} Edit request</button>`
        : `<details class="project-menu" data-key="constraints"><summary>${icon("plus")} Constraints ${icon("down")}</summary><div class="popover"><label for="constraints-text">Constraints (optional)</label><textarea id="constraints-text" maxlength="3000" rows="3" ${locked() ? "disabled" : ""}>${escape(ui.draft.constraints)}</textarea></div></details>`
      : `<label class="sr-only" for="feedback-kind">Reason for revision</label><select id="feedback-kind" class="feedback-kind" ${locked() ? "disabled" : ""}>${[
          ["new-preference", "New preference"],
          ["missed-requirement", "Missed requirement or clarification"],
          ["evaluation-concern", "A check may be wrong"],
        ]
          .map(
            ([value, text]) =>
              `<option value="${value}" ${ui.feedbackKind === value ? "selected" : ""}>${text}</option>`,
          )
          .join("")}</select>`
  }</div><div class="composer-tools-right"><span class="composer-hint">${ui.busy ? "Recording…" : "Enter to send · Shift Enter for a new line"}</span><button class="send-button" aria-label="${sendLabel}" ${locked() ? "disabled" : ""}>${icon("send")}</button></div></div></form><p class="composer-caption">${ui.composing ? "Demo request · kept in this page session only" : "Feedback creates a demo revision. Earlier results are kept."}</p></div>`;
}
function commandError() {
  if (ui.recoveryUnknown)
    return `<div class="alert" role="alert"><strong>Previous submission status is unknown</strong><p>The earlier fixture payload was lost on reload. This is a fresh example. No request was resubmitted.</p><button data-action="reset-lost-fixture">Discard lost fixture session</button></div>`;
  return ui.error
    ? `<div class="alert" role="alert"><strong>${ui.submissionStatus === "acknowledgement-unknown" ? "Acknowledgement unknown" : "Submission rejected"}</strong><p>${escape(ui.error)}</p>${ui.pending && !ui.busy ? '<button data-action="retry">Check submission status</button>' : ""}</div>`
    : "";
}
function controls() {
  return `<details class="fixture-controls" data-key="controls"><summary>${icon("box")} Demo controls <span>Manual playback · no execution</span>${icon("down")}</summary><div class="fixture-controls-body"><p>Advance through authored records. No tool or test runs. Reload resets the demo.</p><div class="button-row"><button id="advance-fixture" data-action="advance" ${locked() || !state.example || state.revision !== 1 || adapter.frame >= 8 ? "disabled" : ""}>Advance fixture ${icon("arrow")}</button><button data-action="disconnect" ${locked() ? "disabled" : ""}>Disconnect fixture</button><button data-action="load-example" ${ui.pending || ui.busy || ui.recoveryUnknown ? "disabled" : ""}>Restart release example</button></div><label class="checkbox-label"><input type="checkbox" id="lose-ack" ${adapter.loseNextAcknowledgement ? "checked" : ""} ${ui.pending || ui.busy || ui.recoveryUnknown ? "disabled" : ""}>Lose the next submission acknowledgement</label><label class="checkbox-label"><input type="checkbox" id="fail-reconnect" ${adapter.failNextReconnect ? "checked" : ""}>Fail the next fixture reconnect</label><p class="fixture-cursor">${escape(state.runId)} · revision ${state.revision} · event ${state.seq}</p></div></details>`;
}
function render(options = {}) {
  const page = currentPage();
  const valid = matchedTask();
  const notice =
    state.connection !== "connected"
      ? `<div class="banner-stack"><div class="alert" role="alert"><strong>Fixture updates are paused</strong><p>${escape(state.notice || "Existing evidence is retained. Reconnect reads state without repeating work.")}</p><button data-action="reconnect" ${ui.busy ? "disabled" : ""}>${ui.busy ? "Reconnecting…" : "Reconnect fixture"}</button></div></div>`
      : state.notice
        ? `<div class="banner-stack"><p class="notice">${escape(state.notice)}</p></div>`
        : "";
  const content = valid
    ? `${notice}${page === "debugger" ? (ui.composing ? empty("Your request is still a draft", "Return to chat to finish the request. No execution has been recorded.", "pipeline") : debuggerPage()) : chat()}${page === "debugger" ? commandError() : ""}${controls()}`
    : `${commandError()}${empty("Demo session unavailable", "Reload resets the demo session. Choose the current release example from the sidebar.")}`;
  view.render(
    shell({
      demo: true,
      page,
      task: ui.composing ? "" : state.taskId,
      title: ui.composing ? "New chat" : state.title,
      nav: navigation(),
      content,
      locked: locked(),
      composer: page === "chat" && valid ? composer() : "",
      actions:
        page === "chat" && !ui.composing
          ? routeLink(
              true,
              "debugger",
              state.taskId,
              "Open debugger",
              "pipeline",
              'class="back-link"',
            )
          : "",
    }),
    `${page}:${ui.composing ? "new" : state.taskId}:${state.revision}`,
    options,
  );
}
function newChat() {
  if (locked()) return;
  ui.composing = true;
  ui.error = "";
  history.pushState({ epochDraft: true }, "", urlFor(true, "chat"));
  document.body.classList.remove("nav-open");
  render({
    focus: ui.stage === "request" ? "request-text" : "destination-text",
  });
}
function routeChanged({ fromLink = false } = {}) {
  // /demo/chat without a task is the current draft; task links restore the conversation.
  const id = new URLSearchParams(location.search).get("task");
  ui.composing =
    !id && (history.state?.epochDraft === true || (fromLink && ui.composing));
  if (ui.composing)
    history.replaceState({ epochDraft: true }, "", location.href);
  render();
  if (location.hash) {
    const el = document.getElementById(
      decodeURIComponent(location.hash.slice(1)),
    );
    if (el) {
      const details = el.querySelector("details");
      if (details) details.open = true;
      el.scrollIntoView({ block: "start" });
    }
  }
}
async function sendCommand(command = ui.pending) {
  if (state.connection !== "connected" || ui.busy || ui.recoveryUnknown) return;
  const reconciling = !!ui.pending;
  if (!ui.pending) ui.pending = freezeSubmission(command);
  command = ui.pending;
  if (!reconciling && !markPending(command)) {
    ui.pending = null;
    ui.submissionStatus = "rejected";
    ui.error =
      "The recovery marker could not be saved. This action was not submitted; your draft is retained.";
    render();
    return;
  }
  ui.submissionStatus = reconciling ? "acknowledgement-unknown" : "submitting";
  ui.busy = true;
  ui.error = "";
  render();
  try {
    let snapshot;
    if (reconciling) {
      const result = await adapter.lookup(command);
      if (result.status !== "accepted")
        throw new Error(
          "The submitted identity cannot be reconciled. Keep this action pending; no replacement or replay is safe.",
        );
      snapshot = result.snapshot;
    } else snapshot = await adapter.command(command);
    if (command.kind === "feedback") {
      const adopted = adoptScope(state, snapshot, command);
      if (adopted.connection !== "connected") throw new Error(adopted.notice);
      state = adopted;
    } else state = snapshot;
    ui.pending = null;
    ui.submissionStatus = "accepted";
    markPending(null);
    ui.composing = false;
    ui.feedback = "";
    ui.draft = { request: "", constraints: "", destination: "" };
    ui.draftId = crypto.randomUUID();
    ui.stage = "request";
    history.replaceState(null, "", urlFor(true, "chat", state.taskId));
    announce("Fixture submission recorded. No execution started.");
  } catch (error) {
    ui.error = error.message;
    if (error.code === "rejected") {
      ui.pending = null;
      ui.submissionStatus = "rejected";
      markPending(null);
    } else ui.submissionStatus = "acknowledgement-unknown";
    announce(error.message);
  } finally {
    ui.busy = false;
    render({ bottom: !ui.error });
  }
}
root.addEventListener("input", (e) => {
  const { id, value, checked } = e.target;
  if (id === "request-text") ui.draft.request = value;
  if (id === "constraints-text") ui.draft.constraints = value;
  if (id === "destination-text") ui.draft.destination = value;
  if (id === "feedback-text") ui.feedback = value;
  if (id === "feedback-kind") ui.feedbackKind = value;
  if (id === "lose-ack") adapter.loseNextAcknowledgement = checked;
  if (id === "fail-reconnect") adapter.failNextReconnect = checked;
});
root.addEventListener("submit", (e) => {
  e.preventDefault();
  if (locked()) return;
  if (e.target.id === "request-form") {
    if (!ui.draft.request.trim()) {
      ui.error = "Describe the result you want.";
      render({ focus: "request-text" });
      return;
    }
    ui.error = "";
    if (ui.stage === "request") {
      ui.stage = "clarification";
      render({ focus: "destination-text" });
      return;
    }
    if (!ui.draft.destination.trim()) {
      ui.error = "Specify a destination, or enter “just here”.";
      render({ focus: "destination-text" });
      return;
    }
    sendCommand({ id: ui.draftId, kind: "create", payload: { ...ui.draft } });
  } else if (e.target.id === "feedback-form") {
    if (!ui.feedback.trim()) {
      ui.error = "Describe the change you want.";
      render({ focus: "feedback-text" });
      return;
    }
    sendCommand({
      id: crypto.randomUUID(),
      kind: "feedback",
      taskId: state.taskId,
      expectedRevision: state.revision,
      payload: { text: ui.feedback, kind: ui.feedbackKind },
    });
  }
});
root.addEventListener("click", async (e) => {
  const b = e.target.closest("button");
  if (!b || b.disabled) return;
  if (b.dataset.tab) {
    ui.tab = b.dataset.tab;
    render({ focus: `tab-${ui.tab}` });
    return;
  }
  const action = b.dataset.action;
  if (
    ui.recoveryUnknown &&
    ["new", "edit-request", "retry", "advance", "load-example"].includes(action)
  )
    return;
  const owner =
    b.dataset.run && b.dataset.run !== state.runId
      ? state.history.find(
          (s) =>
            s.runId === b.dataset.run &&
            s.revision === Number(b.dataset.revision),
        )
      : state;
  switch (action) {
    case "new":
      newChat();
      break;
    case "edit-request":
      if (locked()) return;
      ui.stage = "request";
      render({ focus: "request-text" });
      break;
    case "retry":
      await sendCommand();
      break;
    case "advance": {
      if (locked()) return;
      const frame = adapter.next();
      for (const update of frame.events) state = acceptEvent(state, update);
      render();
      announce(`Fixture: ${frame.label}. No real execution.`);
      break;
    }
    case "disconnect":
      state = { ...state, connection: "disconnected", notice: "" };
      render();
      announce("Fixture disconnected. Evidence retained.");
      break;
    case "reconnect": {
      ui.busy = true;
      render();
      try {
        state = reconnectState(state, await adapter.reconnect());
      } catch {
        state = {
          ...state,
          connection: "disconnected",
          notice:
            "Fixture reconnect failed. Try again; existing work is retained.",
        };
      } finally {
        ui.busy = false;
        render();
        announce(state.notice);
      }
      break;
    }
    case "load-example":
      adapter = new FixtureAdapter({ startAtFailure: false });
      state = adapter.snapshot();
      ui.composing = false;
      ui.error = "";
      ui.tab = "activity";
      history.replaceState(null, "", urlFor(true, currentPage(), state.taskId));
      render();
      announce(
        "Release example reset to planned. Previous fixture session cleared.",
      );
      break;
    case "reset-lost-fixture":
      if (!markPending(null)) {
        ui.error = "Browser storage remains unavailable.";
        render();
        return;
      }
      ui.recoveryUnknown = false;
      ui.submissionStatus = "idle";
      render();
      break;
    case "inspect-intent":
      inspect(
        `Intent · revision ${state.revision} · fixture`,
        state.intent,
        true,
      );
      break;
    case "inspect-checkpoint": {
      const cp = state.checkpoints.find((c) => c.id === b.dataset.id);
      inspect(
        "Checkpoint source & fixture evidence",
        { ...cp, evidence: checkpointEvidence(state, cp) },
        true,
      );
      break;
    }
    case "inspect-evidence":
      inspect(
        "Inspectable fixture artifact / evidence",
        owner?.evidence.find((e) => e.id === b.dataset.id) || {
          missing: "Evidence unavailable. This is not proof of success.",
        },
        true,
      );
      break;
    case "inspect-repair":
      inspect(
        "Repair record · fixture",
        state.repairs.find((r) => r.id === b.dataset.id),
        true,
      );
      break;
    case "inspect-history":
      inspect(
        `Revision ${owner?.revision} · retained fixture history`,
        owner,
        true,
      );
      break;
  }
});
root.addEventListener("keydown", (e) => {
  if (
    e.target.getAttribute("role") !== "tab" ||
    !["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)
  )
    return;
  e.preventDefault();
  const i = tabs.findIndex(([id]) => id === ui.tab);
  ui.tab =
    tabs[
      e.key === "Home"
        ? 0
        : e.key === "End"
          ? tabs.length - 1
          : (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length
    ][0];
  render({ focus: `tab-${ui.tab}` });
});
render();
