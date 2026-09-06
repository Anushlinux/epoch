import { repairView } from './chat-repair.mjs';
import { ChatWorkspace, activeOperation } from './chat-api.mjs';
import { SAMPLE_PROMPT, FESTIVAL_PROMPT, environmentLabel, environmentPicker, environmentView } from './chat-environment.mjs';
import { $, escape, icon, shell, View, installNavigation } from './ui.mjs';
const root = $('#intake'), view = new View(root);
let storage;
try { storage = sessionStorage; } catch { storage = { getItem() { throw new Error('Storage unavailable'); } }; }
let question = '';
const drafts = new Map(), questions = new Map();
const isDebugger = () => location.pathname === '/debugger';
const debuggerURL = id => `/debugger${id ? `?chat=${encodeURIComponent(id)}` : ''}`;
let draft = '', project = 'demo', environment = 'pdf_workshop', settings = false, originDraft = '', seenMessages = 0;
const chatURL = id => `/chat${id ? `?chat=${encodeURIComponent(id)}` : ''}`;
const workspace = new ChatWorkspace({ storage, onChange: render });
environment = workspace.state.pending?.create.environment || 'pdf_workshop';
workspace.state.selected = new URLSearchParams(location.search).get('chat') || '';
const navigate = installNavigation(root, routeChanged, () => navigate(chatURL('')));
function messageBody(content) {
  // Escape before adding markup. Model text can never inject HTML or active URLs.
  return content.split(/(```[\s\S]*?```)/g).map(part => part.startsWith('```')
    ? `<pre><code>${escape(part.slice(3, -3).replace(/^[\w+-]*\n/, ''))}</code></pre>`
    : `<div class="chat-prose">${escape(part)}</div>`).join('');
}
function investigationView(s, blocked) {
  const chat = s.chat;
  const operations = chat?.operations || [];
  const requests = (chat?.messages || []).filter(message => message.role === 'user' && message.agent !== 'debugger' && operations.find(operation => operation.id === message.operation_id)?.kind !== 'debugger');
  const analyses = operations.filter(operation => operation.kind === 'debugger');
  const records = analyses.map(operation => `<article class="investigation-result"><h2>${operation.action === 'repair' ? 'Repair' : 'Investigation'} · ${escape(operation.status)}</h2>${operation.status === 'running' ? `<p role="status">${escape(operation.activity)}</p>` : ''}${operation.question ? `<p class="chat-prose">${escape(operation.question)}</p>` : ''}${operation.error ? `<p class="notice">${escape(operation.error.message)}</p>` : ''}${operation.analysis ? `<div class="chat-prose">${escape(operation.analysis.answer || operation.activity || '')}</div>${operation.analysis.missing_evidence?.length ? `<h3>Missing evidence</h3><ul>${operation.analysis.missing_evidence.map(item => `<li>${escape(typeof item === 'string' ? item : JSON.stringify(item))}</li>`).join('')}</ul>` : ''}<details class="disclosure" data-key="analysis-${escape(operation.id)}"><summary>Evidence, hypotheses and missing information ${icon('down')}</summary><pre>${escape(JSON.stringify(operation.analysis, null, 2))}</pre></details>` : `<p>${escape(operation.error?.message || operation.activity || 'No analysis recorded.')}</p>`}</article>`).join('');
  return `<div class="debugger conversation-debugger"><header class="debug-heading"><h1>Debugger</h1><p>Investigate what went wrong using the conversation, existing requirements and recorded tool evidence.</p></header>${chat?.environment === 'pdf_workshop' ? repairView(s, blocked) : ''}${environmentView(s)}${chat ? `<section class="debugger-context"><h2>${escape(chat.title)}</h2><a data-route class="text-button" href="${chatURL(chat.id)}">Open conversation ${icon('arrow')}</a><details class="disclosure" data-key="debugger-requirements" ${chat.environment === 'pdf_workshop' ? '' : 'open'}><summary>Existing requirements ${icon('down')}</summary><p>Your requests stay unchanged. The debugger distinguishes evidence from hypotheses and identifies missing information.</p>${requests.map(message => `<blockquote class="chat-prose">${escape(message.content)}</blockquote>`).join('') || '<p>No user requirements are recorded yet.</p>'}</details></section>${chat.environment === 'pdf_workshop' ? '' : `<section class="debugger-action"><form id="debugger-form"><label for="debugger-question">What should the debugger investigate? (optional)</label><textarea id="debugger-question" rows="3" maxlength="12000" placeholder="Describe the unexpected result, or leave blank to review the recorded evidence." ${s.busy || s.pending || s.recovery ? 'disabled' : ''}>${escape(question)}</textarea><p>This runs a read-only Luna investigation. It preserves the task criteria and does not rerun the task or publish a repair.</p><button id="investigate-chat" ${blocked || !chat.messages.length || !s.runtime?.debugger?.available ? 'disabled' : ''}>${activeOperation(chat)?.kind === 'debugger' ? 'Investigating…' : 'Investigate conversation'}</button>${activeOperation(chat) ? `<button type="button" data-action="stop" ${s.busy ? 'disabled' : ''}>Stop operation</button>` : ''}${!s.runtime?.debugger?.available ? '<p class="notice">The debugger is unavailable. Enable the backend debugger connection to investigate.</p>' : ''}</form></section>`}${records}` : `<section class="debugger-context"><h2>${s.selected ? 'Conversation unavailable' : 'Choose a conversation to investigate'}</h2><p>${s.selected ? 'Reconnect or select a saved conversation from the sidebar.' : 'Select a saved conversation from the sidebar, or start a chat with Hermes first.'}</p><a data-route class="text-button" href="/chat">Start a chat ${icon('arrow')}</a></section>`}<section class="debugger-other"><h2>Other evidence</h2><p>Inspect grouped failures, imported reports and existing trusted run checks.</p><a href="/incidents" class="text-button">Open incidents and investigations ${icon('arrow')}</a><details class="disclosure" data-key="release-example"><summary>Release example ${icon('down')}</summary><p>The release workflow is a specific demonstration with ticket, checklist and QA checks. Its execution and repair controls are separate from this conversation.</p><a href="/debugger?mode=release" class="text-button">Open release demo controls ${icon('arrow')}</a> · <a href="/demo/chat" class="text-button">Explore authored release example ${icon('arrow')}</a></details></section></div>`;
}
function render() {
  const s = workspace.state, chat = s.chat, running = activeOperation(chat), last = chat?.operations.at(-1);
  const blocked = s.busy || !!s.pending || s.recovery || !s.connected || !!running || !!s.runtime?.active_run_id || (!isDebugger() && !s.runtime?.execution_enabled) || (!!s.selected && !chat);
  const count = chat?.messages.length || 0;
  const scroll = $('#page-scroll');
  const nearBottom = !scroll || scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 140;
  const bottom = !isDebugger() && count > seenMessages && nearBottom;
  seenMessages = count;
  const error = s.error || (last?.status !== 'running' ? last?.error?.message : '');
  const debuggerMode = isDebugger();
  const content = `${settings ? `<section class="connection-panel"><div class="panel-heading"><h2>Local connection</h2><button data-action="settings-close" class="icon-button" aria-label="Close settings">${icon('close')}</button></div><form id="connection-form"><label for="api-origin">API origin</label><input id="api-origin" type="url" value="${escape(originDraft || s.origin)}" ${s.pending ? 'disabled' : ''}><button ${s.loading || s.busy ? 'disabled' : ''}>Connect</button></form><p>Hermes uses its existing server-side Codex connection.</p></section>` : ''}
    ${error ? `<div class="chat-alert" role="alert">${escape(error)}${!s.connected ? '<button data-action="settings">Connection settings</button>' : ''}</div>` : ''}
    ${s.pending ? `<section class="pending-card"><h2>${s.rejected ? 'Request rejected' : 'Request awaiting confirmation'}</h2><p>${escape(s.pending.message.content)}</p><p>${s.pending.kind === 'environment' ? 'PDF tool change' : s.pending.kind === 'debugger' ? 'Debugger investigation' : 'Chat message'} · the original request identity is saved. No automatic resend occurs.</p>${s.pending.create.environment ? `<p>Environment: ${environmentLabel(s.pending.create.environment)}</p>` : ''}<button data-action="${s.rejected ? 'review' : 'retry'}" ${s.busy || !s.connected ? 'disabled' : ''}>${s.rejected ? 'Return to draft' : 'Retry exact request'}</button></section>` : ''}
    ${!debuggerMode ? environmentView(s) : ''}
    ${debuggerMode ? investigationView(s, blocked) : chat?.messages.length ? `<div class="conversation chat-transcript" aria-label="Conversation">${chat.messages.map(m => `<article class="message ${m.role}" data-message-id="${escape(m.id)}"><span class="chat-speaker">${m.role === 'user' ? 'You' : m.agent === 'hermes' ? 'Hermes' : m.agent === 'debugger' || chat.operations.find(operation => operation.id === m.operation_id)?.kind === 'debugger' ? 'Debugger' : 'Hermes'}</span><div class="message-body">${messageBody(m.content)}</div></article>`).join('')}${running ? `<div class="chat-working" role="status">${icon('activity')}<span>${escape(running.activity)}</span></div>` : ''}</div>` : s.selected ? `<div class="empty-state"><h2>${s.loading ? 'Loading conversation…' : chat ? 'Start the conversation' : 'Conversation unavailable'}</h2><p>${chat ? 'Send a message to Hermes below.' : 'Reconnect or choose a saved conversation.'}</p></div>` : '<div class="welcome"><h1>EPOCH</h1><p>What should we work on?</p></div>'}`;
  const composer = `<div class="composer-dock"><form id="chat-form" class="composer-box">${!s.selected ? environmentPicker(environment, s.busy || !!s.pending || s.recovery) : ''}<label class="sr-only" for="chat-message">Message Hermes</label><textarea id="chat-message" data-autogrow data-submit rows="1" maxlength="16000" placeholder="Message Hermes…" ${s.busy || s.pending || s.recovery ? 'disabled' : ''}>${escape(draft)}</textarea><div class="composer-tools"><div class="composer-tools-left"><span class="chat-model">Hermes</span>${!s.selected ? `<details class="project-menu" data-key="chat-project"><summary>${icon('plus')}<span>${escape(project)}</span></summary><div class="popover"><label for="chat-project">Project</label><input id="chat-project" value="${escape(project)}" pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,99}"></div></details>` : ''}</div><div class="composer-tools-right"><span class="composer-hint">Enter to send · Shift Enter for a new line</span>${running ? `<button type="button" data-action="stop" class="chat-stop" ${s.busy ? 'disabled' : ''}>Stop</button>` : `<button class="send-button" aria-label="Send message" ${blocked ? 'disabled' : ''}>${icon('send')}</button>`}</div></div></form><p class="composer-caption">${!s.connected ? '<button class="text-button" data-action="settings">Connect to Hermes</button>' : !s.runtime?.execution_enabled ? 'Hermes is unavailable. Check the backend setup.' : s.runtime?.active_run_id && !running ? 'Hermes is busy with another chat or debugger evaluation.' : 'Your conversation with Hermes · Open Debugger when you need to investigate'}</p></div>`;
  const nav = s.list.length ? s.list.map(c => `<a data-route class="session-item" href="${debuggerMode ? debuggerURL(c.id) : chatURL(c.id)}" ${c.id === s.selected ? 'aria-current="page"' : ''}>${icon('chat')}<span><strong>${escape(c.title)}</strong><small>${escape(c.project_id)}</small></span></a>`).join('') : '<div class="sidebar-empty"><p>Your conversations appear here.</p></div>';
  const pagination = s.total > 20 ? `<div class="pagination"><button data-action="previous" ${s.offset === 0 ? 'disabled' : ''}>Newer</button><button data-action="next" ${s.offset + 20 >= s.total ? 'disabled' : ''}>Older</button></div>` : '';
  const html = shell({ page: debuggerMode ? 'debugger' : 'chat', title: chat?.title || 'New chat', nav: nav + pagination, content, composer: debuggerMode ? '' : composer, debuggerChatId: s.selected, sessionsLabel: 'CHATS',
    locked: s.busy || !!s.pending,
    status: `<span class="connection-state ${s.connected ? 'connected' : ''}"><i></i>${s.loading ? 'Connecting' : s.connected ? 'Backend connected' : 'Not connected'}</span>`,
    actions: `<button class="icon-button" data-action="settings" aria-label="Connection settings">${icon('settings')}</button>`,
    bottom: `<button class="nav-item" data-action="settings">${icon('settings')}Connection settings</button>`,
  });
  view.render(html, `${debuggerMode ? "debugger" : "chat"}:${s.selected}`, { bottom });
  $('#announcement').textContent = running ? running.activity : error || '';
}
async function routeChanged() {
  if (!['/chat', '/', '/index.html', '/debugger'].includes(location.pathname) || (isDebugger() && (new URLSearchParams(location.search).has('task') || new URLSearchParams(location.search).get('mode') === 'release'))) { location.assign(location.href); return; }
  const id = new URLSearchParams(location.search).get('chat') || '';
  if (!id && workspace.state.chat) {
    project = workspace.state.chat.project_id;
    environment = workspace.state.chat.environment || 'default';
  }
  draft = drafts.get(id) || ''; question = questions.get(id) || ''; seenMessages = 0;
  await workspace.select(id);
}
root.addEventListener('input', event => {
  if (event.target.id === 'debugger-question') { question = event.target.value; questions.set(workspace.state.selected, question); }
  if (event.target.id === 'chat-message') { draft = event.target.value; drafts.set(workspace.state.selected, draft); }
  if (event.target.id === 'chat-project') project = event.target.value;
  if (event.target.id === 'api-origin') originDraft = event.target.value;
});
root.addEventListener('submit', async event => {
  event.preventDefault();
  if (event.target.id === 'connection-form') { await workspace.connect(originDraft || workspace.state.origin); if (workspace.state.connected) settings = false; render(); }
  if (event.target.id === 'debugger-form' && await workspace.investigate(question)) { question = ''; questions.delete(workspace.state.selected); render(); }
  const draftId = workspace.state.selected;
  if (event.target.id === 'chat-form' && await workspace.send(draft, workspace.state.chat?.project_id || project, workspace.state.chat?.environment || environment)) {
    draft = ''; drafts.delete(draftId); history.replaceState(null, '', chatURL(workspace.state.selected)); render(); $('#chat-message')?.focus();
  }
});
root.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button || button.disabled) return;
  switch (button.dataset.action) {
    case 'sample-task': draft = SAMPLE_PROMPT; drafts.set('', draft); render(); $('#chat-message')?.focus(); break;
    case 'new': navigate(chatURL('')); break;
    case 'settings': settings = true; originDraft = workspace.state.origin; render(); $('#api-origin')?.focus(); break;
    case 'settings-close': settings = false; render(); break;
    case 'refresh-list': await workspace.refresh(); break;
    case 'stop': await workspace.cancel(); break;
    case 'pdf-environment-action': await workspace.environmentAction(button.dataset.kind); break;
    case 'seed-retreat':
    case 'seed-festival': {
      const pack = button.dataset.action === 'seed-retreat' ? 'retreat' : 'festival';
      if (await workspace.addFiles(project, pack)) { history.replaceState(null, '', chatURL(workspace.state.selected)); draft = pack === 'retreat' ? SAMPLE_PROMPT : FESTIVAL_PROMPT; drafts.set(workspace.state.selected, draft); render(); }
      break;
    }
    case 'preview-pdf': workspace.state.previewAsset = button.dataset.id; workspace.state.previewPage = 1; render(); break;
    case 'close-preview': workspace.state.previewAsset = null; render(); break;
    case 'previous-page': workspace.state.previewPage--; render(); break;
    case 'next-page': workspace.state.previewPage++; render(); break;
    case 'rollback-pdf': await workspace.rollback(); break;
    case 'retry': if (await workspace.retry()) { draft = ''; history.replaceState(null, '', (isDebugger() ? debuggerURL : chatURL)(workspace.state.selected)); render(); } break;
    case 'review': { const kind = workspace.state.pending?.kind; const content = workspace.review(); if (kind === 'debugger') question = content ?? question; else draft = content ?? draft; render(); break; }
    case 'previous': workspace.state.offset = Math.max(0, workspace.state.offset - 20); await workspace.refresh(); break;
    case 'next': workspace.state.offset += 20; await workspace.refresh(); break;
  }
});
root.addEventListener('change', async event => {
  if (event.target.id === 'pdf-upload' && event.target.files[0]) { if (await workspace.addFiles(project, null, event.target.files[0])) { history.replaceState(null, '', chatURL(workspace.state.selected)); render(); } }
  if (event.target.id === 'chat-environment' && !workspace.state.selected && !workspace.state.pending) { environment = event.target.value; render(); }
});
document.addEventListener('visibilitychange', () => { void workspace.setVisible(!document.hidden); });
window.addEventListener('pagehide', () => workspace.stop());
window.addEventListener('pageshow', event => { if (event.persisted) void workspace.refresh(); });
render();
workspace.visible = !document.hidden;
void workspace.connect(); // Read-only connection and recovery; never resubmit on load.
