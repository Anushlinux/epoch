import { IntakeAPI, IntakeError, apiOrigin, ORIGIN_KEY } from './intake-api.mjs';
import { ChatStream } from './chat-stream.mjs';
export const CHAT_PENDING_KEY = 'epoch.chat.pending.v1';
export const CHAT_ENVIRONMENTS = ['default', 'pdf_workshop'];
const uuid = value => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
export const activeOperation = chat => chat?.operations.find(operation => operation.status === 'running');
function ensure(value) { if (!value) throw new IntakeError('The chat response could not be verified.', 0, 'contract'); }
function conversation(value) {
  ensure(uuid(value?.id) && Array.isArray(value.messages) && Array.isArray(value.operations));
  ensure(value.environment == null || CHAT_ENVIRONMENTS.includes(value.environment));
  ensure(value.messages.every(m => uuid(m.id) && ['user', 'assistant'].includes(m.role) && typeof m.content === 'string'));
  ensure(value.operations.every(o => uuid(o.id) && o.chat_id === value.id && ['running', 'completed', 'failed', 'cancelled', 'interrupted'].includes(o.status)));
  return value;
}
export class ChatWorkspace {
  constructor({ storage, onChange = () => {}, onStreamChange = onChange,
    apiFactory = origin => new IntakeAPI(origin), pollMs = 1500, streamFactory } = {}) {
    Object.assign(this, { storage, onChange, onStreamChange, apiFactory, pollMs, streamFactory });
    this.generation = 0;
    this.visible = true;
    this.readFailures = 0;
    this.auxiliary = new Map();
    this.environmentUpdated = 0;
    this.state = { origin: 'http://127.0.0.1:8000', connected: false, busy: false, loading: false, chat: null, selected: '', list: [], total: 0, offset: 0, pending: null, rejected: false, recovery: false, error: '', runtime: null, environment: null, environmentError: '' };
    Object.assign(this.state, { stream: null, streamError: '', runtimeError: '', listError: '', environmentLoading: false });
    try {
      this.state.origin = apiOrigin(storage.getItem(ORIGIN_KEY) || this.state.origin);
      const raw = storage.getItem(CHAT_PENDING_KEY);
      if (raw) {
        const p = JSON.parse(raw);
        ensure([1, 2].includes(p.version) && uuid(p.create?.client_request_id) && uuid(p.message?.client_request_id) && typeof p.message.content === 'string' && typeof p.create.project_id === 'string' && (!p.chatId || uuid(p.chatId)));
        ensure(p.kind == null || ['chat', 'debugger', 'repair', 'environment'].includes(p.kind));
        ensure(!['debugger', 'repair', 'environment'].includes(p.kind) || uuid(p.chatId));
        if (p.create.environment?.startsWith('csv_') || p.kind === 'repair') {
          storage.setItem(CHAT_PENDING_KEY + '.retired', raw);
          storage.removeItem(CHAT_PENDING_KEY);
          this.state.error = 'A pending CSV request was retired and was not replayed.';
          return;
        }
        ensure(p.create.environment == null || CHAT_ENVIRONMENTS.includes(p.create.environment));
        if (p.kind === 'environment') ensure(p.endpoint === `/api/chats/${p.chatId}/environment-actions` && p.payload?.client_request_id === p.message.client_request_id && ['repair_tool', 'create_tool'].includes(p.payload.action));
        p.origin = apiOrigin(p.origin);
        this.state.pending = p;
        this.state.origin = p.origin;
      }
    } catch { this.state.recovery = true; this.state.error = 'Browser recovery storage is unavailable or unreadable. New messages are blocked; saved conversations remain readable.'; }
  }
  emit() { this.onChange(this.state); }
  stop() {
    clearTimeout(this.timer); clearTimeout(this.streamTimer); this.timer = null;
    this.streamTimer = null;
    this.streamReader?.close(); this.streamReader = null; this.streamFinished = '';
    this.generation++;
  }
  async setVisible(visible) {
    if (visible === this.visible) return;
    this.visible = visible;
    this.stop();
    if (visible) await this.refresh();
  }
  async connect(origin = this.state.origin) {
    if (this.state.busy) return;
    try {
      origin = apiOrigin(origin);
      if (this.state.pending && origin !== this.state.pending.origin) throw new Error('Resolve the pending message on its original server first.');
      this.stop();
      if (origin !== this.state.origin) Object.assign(this.state, { chat: null, list: [], runtime: null, environment: null, environmentError: '', stream: null, streamError: '', runtimeError: '', listError: '' });
      Object.assign(this.state, { origin, connected: false, loading: true });
      this.api = this.apiFactory(origin);
      this.emit();
      await this.api.health();
      this.state.connected = true;
      try { this.storage.setItem(ORIGIN_KEY, origin); } catch { /* Writes require their own journal. */ }
      await this.refresh();
    } catch (error) { this.state.error = error.message; this.state.connected = false; }
    finally { this.state.loading = false; this.emit(); }
  }
  async select(id = '') {
    this.stop();
    this.state.selected = id;
    this.state.chat = null;
    this.state.environment = null;
    this.state.environmentError = '';
    this.state.stream = null;
    this.state.streamError = '';
    this.environmentUpdated = 0;
    if (id && !uuid(id)) { this.state.error = 'Invalid conversation ID.'; this.emit(); return; }
    this.emit();
    if (this.state.connected) await this.refresh();
  }
  async refresh({ poll = false } = {}) {
    if (!this.visible || !this.state.connected || !this.api) return;
    const current = this.reading;
    if (current?.generation === this.generation) {
      await current.promise;
      if (poll) return;
      // A user action needs a fresh read after the earlier read completes.
      return this.refresh();
    }
    const generation = this.generation;
    const promise = this.read({ poll });
    this.reading = { generation, promise };
    try { await promise; }
    finally { if (this.reading?.promise === promise) this.reading = null; }
  }
  async read({ poll }) {
    clearTimeout(this.timer);
    this.timer = null;
    const generation = this.generation, id = this.state.selected, api = this.api;
    const full = !poll || !activeOperation(this.state.chat);
    const wasRunning = !!activeOperation(this.state.chat);
    if (full) this.refreshWorkspaceInfo();
    try {
      const detail = id ? await api.call(`/api/chats/${id}`) : null;
      if (generation !== this.generation || id !== this.state.selected || api !== this.api) return;
      const chat = detail ? conversation(detail.body) : null;
      if (chat) ensure(chat.id === id);
      this.state.chat = chat;
      this.readFailures = 0;
      if (!this.state.recovery) this.state.error = '';
      this.reconcileStream();
      this.emit(); // The answer is usable before any runtime, file or preview refresh.
      this.watchStream();
      if (wasRunning && !activeOperation(chat)) this.refreshWorkspaceInfo();
      if (chat?.environment === 'pdf_workshop') this.refreshEnvironment(full || (wasRunning && !activeOperation(chat)));
      else { this.state.environment = null; this.state.environmentError = ''; this.state.environmentLoading = false; }
    } catch (error) {
      if (generation === this.generation && id === this.state.selected) { this.state.error = error.message; this.readFailures++; }
    } finally {
      if (generation === this.generation && id === this.state.selected) {
        this.emit();
        this.scheduleRead();
      }
    }
  }
  scheduleRead() {
    clearTimeout(this.timer); this.timer = null;
    if (!this.visible || !this.state.connected || !(activeOperation(this.state.chat) || this.state.runtime?.active_run_id)) return;
    const interval = activeOperation(this.state.chat) ? this.pollMs : Math.max(5000, this.pollMs);
    const delay = this.readFailures ? Math.min(30000, Math.max(5000, interval) * 2 ** Math.min(this.readFailures - 1, 3)) : interval;
    this.timer = setTimeout(() => { void this.refresh({ poll: true }); }, delay);
  }
  refreshAuxiliary(name, path, accept, assign, repeat = false) {
    const generation = this.generation, id = this.state.selected, api = this.api;
    const valid = () => generation === this.generation && id === this.state.selected && api === this.api;
    const current = this.auxiliary.get(name);
    if (current?.generation === generation && current.id === id) {
      if (repeat) current.again = () => this.refreshAuxiliary(name, path, accept, assign);
      return;
    }
    const job = { generation, id };
    this.auxiliary.set(name, job);
    if (name === 'environment') this.state.environmentLoading = true;
    void (async () => {
      try {
        const { body } = await api.call(path);
        if (!valid()) return;
        accept(body); assign(body); this.state[`${name}Error`] = '';
      } catch (error) {
        if (valid()) this.state[`${name}Error`] = `${name === 'environment' ? 'Files and tool information' : name === 'runtime' ? 'Runtime information' : 'Conversation list'} could not be refreshed. ${error.message}`;
      } finally {
        if (this.auxiliary.get(name) === job) this.auxiliary.delete(name);
        if (valid()) {
          if (name === 'environment') this.state.environmentLoading = false;
          this.emit();
          if (name === 'runtime') this.scheduleRead();
          job.again?.();
        }
      }
    })();
  }
  refreshWorkspaceInfo() {
    if (!this.api || !this.visible || !this.state.connected) return;
    this.refreshAuxiliary('list', `/api/chats?limit=20&offset=${this.state.offset}`,
      body => ensure(Array.isArray(body.items) && body.items.every(c => uuid(c.id) && typeof c.title === 'string')),
      body => Object.assign(this.state, { list: body.items, total: body.total }), true);
    this.refreshAuxiliary('runtime', '/api/runtime', body => ensure(typeof body.execution_enabled === 'boolean'),
      body => { this.state.runtime = body; }, true);
  }
  refreshEnvironment(force = false) {
    if (this.state.chat?.environment !== 'pdf_workshop' || (!force && Date.now() - this.environmentUpdated < 5000)) return;
    this.environmentUpdated = Date.now(); this.state.environmentLoading = true;
    this.refreshAuxiliary('environment', `/api/chats/${this.state.selected}/environment`,
      body => ensure(body.environment === 'pdf_workshop' && body.local === true && Array.isArray(body.assets) && Array.isArray(body.tools) && Array.isArray(body.actions)),
      body => { this.state.environment = body; }, force);
  }
  reconcileStream() {
    const stream = this.state.stream, chat = this.state.chat;
    if (!stream || !chat) return;
    const operation = chat.operations.find(op => op.id === stream.operation_id);
    if (!operation || chat.messages.some(m => m.operation_id === stream.operation_id && m.role === 'assistant')) {
      this.state.stream = null; this.state.streamError = '';
    } else if (operation.status !== 'running') {
      Object.assign(stream, { status: operation.status, activity: operation.activity });
    }
  }
  watchStream() {
    const operation = activeOperation(this.state.chat);
    if (!operation || operation.kind === 'debugger' || !this.visible) {
      this.streamReader?.close(); this.streamReader = null; return;
    }
    if (this.streamReader?.operation === operation.id || this.streamFinished === operation.id) return;
    if (!this.streamFactory && typeof EventSource === 'undefined') return; // Polling remains available.
    this.streamReader?.close();
    const generation = this.generation, id = this.state.selected;
    const valid = () => generation === this.generation && id === this.state.selected;
    try {
      this.streamReader = new ChatStream({ origin: this.state.origin, chat: id, operation: operation.id,
        ...(this.streamFactory ? { factory: this.streamFactory } : {}),
        onUpdate: state => {
          if (!valid()) return;
          this.state.stream = state; this.state.streamError = '';
          if (!this.streamTimer) this.streamTimer = setTimeout(() => {
            this.streamTimer = null;
            if (valid()) this.onStreamChange(this.state);
          }, 40);
        },
        onIssue: message => { if (valid()) { this.state.streamError = message; this.onStreamChange(this.state); } },
        onFinish: state => {
          if (!valid()) return;
          this.streamFinished = operation.id;
          if (state?.saved === false) this.state.streamError = 'The final response could not be saved. Inspect storage and restart before more work.';
          if (state?.warning) this.state.streamError = state.warning;
          this.onStreamChange(this.state);
          void this.refresh();
        },
      });
    } catch (error) { this.state.streamError = `Live preview unavailable. ${error.message}`; }
  }
  async send(content, project = 'demo', environment = 'default') {
    const s = this.state;
    if (s.busy || s.pending || s.recovery || !s.connected || activeOperation(s.chat)) return false;
    try {
      content = content.trim();
      if (!content || [...content].length > 16000) throw new Error('Enter a message of 1–16,000 characters.');
      if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(project)) throw new Error('Use a project label with letters, numbers, underscores or hyphens.');
      ensure(CHAT_ENVIRONMENTS.includes(environment));
      const pending = { version: 2, origin: s.origin, chatId: s.selected || null, create: { client_request_id: crypto.randomUUID(), project_id: project, ...(environment !== 'default' ? { environment } : {}) }, message: { client_request_id: crypto.randomUUID(), content,
        ...(s.contextPreview ? { context_preview_id: s.contextPreview } : {}) } };
      this.storage.setItem(CHAT_PENDING_KEY, JSON.stringify(pending));
      s.pending = pending;
    } catch (error) { s.error = error.message; this.emit(); return false; }
    return this.retry();
  }
  async environmentAction(kind) {
    const s = this.state;
    const action = s.environment?.actions.find(a => a.action === kind && a.eligible);
    if (!action || s.busy || s.pending || s.recovery || activeOperation(s.chat)) return false;
    const id = crypto.randomUUID();
    const pending = {version: 2, kind: 'environment', origin: s.origin, chatId: s.chat.id, create: {client_request_id: crypto.randomUUID(), project_id: s.chat.project_id}, message: {client_request_id: id, content: ''}, endpoint: `/api/chats/${s.chat.id}/environment-actions`, payload: {client_request_id: id, action: kind, evidence_id: action.evidence_id, expected_version: action.expected_version}};
    try { this.storage.setItem(CHAT_PENDING_KEY, JSON.stringify(pending)); s.pending = pending; }
    catch (error) { s.error = error.message; this.emit(); return false; }
    return this.retry();
  }
  async ensurePdfChat(project) {
    if (this.state.selected) return this.state.selected;
    const key = `epoch.pdf.draft-create.v2.${this.state.origin}.${project}`;
    let payload = JSON.parse(this.storage.getItem(key) || 'null');
    if (!payload) { payload = {client_request_id: crypto.randomUUID(), project_id: project, environment: 'pdf_workshop'}; this.storage.setItem(key, JSON.stringify(payload)); }
    const {body} = await this.api.call('/api/chats', payload);
    const chat = conversation(body);
    ensure(chat.client_request_id === payload.client_request_id);
    this.state.selected = chat.id; this.state.chat = chat;
    this.storage.removeItem(key);
    return chat.id;
  }
  async addFiles(project, pack, file) {
    const s = this.state;
    if (!s.connected || s.busy || s.pending || s.recovery || activeOperation(s.chat)) return false;
    s.busy = true; s.error = ''; this.emit();
    try {
      const id = await this.ensurePdfChat(project);
      let body;
      if (pack) {
        const api = new IntakeAPI(s.origin, undefined, 120000);
        body = (await api.call(`/api/chats/${id}/assets/bundled`, {pack})).body;
      } else {
        if (!file || file.size > 10 * 1024 * 1024) throw new Error('Choose a PDF of at most 10 MB.');
        const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))].map(b => b.toString(16).padStart(2, '0')).join('');
        const key = `epoch.pdf.upload.${id}.${digest}.${file.name}`;
        let requestId = this.storage.getItem(key);
        if (!requestId) { requestId = crypto.randomUUID(); this.storage.setItem(key, requestId); }
        const response = await fetch(`${s.origin}/api/chats/${id}/assets?name=${encodeURIComponent(file.name)}&client_request_id=${requestId}`, {method:'POST', body:file, headers:{'Content-Type':'application/pdf'}, redirect:'error', credentials:'omit', signal:AbortSignal.timeout(120000)});
        body = await response.json();
        if (!response.ok) throw new Error(body.error?.message || 'Upload failed. Select the same file to retry safely.');
      }
      if (!body.ok) throw new Error(body.error?.message || 'Files could not be added.');
      return true;
    } catch (error) { s.error = error.message; return false; }
    finally { const error = s.error; s.busy = false; this.emit(); await this.refresh(); if (error) { s.error = error; this.emit(); } }
  }
  async rollback() {
    const s = this.state;
    if (s.busy || s.pending || activeOperation(s.chat) || !s.environment) return;
    s.busy = true; this.emit();
    try {
      const key = `epoch.pdf.rollback.${s.chat.id}.${s.environment.active_version}`;
      let id = this.storage.getItem(key);
      if (!id) { id = crypto.randomUUID(); this.storage.setItem(key, id); }
      await this.api.call(`/api/chats/${s.chat.id}/environment/rollback`, {client_request_id:id, expected_version:s.environment.active_version});
    } catch (error) { s.error = error.message; }
    finally { s.busy = false; this.emit(); await this.refresh(); }
  }
  async investigate(question = '', kind = 'debugger') {
    const s = this.state;
    if (s.busy || s.pending || s.recovery || !s.connected || !s.chat || activeOperation(s.chat)) return false;
    try {
      question = question.trim();
      if ([...question].length > 12000) throw new Error('Keep your question within 12,000 characters.');
      const pending = { version: 2, kind, origin: s.origin, chatId: s.chat.id, create: { client_request_id: crypto.randomUUID(), project_id: s.chat.project_id }, message: { client_request_id: crypto.randomUUID(), content: question } };
      this.storage.setItem(CHAT_PENDING_KEY, JSON.stringify(pending));
      s.pending = pending;
    } catch (error) { s.error = error.message; this.emit(); return false; }
    return this.retry();
  }
  async retry() {
    const s = this.state, p = s.pending;
    if (!p || s.busy || !s.connected || s.recovery || s.rejected || p.origin !== s.origin) return false;
    s.busy = true; s.error = ''; this.emit();
    try {
      if (!p.chatId) {
        const { body } = await this.api.call('/api/chats', p.create);
        const chat = conversation(body);
        ensure(chat.client_request_id === p.create.client_request_id && chat.project_id === p.create.project_id && (chat.environment || 'default') === (p.create.environment || 'default'));
        p.chatId = chat.id;
        this.storage.setItem(CHAT_PENDING_KEY, JSON.stringify(p));
      }
      if (!p.endpoint) {
        p.endpoint = `/api/chats/${p.chatId}/${p.kind === 'debugger' ? 'debugger' : 'messages'}`;
        p.payload = p.kind === 'debugger' ? {client_request_id:p.message.client_request_id, ...(p.message.content ? {question:p.message.content} : {})} : p.message;
        this.storage.setItem(CHAT_PENDING_KEY, JSON.stringify(p));
      }
      const {body} = await this.api.call(p.endpoint, p.payload);
      ensure(uuid(body.id) && body.chat_id === p.chatId && body.client_request_id === p.message.client_request_id);
      this.storage.removeItem(CHAT_PENDING_KEY);
      this.stop();
      s.pending = null;
      s.contextPreview = null;
      s.selected = p.chatId;
      s.stream = null; s.streamError = '';
      return true;
    } catch (error) {
      s.rejected = [403, 404, 409, 410, 422].includes(error.status);
      s.error = `${error.message} ${s.rejected ? 'The message was rejected; review it before sending again.' : 'Acknowledgement is uncertain. Use Retry exact message to confirm this submission.'}`;
      return false;
    } finally { s.busy = false; this.emit(); if (!s.pending) await this.refresh(); }
  }
  review() {
    if (!this.state.rejected || this.state.busy) return null;
    const draft = this.state.pending.message.content;
    try { this.storage.removeItem(CHAT_PENDING_KEY); }
    catch { this.state.error = 'Restore browser storage before editing this submission.'; this.emit(); return null; }
    this.state.pending = null; this.state.rejected = false; this.state.error = ''; this.emit(); return draft;
  }
  async cancel() {
    const operation = activeOperation(this.state.chat);
    if (!operation || this.state.busy) return;
    this.state.busy = true; this.emit();
    try { await this.api.call(`/api/chats/${operation.chat_id}/operations/${operation.id}/cancel`, {}); }
    catch (error) { this.state.error = error.message; }
    finally { this.state.busy = false; this.emit(); await this.refresh(); }
  }
}
