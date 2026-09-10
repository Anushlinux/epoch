import { $, escape, icon, shell, View, installNavigation } from './ui.mjs';
import { apiOrigin } from './intake-api.mjs';
import { TraceAPI } from './trace-api.mjs';

const root = $('#intake');
const view = new View(root);
const originKey = 'epoch.traces.origin.v1';
let savedOrigin;
try { savedOrigin = localStorage.getItem(originKey); } catch { /* The page also works without storage. */ }
let origin = 'http://127.0.0.1:8000';
try { if (savedOrigin) origin = apiOrigin(savedOrigin); } catch { /* Ignore an invalid saved origin. */ }
let api = new TraceAPI(origin);
let generation = 0, busy = false, timer, lastData = '', previousRenderKey = '';
let state = { runtime: null, list: null, detail: null, span: null, raw: null, rawError: '', error: '', updated: null };
const drafts = {};
const filterNames = ['q', 'project_id', 'workflow', 'session_id', 'started_after', 'started_before'];
const pageOffset = value => Math.min(1_000_000, Math.max(0, Number.parseInt(value, 10) || 0));
const selection = () => {
  const p = new URLSearchParams(location.search);
  return { trace: p.get('trace') || '', span: p.get('span') || '', offset: pageOffset(p.get('offset')),
    spanOffset: pageOffset(p.get('span_offset')), filters: Object.fromEntries(filterNames.map(name => [name, p.get(name) || ''])) };
};
const navigate = installNavigation(root, routeChanged, () => location.assign('/chat'));
const short = value => String(value || '').slice(0, 12);
const date = value => Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : 'Time unavailable';
const duration = value => Number.isFinite(value) ? value < 1000 ? `${value.toFixed(1)} ms` : `${(value / 1000).toFixed(2)} s` : 'Unknown';
const notices = values => [...new Set(values || [])].map(value => `<p class="trace-notice">${icon('info')}${escape(value)}</p>`).join('');
const badge = (status, count) => `<span class="trace-status ${status === 'recorded_error' ? 'trace-error' : ''}"><i></i>${status === 'recorded_error' ? `${count ?? ''} recorded error${count === 1 ? '' : 's'}` : 'No recorded error'}</span>`;
const code = value => `<pre class="trace-json" tabindex="0">${escape(JSON.stringify(value, null, 2))}</pre>`;

function url(changes = {}) {
  const p = new URLSearchParams(location.search);
  for (const [key, value] of Object.entries(changes)) {
    if (value === '' || value === null || value === undefined || value === 0) p.delete(key);
    else p.set(key, String(value));
  }
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

function listView() {
  const s = selection(), list = state.list;
  const items = list?.items || [];
  return `<section class="trace-run-panel" aria-labelledby="trace-list-title"><header class="trace-section-heading"><h2 id="trace-list-title">Executions</h2><span>${list ? `${list.total} traces` : 'Not loaded'}</span></header>
    ${items.length ? `<div class="trace-run-list">${items.map(item => `<a data-route class="trace-run ${s.trace === item.trace_id ? 'selected' : ''}" href="${escape(url({ trace: item.trace_id, span: '', span_offset: 0 }))}" ${s.trace === item.trace_id ? 'aria-current="true"' : ''}>
      <div class="trace-run-heading"><strong>${escape(item.name || 'Unnamed execution')}</strong><span>${escape(duration(item.duration_ms))}</span></div>
      <div class="trace-run-meta">${escape(item.workflows.join(', ') || 'Workflow not recorded')} · ${item.span_count} spans</div>
      ${badge(item.status, item.error_count)}<div class="trace-run-meta"><time>${escape(date(item.start_time))}</time><code>${escape(short(item.trace_id))}</code></div>
      ${item.missing_parent_count ? '<span class="trace-warning-label">Incomplete hierarchy</span>' : ''}</a>`).join('')}</div>` : `<div class="trace-empty">${icon('activity')}<h3>${busy && !list ? 'Loading executions…' : list ? 'No matching traces' : 'Connect your collector'}</h3><p>${list ? 'Run your instrumented application or adjust the search filters. Incoming spans appear here after export.' : 'Start the local backend, then connect to browse recorded executions.'}</p></div>`}
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
  if (!state.detail) return `<section class="trace-detail-panel"><div class="trace-empty"><h2>${busy ? 'Loading trace…' : 'Trace unavailable'}</h2><p>${escape(selected.trace)}</p></div></section>`;
  const { trace, spans, warnings, total } = state.detail;
  return `<section class="trace-detail-panel" aria-labelledby="trace-detail-title"><header class="trace-detail-header"><p class="trace-eyebrow">EXECUTION</p><h2 id="trace-detail-title">${escape(trace.name || 'Unnamed execution')}</h2><code class="trace-id">${escape(trace.trace_id)}</code><div class="trace-statline">${badge(trace.status, trace.error_count)}<span>${trace.span_count} spans</span><span>${escape(duration(trace.duration_ms))}</span></div><p class="trace-muted">${escape(trace.project_ids.join(', '))} · ${escape(trace.workflows.join(', ') || 'Workflow not recorded')} · ${escape(date(trace.start_time))}</p>${trace.session_ids.length ? `<p class="trace-muted">Session: ${escape(trace.session_ids.join(', '))}</p>` : ''}</header>
    ${notices(warnings)}<p class="trace-explanation">A span records one step. No recorded error does not establish that the requested task succeeded.</p>
    <div class="trace-inspection"><section class="trace-tree-panel" aria-label="Recorded span hierarchy"><header class="trace-section-heading"><h3>Recorded steps</h3><span>${spans.length} shown</span></header>${treeView(spans, trace.trace_id)}${pagination(total, selected.spanOffset, 200, 'span_offset')}</section>${spanView()}</div></section>`;
}

function spanView() {
  const selected = selection();
  if (!selected.span) return `<aside class="trace-span-panel"><div class="trace-empty"><h3>Inspect a step</h3><p>Select a span to see its captured input, output and attributes.</p></div></aside>`;
  const span = state.span;
  if (!span) return `<aside class="trace-span-panel"><div class="trace-empty"><h3>${busy ? 'Loading span…' : 'Span unavailable'}</h3><code>${escape(selected.span)}</code></div></aside>`;
  const rawPath = `/api/telemetry/traces/${encodeURIComponent(selected.trace)}/spans/${encodeURIComponent(selected.span)}`;
  return `<aside class="trace-span-panel" aria-labelledby="trace-span-title"><header class="trace-section-heading"><h3 id="trace-span-title">${escape(span.name || 'Unnamed span')}</h3><span class="trace-kind">${escape(span.kind)}</span></header>
    <dl class="trace-facts"><dt>Span</dt><dd><code>${escape(span.span_id)}</code></dd><dt>Parent</dt><dd><code>${escape(span.parent_span_id || 'Root')}</code></dd><dt>Duration</dt><dd>${escape(duration(span.duration_ms))}</dd>${span.tool ? `<dt>Tool</dt><dd>${escape(span.tool)}</dd>` : ''}${span.model ? `<dt>Model</dt><dd>${escape(span.model)}</dd>` : ''}</dl>
    ${notices(span.warnings)}<section class="trace-content"><h4>Input</h4>${span.has_input ? code(span.input) : '<p class="trace-muted">Not captured</p>'}</section><section class="trace-content"><h4>Output</h4>${span.has_output ? code(span.output) : '<p class="trace-muted">Not captured</p>'}</section>
    ${span.status_message ? `<section class="trace-content"><h4>Recorded status</h4><p>${escape(span.status_message)}</p></section>` : ''}
    <details class="trace-disclosure" data-key="events-${span.span_id}"><summary>Events and exceptions · ${span.events.length}</summary>${code(span.events)}</details>
    <details class="trace-disclosure" data-key="attributes-${span.span_id}"><summary>Attributes and resource</summary>${code({ span: span.attributes, resource: span.resource_attributes, scope: span.scope })}</details>
    <details class="trace-disclosure" data-key="links-${span.span_id}"><summary>Links and timing</summary>${code({ links: span.links, start_time_unix_nano: span.start_time_unix_nano, end_time_unix_nano: span.end_time_unix_nano, otlp_kind: span.otlp_kind, status_code: span.status_code })}</details>
    <details class="trace-disclosure" data-key="original-${span.span_id}"><summary>Original evidence</summary><p>The original OTLP record is retained separately from this searchable view.</p><div class="trace-inline-actions"><button data-action="trace-raw">Load original record</button><a href="${escape(origin + rawPath)}" target="_blank" rel="noopener">Open source ↗</a></div>${state.rawError ? notices([state.rawError]) : ''}${state.raw ? code(state.raw) : ''}</details></aside>`;
}

function render() {
  const selected = selection(), runtime = state.runtime;
  const index = runtime?.trace_index;
  const connection = `<details class="trace-connection" data-key="trace-connection" ${!runtime ? 'open' : ''}><summary>${icon('settings')}Collector connection</summary><form id="trace-connection-form"><label for="trace-origin">Local API origin<input id="trace-origin" name="origin" type="url" required value="${escape(drafts.origin ?? origin)}"></label><button type="submit">Connect</button></form><p>Run <code>epoch-backend serve --profile trace-debugger</code>. SDK authentication uses the server process token; no credential is entered here.</p></details>`;
  const content = `<div class="trace-page"><header class="trace-page-header"><div><p class="trace-eyebrow">NEATLOGS / LOCAL EXPLORER</p><h1>Traces</h1><p>See what your agent actually did.</p></div><button data-action="trace-refresh" ${busy ? 'disabled' : ''}>${icon('refresh')}${busy ? 'Refreshing…' : 'Refresh'}</button></header>
    <div class="trace-runtime" role="status"><span class="${runtime?.collector_ready ? 'trace-ready' : 'trace-pending'}"><i></i>${runtime ? runtime.collector_ready ? 'Collector ready' : 'Collector needs setup' : 'Collector not connected'}</span><span>${index?.ready ? `${index.indexed_spans} indexed spans` : 'Index unavailable'}</span><span>${runtime?.cloud_enabled ? 'Cloud forwarding enabled' : runtime ? 'Cloud forwarding disabled' : 'Routing unknown'}</span><span id="trace-updated">${state.updated ? `Updated ${new Date(state.updated).toLocaleTimeString()}` : 'Waiting for connection'}</span></div>
    ${state.error ? `<div class="trace-error-banner" role="alert"><strong>${state.updated ? 'Showing saved view — refresh failed' : 'Unable to load traces'}</strong><p>${escape(state.error)}</p></div>` : ''}
    ${connection}${notices([...(runtime?.warnings || []), ...(state.list?.warnings || [])])}
    <form id="trace-filter-form" class="trace-filters">${field('q', 'Search captured content', 'Invoice ID, tool name, input or output…')}<div class="trace-filter-actions"><button type="submit">Search</button><a data-route href="/traces">Clear</a></div><details class="trace-filter-more" data-key="trace-filters"><summary>Filter by workflow, project, session or time</summary><div>${field('project_id', 'Project', 'All projects')}${field('workflow', 'Workflow', 'All workflows')}${field('session_id', 'Session', 'All sessions')}${field('started_after', 'Started after (ISO time)', '2026-09-10T00:00:00Z')}${field('started_before', 'Started before (ISO time)', '2026-09-11T00:00:00Z')}</div></details></form>
    <div class="trace-layout">${listView()}${detailView()}</div><p class="trace-footnote">Refreshes every five seconds while this page is visible. Search indexes the first 64,000 characters of each content field; the original source remains available.</p></div>`;
  const renderKey = `traces:${origin}:${selected.trace}:${selected.span}`;
  const scrolls = new Map(previousRenderKey === renderKey ? [...root.querySelectorAll('.trace-json, .trace-run-list')].map((el, i) => [i, [el.scrollTop, el.scrollLeft]]) : []);
  view.render(shell({ page: 'traces', title: 'Trace explorer', sessionsLabel: 'TRACE EXPLORER', nav: '<p class="trace-nav-note">Local execution evidence.<br>Capture, browse and search.</p>', content,
    status: '<span class="trace-header-label">Read-only explorer</span>' }), renderKey);
  root.querySelectorAll('.trace-json, .trace-run-list').forEach((el, i) => { const pos = scrolls.get(i); if (pos) [el.scrollTop, el.scrollLeft] = pos; });
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
    ]);
    if (generation !== token) return;
    const errors = [];
    for (const [i, key] of ['runtime', 'list', 'detail', 'span'].entries()) {
      const result = results[i];
      if (result.status === 'fulfilled') state[key] = result.value;
      else errors.push(result.reason.message || 'A local request failed.');
    }
    state.error = [...new Set(errors)].join(' ');
    const snapshot = JSON.stringify([state.runtime, state.list, state.detail, state.span, state.error]);
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

async function routeChanged() {
  if (location.pathname !== '/traces') { location.assign(location.href); return; }
  generation++;
  busy = false;
  const selected = selection();
  if (state.detail?.trace.trace_id !== selected.trace) state.detail = null;
  if (state.span?.trace_id !== selected.trace || state.span?.span_id !== selected.span) state.span = null;
  state.raw = null;
  state.rawError = '';
  state.error = '';
  for (const name of filterNames) delete drafts[name];
  render();
  await refresh();
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
    navigate(url({ ...filters, offset: 0, span_offset: 0, trace: '', span: '' }));
  }
  if (event.target.id === 'trace-connection-form') {
    event.preventDefault();
    try {
      const next = apiOrigin(new FormData(event.target).get('origin'));
      generation++;
      busy = false;
      origin = next;
      api = new TraceAPI(origin);
      state = { runtime: null, list: null, detail: null, span: null, raw: null, rawError: '', error: '', updated: null };
      try { localStorage.setItem(originKey, origin); } catch { /* Persistence is optional. */ }
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
void refresh();
