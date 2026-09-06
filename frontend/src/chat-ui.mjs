import { activityView } from './chat-activity.mjs';
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
  const chat = s.chat, pdf = chat?.environment === 'pdf_workshop';
  if (!chat) return `<div class="debugger conversation-debugger"><h1>Debugger</h1><p>Select a conversation to review its results.</p></div>`;
  const operations = chat.operations || [];
  const analyses = operations.filter(o => o.kind === 'debugger');
  const requests = chat.messages.filter(m => m.role === 'user' && m.agent !== 'debugger' && operations.find(o => o.id === m.operation_id)?.kind !== 'debugger');
  return `<div class="debugger conversation-debugger"><header class="debug-heading"><h1>Debugger</h1><a data-route class="text-button" href="${chatURL(chat.id)}">Back to conversation ${icon('arrow')}</a></header>
    ${pdf ? repairView(s, blocked) : `${activityView(s, true)}<section class="debugger-action"><form id="debugger-form"><label for="debugger-question">Anything to focus on? <span class="muted">Optional</span></label><textarea id="debugger-question" rows="2" maxlength="12000" ${blocked ? 'disabled' : ''}>${escape(question)}</textarea><button id="investigate-chat" class="primary-action" ${blocked || !chat.messages.length || !s.runtime?.debugger?.available ? 'disabled' : ''}>Investigate conversation</button></form></section>`}
    ${environmentView(s, { showTools: true })}
    <details class="disclosure" data-key="debugger-requirements"><summary>Task context</summary>${requests.map(m => `<blockquote class="chat-prose">${escape(m.content)}</blockquote>`).join('')}</details>
    ${analyses.length ? `<details class="disclosure" data-key="debugger-history"><summary>Activity and evidence <span>${analyses.length}</span></summary>${analyses.map(op => `<article class="investigation-result"><h2>${['repair', 'repair_tool'].includes(op.action) ? 'Repair' : op.action === 'create_tool' ? 'Tool creation' : 'Investigation'} · ${escape(op.status)}</h2>${op.question ? `<p>${escape(op.question)}</p>` : ''}<div class="chat-prose">${escape(op.error?.message || op.analysis?.answer || op.activity || '')}</div>${op.analysis ? `<details class="disclosure" data-key="analysis-${escape(op.id)}"><summary>Full evidence</summary><pre>${escape(JSON.stringify(op.analysis,null,2))}</pre></details>` : ''}</article>`).join('')}</details>` : ''}
    <details class="disclosure debugger-other" data-key="other-workflows"><summary>Other workflows</summary><a href="/incidents">Incidents</a> · <a href="/debugger?mode=release">Release debugger</a> · <a href="/demo/chat">Release example</a></details></div>`;
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
    ${debuggerMode ? investigationView(s, blocked) : chat?.messages.length ? `<div class="conversation chat-transcript" aria-label="Conversation">${chat.messages.map(m => `<article class="message ${m.role}" data-message-id="${escape(m.id)}"><span class="chat-speaker">${m.role === 'user' ? 'You' : m.agent === 'hermes' ? 'Hermes' : m.agent === 'debugger' || chat.operations.find(operation => operation.id === m.operation_id)?.kind === 'debugger' ? 'Debugger' : 'Hermes'}</span><div class="message-body">${messageBody(m.content)}</div></article>`).join('')}${activityView(s)}</div>` : s.selected ? `<div class="empty-state"><h2>${s.loading ? 'Loading conversation…' : chat ? 'Start the conversation' : 'Conversation unavailable'}</h2><p>${chat ? (s.environment?.assets?.length ? 'Your files are ready. Send a message to begin.' : 'Send a message to begin.') : 'Reconnect or choose a saved conversation.'}</p></div>` : `<div class="welcome chat-welcome"><h1>EPOCH</h1><p>Give Hermes a task. Follow the work here.</p><button type="button" class="example-button" data-action="seed-retreat" ${!s.connected || s.busy || s.pending || s.recovery ? 'disabled' : ''}>${icon('plus')} Try Northstar example</button></div>`}`;
  const files = !debuggerMode ? environmentView(s, { showResult: false }) : '';
  const composer = `<div class="composer-dock"><form id="chat-form" class="composer-box"><label class="sr-only" for="chat-message">Message Hermes</label><textarea id="chat-message" data-autogrow data-submit rows="1" maxlength="16000" placeholder="Message Hermes…" ${s.busy || s.pending || s.recovery ? 'disabled' : ''}>${escape(draft)}</textarea><div class="composer-tools"><div class="composer-tools-left"><span class="chat-model">Hermes</span><details class="composer-options" data-key="composer-options"><summary aria-label="Chat options">${icon('plus')}</summary><div class="popover">${!s.selected ? `${environmentPicker(environment, s.busy || !!s.pending || s.recovery)}<label class="compact-field" for="chat-project">Project<input id="chat-project" value="${escape(project)}" pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,99}"></label>` : ''}${(chat?.environment || environment) === 'pdf_workshop' ? `<button type="button" data-action="seed-retreat" ${s.busy || s.pending || s.recovery || running ? 'disabled' : ''}>Northstar example</button><button type="button" data-action="seed-festival" ${s.busy || s.pending || s.recovery || running ? 'disabled' : ''}>Festival example</button>${!s.selected ? `<label class="pdf-upload">Upload PDF<input id="pdf-upload" type="file" accept="application/pdf,.pdf" ${s.busy || s.pending || s.recovery ? 'disabled' : ''}></label>` : ''}` : ''}</div></details></div><div class="composer-tools-right"><span class="composer-hint">Enter to send</span>${running ? `<button type="button" data-action="stop" class="chat-stop" ${s.busy ? 'disabled' : ''}>Stop</button>` : `<button class="send-button" aria-label="Send message" ${blocked ? 'disabled' : ''}>${icon('send')}</button>`}</div></div></form><p class="composer-caption">${!s.connected ? '<button class="text-button" data-action="settings">Connect to Hermes</button>' : !s.runtime?.execution_enabled ? 'Hermes is unavailable. Check the backend setup.' : s.runtime?.active_run_id && !running ? 'Hermes is busy with another chat or debugger evaluation.' : ''}</p></div>`;
  const nav = s.list.length ? s.list.map(c => `<a data-route class="session-item" href="${debuggerMode ? debuggerURL(c.id) : chatURL(c.id)}" ${c.id === s.selected ? 'aria-current="page"' : ''}>${icon('chat')}<span><strong>${escape(c.title)}</strong><small>${escape(c.environment === 'pdf_workshop' ? 'Documents' : 'Chat')}</small></span></a>`).join('') : '<div class="sidebar-empty"><p>Your conversations appear here.</p></div>';
  const pagination = s.total > 20 ? `<div class="pagination"><button data-action="previous" ${s.offset === 0 ? 'disabled' : ''}>Newer</button><button data-action="next" ${s.offset + 20 >= s.total ? 'disabled' : ''}>Older</button></div>` : '';
  const html = shell({ page: debuggerMode ? 'debugger' : 'chat', title: chat?.title || 'New chat', nav: nav + pagination, content: content + files, composer: debuggerMode ? '' : composer, debuggerChatId: s.selected, sessionsLabel: 'CHATS',
    locked: s.busy || !!s.pending,
    status: `<span class="connection-state ${s.connected ? 'connected' : ''}"><i></i>${s.loading ? 'Connecting' : s.connected ? 'Backend connected' : 'Not connected'}</span>`,
    actions: `<button class="icon-button" data-action="settings" aria-label="Connection settings">${icon('settings')}</button>`,
    bottom: `<button class="nav-item" data-action="settings">${icon('settings')}Connection settings</button>`,
  });
  view.render(html, `${debuggerMode ? "debugger" : "chat"}:${s.selected}`);
  if (bottom) {
    const target = $('.chat-transcript .chat-working') || $('.chat-transcript .message:last-of-type');
    target?.scrollIntoView({ block: 'end' });
  }
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
      if (!workspace.state.selected) environment = 'pdf_workshop';
      if (await workspace.addFiles(project, pack)) { history.replaceState(null, '', chatURL(workspace.state.selected)); draft = pack === 'retreat' ? SAMPLE_PROMPT : FESTIVAL_PROMPT; drafts.set(workspace.state.selected, draft); render(); $('#chat-message')?.focus(); }
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
