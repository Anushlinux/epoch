import { FixtureAdapter } from "./fixtures.mjs";
import {
  acceptEvent,
  reconnectState,
  checkpointEvidence,
  adoptScope,
  freezeSubmission,
} from "./state.mjs";

const $ = (selector) => document.querySelector(selector);
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const paths = {
  plus: "M12 5v14M5 12h14",
  layers: "m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  arrowLeft: "M19 12H5m5-5-5 5 5 5",
  chevron: "m9 5 7 7-7 7",
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6ZM14 2v6h6M8 13h8M8 17h6",
  activity: "M3 12h4l3-8 4 16 3-8h4",
  wrench:
    "m14 6 4 4M21 3l-5 5M21 3a6 6 0 0 1-8 8L5 19a2 2 0 0 1-3-3l8-8a6 6 0 0 1 8-8",
  info: "M12 11v6M12 7h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  history: "M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2",
  box: "m12 3 9 5v9l-9 5-9-5V8l9-5Zm0 10v9M3 8l9 5 9-5M8 5l9 5",
  alert: "m12 3 10 18H2L12 3ZM12 9v5M12 17h.01",
  link: "m10 13 4-4M8 15l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M16 9l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0",
};
const icon = (name) =>
  `<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${(
    paths[name] || paths.file
  )
    .split("ZZ")
    .map((d) => `<path d="${d}"/>`)
    .join("")}</svg>`;
const pendingMarker = "epoch.fixture.pending";
const markPending = (command) => {
  try {
    if (command)
      sessionStorage.setItem(pendingMarker, JSON.stringify({ id: command.id }));
    else sessionStorage.removeItem(pendingMarker);
    return true;
  } catch {
    /* No task content is stored; reload fallback below stays conservative. */
    return false;
  }
};
const hasLostSubmission = () => {
  try {
    return sessionStorage.getItem(pendingMarker) !== null;
  } catch {
    return performance.getEntriesByType("navigation")[0]?.type === "reload";
  }
};
let adapter = new FixtureAdapter();
let state = adapter.snapshot();
let ui = {
  tab: "overview",
  composer: false,
  stage: "request",
  draft: { request: "", constraints: "", destination: "" },
  draftId: crypto.randomUUID(),
  feedback: "",
  feedbackKind: "new-preference",
  pending: null,
  submissionStatus: "idle",
  recoveryUnknown: hasLostSubmission(),
  busy: false,
  error: "",
};
let inspection = null;
const tabs = [
  ["overview", "Overview"],
  ["activity", "Activity"],
  ["repairs", "Repairs"],
  ["results", "Results"],
  ["history", "History"],
];
const announce = (text) => {
  $("#announcement").textContent = text;
};
const badge = (status) =>
  `<span class="badge ${escape(status)}"><span class="state-dot" aria-hidden="true"></span>${escape(status === "needs-input" ? "Needs input" : status[0].toUpperCase() + status.slice(1))}</span>`;
const taskLabel = () =>
  state.status === "delivered"
    ? "Delivered · fixture"
    : state.checkpoints.some((c) => c.status === "failed")
      ? "Needs attention · fixture"
      : state.checkpoints.some((c) => c.status === "needs-input")
        ? "Needs input · fixture"
        : state.checkpoints.some((c) =>
              ["running", "checking"].includes(c.status),
            )
          ? "In progress · fixture"
          : state.status === "planned"
            ? "Planned · fixture"
            : "Incomplete · fixture";
function header() {
  return `<div class="demo-banner"><span>${icon("info")}<strong>Fixture workspace</strong><span class="banner-description">All progress, tests and artifacts are authored examples. No task is executing.</span></span><a href="./CONTRACT-PROPOSAL.md" target="_blank" rel="noopener">Integration pending ${icon("arrow")}</a></div>
  <header class="topbar"><div class="breadcrumb">Workspace ${icon("chevron")} <strong>Release preparation</strong></div><div class="connection"><span class="connection-dot ${state.connection === "connected" ? "" : "offline"}"></span>${state.connection === "connected" ? "Local fixtures" : "Updates paused"}</div></header>`;
}
function sidebar() {
  return `<aside class="sidebar"><a class="brand" href="./index.html" aria-label="Epoch saved tasks"><img src="./mark.svg" alt="" width="32" height="32">epoch<span>preview</span></a>
    <button class="new-task" data-action="new" ${ui.pending || ui.recoveryUnknown ? "disabled" : ""}>${icon("plus")} New request</button>
    <nav aria-label="Workspace"><a href="./index.html">Saved tasks · real API</a><p class="nav-label">Fixture workspace</p><button class="nav-item selected" data-action="task">${icon("layers")} Task workspace <span class="nav-count">1</span></button></nav>
    <div class="task-nav"><p class="nav-label">Current task</p><button data-action="task" class="current-task"><span class="task-bullet"></span><span>${escape(state.title)}<small>${taskLabel()}</small></span></button></div>
    <div class="sidebar-bottom"><div class="local-label">${icon("box")} Development space</div><p>Session memory only.<br>Reloading restores the example.</p><a href="./README.md" target="_blank" rel="noopener">Frontend handoff ${icon("arrow")}</a></div>
  </aside>`;
}
function sources() {
  return `<aside class="context-column"><section><h2>Task brief</h2><div class="source-label">${icon("file")} Original request · revision 1</div><blockquote>${escape(state.intent.original)}</blockquote><button class="text-button" data-action="inspect-intent">Inspect full intent ${icon("arrow")}</button></section>
    <section><h3>Constraints</h3><p>${escape(state.intent.constraints || "No additional constraints supplied.")}</p><span class="source-tag">Explicit · user input</span></section>
    <section><h3>Clarification</h3><p>${escape(state.intent.clarifications[0].question)}</p><div class="answer">${escape(state.intent.clarifications[0].answer)}</div><span class="source-tag">Explicit · clarification answer</span></section>
    <section><h3>Inferred default</h3><p>${escape(state.intent.defaults[0])}</p><span class="source-tag">Inferred · fixture brief, open to revision</span></section>
    ${state.intent.feedback.length ? `<section><h3>Latest revision</h3><p>${escape(state.intent.feedback.at(-1).text)}</p><button class="text-button" data-tab="history">View retained history ${icon("arrow")}</button></section>` : ""}
    <div class="boundary-note">${icon("info")}<p>Requirements stay attached to their source. A repair never changes what “done” means.</p></div></aside>`;
}
function checkpointRows() {
  return state.checkpoints
    .map(
      (cp, i) =>
        `<article class="checkpoint"><div class="checkpoint-index ${escape(cp.status)}">${i + 1}</div><div class="checkpoint-body"><div class="checkpoint-heading"><h3>${escape(cp.text)}</h3>${badge(cp.status)}</div><p class="checkpoint-source">${escape(cp.source.kind)} · ${escape(cp.source.label)}<span>Criterion v${cp.criterionVersion}</span></p><p class="checkpoint-detail">${escape(checkpointEvidence(state, cp).at(-1)?.observed || (cp.dependencies.length ? `Depends on ${cp.dependencies.join(" + ")}. No outcome evidence yet.` : "Waiting for an outcome record."))}</p><button class="text-button small" data-action="inspect-checkpoint" data-id="${escape(cp.id)}">${icon("link")} ${cp.evidenceIds.length ? "Inspect evidence & source" : "Inspect requirement source"}</button></div></article>`,
    )
    .join("");
}
function overview() {
  const failed = state.checkpoints.find((c) => c.status === "failed");
  const needsInput = state.checkpoints.find((c) => c.status === "needs-input");
  return `<div class="overview-grid"><div class="main-column">
    ${failed ? `<div class="attention"><span class="attention-icon">${icon("alert")}</span><div><h2>The checklist needs attention</h2><p>The fixture ticket is retained. Checklist creation failed, so QA has not been notified.</p><button class="text-button" data-tab="repairs">Review repair evidence ${icon("arrow")}</button></div></div>` : needsInput ? `<div class="attention"><span>${icon("info")}</span><div><h2>A clarification is needed</h2><p>${escape(checkpointEvidence(state, needsInput).at(-1)?.observed)}</p><button class="text-button" data-tab="results">Record a clarification as feedback ${icon("arrow")}</button></div></div>` : state.status === "delivered" ? `<div class="delivery-note"><h2>Fixture results are ready to inspect</h2><p>The authored sequence has ended. These results do not establish actual execution.</p><button class="text-button" data-tab="results">Inspect fixture artifacts ${icon("arrow")}</button></div>` : `<div class="quiet-note"><h2>${state.revision > 1 ? "Revision recorded. Execution is pending." : state.example ? "Follow the work, one checkpoint at a time." : "Your request is preserved."}</h2><p>${state.example && state.revision === 1 ? "Use the fixture controls to explore the interface. Progress advances only when you request it." : "Backend interpretation is unavailable. The original request is shown verbatim; the fixture does not invent an executable plan."}</p></div>`}
    <section class="checkpoint-section"><div class="section-heading"><h2>Checkpoints</h2><span>${state.checkpoints.filter((c) => c.status === "passed").length} of ${state.checkpoints.length} fixture passes</span></div><p class="section-description">Each outcome is tied to its original requirement and evidence.</p><div class="checkpoint-list">${checkpointRows()}</div><p class="evidence-caption">${icon("info")} All states above are fixtures, including passed. No real checks have run.</p></section>
    <section class="activity-preview"><div class="section-heading"><h2>Latest activity</h2><button class="text-button" data-tab="activity">View all ${icon("arrow")}</button></div>${state.activity.length ? activityList(state.activity.slice(-2)) : empty("activity", "No activity captured", "This request has not executed. Future captured tool calls and explicit progress summaries will appear here.")}</section>
  </div>${sources()}</div>`;
}
function empty(glyph, title, description) {
  return `<div class="empty-state">${icon(glyph)}<h3>${title}</h3><p>${description}</p></div>`;
}
function activityList(items) {
  return `<ol class="activity-list">${items.map((a) => `<li><span class="activity-mark">${icon(a.type === "supervisor" ? "arrow" : a.type === "context" ? "file" : "activity")}</span><div><div class="activity-title"><h3>${escape(a.title)}</h3><span>${escape(a.time)}</span></div><p>${escape(a.detail)}</p><span class="source-tag">Fixture · ${escape(a.type)}</span></div></li>`).join("")}</ol>`;
}
function activity() {
  return `<div class="panel-heading"><h2>Observable activity</h2><p>Captured calls, results, context and explicit supervisor messages. Every entry here is an authored fixture.</p></div>${state.activity.length ? activityList(state.activity) : empty("activity", "No captured activity", "Nothing has executed for this revision. Missing activity is not proof that a business step happened or failed.")}`;
}
function repairs() {
  return `<div class="panel-heading"><h2>Repair evidence</h2><p>Environment changes have their own verification history. An active repair does not complete the user’s task.</p></div>${
    state.repairs.length
      ? state.repairs
          .map(
            (r, index) =>
              `<details class="repair-record" ${index === state.repairs.length - 1 ? "open" : ""}><summary><span>${icon("wrench")}<strong>${escape(r.title)}</strong></span>${badge(r.status)}</summary><div class="repair-content"><p class="fixture-note">Authored fixture diagnosis, diff and test records · nothing executed</p><h3>Diagnosis</h3><p>${escape(r.diagnosis)}</p><p class="muted">${escape(r.uncertainty)}</p><dl class="repair-meta"><div><dt>Trigger evidence</dt><dd><button class="text-button" data-action="inspect-evidence" data-id="${escape(r.trigger)}">${escape(r.trigger)} ${icon("arrow")}</button></dd></div><div><dt>Permitted surface</dt><dd>${escape(r.scope)}</dd></div></dl><h3>Candidate diff</h3><pre class="diff" tabindex="0" aria-label="Illustrative candidate diff">${r.diff
                .split("\n")
                .map(
                  (line) =>
                    `<span class="${line.startsWith("+") ? "addition" : line.startsWith("-") ? "deletion" : ""}">${escape(line)}</span>`,
                )
                .join(
                  "\n",
                )}</pre><h3>Verification records <span class="subtle">· fixtures</span></h3><div class="test-table" role="table" aria-label="Fixture verification records"><div class="test-row test-head" role="row"><span role="columnheader">Check</span><span role="columnheader">Recorded result</span></div>${r.tests.map((t) => `<div class="test-row" role="row"><div role="cell"><strong>${escape(t.name)}</strong><p>${escape(t.detail)}</p></div><span role="cell">${badge(t.status)}</span></div>`).join("")}</div><p class="repair-reason">${escape(r.reason)}</p><p class="muted">${escape(r.versions)}</p><p class="muted">${escape(r.limits)}</p><button class="text-button" data-action="inspect-repair" data-id="${escape(r.id)}">Inspect full fixture record ${icon("arrow")}</button></div></details>`,
          )
          .join("")
      : empty(
          "wrench",
          "No repair records for this revision",
          "A request or user preference does not automatically trigger an environment repair.",
        )
  }`;
}
function artifacts(owner = state) {
  const records =
    owner.result?.artifactIds
      .map((id) => owner.evidence.find((e) => e.id === id))
      .filter(Boolean) || [];
  return records.length
    ? `<div class="artifact-list">${records.map((e) => `<button class="artifact" data-action="inspect-evidence" data-id="${escape(e.id)}" data-revision="${owner.revision}" data-run="${escape(owner.runId)}"><span class="artifact-icon">${icon(e.object?.type === "message" ? "activity" : "file")}</span><span><strong>${escape(e.object?.id || e.id)}</strong><small>${escape(e.object?.type || "record")} · fixture JSON · revision ${owner.revision}</small></span>${icon("arrow")}</button>`).join("")}</div>`
    : empty(
        "box",
        "No result artifacts yet",
        "Results appear only when an explicit outcome includes inspectable evidence. Repair status alone cannot produce a result.",
      );
}
function results() {
  return `<div class="results-grid"><section><div class="panel-heading"><h2>${state.status === "delivered" ? "Delivered fixture results" : "Partial results & gaps"}</h2><p>${state.status === "delivered" ? "Inspect the authored objects behind each fixture outcome." : "Completed partial effects remain inspectable while other requirements are unresolved."}</p></div>${artifacts()}<div class="limitations"><h3>Limitations</h3><ul>${(state.result?.limitations || ["No task has executed for this revision.", "Backend contracts and integration remain pending."]).map((l) => `<li>${escape(l)}</li>`).join("")}</ul></div></section>
    <section class="feedback-section"><h2>What needs to change?</h2><p>Record feedback as a new intent revision. Keep this request, its evidence and its results in history.</p><form id="feedback-form"><fieldset ${ui.busy || ui.pending || ui.recoveryUnknown || state.connection !== "connected" ? "disabled" : ""}><label for="feedback-kind">Reason for revision</label><select id="feedback-kind" name="kind"><option value="new-preference" ${ui.feedbackKind === "new-preference" ? "selected" : ""}>New preference</option><option value="missed-requirement" ${ui.feedbackKind === "missed-requirement" ? "selected" : ""}>Missed requirement or clarification</option><option value="evaluation-concern" ${ui.feedbackKind === "evaluation-concern" ? "selected" : ""}>A check may be wrong</option></select><label for="feedback-text">Your feedback</label><textarea id="feedback-text" name="feedback" required maxlength="4000" rows="5" placeholder="For example, include the rollback owner in the checklist.">${escape(ui.feedback)}</textarea><p class="field-hint">Your exact feedback is retained. This does not authorize a shared-tool repair.</p><button class="primary" type="submit">${ui.busy ? "Recording…" : "Create fixture revision"} ${icon("arrow")}</button></fieldset></form><p class="fixture-note">Saved in this page session only. No backend execution starts.</p></section></div>`;
}
function history() {
  return `<div class="panel-heading"><h2>Intent & result history</h2><p>Previous requirements, clarifications, checkpoints, artifacts and rejected attempts remain attached to their revision.</p></div><div class="current-revision"><strong>Revision ${state.revision} · current</strong><p>${escape(state.intent.feedback.at(-1)?.text || state.intent.original)}</p></div>${
    state.history.length
      ? [...state.history]
          .reverse()
          .map(
            (previous) =>
              `<details class="history-record" open><summary><strong>Revision ${previous.revision}</strong><span>${escape(previous.status)} · fixture</span></summary><div><h3>Original request</h3><p>${escape(previous.intent.original)}</p><h3>Constraints</h3><p>${escape(previous.intent.constraints || "None supplied.")}</p>${previous.intent.feedback.map((f) => `<p>Revision feedback: ${escape(f.text)}</p>`).join("")}<h3>Checkpoints at revision boundary</h3><ul>${previous.checkpoints.map((cp) => `<li>${escape(cp.text)} · ${escape(cp.status)} · criterion v${cp.criterionVersion}</li>`).join("")}</ul>${artifacts(previous)}<button class="text-button" data-action="inspect-history" data-revision="${previous.revision}" data-run="${escape(previous.runId)}">Inspect complete revision & repair history ${icon("arrow")}</button></div></details>`,
          )
          .join("")
      : empty(
          "history",
          "The original request is intact",
          "Submit feedback from Results to create a revision. Previous outcomes and requirements will be retained here.",
        )
  }`;
}
function commandError() {
  if (ui.recoveryUnknown)
    return `<div class="form-error" role="alert"><strong>Previous submission status is unknown</strong><p>The prior fixture adapter and submitted payload were lost on reload. This is a fresh example, not the previous task. No request was resubmitted. Recovery cannot be verified locally.</p><button data-action="reset-lost-fixture" type="button">Discard lost fixture session</button><p>Clears only this local fixture warning; never repeats or cancels backend work.</p></div>`;
  return ui.error
    ? `<div class="form-error" role="alert"><strong>${ui.submissionStatus === "acknowledgement-unknown" ? "Acknowledgement unknown" : "Submission rejected"}</strong><p>${escape(ui.error)}</p>${ui.pending && !ui.busy ? '<button data-action="retry" type="button">Check submission status</button>' : ""}</div>`
    : "";
}
function composer() {
  return `<div class="composer"><button class="text-button" data-action="back" ${ui.pending || ui.recoveryUnknown ? "disabled" : ""}>${icon("arrowLeft")} Back to task</button><h1>${ui.stage === "request" ? "What should get done?" : "One detail before the brief"}</h1><p class="composer-intro">Describe the result you want. Your original words and constraints stay with the task.</p><form id="request-form"><fieldset ${ui.busy || ui.pending || ui.recoveryUnknown ? "disabled" : ""}>${ui.stage === "request" ? `<label for="request-text">Your request</label><textarea id="request-text" name="request" rows="5" required maxlength="6000" placeholder="Prepare a release, collect the evidence, and share the result…">${escape(ui.draft.request)}</textarea><label for="constraints-text">Constraints <span class="subtle">(optional)</span></label><textarea id="constraints-text" name="constraints" rows="3" maxlength="3000" placeholder="What must be kept, avoided, or checked?">${escape(ui.draft.constraints)}</textarea><p class="field-hint">Do not include credentials or secrets. This is a local UI fixture.</p><button class="primary" type="submit">Review clarification ${icon("arrow")}</button>` : `<div class="request-review"><h2>Your request · unchanged</h2><p>${escape(ui.draft.request)}</p><h3>Constraints</h3><p>${escape(ui.draft.constraints || "None supplied.")}</p></div><label for="destination-text">Where should the result be shared?</label><input id="destination-text" name="destination" required maxlength="200" value="${escape(ui.draft.destination)}" placeholder="A team channel, or just here"><p class="field-hint">A fixed fixture question, not a backend-generated clarification. “Just here” is a valid answer.</p><div class="button-row"><button type="button" data-action="edit-request">Edit request</button><button class="primary" type="submit">${ui.busy ? "Recording…" : "Create fixture task"} ${icon("arrow")}</button></div>`}</fieldset></form><div class="boundary-note">${icon("info")}<p>Backend interpretation is pending. Custom requests remain verbatim and do not receive invented execution progress.</p></div></div>`;
}
function fixtureControls() {
  return `<details class="fixture-controls"><summary>${icon("box")} Fixture controls <span>Manual playback · no execution</span></summary><div class="fixture-controls-body"><p>Explore authored states and connection failures. Advancing never runs a tool or test. A reload resets this session.</p><div class="button-row"><button id="advance-fixture" data-action="advance" ${state.connection !== "connected" || !state.example || state.revision !== 1 || adapter.frame >= 8 || ui.pending || ui.busy || ui.recoveryUnknown ? "disabled" : ""}>Advance fixture ${icon("arrow")}</button><button data-action="disconnect" ${state.connection !== "connected" || ui.pending || ui.busy || ui.recoveryUnknown ? "disabled" : ""}>Disconnect fixture</button><button data-action="load-example" ${ui.pending || ui.busy || ui.recoveryUnknown ? "disabled" : ""}>Restart release example</button></div><label class="checkbox-label"><input type="checkbox" id="lose-ack" ${adapter.loseNextAcknowledgement ? "checked" : ""} ${ui.pending || ui.busy || ui.recoveryUnknown ? "disabled" : ""}> Lose the next submission acknowledgement</label><label class="checkbox-label"><input type="checkbox" id="fail-reconnect" ${adapter.failNextReconnect ? "checked" : ""}> Fail the next fixture reconnect</label><p class="fixture-cursor">${escape(state.runId)} · revision ${state.revision} · event ${state.seq}</p></div></details>`;
}
function render(focusId) {
  $("#app").innerHTML =
    `${sidebar()}<div class="shell">${header()}<main id="workspace" tabindex="-1">${state.connection !== "connected" ? `<div class="reconnect-banner" role="alert"><div><strong>Fixture updates are paused</strong><p>${escape(state.notice || "Connection interrupted. Existing evidence is retained. Reconnect retrieves state without repeating work.")}</p></div><button data-action="reconnect" ${ui.busy ? "disabled" : ""}>${ui.busy ? "Reconnecting…" : "Reconnect fixture"}</button></div>` : state.notice ? `<div class="notice" role="status">${escape(state.notice)}</div>` : ""}${commandError()}${ui.composer ? composer() : `<div class="task-heading"><div><p class="task-identity">${icon("layers")} Task workspace <span>/</span> Revision ${state.revision}</p><h1>${escape(state.title)}</h1><div class="task-meta"><span class="task-state">${taskLabel()}</span><span>Environment: fixture ${state.repairs.some((r) => r.status === "active") ? "v2" : "v1"}</span></div></div><button data-action="revise" ${ui.pending || ui.recoveryUnknown ? "disabled" : ""}>Revise request ${icon("arrow")}</button></div><div class="tabs" role="tablist" aria-label="Task sections">${tabs.map(([id, label]) => `<button id="tab-${id}" role="tab" ${ui.pending || ui.recoveryUnknown ? "disabled" : ""} aria-selected="${ui.tab === id}" tabindex="${ui.tab === id ? 0 : -1}" aria-controls="task-panel" data-tab="${id}">${label}${id === "repairs" && state.repairs.length ? `<span class="tab-count">${state.repairs.length}</span>` : ""}</button>`).join("")}</div><div id="task-panel" role="tabpanel" aria-labelledby="tab-${ui.tab}" tabindex="0">${{ overview, activity, repairs, results, history }[ui.tab]()}</div>`}${fixtureControls()}<footer>Epoch frontend preview <span>PROPOSED contract · integration blocked</span></footer></main></div>`;
  if (focusId) document.getElementById(focusId)?.focus();
}
function inspect(title, data) {
  inspection = data;
  $("#inspector-title").textContent = title;
  $("#inspector-content").replaceChildren();
  const pre = document.createElement("pre");
  pre.tabIndex = 0;
  pre.textContent = JSON.stringify(data, null, 2);
  $("#inspector-content").append(pre);
  $("#inspector").showModal();
  $("#close-inspector").focus();
}
function switchTab(tab, focus = false) {
  ui.tab = tab;
  ui.composer = false;
  render(focus ? `tab-${tab}` : undefined);
}
async function sendCommand(command = ui.pending) {
  if (ui.busy || ui.recoveryUnknown) return;
  const reconciling = Boolean(ui.pending);
  if (!ui.pending) ui.pending = freezeSubmission(command);
  command = ui.pending;
  if (!reconciling && !markPending(command)) {
    ui.pending = null;
    ui.submissionStatus = "rejected";
    ui.error =
      "The fixture recovery marker could not be saved. This action was not submitted; your draft is retained.";
    render();
    return;
  }
  ui.submissionStatus = reconciling ? "acknowledgement-unknown" : "submitting";
  ui.busy = true;
  ui.error = "";
  render();
  announce(
    reconciling
      ? "Checking fixture submission status; no work is being replayed."
      : "Recording fixture submission.",
  );
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
    ui.composer = false;
    ui.tab = command.kind === "feedback" ? "history" : "overview";
    ui.feedback = "";
    ui.draft = { request: "", constraints: "", destination: "" };
    ui.draftId = crypto.randomUUID();
    ui.stage = "request";
    announce("Fixture submission recorded. No task execution started.");
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
    render(ui.error ? undefined : `tab-${ui.tab}`);
  }
}
$("#app").addEventListener("input", (event) => {
  const { id, value, checked } = event.target;
  if (id === "request-text") ui.draft.request = value;
  if (id === "constraints-text") ui.draft.constraints = value;
  if (id === "destination-text") ui.draft.destination = value;
  if (id === "feedback-text") ui.feedback = value;
  if (id === "feedback-kind") ui.feedbackKind = value;
  if (id === "lose-ack") adapter.loseNextAcknowledgement = checked;
  if (id === "fail-reconnect") adapter.failNextReconnect = checked;
});
$("#app").addEventListener("submit", (event) => {
  event.preventDefault();
  if (ui.busy || ui.pending || ui.recoveryUnknown) return;
  if (event.target.id === "request-form") {
    if (!ui.draft.request.trim()) {
      ui.error = "Describe the result you want before continuing.";
      render("request-text");
      return;
    }
    ui.error = "";
    if (ui.stage === "request") {
      ui.stage = "clarification";
      render("destination-text");
      return;
    }
    if (!ui.draft.destination.trim()) {
      ui.error = "Specify a destination, or enter “just here”.";
      render("destination-text");
      return;
    }
    sendCommand({ id: ui.draftId, kind: "create", payload: { ...ui.draft } });
  } else if (event.target.id === "feedback-form") {
    if (!ui.feedback.trim()) {
      ui.error = "Describe the change you want.";
      render("feedback-text");
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
$("#app").addEventListener("click", async (event) => {
  const button = event.target.closest("button");
  if (!button || button.disabled) return;
  if (ui.recoveryUnknown && button.dataset.action === "reset-lost-fixture") {
    markPending(null);
    ui.recoveryUnknown = false;
    ui.submissionStatus = "idle";
    render();
    announce("Lost local fixture session discarded. No action was replayed.");
    return;
  }
  if (
    ui.recoveryUnknown &&
    [
      "new",
      "edit-request",
      "revise",
      "retry",
      "advance",
      "load-example",
    ].includes(button.dataset.action)
  )
    return;
  if (button.dataset.tab) {
    switchTab(button.dataset.tab, true);
    return;
  }
  const id = button.dataset.id;
  const owner =
    button.dataset.run && button.dataset.run !== state.runId
      ? state.history.find(
          (s) =>
            s.runId === button.dataset.run &&
            s.revision === Number(button.dataset.revision),
        )
      : state;
  switch (button.dataset.action) {
    case "new":
      ui.composer = true;
      ui.error = "";
      render("request-text");
      break;
    case "task":
    case "back":
      if (ui.pending) return;
      ui.composer = false;
      render("tab-overview");
      break;
    case "edit-request":
      ui.stage = "request";
      render("request-text");
      break;
    case "revise":
      ui.tab = "results";
      ui.composer = false;
      render("feedback-text");
      break;
    case "retry":
      await sendCommand();
      break;
    case "advance": {
      const frame = adapter.next();
      for (const update of frame.events) state = acceptEvent(state, update);
      announce(`Fixture: ${frame.label}. No real execution.`);
      render();
      document.querySelector(".fixture-controls").open = true;
      document.getElementById("advance-fixture").focus();
      break;
    }
    case "disconnect":
      state = { ...state, connection: "disconnected", notice: "" };
      render();
      announce("Fixture disconnected. Current evidence retained.");
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
      ui.composer = false;
      ui.tab = "overview";
      ui.error = "";
      render("tab-overview");
      announce(
        "Release example reset to planned. Previous fixture session was cleared.",
      );
      break;
    case "inspect-intent":
      inspect(`Intent · revision ${state.revision} · fixture`, state.intent);
      break;
    case "inspect-checkpoint": {
      const cp = state.checkpoints.find((c) => c.id === id);
      inspect("Checkpoint source & fixture evidence", {
        ...cp,
        evidence: checkpointEvidence(state, cp),
      });
      break;
    }
    case "inspect-evidence":
      inspect(
        "Inspectable fixture artifact / evidence",
        owner?.evidence.find((e) => e.id === id) || {
          missing: "Evidence unavailable. This is not proof of success.",
        },
      );
      break;
    case "inspect-repair":
      inspect(
        "Repair record · fixture",
        state.repairs.find((r) => r.id === id),
      );
      break;
    case "inspect-history":
      inspect(`Revision ${owner.revision} · retained fixture history`, owner);
      break;
  }
});
$("#app").addEventListener("keydown", (event) => {
  if (
    event.target.getAttribute("role") !== "tab" ||
    !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
  )
    return;
  event.preventDefault();
  const index = tabs.findIndex(([id]) => id === ui.tab);
  const next =
    event.key === "Home"
      ? 0
      : event.key === "End"
        ? tabs.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
          tabs.length;
  switchTab(tabs[next][0], true);
});
$("#close-inspector").addEventListener("click", () => $("#inspector").close());
$("#download-artifact").addEventListener("click", () => {
  const blob = new Blob(
    [
      JSON.stringify(
        {
          label: "AUTHORED UI FIXTURE — NOT EXECUTION EVIDENCE",
          data: inspection,
        },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "epoch-fixture-evidence.json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
render();
