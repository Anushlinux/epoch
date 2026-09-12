import { $, escape, icon, shell, View, installNavigation } from './ui.mjs';
import { apiOrigin, ORIGIN_KEY } from './intake-api.mjs';
import { TraceAPI } from './trace-api.mjs';
import { TraceQuestionPanel } from './trace-question-ui.mjs';
import { NoisePanel } from './noise-ui.mjs';
import { chatID, tracesURL } from './trace-links.mjs';
import { renderTraceContent } from './trace-content.mjs';

const root = $('#intake');
const view = new View(root);
const originKey = 'epoch.traces.origin.v1';
let origin = 'http://127.0.0.1:8000';
try {
  const saved = localStorage.getItem(originKey);
  if (saved) origin = apiOrigin(saved);
} catch { /* Ignore an unavailable or invalid legacy trace connection. */ }
try {
  const workspaceOrigin = sessionStorage.getItem(ORIGIN_KEY);
  if (workspaceOrigin) origin = apiOrigin(workspaceOrigin);
} catch { /* Traces also work when workspace preferences cannot be read. */ }
let api = new TraceAPI(origin);
let generation = 0, busy = false, timer, lastData = '', previousRenderKey = '';
let state = { runtime: null, list: null, detail: null, span: null, context: null, contextError: '', raw: null, rawError: '', error: '', updated: null };
const drafts = {};
const filterNames = ['q', 'project_id', 'workflow', 'session_id', 'started_after', 'started_before'];
const pageOffset = value => Math.min(1_000_000, Math.max(0, Number.parseInt(value, 10) || 0));
const selection = () => {
  const p = new URLSearchParams(location.search);
  const chat = chatID(p.get('chat')) ? p.get('chat') : '';
  const filters = Object.fromEntries(filterNames.map(name => [name, p.get(name) || '']));
  if (chat) filters.session_id = chat;
  return { chat, trace: p.get('trace') || '', span: p.get('span') || '', offset: pageOffset(p.get('offset')),
    spanOffset: pageOffset(p.get('span_offset')), question: p.get('question') || '',
    questionOffset: pageOffset(p.get('question_offset')), panel: p.get('panel') || '',
    filters };
};
let filterRouteKey = JSON.stringify(selection().filters);
const navigate = installNavigation(root, routeChanged, () => location.assign('/chat'));
const questions = new TraceQuestionPanel(root, () => ({ ...selection(), origin, api }), render, navigate, url);
const noise = new NoisePanel(root, () => ({ ...selection(), origin, api }), render, url);
const short = value => String(value || '').slice(0, 12);
const date = value => Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Time unavailable';
const duration = value => Number.isFinite(value) ? value < 1000 ? `${value.toFixed(1)} ms` : `${(value / 1000).toFixed(2)} s` : 'Unknown';
const notices = values => [...new Set(values || [])].map(value => `<p class="trace-notice">${icon('info')}${escape(value)}</p>`).join('');
const badge = (status, count) => `<span class="trace-status ${status === 'recorded_error' ? 'trace-error' : ''}"><i></i>${status === 'recorded_error' ? `${count ?? ''} recorded error${count === 1 ? '' : 's'}` : 'No recorded error'}</span>`;
const code = value => `<pre class="trace-json" tabindex="0">${escape(JSON.stringify(value, null, 2))}</pre>`;
const showSteps = () => {
  const selected = selection();
  return !selected.chat || selected.panel === 'steps' || (!selected.panel && !!selected.question) || location.hash === '#trace-selected-span';
};
const compactNotices = (values, key, label = 'Recording notices') => {
  const items = [...new Set(values || [])];
  return items.length ? `<details class="trace-recording-notices" data-key="${escape(key)}"><summary>${escape(label)} · ${items.length}</summary>${notices(items)}</details>` : '';
};

function url(changes = {}) {
  const p = new URLSearchParams(location.search);
  if ('trace' in changes && changes.trace !== p.get('trace')) {
    p.delete('question');
    p.delete('question_offset');
  }
  for (const [key, value] of Object.entries(changes)) {
    if (value === '' || value === null || value === undefined || value === 0) p.delete(key);
    else p.set(key, String(value));
  }
  if (changes.span || changes.question) p.set('panel', 'steps');
  return `/traces${p.size ? `?${p}` : ''}`;
}

function field(name, label, placeholder = '') {
  const value = drafts[name] ?? selection().filters[name];
  return `<label class="trace-field" for="trace-${name}"><span>${label}</span><input id="trace-${name}" name="${name}" value="${escape(value)}" placeholder="${escape(placeholder)}" maxlength="${name === 'q' ? 500 : 300}"></label>`;
}

function pagination(total, offset, limit, key) {
  if (total <= limit && !offset) return '';
  return `<nav class="trace-pagination" aria-label="${key === 'offset' ? 'Trace' : 'Span'} pages">${offset ? `<a data-route href="${escape(url({ [key]: Math.max(0, offset - limit) }))}">${icon('back')}Previous</a>` : '<span></span>'}<span>${Math.min(offset + 1, total)}–${Math.min(offset + limit, total)} of ${total}</span>${offset + limit < total ? `<a data-route href="${escape(url({ [key]: offset + limit }))}">Next${icon('chevron')}</a>` : '<span></span>'}</nav>`;
}

function conversationView() {
  const { chat, trace } = selection(), context = state.context;
  if (!chat) return '';
  const operation = trace ? context?.selected_operation?.trace_id === trace ? context.selected_operation : null : context?.latest_operation;
  const notes = [...(operation?.trace_warnings || [])];
  if (operation?.trace_capture === 'recording') notes.push('Hermes is still running. Completed tool steps appear first; the conversation step is stored when this response ends.');
  if (context?.uncaptured_operations) notes.push(`${context.uncaptured_operations} earlier message(s) have no captured trace. New messages are captured automatically; earlier runs are not recreated.`);
  if (context?.requested_trace_id === trace && trace && !context.selected_operation) notes.push('This trace is not linked to a message in this conversation.');
  return `<section class="trace-conversation" aria-label="Conversation context"><div><p class="trace-eyebrow">CONVERSATION</p><h2>${escape(context?.title || 'Conversation traces')}</h2></div><div class="trace-inline-actions"><a href="/chat?chat=${encodeURIComponent(chat)}">${icon('back')}Back to chat</a><a data-route href="/traces">All traces</a></div>${compactNotices(notes, 'conversation-notices')}${state.contextError ? notices([state.contextError]) : ''}</section>`;
}

function listView() {
  const s = selection(), list = state.list;
  const items = list?.items || [];
  return `<section class="trace-run-panel" aria-labelledby="trace-list-title"><header class="trace-section-heading"><h2 id="trace-list-title">Executions</h2><span>${list ? `${list.total} traces` : 'Not loaded'}</span></header>
    ${items.length ? `<div class="trace-run-list">${items.map(item => `<a data-route class="trace-run ${s.trace === item.trace_id ? 'selected' : ''}" href="${escape(url({ trace: item.trace_id, span: '', span_offset: 0 }))}" ${s.trace === item.trace_id ? 'aria-current="true"' : ''}>
      <div class="trace-run-heading"><strong>${escape(item.name || 'Unnamed execution')}</strong><span>${escape(duration(item.duration_ms))}</span></div>
      <div class="trace-run-meta">${escape(item.workflows.join(', ') || 'Workflow not recorded')} · ${item.span_count} spans</div>
      ${badge(item.status, item.error_count)}<div class="trace-run-meta"><time>${escape(date(item.start_time))}</time><code>${escape(short(item.trace_id))}</code></div>
      ${item.missing_parent_count ? '<span class="trace-warning-label">Incomplete hierarchy</span>' : ''}</a>`).join('')}</div>` : `<div class="trace-empty">${icon('activity')}<h3>${busy && !list ? 'Loading runs…' : list ? 'No matching traces' : 'Connect your collector'}</h3><p>${list ? 'Completed steps appear after a chat message. Adjust filters to find another run.' : 'Start the local backend and connect.'}</p>${s.chat ? `<a href="/chat?chat=${encodeURIComponent(s.chat)}">Back to chat</a>` : '<a href="/chat">Open Chat</a>'}</div>`}
    ${list ? pagination(list.total, s.offset, 50, 'offset') : ''}</section>`;
}

function treeView(spans, traceId) {
  const selected = selection().span;
  const byId = new Map(spans.map(span => [span.span_id, span]));
  const children = new Map();
  for (const span of spans) {
    const parent = byId.has(span.parent_span_id) && span.parent_span_id !== span.span_id ? span.parent_span_id : '';
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent).push(span);
  }
  const visited = new Set();
  function renderNode(span, depth = 0) {
    if (visited.has(span.span_id)) return '';
    visited.add(span.span_id);
    const descendants = (children.get(span.span_id) || []).filter(child => !visited.has(child.span_id));
    const row = `<a data-route class="trace-span-row ${selected === span.span_id ? 'selected' : ''}" href="${escape(url({ span: span.span_id }))}" ${selected === span.span_id ? 'aria-current="true"' : ''}><span class="trace-kind">${escape(span.kind)}</span><span class="trace-span-name">${escape(span.name || 'Unnamed span')}</span><span class="trace-span-duration">${escape(duration(span.duration_ms))}</span>${span.status === 'recorded_error' ? '<span class="trace-error-dot" aria-label="Recorded error"></span>' : ''}</a>`;
    const warning = span.parent_missing ? '<small class="trace-parent-note">Parent not recorded</small>' : span.parent_span_id && !byId.has(span.parent_span_id) ? '<small class="trace-parent-note">Parent is on another page</small>' : '';
    if (descendants.length && depth < 40) {
      return `<li><details data-key="tree-${traceId}-${span.span_id}" open><summary>${row}</summary>${warning}<ul>${descendants.map(child => renderNode(child, depth + 1)).join('')}</ul></details></li>`;
    }
    return `<li>${row}${warning}${descendants.length ? '<small class="trace-parent-note">Deeper spans listed separately</small>' : ''}</li>`;
  }
  let nodes = (children.get('') || []).map(span => renderNode(span)).join('');
  const detached = spans.filter(span => !visited.has(span.span_id));
  if (detached.length) nodes += `<li class="trace-parent-note">Unresolved or deeply nested hierarchy</li>${detached.map(span => renderNode(span)).join('')}`;
  return `<ul class="trace-tree">${nodes}</ul>`;
}

function detailView() {
  const selected = selection();
  if (!selected.trace) return `<section class="trace-detail-panel"><div class="trace-empty trace-choose">${icon('pipeline')}<h2>Follow an execution</h2><p>Select a trace to inspect the steps, inputs and outputs that were actually recorded.</p></div></section>`;
  if (!state.detail) return `<section class="trace-detail-panel"><div class="trace-empty"><h2>${state.context?.selected_operation?.trace_capture === 'recording' ? 'Waiting for recorded steps…' : busy ? 'Loading trace…' : 'Trace unavailable'}</h2><p>${escape(selected.trace)}</p><p>A running step is exported when it ends. If capture was interrupted, unfinished steps may be missing.</p></div></section>`;
  const { trace, spans, warnings, total } = state.detail;
  const stepQuestions = questions.view();
  const questionAttention = !!(selected.question || questions.pending || questions.state.sending || questions.drafts.get(questions.key));
  return `<section class="trace-detail-panel" aria-labelledby="trace-detail-title"><header class="trace-detail-header"><h2 id="trace-detail-title">${escape(trace.name || 'Unnamed execution')}</h2><div class="trace-statline">${badge(trace.status, trace.error_count)}<span>${trace.span_count} steps</span><span>${escape(duration(trace.duration_ms))}</span><span>${escape(date(trace.start_time))}</span></div><details class="trace-run-info" data-key="run-info-${trace.trace_id}"><summary>Run details</summary>${code({ trace_id: trace.trace_id, projects: trace.project_ids, workflows: trace.workflows, sessions: trace.session_ids })}<p class="trace-muted">No recorded error does not establish task success.</p></details></header>
    ${compactNotices(warnings, `trace-notices-${trace.trace_id}`)}${!selected.chat && chatID(state.span?.attributes?.['epoch.chat_id']) ? `<p class="trace-explanation"><a href="/chat?chat=${encodeURIComponent(state.span.attributes['epoch.chat_id'])}">Back to this conversation</a></p>` : ''}
    ${selected.chat ? `<details class="trace-step-question" data-key="${escape(`step-question-${trace.trace_id}-${selected.question}-${questionAttention ? 'active' : 'idle'}`)}" ${questionAttention ? 'open' : ''}><summary>${questions.pending ? 'Question awaiting confirmation' : 'Ask about these steps'}</summary>${stepQuestions}</details>` : stepQuestions}
    <div class="trace-inspection"><section class="trace-tree-panel" aria-label="Recorded span hierarchy"><header class="trace-section-heading"><h3>Steps</h3><span>${spans.length} shown</span></header>${treeView(spans, trace.trace_id)}${pagination(total, selected.spanOffset, 200, 'span_offset')}</section>${spanView()}</div></section>`;
}

function spanView() {
  const selected = selection();
  if (!selected.span) return `<aside class="trace-span-panel"><div class="trace-empty"><h3>Inspect a step</h3><p>Select a span to see its captured input, output and attributes.</p></div></aside>`;
  const span = state.span;
  if (!span) return `<aside class="trace-span-panel"><div class="trace-empty"><h3>${busy ? 'Loading span…' : 'Span unavailable'}</h3><code>${escape(selected.span)}</code></div></aside>`;
  const rawPath = `/api/telemetry/traces/${encodeURIComponent(selected.trace)}/spans/${encodeURIComponent(selected.span)}`;
  return `<aside class="trace-span-panel" id="trace-selected-span" tabindex="-1" aria-labelledby="trace-span-title"><header class="trace-section-heading"><h3 id="trace-span-title">${escape(span.name || 'Unnamed span')}</h3><span class="trace-kind">${escape(span.kind)}</span></header>
    <dl class="trace-facts"><dt>Duration</dt><dd>${escape(duration(span.duration_ms))}</dd>${span.tool ? `<dt>Tool</dt><dd>${escape(span.tool)}</dd>` : ''}${span.model ? `<dt>Model</dt><dd>${escape(span.model)}</dd>` : ''}</dl>
    ${notices(span.warnings)}<section class="trace-content"><h4>Input</h4>${span.has_input ? renderTraceContent(span.input, { key: `input-${span.span_id}` }) : '<p class="trace-muted">Not captured</p>'}</section><section class="trace-content"><h4>Output</h4>${span.has_output ? renderTraceContent(span.output, { key: `output-${span.span_id}` }) : '<p class="trace-muted">Not captured</p>'}</section>
    ${span.status_message ? `<section class="trace-content"><h4>Recorded status</h4><p>${escape(span.status_message)}</p></section>` : ''}
    ${span.events.length ? `<details class="trace-disclosure" data-key="events-${span.span_id}"><summary>Events and exceptions · ${span.events.length}</summary>${renderTraceContent(span.events, { key: `events-${span.span_id}` })}</details>` : ''}
    <details class="trace-disclosure" data-key="technical-${span.span_id}"><summary>Technical details</summary>${code({ span_id: span.span_id, parent_span_id: span.parent_span_id, attributes: span.attributes, resource: span.resource_attributes, scope: span.scope, links: span.links, start_time_unix_nano: span.start_time_unix_nano, end_time_unix_nano: span.end_time_unix_nano, otlp_kind: span.otlp_kind, status_code: span.status_code })}</details>
    <details class="trace-disclosure" data-key="original-${span.span_id}"><summary>Original evidence</summary><details data-key="recorded-content-${span.span_id}"><summary>Recorded input and output</summary>${code({ input: span.input, output: span.output })}</details><div class="trace-inline-actions"><button data-action="trace-raw">Load original record</button><a href="${escape(origin + rawPath)}" target="_blank" rel="noopener">Open source ↗</a></div>${state.rawError ? notices([state.rawError]) : ''}${state.raw ? code(state.raw) : ''}</details></aside>`;
}

function render() {
  const selected = selection(), runtime = state.runtime;
  questions.sync();
  const index = runtime?.trace_index;
  const steps = showSteps();
  const connection = `<details class="trace-connection" data-key="trace-connection" ${!runtime ? 'open' : ''}><summary>${icon('settings')}Connection</summary><form id="trace-connection-form"><label for="trace-origin">Local API origin<input id="trace-origin" name="origin" type="url" required value="${escape(drafts.origin ?? origin)}"></label><button type="submit">Connect</button></form><p>${index?.ready ? `${index.indexed_spans} indexed steps` : 'Index unavailable'} · ${runtime?.collector_ready ? 'External SDK ingestion ready' : 'External SDK ingestion needs a token'}</p><p>${runtime?.cloud_enabled ? 'External trace cloud forwarding enabled; chat capture stays local.' : runtime ? 'Cloud forwarding disabled.' : 'Routing unavailable.'}</p><p>Refreshes every five seconds. Search covers the first 64,000 characters per content field; originals remain available.</p>${!runtime ? '<p>Start the backend with <code>epoch-backend --env-file .env serve</code>.</p>' : ''}</details>`;
  const filters = `<form id="trace-filter-form" class="trace-filters">${field('q', 'Search runs', 'Search names, inputs or outputs')}<div class="trace-filter-actions"><button type="submit">Search</button><a data-route href="${escape(url({ q: '', project_id: '', workflow: '', session_id: selected.chat || '', started_after: '', started_before: '', trace: '', span: '', offset: 0, span_offset: 0 }))}">Clear</a></div><details class="trace-filter-more" data-key="trace-filters"><summary>More filters</summary><div>${field('project_id', 'Project')}${field('workflow', 'Workflow')}${field('session_id', 'Session')}${field('started_after', 'Started after (ISO time)')}${field('started_before', 'Started before (ISO time)')}</div></details></form>`;
  const tabs = selected.chat && selected.trace ? `<nav class="trace-view-switch" aria-label="Trace view"><a data-route href="${escape(url({ panel: 'analysis' }))}" ${!steps ? 'aria-current="page"' : ''}>Analysis</a><a data-route href="${escape(url({ panel: 'steps' }))}" ${steps ? 'aria-current="page"' : ''}>Recorded steps${questions.pending ? ' · Pending question' : ''}</a></nav>` : '';
  const runs = selected.trace ? `<details class="trace-run-picker" data-key="run-picker-${selected.chat}"><summary>Choose another run${state.list ? ` · ${state.list.total}` : ''}</summary>${filters}${listView()}</details>` : filters;
  const main = selected.trace
    ? (steps ? detailView() : noise.view())
    : selected.chat ? `${listView()}${noise.view()}` : `<div class="trace-layout">${listView()}${detailView()}</div>`;
  const content = `<div class="trace-page ${selected.trace ? 'trace-page-focused' : ''}"><header class="trace-page-header"><div><h1>Traces</h1></div><div class="trace-toolbar"><span class="${runtime?.local_capture_ready || runtime?.collector_ready ? 'trace-ready' : 'trace-pending'}">${runtime ? runtime.local_capture_ready || runtime.collector_ready ? 'Connected' : 'Capture unavailable' : 'Not connected'}</span><button data-action="trace-refresh" ${busy ? 'disabled' : ''}>${icon('refresh')}${busy ? 'Refreshing…' : 'Refresh'}</button></div></header>
    ${state.error ? `<div class="trace-error-banner" role="alert"><strong>${state.updated ? 'Showing saved view — refresh failed' : 'Unable to load traces'}</strong><p>${escape(state.error)}</p></div>` : ''}
    <div class="trace-utility-row">${connection}<span id="trace-updated">${state.updated ? `Updated ${new Date(state.updated).toLocaleTimeString()}` : 'Waiting for connection'}</span></div>
    ${compactNotices([...(runtime?.warnings || []), ...(state.list?.warnings || []), ...(runtime && !index?.ready ? ['Trace indexing is incomplete or unavailable.'] : [])], 'index-notices', 'Indexing notices')}${conversationView()}${runs}${tabs}${main}</div>`;
  const renderKey = `traces:${origin}:${selected.trace}:${steps ? 'steps' : 'analysis'}:${steps ? selected.span : ''}`;
  const scrolls = new Map(previousRenderKey === renderKey ? [...root.querySelectorAll('.trace-json, .trace-readable-json, .trace-run-list')].map((el, i) => [i, [el.scrollTop, el.scrollLeft]]) : []);
  view.render(shell({ page: 'traces', title: 'Trace explorer', sessionsLabel: 'WORKSPACE', nav: selected.chat ? `<a class="nav-item" href="/chat?chat=${encodeURIComponent(selected.chat)}">${icon('back')}Back to chat</a>` : '', content,
    debuggerChatId: selected.chat, tracesHref: tracesURL(selected.chat),
    status: '<span class="trace-header-label">Local trace workspace</span>' }), renderKey);
  root.querySelectorAll('.trace-json, .trace-readable-json, .trace-run-list').forEach((el, i) => { const pos = scrolls.get(i); if (pos) [el.scrollTop, el.scrollLeft] = pos; });
  previousRenderKey = renderKey;
  document.title = 'Epoch · Traces';
}

async function refresh({ quiet = false } = {}) {
  if (busy || document.hidden || location.pathname !== '/traces') return;
  busy = true;
  const token = generation, chosen = selection(), activeAPI = api;
  if (!quiet) render();
  try {
    const results = await Promise.allSettled([
      activeAPI.runtime(),
      activeAPI.list({ ...chosen.filters, limit: 50, offset: chosen.offset }),
      chosen.trace ? activeAPI.trace(chosen.trace, chosen.spanOffset) : Promise.resolve(null),
      chosen.trace && chosen.span ? activeAPI.span(chosen.trace, chosen.span) : Promise.resolve(null),
      questions.refresh(),
      chosen.chat ? activeAPI.chatContext(chosen.chat, chosen.trace) : Promise.resolve(null),
      noise.refresh(),
    ]);
    if (generation !== token) return;
    const errors = [];
    if (results[5].status === 'fulfilled') {
      state.context = results[5].value;
      state.contextError = '';
    } else state.contextError = 'Conversation context could not be loaded. Use the normal backend serve command and the same data directory as Chat. ' + (results[5].reason.message || '');
    for (const [i, key] of ['runtime', 'list', 'detail', 'span'].entries()) {
      const result = results[i];
      if (result.status === 'fulfilled') state[key] = result.value;
      else if (!(key === 'detail' && result.reason.status === 404 && state.context?.selected_operation?.trace_capture === 'recording')) errors.push(result.reason.message || 'A local request failed.');
    }
    state.error = [...new Set(errors)].join(' ');
    if (results[4].status === 'rejected') questions.state.error = results[4].reason.message || 'Question history could not be refreshed.';
    const snapshot = JSON.stringify([state.runtime, state.list, state.detail, state.span, state.context, state.contextError, state.error, questions.state, noise.data, noise.error]);
    if (!errors.length) state.updated = Date.now();
    busy = false;
    if (snapshot !== lastData || !quiet) { lastData = snapshot; render(); }
    else if (!errors.length && $('#trace-updated')) {
      $('#trace-updated').textContent = `Updated ${new Date(state.updated).toLocaleTimeString()}`;
    }
  } catch (error) {
    if (generation === token) { busy = false; state.error = error.message; render(); }
  } finally {
    if (generation === token) busy = false;
  }
}

function focusCitation() {
  if (location.hash === '#trace-selected-span') {
    const inspector = $('#trace-selected-span');
    inspector?.scrollIntoView({ block: 'start', behavior: 'instant' });
    inspector?.focus({ preventScroll: true });
  }
}

async function routeChanged() {
  if (location.pathname !== '/traces') { location.assign(location.href); return; }
  generation++;
  busy = false;
  const selected = selection();
  if (state.detail?.trace.trace_id !== selected.trace) state.detail = null;
  if (state.span?.trace_id !== selected.trace || state.span?.span_id !== selected.span) state.span = null;
  if (state.context?.chat_id !== selected.chat) state.context = null;
  else if (state.context && state.context.requested_trace_id !== selected.trace) state.context = { ...state.context, selected_operation: null, requested_trace_id: null };
  state.contextError = '';
  state.raw = null;
  state.rawError = '';
  state.error = '';
  const nextFilterKey = JSON.stringify(selected.filters);
  if (nextFilterKey !== filterRouteKey) for (const name of filterNames) delete drafts[name];
  filterRouteKey = nextFilterKey;
  render();
  const routeGeneration = generation;
  await refresh();
  if (generation === routeGeneration) focusCitation();
}

root.addEventListener('input', event => {
  const name = event.target.name;
  if (name === 'origin' || filterNames.includes(name)) drafts[name] = event.target.value;
});
root.addEventListener('submit', async event => {
  if (event.target.id === 'trace-filter-form') {
    event.preventDefault();
    const form = new FormData(event.target);
    const filters = Object.fromEntries(filterNames.map(name => [name, String(form.get(name) || '').trim()]));
    const chat = selection().chat;
    navigate(url({ ...filters, chat: filters.session_id === chat ? chat : '', offset: 0, span_offset: 0, trace: '', span: '' }));
  }
  if (event.target.id === 'trace-connection-form') {
    event.preventDefault();
    try {
      const next = apiOrigin(new FormData(event.target).get('origin'));
      generation++;
      busy = false;
      origin = next;
      api = new TraceAPI(origin);
      state = { runtime: null, list: null, detail: null, span: null, context: null, contextError: '', raw: null, rawError: '', error: '', updated: null };
      try { localStorage.setItem(originKey, origin); } catch { /* Persistence is optional. */ }
      try { sessionStorage.setItem(ORIGIN_KEY, origin); } catch { /* The current connection remains usable. */ }
      await refresh();
    } catch (error) { state.error = error.message; render(); }
  }
});
root.addEventListener('click', async event => {
  const action = event.target.closest('[data-action]')?.dataset.action;
  if (['trace-refresh', 'refresh-list'].includes(action)) await refresh();
  if (action === 'trace-raw') {
    const token = generation, chosen = selection();
    event.target.closest('button').disabled = true;
    try {
      const record = await api.span(chosen.trace, chosen.span, true);
      if (token === generation) { state.raw = record; state.rawError = ''; }
    } catch (error) { if (token === generation) state.rawError = error.message; }
    if (token === generation) render();
  }
});
function schedule() {
  clearInterval(timer);
  if (!document.hidden) timer = setInterval(() => { void refresh({ quiet: true }); }, 5000);
}
document.addEventListener('visibilitychange', () => { schedule(); if (!document.hidden) void refresh(); });
window.addEventListener('pagehide', () => { clearInterval(timer); generation++; busy = false; });
window.addEventListener('pageshow', event => { if (event.persisted) { schedule(); void refresh(); } });
render();
schedule();
void refresh().then(focusCitation);
