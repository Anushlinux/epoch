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
let draft = { message: "", project: "demo" };
let settings = false;
let originDraft = null;
const releaseDraft = { release: "", scenario: "control", max_turns: 16, timeout_seconds: 180 };
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
if (execution.state.pending) {
  Object.assign(releaseDraft, execution.state.pending.payload);
  if (!workspace.state.pending) workspace.state.origin = execution.state.pending.origin;
  if (!selected) {
    selected = execution.state.pending.taskId;
    history.replaceState(null, "", urlFor(false, currentPage(), selected));
  }
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
  workspace.state.busy || !!workspace.state.pending || workspace.state.recovery || execution.state.busy;
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
            `<a data-route data-task="${escape(t.id)}" class="session-item" href="${urlFor(false, currentPage(), t.id)}" ${selected === t.id ? 'aria-current="page"' : ""}>${icon("chat")}<span><strong>${escape(t.request.message)}</strong><small>${escape(t.request.project_id)} · ${escape(t.status)}</small></span></a>`,
        )
        .join("")
    : `<div class="sidebar-empty">${icon("chat")}<p>${state.list ? "No chats yet" : "Connect to see your chats"}</p></div>`;
  if (state.list)
    html += `<div class="pagination"><button id="previous-page" data-action="previous" ${state.busy || !state.connected || !state.offset ? "disabled" : ""}>Newer</button><span>${state.list.total ? state.offset + 1 : 0}–${state.offset + state.list.items.length} of ${state.list.total}</span><button id="next-page" data-action="next" ${state.busy || !state.connected || state.offset + state.list.items.length >= state.list.total ? "disabled" : ""}>Older</button></div>`;
  return html;
}
function connection(state) {
  if (!settings) return "";
  return `<section class="connection-panel" aria-labelledby="connection-heading"><div class="panel-heading"><h2 id="connection-heading">Local connection</h2><button class="icon-button" data-action="settings-close" aria-label="Close connection settings">${icon("close")}</button></div><form id="connection-form"><div><label for="api-origin">API origin</label><input id="api-origin" type="url" required value="${escape(originDraft ?? state.origin)}" ${state.busy || state.pending || execution.state.pending ? "disabled" : ""}></div><button id="connect" ${state.busy ? "disabled" : ""}>${state.busy ? "Connecting…" : state.connected ? "Refresh connection" : "Connect / reconnect"}</button></form><p>Connect to your local Epoch backend. Requests are saved as pending.</p><details class="disclosure" data-key="connection-details"><summary>Connection details ${icon("down")}</summary><p>The backend must allow <code>${escape(location.origin)}</code>. No credentials are used.</p><a class="text-button" href="/README.md" target="_blank" rel="noopener">Setup instructions ↗</a></details></section>`;
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
function chat(state) {
  const t = task();
  if (!t) {
    if (selected)
      return empty(
        state.busy ? "Loading request…" : "Request not loaded",
        state.connected
          ? "This request could not be loaded. Refresh the connection or choose another chat."
          : "Connect to the local backend to load this request.",
      );
    return `${welcome()}${state.pending ? `<div class="conversation pending-conversation">${pending(state)}</div>` : ""}`;
  }
  return `<div class="conversation"><div class="message user"><div class="message-body"><blockquote>${escape(t.request.message)}</blockquote></div></div><div class="system-receipt">${icon("info")}<div><strong>System receipt</strong><p>${state.taskUnavailable ? "The previously saved request is currently unavailable." : t.status === "pending" ? "Request saved. Start a release run below when ready." : `Request saved. Current task status: ${escape(t.status)}.`}</p></div></div><details class="disclosure" data-key="receipt" open><summary>Request details ${icon("down")}</summary><div class="disclosure-body">${receipt(t, state)}</div></details>${executionPanel(execution.state, releaseDraft, { unavailable: state.taskUnavailable })}${routeLink(false, "debugger", selected, "Open debugger", "pipeline", 'class="back-link"')}${pending(state)}</div>`;
}
function debuggerPage(state) {
  const t = task();
  return `<div class="debugger"><header class="debug-heading"><p class="eyebrow">Epoch / debugger</p><h1>${execution.state.run ? "Release execution evidence" : "No execution recorded"}</h1><p>Inspect the recorded run, trusted checkpoints and partial simulated effects.</p></header><div class="debug-layout"><div>${t ? executionPanel(execution.state, releaseDraft, { debuggerView: true, unavailable: state.taskUnavailable }) : "Select a saved chat to inspect its execution."}</div><aside class="context-column"><h2>Original request</h2>${t ? `<blockquote>${escape(t.request.message)}</blockquote><p>Saving a request does not start execution.</p>${badge(t.status, t.status)}<dl class="metadata"><dt>Project</dt><dd>${escape(t.request.project_id)}</dd><dt>Task ID</dt><dd>${escape(t.id)}</dd></dl><button class="text-button" data-action="inspect-record">Inspect saved record</button>` : "<p>No chat selected.</p>"}</aside></div>${pending(state)}</div>`;
}
function composer(state) {
  const disabled = locked() || !!selected;
  return `<div class="composer-dock"><form id="request-form" class="composer-box"><label class="sr-only" for="request-message">What needs to be done?</label><textarea id="request-message" data-autogrow data-submit rows="1" required placeholder="${selected ? "Start a new chat to save another request" : "What should we work on?"}" ${disabled ? "disabled" : ""}>${escape(selected ? "" : draft.message)}</textarea><div class="composer-tools"><div class="composer-tools-left"><details class="project-menu" data-key="project"><summary>${icon("plus")}<span id="project-label">${escape(draft.project)}</span>${icon("down")}</summary><div class="popover"><label for="project-id">Project label</label><input id="project-id" value="${escape(draft.project)}" ${disabled ? "disabled" : ""}><p>A label to organize this request. Up to 100 characters.</p></div></details></div><div class="composer-tools-right"><span class="composer-hint">${selected ? "Start the explicit release workflow above" : state.busy ? "Saving…" : "Enter to save · Shift Enter for a new line"}</span><button id="save-request" class="send-button" aria-label="Save request" ${disabled || !state.connected ? "disabled" : ""}>${icon("send")}</button></div></div></form><p class="composer-caption">${selected ? '<button class="text-button" data-action="new">New chat</button>' : !state.connected ? '<button class="text-button" data-action="settings">Connect your local backend to save a request</button>' : "Saving a request does not start execution."}</p></div>`;
}
function render(options = {}) {
  const state = workspace.state;
  if (state.submission === "saved" && lastSubmission !== "saved") {
    draft.message = "";
    selected = state.task.id;
    history.replaceState(null, "", urlFor(false, "chat", selected));
    options.focus = "detail-heading";
    options.bottom = true;
  }
  lastSubmission = state.submission;
  execution.setContext(state.origin, task()?.id || "", state.connected && !state.taskUnavailable);
  const page = currentPage();
  const t = task();
  const content = `${notices(state)}${connection(state)}${page === "debugger" ? debuggerPage(state) : chat(state)}`;
  view.render(
    shell({
      page,
      task: selected,
      title: t?.request.message || "New chat",
      nav: navigation(state),
      content,
      locked: locked(),
      composer: page === "chat" ? composer(state) : "",
      status: `<span class="connection-state ${state.connected ? "connected" : ""}" title="${state.connected ? "Connected · local API" : "Not connected"}"><i></i>${state.connected ? "Connected · local API" : "Not connected"}</span>`,
      actions: `<button class="icon-button" data-action="settings" aria-label="Connection settings">${icon("settings")}</button>`,
      bottom: `<button class="nav-item" data-action="settings">${icon("settings")}Connection settings</button>`,
    }),
    `${page}:${selected}`,
    options,
  );
  const refresh = $("#refresh-list");
  if (refresh) refresh.disabled = state.busy || !state.connected;
  $("#announcement").textContent = state.busy
    ? "Loading from the local API."
    : state.error ||
      state.notice ||
      (state.connected
        ? "Connected to the local Phase 3 API."
        : "Not connected.");
}
async function routeChanged() {
  selected = new URLSearchParams(location.search).get("task") || "";
  render();
  if (selected && workspace.state.connected && task()?.id !== selected)
    await workspace.read(selected);
  if (currentPage() === "debugger")
    $("#workspace")?.focus({ preventScroll: true });
  else if (task()) render({ focus: "detail-heading" });
}
function newChat() {
  if (locked()) return;
  navigate(urlFor(false, "chat"));
  $("#request-message")?.focus();
}
root.addEventListener("input", (e) => {
  if (e.target.id === "api-origin") originDraft = e.target.value;
  const releaseField = { "release-value": "release", "release-scenario": "scenario", "release-turns": "max_turns", "release-timeout": "timeout_seconds" }[e.target.id];
  if (releaseField) releaseDraft[releaseField] = e.target.value;
  if (e.target.id === "request-message") draft.message = e.target.value;
  if (e.target.id === "project-id") {
    draft.project = e.target.value;
    $("#project-label").textContent = e.target.value || "Project";
  }
});
root.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (e.target.id === "connection-form") {
    const nextOrigin = $("#api-origin").value;
    if (execution.state.pending && new URL(nextOrigin).origin !== execution.state.pending.origin) {
      execution.state.error = "Resolve the pending run on its original server before switching.";
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
  if (e.target.id === "release-form") await execution.start(releaseDraft);
  if (e.target.id === "request-form" && !selected)
    await workspace.submit(draft.message, draft.project);
});
root.addEventListener("click", async (e) => {
  const button = e.target.closest("button");
  if (!button || button.disabled) return;
  switch (button.dataset.action) {
    case "run-refresh": await execution.refresh(); break;
    case "run-retry": await execution.retry(); break;
    case "run-review": execution.reviewRejected(); break;
    case "run-cancel": await execution.cancel(); break;
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
        history.replaceState(null, "", urlFor(false, "chat"));
        render({ focus: "request-message" });
      }
      break;
    case "inspect-record":
      if (task()) inspect("Saved request · intake only", task());
      break;
  }
});
root.addEventListener("change", (e) => {
  if (e.target.id === "run-history") void execution.select(e.target.value);
});
window.addEventListener("pagehide", () => execution.stop());
window.addEventListener("pageshow", (event) => { if (event.persisted) void execution.refresh(); });
render();
// Opening, refreshing, and navigating never submit or auto-connect.
