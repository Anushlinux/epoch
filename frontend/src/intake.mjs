import { IntakeWorkspace } from './intake-api.mjs';
const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const $ = (selector) => document.querySelector(selector);
let draft = { message: '', project: 'demo' };
let lastSubmission = 'idle';
let storage;
try { storage = window.sessionStorage; } catch { storage = { getItem() { throw new Error('Storage unavailable'); } }; }
const workspace = new IntakeWorkspace({ storage, onChange: render });
if (workspace.state.pending) draft = { message: workspace.state.pending.payload.message, project: workspace.state.pending.payload.project_id };
const stamp = (date) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(date));
function render(state = workspace.state) {
  const focus = document.activeElement?.id;
  if (state.submission === 'saved' && lastSubmission !== 'saved') draft.message = '';
  lastSubmission = state.submission;
  const locked = state.busy || !!state.pending || state.recovery;
  $('#intake').innerHTML = `
    <aside class="intake-rail"><a class="intake-brand" href="./index.html"><img src="./mark.svg" alt="" width="29" height="29" /> Epoch</a>
      <nav aria-label="Workspace"><a href="./index.html" aria-current="page">Saved tasks</a><a href="./fixtures.html">Future workflow · fixtures</a></nav>
      <div class="intake-rail-note"><strong>Local workspace</strong><p>Task intake & storage<br>Phase 1</p><a href="./README.md">Setup & evidence</a></div>
    </aside>
    <main id="workspace" class="intake-main" tabindex="-1">
      <header class="intake-header"><div><h1>Saved tasks</h1><p>Capture the request. Keep the original intent.</p></div><span class="intake-status">${state.connected ? 'Connected · local API' : 'Not connected'}</span></header>
      <section class="intake-boundary" aria-labelledby="phase-heading"><div><h2 id="phase-heading">Requests are saved. Execution is not enabled.</h2><p>Phase 1 stores tasks as pending. Checkpoints, activity, feedback and repairs are not available for these tasks.</p></div><a href="./fixtures.html">Explore labeled fixtures</a></section>
      <details class="intake-connection" ${!state.connected ? 'open' : ''}><summary>Local API connection <span>${escape(state.origin)}</span></summary>
        <form id="connection-form"><div><label for="api-origin">API origin</label><input id="api-origin" type="url" required value="${escape(state.origin)}" ${state.busy || state.pending ? 'disabled' : ''} /><p id="cors-help">The backend must allow this browser origin: <code>${escape(location.origin)}</code>. No credentials are used.</p></div><button id="connect" ${state.busy ? 'disabled' : ''}>${state.busy ? 'Please wait…' : state.connected ? 'Refresh connection' : 'Connect / reconnect'}</button></form>
      </details>
      ${state.error ? `<div class="intake-alert" role="alert">${escape(state.error)}</div>` : ''}
      ${state.recovery ? '<p class="intake-alert">Recovery identity is unavailable. Read-only task inspection is available after connecting; this page will not submit work.</p>' : ''}
      ${state.notice ? `<p class="intake-notice">${escape(state.notice)}</p>` : ''}
      <div class="intake-grid"><section class="intake-compose" aria-labelledby="request-heading"><h2 id="request-heading">New request</h2><p>Describe the result you want, including constraints and any details already clarified.</p>
        <form id="request-form"><label for="request-message">What needs to be done?</label><textarea id="request-message" required rows="7" placeholder="Prepare the Atlas release checklist. Include QA ownership and rollback steps." aria-describedby="message-help" ${locked ? 'disabled' : ''}>${escape(draft.message)}</textarea><p id="message-help">Up to 16,000 characters. The backend trims outer whitespace and preserves the submitted text.</p>
          <label for="project-id">Project label</label><input id="project-id" required value="${escape(draft.project)}" aria-describedby="project-help" ${locked ? 'disabled' : ''} /><p id="project-help">Up to 100 characters. A grouping label, not an access boundary.</p>
          <div class="intake-submit"><button id="save-request" class="primary" ${locked || !state.connected ? 'disabled' : ''}>${state.submission === 'sending' ? 'Saving request…' : 'Save request'}</button><span>Save only · no execution</span></div>
        </form>
        ${state.pending ? `<section class="intake-pending"><h3>${state.submission === 'rejected' ? 'Submission rejected' : 'Submission awaiting confirmation'}</h3><p>The ID and content below are frozen. A pending payload stays in this tab’s session storage until acknowledged.</p><code>${escape(state.pending.payload.client_request_id)}</code><details><summary>Inspect frozen submission</summary><pre>${escape(JSON.stringify(state.pending.payload, null, 2))}</pre></details>${state.submission === 'rejected' ? `<button id="edit-rejected" ${state.busy ? 'disabled' : ''}>Return rejected content to draft</button>` : `<button id="retry-submission" ${state.busy || !state.connected || state.recovery ? 'disabled' : ''}>Retry exact submission</button>`}</section>` : ''}
      </section><section class="intake-tasks" aria-labelledby="tasks-heading"><div class="intake-section-heading"><h2 id="tasks-heading">Stored requests${state.list ? ` (${state.list.total})` : ''}</h2><button id="refresh-list" ${state.busy || !state.connected ? 'disabled' : ''}>Refresh list</button></div>
        ${state.list && !state.connected ? '<p class="intake-stale">Last loaded records · connection unavailable</p>' : ''}
        ${state.list?.items.length ? `<ol class="intake-task-list">${state.list.items.map((task) => `<li><button data-task="${escape(task.id)}" aria-pressed="${state.task?.id === task.id}" ${state.busy || !state.connected ? 'disabled' : ''}><span class="intake-task-title">${escape(task.request.message)}</span><span class="intake-task-meta">${escape(task.request.project_id)} · ${escape(stamp(task.created_at))}</span><span class="intake-pending-label">Pending · no execution</span></button></li>`).join('')}</ol>` : `<div class="intake-empty"><h3>${state.list ? 'No saved requests yet' : 'Connect to load your requests'}</h3><p>${state.list ? 'Your first saved request will appear here with its original text and receipt.' : 'This list comes from the local API. Fixture records never appear here.'}</p></div>`}
        ${state.list ? `<div class="intake-pagination"><button id="previous-page" ${state.busy || !state.connected || state.offset === 0 ? 'disabled' : ''}>Newer</button><span>${state.list.total ? state.offset + 1 : 0}–${state.offset + state.list.items.length} of ${state.list.total}</span><button id="next-page" ${state.busy || !state.connected || state.offset + state.list.items.length >= state.list.total ? 'disabled' : ''}>Older</button></div>` : ''}
      </section></div>
      <section class="intake-detail" aria-labelledby="detail-heading"><h2 id="detail-heading">${state.task ? 'Saved request detail' : 'Request detail'}</h2>${state.task ? `<div class="intake-detail-heading"><span class="intake-pending-label">Pending · no execution</span><button id="refresh-detail" ${state.busy || !state.connected ? 'disabled' : ''}>Reload detail</button></div>${!state.connected ? '<p class="intake-stale">Last loaded detail · reconnect to verify the current stored record</p>' : ''}<blockquote>${escape(state.task.request.message)}</blockquote><dl><div><dt>Task ID</dt><dd>${escape(state.task.id)}</dd></div><div><dt>Project</dt><dd>${escape(state.task.request.project_id)}</dd></div><div><dt>Request ID</dt><dd>${escape(state.task.request.client_request_id)}</dd></div><div><dt>Saved</dt><dd>${escape(stamp(state.task.created_at))}</dd></div></dl><details><summary>Inspect API record · intake only</summary><pre id="task-record">${escape(JSON.stringify(state.task, null, 2))}</pre></details><p class="intake-detail-note">This receipt proves task intake only. No task result, run, checkpoint or repair evidence is available.</p>` : '<p>Select a stored request to inspect its original text, IDs and API record.</p>'}</section>
    </main>`;
  $('#connection-form').onsubmit = (event) => { event.preventDefault(); workspace.connect($('#api-origin').value); };
  $('#request-message').oninput = (event) => { draft.message = event.target.value; };
  $('#project-id').oninput = (event) => { draft.project = event.target.value; };
  $('#request-form').onsubmit = async (event) => { event.preventDefault(); await workspace.submit(draft.message, draft.project); if (workspace.state.submission === 'saved') focusDetail(); };
  const bind = (id, callback) => { const el = $(id); if (el) el.onclick = callback; };
  bind('#refresh-list', () => workspace.read());
  bind('#previous-page', () => workspace.read(null, Math.max(0, state.offset - 20)));
  bind('#next-page', () => workspace.read(null, state.offset + 20));
  bind('#refresh-detail', () => workspace.read(state.task.id));
  bind('#retry-submission', () => workspace.retry());
  bind('#edit-rejected', () => { workspace.editRejected(); $('#request-message').focus(); });
  document.querySelectorAll('[data-task]').forEach((el) => { el.onclick = async () => { await workspace.read(el.dataset.task); if (workspace.state.task?.id === el.dataset.task) focusDetail(); }; });
  if (focus) document.getElementById(focus)?.focus({ preventScroll: true });
  $('#detail-heading').setAttribute('tabindex', '-1');
  $('#announcement').textContent = state.busy ? 'Loading from the local API.' : state.error || state.notice || (state.connected ? 'Connected. Execution is disabled.' : 'Not connected.');
}
function focusDetail() { $('#detail-heading').focus(); }
render();
// Opening or reloading this page never submits. Connecting is an explicit read-only action.
