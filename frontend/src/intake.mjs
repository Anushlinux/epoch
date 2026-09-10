import { IncidentWorkspace } from './incident-api.mjs';
import { incidentsView, incidentURL } from './incident-ui.mjs';
import { ExecutionWorkspace } from "./execution-api.mjs";
import { executionPanel } from "./execution-ui.mjs";
import { IntakeWorkspace } from "./intake-api.mjs";
import {
  $,
  escape,
  icon,
  badge,
  empty,
  welcome,
  shell,
  currentPage,
  urlFor,
  routeLink,
  View,
  installNavigation,
  installInspector,
} from "./ui.mjs";

const root = $("#intake");
const view = new View(root);
const inspect = installInspector();
let draft = { message: "Prepare the release ticket, checklist, and QA notification.", project: "demo" };
let settings = false;
let originDraft = null;
const releaseDraft = { release: "", scenario: "control", max_turns: 20, timeout_seconds: 600,
  supervised: true, repair_enabled: false, demo_omit_notification: false };
const feedbackDrafts = new Map();
const incidentQuestions = new Map();
let importDraft = "";
let incidentProjectDraft = null;
let lastSubmission = "idle";
let selected = new URLSearchParams(location.search).get("task") || "";
let storage;
try {
  storage = window.sessionStorage;
} catch {
  storage = {
    getItem() {
      throw new Error("Storage unavailable");
    },
  };
}
const workspace = new IntakeWorkspace({ storage, onChange: () => render() });
const execution = new ExecutionWorkspace({ storage, onChange: () => render(), onTask: (updated) => {
  if (workspace.state.task?.id === updated.id && !workspace.state.taskUnavailable) {
    workspace.state.task = updated;
    if (updated.status !== 'pending' && workspace.state.notice.startsWith('Request saved.')) workspace.state.notice = '';
  }
  if (workspace.state.list) workspace.state.list.items = workspace.state.list.items.map((t) => t.id === updated.id ? updated : t);
} });
const incidents = new IncidentWorkspace({ storage, onChange: () => render() });
if (incidents.state.pending && !workspace.state.pending && !execution.state.pending && !execution.state.operationPending) {
  workspace.state.origin = incidents.state.pending.origin;
  if (incidents.state.pending.kind === "import") importDraft = JSON.stringify(incidents.state.pending.payload.records, null, 2);
  else if (incidents.state.pending.payload.question) incidentQuestions.set(incidents.state.pending.incidentId, incidents.state.pending.payload.question);
}
if (execution.state.pending) {
  Object.assign(releaseDraft, execution.state.pending.payload);
  if (!workspace.state.pending) workspace.state.origin = execution.state.pending.origin;
  if (!selected) {
    selected = execution.state.pending.taskId;
    history.replaceState(null, "", urlFor(false, currentPage(), selected));
  }
}
if (execution.state.operationPending) {
  const pending = execution.state.operationPending;
  if (!workspace.state.pending && !execution.state.pending) workspace.state.origin = pending.origin;
  if (!selected && pending.taskId) {
    selected = pending.taskId;
    history.replaceState(null, "", urlFor(false, currentPage(), selected));
  }
  if (pending.runId && pending.payload.message) feedbackDrafts.set(pending.runId, pending.payload.message);
}
if (workspace.state.pending)
  draft = {
    message: workspace.state.pending.payload.message,
    project: workspace.state.pending.payload.project_id,
  };
const stamp = (date) =>
  new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(date));
const task = () =>
  selected && workspace.state.task?.id === selected
    ? workspace.state.task
    : null;
const locked = () =>
  workspace.state.busy || !!workspace.state.pending || workspace.state.recovery || execution.state.busy || incidents.state.busy;
const feedbackDraft = () => feedbackDrafts.get(execution.state.run?.id) || "";
const navigate = installNavigation(root, routeChanged, newChat);

function navigation(state) {
  let html = "";
  if (state.list && !state.connected)
    html +=
      '<p class="intake-stale">Last loaded records · connection unavailable</p>';
  html += state.list?.items.length
    ? state.list.items
        .map(
          (t) =>
            `<a data-route data-task="${escape(t.id)}" class="session-item" href="${urlFor(false, "debugger", t.id)}" ${selected === t.id ? 'aria-current="page"' : ""}>${icon("chat")}<span><strong>${escape(t.request.message)}</strong><small>${escape(t.request.project_id)} · ${escape(t.status)}</small></span></a>`,
        )
        .join("")
    : `<div class="sidebar-empty">${icon("chat")}<p>${state.list ? "No evaluations yet" : "Connect to see evaluations"}</p></div>`;
  if (state.list)
    html += `<div class="pagination"><button id="previous-page" data-action="previous" ${state.busy || !state.connected || !state.offset ? "disabled" : ""}>Newer</button><span>${state.list.total ? state.offset + 1 : 0}–${state.offset + state.list.items.length} of ${state.list.total}</span><button id="next-page" data-action="next" ${state.busy || !state.connected || state.offset + state.list.items.length >= state.list.total ? "disabled" : ""}>Older</button></div>`;
  return html;
}
function connection(state) {
  if (!settings) return "";
  return `<section class="connection-panel" aria-labelledby="connection-heading"><div class="panel-heading"><h2 id="connection-heading">Local connection</h2><button class="icon-button" data-action="settings-close" aria-label="Close connection settings">${icon("close")}</button></div><form id="connection-form"><div><label for="api-origin">API origin</label><input id="api-origin" type="url" required value="${escape(originDraft ?? state.origin)}" ${state.busy || state.pending || execution.state.pending || execution.state.operationPending || incidents.state.pending ? "disabled" : ""}></div><button id="connect" ${state.busy ? "disabled" : ""}>${state.busy ? "Connecting…" : state.connected ? "Refresh connection" : "Connect / reconnect"}</button></form><p>Connect to your local Epoch backend. Requests are saved as pending.</p><details class="disclosure" data-key="connection-details"><summary>Connection details ${icon("down")}</summary><p>The backend must allow <code>${escape(location.origin)}</code>. No credentials are used.</p><a class="text-button" href="/README.md" target="_blank" rel="noopener">Setup instructions ↗</a></details></section>`;
}
function notices(state) {
  if (!state.error && !state.notice && !state.recovery) return "";
  return `<div class="banner-stack">${state.error ? `<div class="alert" role="alert">${escape(state.error)}${!state.connected ? '<br><button data-action="settings">Connection settings</button>' : ""}</div>` : ""}${state.recovery ? '<p class="alert">Recovery identity is unavailable. Connect for read-only inspection; new submissions are blocked.</p>' : ""}${state.notice ? `<p class="notice intake-notice">${escape(state.notice)}</p>` : ""}</div>`;
}
function pending(state) {
  if (!state.pending) return "";
  return `<section class="pending-card"><h2>${state.submission === "rejected" ? "Submission rejected" : "Submission awaiting confirmation"}</h2><p>This request may already be saved. Its original ID and content are retained in this tab until confirmed.</p><code>${escape(state.pending.payload.client_request_id)}</code><details class="disclosure" data-key="pending"><summary>Inspect frozen submission ${icon("down")}</summary><pre>${escape(JSON.stringify(state.pending.payload, null, 2))}</pre></details>${state.submission === "rejected" ? `<button id="edit-rejected" data-action="edit-rejected" ${state.busy ? "disabled" : ""}>Return rejected content to draft</button>` : `<button id="retry-submission" data-action="retry" ${state.busy || !state.connected || state.recovery ? "disabled" : ""}>Retry exact submission</button>`}</section>`;
}
function receipt(t, state) {
  return `<section class="intake-detail"><div class="inline-row"><h2 id="detail-heading" tabindex="-1">Saved request detail</h2><button class="text-button" id="refresh-detail" data-action="refresh-detail" ${state.busy || !state.connected ? "disabled" : ""}>${icon("refresh")} Reload detail</button></div><p class="intake-stale">${state.taskUnavailable ? "Unavailable · last loaded record" : t.status === "pending" ? "Pending · no execution" : escape(t.status)}</p>${state.taskUnavailable ? '<p class="intake-stale">The API could not find this task. This is a retained copy, not a current stored record.</p>' : ""}${!state.connected ? '<p class="intake-stale">Last loaded detail · reconnect to verify the stored record</p>' : ""}<dl class="metadata"><dt>Task ID</dt><dd>${escape(t.id)}</dd><dt>Project</dt><dd>${escape(t.request.project_id)}</dd><dt>Request ID</dt><dd>${escape(t.request.client_request_id)}</dd><dt>Saved</dt><dd>${escape(stamp(t.created_at))}</dd></dl><details class="disclosure" data-key="api-record"><summary>Inspect API record · intake only ${icon("down")}</summary><pre id="task-record">${escape(JSON.stringify(t, null, 2))}</pre><button class="text-button" data-action="inspect-record">Open record inspector ${icon("arrow")}</button></details></section>`;
}
function debuggerPage(state) {
  const t = task();
  const input = !t ? `<section class="evaluation-brief"><h2>Evaluation request</h2><label for="request-message">What should the release workflow accomplish?</label><textarea id="request-message" maxlength="16000" ${locked() ? 'disabled' : ''}>${escape(draft.message)}</textarea><label for="project-id">Project</label><input id="project-id" value="${escape(draft.project)}" ${locked() ? 'disabled' : ''}><p>Starting creates a separate evaluation task and sandbox. Chat messages and objects stay separate.</p></section>` : '';
  return `<div class="debugger"><header class="debug-heading"><h1>Release demo</h1><p>This example runs the release workflow against local simulated services. Start it explicitly to inspect its checks and repair evidence.</p><a href="/debugger?mode=release" class="text-button">New release example</a> · <a href="/debugger" class="text-button">Open debugger</a> · <a data-route href="/incidents" class="text-button">Incidents and investigations</a></header><div class="debug-layout"><div>${input}${executionPanel(execution.state, releaseDraft, { debuggerView: true, allowNewTask: !t, unavailable: state.taskUnavailable || state.busy || !!state.pending, feedbackDraft: feedbackDraft() })}</div><aside class="context-column"><h2>Evaluation context</h2>${t ? `<blockquote>${escape(t.request.message)}</blockquote>${badge(t.status, t.status)}<dl class="metadata"><dt>Project</dt><dd>${escape(t.request.project_id)}</dd><dt>Task ID</dt><dd>${escape(t.id)}</dd></dl><button class="text-button" data-action="inspect-record">Inspect saved record</button>` : '<p>The release workflow uses Hermes, optional Luna supervision, and scoped simulated services.</p><p>Generated repair must be enabled explicitly and pass its verification gates before publication.</p>'}</aside></div>${pending(state)}</div>`;
}
function render(options = {}) {
  const state = workspace.state;
  if (state.submission === "saved" && lastSubmission !== "saved") {
    selected = state.task.id;
    history.replaceState(null, "", urlFor(false, "debugger", selected));
    options.focus = "release-value";
    options.bottom = true;
  }
  lastSubmission = state.submission;
  execution.setContext(state.origin, task()?.id || "", state.connected && !state.taskUnavailable);
  const page = currentPage();
  const incidentQuery = new URLSearchParams(location.search);
  const incidentId = page === "incidents" ? incidentQuery.get("incident") || "" : "";
  const incidentProject = page === "incidents" ? incidentQuery.get("project") || "" : "";
  const incidentOffset = Math.max(0, Number.parseInt(incidentQuery.get("offset"), 10) || 0);
  incidents.setContext(state.origin, state.connected, page === "incidents" && !document.hidden, incidentId, incidentProject, incidentOffset);
  const t = task();
  const content = `${notices(state)}${connection(state)}${page === "incidents" ? incidentsView(incidents.state, { importDraft, questionDraft: incidentQuestions.get(incidentId) || "", projectDraft: incidentProjectDraft ?? incidentProject }) : debuggerPage(state)}`;
  view.render(
    shell({
      page,
      task: selected,
      title: page === "incidents" ? "Incidents" : t?.request.message || "New chat",
      nav: navigation(state),
      content,
      locked: locked(),
      composer: "",
      status: `<span class="connection-state ${state.connected ? "connected" : ""}" title="${state.connected ? "Connected · local API" : "Not connected"}"><i></i>${state.connected ? "Connected · local API" : "Not connected"}</span>`,
      actions: `<button class="icon-button" data-action="settings" aria-label="Connection settings">${icon("settings")}</button>`,
      bottom: `<button class="nav-item" data-action="settings">${icon("settings")}Connection settings</button>`,
    }),
    `${page}:${page === "incidents" ? incidentId : selected}`,
    options,
  );
  const refresh = $("#refresh-list");
  if (refresh) refresh.disabled = state.busy || !state.connected;
  $("#announcement").textContent = state.busy
    ? "Loading from the local API."
    : state.error ||
      state.notice ||
      (state.connected
        ? "Connected to the local API."
        : "Not connected.");
}
async function routeChanged() {
  if (location.pathname === "/traces") { location.assign(location.href); return; }
  const query = new URLSearchParams(location.search);
  if (currentPage() === "chat" || (currentPage() === "debugger" && !query.has("task") && query.get("mode") !== "release")) { location.assign(location.href); return; }
  incidentProjectDraft = null;
  selected = new URLSearchParams(location.search).get("task") || "";
  render();
  if (selected && workspace.state.connected && task()?.id !== selected)
    await workspace.read(selected);
  if (currentPage() === "debugger") {
    const runId = new URLSearchParams(location.search).get("run");
    if (runId && workspace.state.connected) { await execution.refresh(); await execution.select(runId); }
  }
  if (currentPage() !== "chat")
    $("#workspace")?.focus({ preventScroll: true });
  else if (task()) render({ focus: "detail-heading" });
}
function newChat() {
  if (locked()) return;
  location.assign("/chat");
}
root.addEventListener("input", (e) => {
  if (e.target.id === "api-origin") originDraft = e.target.value;
  if (e.target.id === "incident-import-json") importDraft = e.target.value;
  if (e.target.id === "incident-project") incidentProjectDraft = e.target.value;
  if (e.target.id === "incident-question") incidentQuestions.set(incidents.state.selected, e.target.value);
  if (e.target.id === "feedback-message" && execution.state.run) feedbackDrafts.set(execution.state.run.id, e.target.value);
  const releaseField = { "release-value": "release", "release-scenario": "scenario", "release-turns": "max_turns", "release-timeout": "timeout_seconds" }[e.target.id];
  if (releaseField) releaseDraft[releaseField] = e.target.value;
  if (e.target.id === "request-message") draft.message = e.target.value;
  if (e.target.id === "project-id") {
    draft.project = e.target.value;
    if ($("#project-label")) $("#project-label").textContent = e.target.value || "Project";
  }
});
root.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (e.target.id === "connection-form") {
    const nextOrigin = $("#api-origin").value;
    const pending = execution.state.pending || execution.state.operationPending || incidents.state.pending;
    if (pending && new URL(nextOrigin).origin !== pending.origin) {
      execution.state.error = "Resolve the pending operation on its original server before switching.";
      render(); return;
    }
    await workspace.connect(nextOrigin);
    originDraft = null;
    if (workspace.state.connected) {
      settings = false;
      render();
      if (selected && !task()) await workspace.read(selected);
    }
  }
  if (e.target.id === "incident-filter-form") navigate(incidentURL("", incidentProjectDraft ?? incidents.state.project));
  if (e.target.id === "incident-import-form" && await incidents.submit("import", importDraft)) { importDraft = ""; render(); }
  if (e.target.id === "incident-question-form" && await incidents.submit("questions", incidentQuestions.get(incidents.state.selected) || "")) { incidentQuestions.delete(incidents.state.selected); render(); }
  if (e.target.id === "release-form" && currentPage() === "debugger") {
    if (locked()) return;
    if (!selected) {
      await workspace.submit(draft.message, draft.project);
      if (workspace.state.submission !== "saved") return;
      await execution.refresh();
    }
    await execution.start(releaseDraft);
  }
  if (e.target.id === "feedback-form") {
    const run = execution.state.run;
    if (run && await execution.submitFeedback(feedbackDraft(), { clarification: run.status === "needs_input" })) {
      feedbackDrafts.delete(run.id);
      render();
    }
  }

});
root.addEventListener("click", async (e) => {
  const button = e.target.closest("button");
  if (!button || button.disabled) return;
  switch (button.dataset.action) {
    case "run-refresh": await execution.refresh(); break;
    case "incident-refresh": await incidents.refresh(); break;
    case "incident-analyze": await incidents.submit("analyze"); break;
    case "incident-retry": await incidents.retry(); break;
    case "incident-review": incidents.reviewRejected(); break;
    case "run-retry": await execution.retry(); break;
    case "run-review": execution.reviewRejected(); break;
    case "run-cancel": await execution.cancel(); break;
    case "operation-retry": await execution.retryOperation(); break;
    case "operation-review": execution.reviewRejectedOperation(); break;
    case "environment-rollback": await execution.rollback(); break;
    case "new":
      newChat();
      break;
    case "settings":
      settings = true;
      originDraft = workspace.state.origin;
      render({ focus: "api-origin" });
      $("#page-scroll").scrollTop = 0;
      break;
    case "settings-close":
      settings = false;
      render();
      break;
    case "refresh-list":
      await workspace.read();
      break;
    case "previous":
      await workspace.read(null, Math.max(0, workspace.state.offset - 20));
      break;
    case "next":
      await workspace.read(null, workspace.state.offset + 20);
      break;
    case "refresh-detail":
      if (selected) await workspace.read(selected);
      break;
    case "retry":
      await workspace.retry();
      break;
    case "edit-rejected":
      if (workspace.editRejected()) {
        selected = "";
        history.replaceState(null, "", "/debugger?mode=release");
        render({ focus: "request-message" });
      }
      break;
    case "inspect-record":
      if (task()) inspect("Saved request · intake only", task());
      break;
  }
});
root.addEventListener("change", async (e) => {
  if (e.target.id === "incident-import-file" && e.target.files?.[0]) {
    const file = e.target.files[0];
    try {
      if (file.size > 2_000_000) throw new Error("Choose a JSON file smaller than 2 MB.");
      importDraft = await file.text(); render();
    } catch (error) { incidents.state.error = error.message; render(); }
  }
  if (e.target.id === "release-scenario") { releaseDraft.scenario = e.target.value; render(); }
  if (e.target.id === "run-history") void execution.select(e.target.value);
  const field = { "release-supervised": "supervised", "release-repair": "repair_enabled", "release-omission": "demo_omit_notification" }[e.target.id];
  if (field) {
    releaseDraft[field] = e.target.checked;
    if (!releaseDraft.supervised) {
      releaseDraft.repair_enabled = false;
      releaseDraft.demo_omit_notification = false;
    } else if (e.target.checked && field === "repair_enabled") releaseDraft.demo_omit_notification = false;
    else if (e.target.checked && field === "demo_omit_notification") releaseDraft.repair_enabled = false;
    render();
  }
});
document.addEventListener("visibilitychange", () => render());
window.addEventListener("pagehide", () => { execution.stop(); incidents.stop(); });
window.addEventListener("pageshow", (event) => { if (event.persisted) { void execution.refresh(); void incidents.refresh(); } });
render();
// Startup connects read-only. No evaluation, investigation, or retry is automatic.
void workspace.connect().then(async () => {
  if (selected) await workspace.read(selected);
  if (selected && new URLSearchParams(location.search).get("run")) await routeChanged();
});
