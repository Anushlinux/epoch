// Phase 1 only: these routes and fields come from backend/docs/FRONTEND_HANDOFF.md.
export const PENDING_KEY = 'epoch.intake.pending.v1';
export const ORIGIN_KEY = 'epoch.intake.origin.v1';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const object = (x) => x && typeof x === 'object' && !Array.isArray(x);
const keys = (x, names) => object(x) && Object.keys(x).every((key) => names.includes(key));
const text = (x, max) => typeof x === 'string' && x.trim().length > 0 && [...x].length <= max;
const timestamp = (x) => typeof x === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(x) && Number.isFinite(Date.parse(x));
export class IntakeError extends Error {
  constructor(message, status = 0, code = 'unavailable') {
    super(message); this.status = status; this.code = code;
  }
}
export function apiOrigin(value) {
  const url = new URL(value);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) || url.username || url.password || url.search || url.hash || url.pathname !== '/')
    throw new IntakeError('Use an exact local HTTP origin, such as http://127.0.0.1:8000.');
  return url.origin;
}
export function validRequest(x) {
  return keys(x, ['client_request_id', 'message', 'project_id']) && uuid.test(x.client_request_id) && text(x.message, 16000) && text(x.project_id, 100);
}
export function requestPayload(message, project, id = crypto.randomUUID()) {
  const payload = { client_request_id: id, message, project_id: project };
  if (!validRequest(payload)) throw new IntakeError('Enter a request of 1–16,000 characters and a project label of 1–100 characters.');
  return Object.freeze(payload);
}
export function sameRequest(a, b) {
  return validRequest(a) && validRequest(b) && a.client_request_id === b.client_request_id && a.message.trim() === b.message.trim() && a.project_id.trim() === b.project_id.trim();
}
export function taskRecord(x) {
  if (!keys(x, ['schema_version', 'id', 'request', 'status', 'created_at', 'updated_at']) || x.schema_version !== 1 || !uuid.test(x.id) || !validRequest(x.request) || x.status !== 'pending' || !timestamp(x.created_at) || !timestamp(x.updated_at))
    throw new IntakeError('This response does not match the supported Phase 1 pending-task contract.', 0, 'contract');
  return structuredClone(x);
}
export class IntakeAPI {
  constructor(origin, fetcher = globalThis.fetch.bind(globalThis), timeout = 10000) {
    this.origin = apiOrigin(origin); this.fetcher = fetcher; this.timeout = timeout;
  }
  async call(path, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    try {
      const response = await this.fetcher(this.origin + path, {
        method: payload ? 'POST' : 'GET', credentials: 'omit', cache: 'no-store', redirect: 'error',
        headers: payload ? { 'Content-Type': 'application/json' } : {},
        ...(payload ? { body: JSON.stringify(payload) } : {}), signal: controller.signal,
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new IntakeError(
        typeof body?.error?.message === 'string' ? body.error.message : `The server returned HTTP ${response.status}.`,
        response.status, body?.error?.code || 'http_error');
      if (!body) throw new IntakeError('The server returned an unreadable response.', 0, 'contract');
      return { body, status: response.status };
    } catch (error) {
      if (error instanceof IntakeError) throw error;
      throw new IntakeError('The local API could not be reached. Check the server and its allowed browser origin, then reconnect.');
    } finally { clearTimeout(timer); }
  }
  async health() {
    const { body, status } = await this.call('/api/health');
    if (status !== 200 || !keys(body, ['status', 'phase', 'storage', 'execution_enabled']) || body.status !== 'ok' || body.phase !== 1 || body.storage !== 'ok' || body.execution_enabled !== false)
      throw new IntakeError('Unsupported server capabilities. This view requires Phase 1 with execution disabled.', 0, 'contract');
    return body;
  }
  async list(offset = 0) {
    const { body, status } = await this.call(`/api/tasks?limit=20&offset=${offset}`);
    if (status !== 200 || !keys(body, ['items', 'total', 'limit', 'offset']) || !Array.isArray(body.items) || !Number.isInteger(body.total) || body.total < 0 || body.limit !== 20 || body.offset !== offset || body.items.length > 20)
      throw new IntakeError('The task list does not match the published contract.', 0, 'contract');
    return { ...body, items: body.items.map(taskRecord) };
  }
  async detail(id) {
    if (!uuid.test(id)) throw new IntakeError('The task ID is not a valid UUID.');
    const { body, status } = await this.call(`/api/tasks/${id}`);
    const task = taskRecord(body);
    if (status !== 200 || task.id !== id) throw new IntakeError('The response belongs to another task.', 0, 'contract');
    return task;
  }
  async create(payload) {
    const { body, status } = await this.call('/api/tasks', payload);
    const task = taskRecord(body);
    if (![200, 201].includes(status) || !sameRequest(task.request, payload))
      throw new IntakeError('The acknowledgement does not match the submitted request. Keep its ID for recovery.', 0, 'contract');
    return { task, status };
  }
}

export class IntakeWorkspace {
  constructor({ storage, apiFactory = (origin) => new IntakeAPI(origin), onChange = () => {} }) {
    this.storage = storage; this.apiFactory = apiFactory; this.onChange = onChange; this.generation = 0;
    this.state = { origin: 'http://127.0.0.1:8000', connected: false, busy: false, pending: null, recovery: false, submission: 'idle', error: '', notice: '', list: null, task: null, taskUnavailable: false, offset: 0 };
    try {
      const saved = storage.getItem(ORIGIN_KEY);
      if (saved) this.state.origin = apiOrigin(saved);
      const raw = storage.getItem(PENDING_KEY);
      if (raw !== null) {
        const item = JSON.parse(raw);
        if (!keys(item, ['version', 'origin', 'payload']) || item.version !== 1 || !validRequest(item.payload)) throw new Error('Invalid identity');
        this.state.origin = apiOrigin(item.origin);
        this.state.pending = Object.freeze({ ...item, payload: Object.freeze(item.payload) });
        this.state.submission = 'unknown';
        this.state.notice = 'A previous submission has no confirmed acknowledgement. Reconnect, then retry the exact saved request to reconcile it.';
      }
    } catch {
      this.state.recovery = true;
      this.state.error = 'Submission recovery is uncertain: browser storage is unavailable or the saved identity is unreadable. New submissions are blocked. Inspect saved tasks; do not silently resubmit the previous request.';
    }
  }
  emit() { this.onChange(this.state); }
  async connect(origin = this.state.origin) {
    if (this.state.busy) return;
    try {
      origin = apiOrigin(origin);
      if (this.state.pending && origin !== this.state.pending.origin) throw new IntakeError('Resolve the pending submission on its original API before switching servers.');
    } catch (error) { this.state.error = error.message; this.emit(); return; }
    const changed = origin !== this.state.origin;
    const generation = ++this.generation;
    Object.assign(this.state, { origin, busy: true, connected: false, error: '' });
    if (changed) Object.assign(this.state, { task: null, taskUnavailable: false, list: null, offset: 0, notice: '', submission: 'idle' });
    this.api = this.apiFactory(origin); this.emit();
    try {
      await this.api.health();
      const list = await this.api.list(this.state.offset);
      let task = this.state.task;
      let taskUnavailable = false;
      if (task) {
        try { task = await this.api.detail(task.id); }
        catch (error) {
          if (error.status !== 404) throw error;
          taskUnavailable = true;
          this.state.error = `${error.message} HTTP 404. The last loaded detail is retained as unavailable.`;
        }
      }
      if (generation !== this.generation) return;
      Object.assign(this.state, { connected: true, list, task, taskUnavailable });
      try { this.storage.setItem(ORIGIN_KEY, origin); } catch { /* POST still requires durable pending storage. */ }
    } catch (error) { if (generation === this.generation) this.state.error = error.message; }
    finally { if (generation === this.generation) { this.state.busy = false; this.emit(); } }
  }
  async read(id = null, offset = this.state.offset) {
    if (!this.state.connected) return;
    const generation = ++this.generation;
    this.state.busy = true; this.state.error = ''; this.emit();
    try {
      const result = id ? await this.api.detail(id) : await this.api.list(offset);
      if (generation !== this.generation) return;
      if (id) Object.assign(this.state, { task: result, taskUnavailable: false });
      else Object.assign(this.state, { list: result, offset });
    } catch (error) {
      if (generation !== this.generation) return;
      this.state.error = error.message;
      if (error.status === 404 && this.state.task?.id === id) this.state.taskUnavailable = true;
      if (!error.status || error.status >= 500) this.state.connected = false;
    } finally { if (generation === this.generation) { this.state.busy = false; this.emit(); } }
  }
  async submit(message, project) {
    if (this.state.busy || this.state.pending || this.state.recovery || !this.state.connected) return;
    try {
      const payload = requestPayload(message, project);
      const pending = Object.freeze({ version: 1, origin: this.state.origin, payload });
      this.storage.setItem(PENDING_KEY, JSON.stringify(pending));
      this.state.pending = pending;
    } catch (error) {
      this.state.error = error instanceof IntakeError ? error.message : 'Cannot retain the submitted identity in browser storage. Nothing was sent; keep your draft and restore storage first.';
      this.emit(); return;
    }
    await this.retry();
  }
  async retry() {
    if (this.state.busy || !this.state.pending || this.state.recovery || !this.state.connected || this.state.submission === 'rejected') return;
    const pending = this.state.pending;
    this.state.busy = true; this.state.submission = 'sending'; this.state.error = ''; this.state.notice = ''; this.emit();
    try {
      const { task, status } = await this.api.create(pending.payload);
      this.state.task = task; this.state.taskUnavailable = false;
      // If cleanup fails, retaining this identity permits only another identical retry.
      this.storage.removeItem(PENDING_KEY);
      this.state.pending = null; this.state.submission = 'saved';
      this.state.notice = status === 201 ? 'Request saved. It is pending; execution has not started.' : 'Existing request confirmed by an identical retry. No new task was created.';
      try { this.state.list = await this.api.list(0); this.state.offset = 0; }
      catch (error) { this.state.error = `Request saved, but the list could not refresh. ${error.message}`; this.state.connected = false; }
    } catch (error) {
      const rejected = [403, 409, 422].includes(error.status);
      this.state.submission = rejected ? 'rejected' : 'unknown';
      this.state.error = rejected
        ? `${error.message} HTTP ${error.status}. The submitted content was not accepted. Review saved tasks before starting a different request.`
        : `${error.message} Acknowledgement unknown: this request may already be saved. Reconnect and retry the exact submission; do not create another ID.`;
      if (!rejected) this.state.connected = false;
    } finally { this.state.busy = false; this.emit(); }
  }
  editRejected() {
    if (this.state.busy || this.state.submission !== 'rejected') return false;
    try { this.storage.removeItem(PENDING_KEY); }
    catch { this.state.error = 'Cannot clear the rejected submission identity. Restore browser storage before editing.'; this.emit(); return false; }
    this.state.pending = null; this.state.submission = 'idle'; this.state.error = '';
    this.state.notice = 'Rejected content returned to the draft. A deliberate new submission will get a new request ID.';
    this.emit(); return true;
  }
}
