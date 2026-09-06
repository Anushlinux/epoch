import { IntakeAPI, IntakeError, apiOrigin } from './intake-api.mjs';

export const RUN_PENDING_KEY = 'epoch.execution.pending.v1';
export const TERMINAL = new Set(['completed', 'failed', 'cancelled', 'interrupted']);
export const EVENT_NAMES = [
  'sandbox.initialized', 'sandbox.reset', 'state.changed', 'brief.created',
  'run.started', 'run.verifying', 'run.finished', 'run.interrupted', 'run.cancellation_requested',
  'tool.discovery', 'tool.described', 'tool.called', 'tool.result', 'tool.error',
  'context.supplied', 'mcp.invalid_call', 'executor.started', 'executor.step', 'executor.message',
  'executor.tool_started', 'executor.tool_completed', 'executor.baseline', 'executor.error',
  'verification.completed', 'checkpoint.updated',
];
const object = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
const uuid = (x) => typeof x === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(x);
const strings = (x) => Array.isArray(x) && x.every((item) => typeof item === 'string');
const ids = (x) => Array.isArray(x) && x.every(uuid);
const date = (x) => typeof x === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(x) && Number.isFinite(Date.parse(x));
const ensure = (condition, message = 'The execution response does not match the published contract.') => {
  if (!condition) throw new IntakeError(message, 0, 'contract');
};
export function runRequest(input, id = crypto.randomUUID()) {
  const result = { client_request_id: id, workflow: 'release', release: input.release?.trim(),
    scenario: input.scenario ?? 'control', max_turns: Number(input.max_turns ?? 16), timeout_seconds: Number(input.timeout_seconds ?? 180) };
  ensure(validRunRequest(result), 'Enter a release of 1–80 characters, 1–30 turns and a timeout of 10–300 seconds.');
  return Object.freeze(result);
}
export function validRunRequest(x) {
  return object(x) && Object.keys(x).every((k) => ['client_request_id', 'workflow', 'release', 'scenario', 'max_turns', 'timeout_seconds'].includes(k)) &&
    uuid(x.client_request_id) && x.workflow === 'release' && typeof x.release === 'string' && x.release.trim().length > 0 && [...x.release].length <= 80 &&
    ['control', 'broken_checklist', 'missing_lookup', 'outdated_context'].includes(x.scenario) &&
    Number.isInteger(x.max_turns) && x.max_turns >= 1 && x.max_turns <= 30 &&
    Number.isInteger(x.timeout_seconds) && x.timeout_seconds >= 10 && x.timeout_seconds <= 300;
}
export function sameRunRequest(a, b) {
  return validRunRequest(a) && validRunRequest(b) && ['client_request_id', 'workflow', 'scenario', 'max_turns', 'timeout_seconds'].every((k) => a[k] === b[k]) && a.release.trim() === b.release.trim();
}
export function executionRecord(x, taskId, runId) {
  ensure(object(x) && x.schema_version === 1 && uuid(x.id) && uuid(x.task_id) &&
    (!taskId || x.task_id === taskId) && (!runId || x.id === runId) && validRunRequest(x.request) &&
    ['running', 'verifying', ...TERMINAL].includes(x.status) && date(x.created_at) && date(x.updated_at) &&
    (x.final_response === null || typeof x.final_response === 'string') &&
    (x.executor_success === null || typeof x.executor_success === 'boolean') &&
    object(x.baseline) && strings(x.missing_evidence) && (x.error === null || object(x.error)) &&
    (x.verification === null || (object(x.verification) && typeof x.verification.passed === 'boolean' && Array.isArray(x.verification.checks) && x.verification.checks.every((c) => object(c) && typeof c.name === 'string' && typeof c.passed === 'boolean'))));
  const b = x.brief;
  ensure(object(b) && b.schema_version === 1 && uuid(b.id) && b.task_id === x.task_id && typeof b.instructions === 'string' &&
    strings(b.constraints) && strings(b.clarification_requests) && Array.isArray(b.checkpoints) && b.checkpoints.length > 0);
  for (const c of b.checkpoints) {
    ensure(object(c) && uuid(c.id) && typeof c.description === 'string' && typeof c.scope === 'string' &&
      typeof c.verification_rule === 'string' && typeof c.evaluator_version === 'string' && ids(c.depends_on) && ids(c.evidence_refs) &&
      ['pending', 'verified', 'failed', 'blocked'].includes(c.status) && (c.status !== 'verified' || c.evidence_refs.length > 0) &&
      Array.isArray(c.source_refs) && c.source_refs.length > 0 && c.source_refs.every((s) => object(s) && uuid(s.id) && typeof s.locator === 'string' && ['explicit', 'inferred'].includes(s.attribution)));
  }
  ensure(x.status !== 'completed' || (x.executor_success === true && x.verification?.passed === true), 'A completed run must include executor success and passing trusted verification.');
  return structuredClone(x);
}
export function runEvent(x, taskId, runId) {
  ensure(object(x) && uuid(x.id) && x.task_id === taskId && x.run_id === runId &&
    Number.isSafeInteger(x.sequence) && x.sequence > 0 && typeof x.type === 'string' && object(x.payload) && date(x.emitted_at));
  return structuredClone(x);
}
export class ExecutionAPI extends IntakeAPI {
  async runtime() {
    const { body: x, status } = await this.call('/api/runtime');
    ensure(status === 200 && object(x) && x.phase === 3 && typeof x.execution_enabled === 'boolean' && typeof x.hermes_available === 'boolean' &&
      (x.active_run_id === null || uuid(x.active_run_id)) && x.workflow === 'release' && x.simulation_only === true &&
      x.automatic_supervision === false && x.automatic_repair === false);
    return x;
  }
  async runs(taskId) {
    ensure(uuid(taskId));
    const { body, status } = await this.call(`/api/tasks/${taskId}/runs`);
    ensure(status === 200 && Array.isArray(body));
    return body.map((x) => executionRecord(x, taskId));
  }
  async run(taskId, runId) {
    ensure(uuid(taskId) && uuid(runId));
    const { body, status } = await this.call(`/api/runs/${runId}`);
    ensure(status === 200);
    return executionRecord(body, taskId, runId);
  }
  async start(taskId, payload) {
    ensure(uuid(taskId) && validRunRequest(payload));
    const { body, status } = await this.call(`/api/tasks/${taskId}/runs`, payload);
    ensure([200, 202].includes(status));
    const run = executionRecord(body, taskId);
    ensure(sameRunRequest(run.request, payload), 'Run acknowledgement does not match the frozen request. Retain its ID for recovery.');
    return run;
  }
  async cancel(taskId, runId) {
    ensure(uuid(taskId) && uuid(runId));
    const { body, status } = await this.call(`/api/runs/${runId}/cancel`, {});
    ensure(status === 202);
    return executionRecord(body, taskId, runId);
  }
  async snapshot(runId) {
    ensure(uuid(runId));
    const { body, status } = await this.call(`/api/runs/${runId}/state`);
    ensure(status === 200 && object(body) && body.simulated === true && typeof body.project_id === 'string' && Number.isInteger(body.generation) &&
      ['tickets', 'checklists', 'messages', 'directory', 'runbooks'].every((k) => Array.isArray(body[k]) && body[k].every(object)));
    return body;
  }
  async trace(taskId, runId, after = 0) {
    ensure(uuid(taskId) && uuid(runId) && Number.isSafeInteger(after) && after >= 0);
    const { body, status } = await this.call(`/api/runs/${runId}/trace?after=${after}`);
    ensure(status === 200 && Array.isArray(body));
    let cursor = after;
    return body.map((raw) => {
      const event = runEvent(raw, taskId, runId);
      ensure(event.sequence === cursor + 1, 'Execution activity has a sequence gap. Reconnect to recover the persisted trace.');
      cursor = event.sequence;
      return event;
    });
  }
}

// Writes are explicit and retained before dispatch. All automatic recovery is read-only.
export class ExecutionWorkspace {
  constructor({ storage, apiFactory = (origin) => new ExecutionAPI(origin), sourceFactory = (url) => new EventSource(url), onChange = () => {}, onTask = () => {}, pollMs = 3000 }) {
    Object.assign(this, { storage, apiFactory, sourceFactory, onChange, onTask, pollMs });
    this.generation = 0; this.context = ''; this.cache = new Map();
    this.state = { origin: '', taskId: '', connected: false, runtime: null, runs: [], run: null, snapshot: null, events: [], cursor: 0,
      loading: false, busy: false, error: '', notice: '', stream: 'idle', pending: null, recovery: false, rejected: false };
    try {
      const raw = storage.getItem(RUN_PENDING_KEY);
      if (raw !== null) {
        const p = JSON.parse(raw);
        ensure(object(p) && p.version === 1 && uuid(p.taskId) && validRunRequest(p.payload));
        this.state.pending = Object.freeze({ version: 1, origin: apiOrigin(p.origin), taskId: p.taskId, payload: Object.freeze(p.payload) });
        this.state.notice = 'A run submission is awaiting confirmation. Connect to its original server and retry the exact run request.';
      }
    } catch { this.state.recovery = true; this.state.error = 'Run recovery storage is unavailable or corrupt. New executions are blocked; saved runs remain inspectable.'; }
  }
  emit() { this.onChange(this.state); }
  stopStream() { this.source?.close(); this.source = null; this.sourceRun = ''; }
  stop() { clearTimeout(this.timer); clearTimeout(this.eventTimer); this.eventTimer = null; this.stopStream(); this.generation++; this.refreshing = null; }
  setContext(origin, taskId, connected) {
    const key = `${origin}|${taskId}|${connected}`;
    if (this.context === key) return;
    const changed = origin !== this.state.origin || taskId !== this.state.taskId;
    this.stop(); this.context = key;
    Object.assign(this.state, { origin, taskId, connected, loading: false, stream: connected ? 'idle' : 'disconnected' });
    if (changed) Object.assign(this.state, { runtime: null, runs: [], run: null, snapshot: null, events: [], cursor: 0 });
    if (!this.state.pending && !this.state.recovery) this.state.error = '';
    this.api = this.apiFactory(origin);
    if (connected) void this.refresh();
  }
  async select(runId) {
    if (!this.state.runs.some((run) => run.id === runId) || this.state.busy) return;
    this.stop();
    this.state.run = this.state.runs.find((run) => run.id === runId);
    this.state.snapshot = null; this.state.events = []; this.state.cursor = 0;
    await this.refresh();
  }
  async refresh() {
    if (!this.state.connected) return;
    if (this.refreshing) return this.refreshing;
    const generation = this.generation;
    const api = this.api;
    const { taskId } = this.state;
    clearTimeout(this.timer);
    this.state.loading = true;
    // Defer work so the guard is installed before any callbacks can ask for a refresh.
    this.refreshing = Promise.resolve().then(async () => {
      try {
        const [runtime, runs, task] = await Promise.all([api.runtime(), taskId ? api.runs(taskId) : [], taskId ? api.detail(taskId) : null]);
        if (generation !== this.generation) return;
        this.state.runtime = runtime; this.state.runs = runs;
        const chosen = runs.find((run) => run.id === this.state.run?.id) || runs[0];
        if (chosen) {
          const cacheKey = `${api.origin}|${chosen.id}`;
          const cached = this.cache.get(cacheKey) || [];
          const cursor = cached.at(-1)?.sequence || 0;
          const [run, snapshot, trace] = await Promise.all([api.run(taskId, chosen.id), api.snapshot(chosen.id), api.trace(taskId, chosen.id, cursor)]);
          if (generation !== this.generation) return;
          const events = [...cached, ...trace];
          this.cache.set(cacheKey, events);
          Object.assign(this.state, { run, snapshot, events, cursor: events.at(-1)?.sequence || 0 });
          this.state.runs = runs.map((item) => item.id === run.id ? run : item);
          if (TERMINAL.has(run.status)) { this.stopStream(); this.state.stream = 'finished'; }
          else this.subscribe(run, generation);
        } else {
          this.stopStream();
          Object.assign(this.state, { run: null, snapshot: null, events: [], cursor: 0, stream: 'idle' });
        }
        if (!this.state.pending && !this.state.recovery) this.state.error = '';
        if (task) this.onTask(task);
      } catch (error) {
        if (generation === this.generation) {
          this.state.error = `${error.message} Last loaded evidence is retained. No execution was retried.`;
          this.state.stream = 'reconnecting';
        }
      } finally {
        if (generation === this.generation) {
          this.refreshing = null; this.state.loading = false; this.emit();
          this.timer = setTimeout(() => void this.refresh(), this.pollMs);
        }
      }
    });
    return this.refreshing;
  }
  subscribe(run, generation) {
    if (this.sourceRun === run.id) return;
    this.stopStream();
    this.state.stream = 'connecting';
    try {
      const source = this.sourceFactory(`${this.api.origin}/api/runs/${run.id}/events?after=${this.state.cursor}`);
      this.source = source; this.sourceRun = run.id;
      const current = () => generation === this.generation && this.source === source;
      source.onopen = () => { if (current()) { this.state.stream = 'live'; this.emit(); } };
      const refreshSoon = () => {
        if (!current() || this.eventTimer) return;
        this.eventTimer = setTimeout(() => { this.eventTimer = null; if (current()) void this.refresh(); }, 150);
      };
      // Named events are notifications; the persisted trace is the ordered source of truth.
      // Polling also catches unknown future event types and any stream/HTTP race.
      for (const name of EVENT_NAMES) source.addEventListener(name, refreshSoon);
      source.onerror = () => { if (current()) { this.state.stream = 'reconnecting'; this.emit(); refreshSoon(); } };
    } catch { this.state.stream = 'polling'; }
  }
  async start(input) {
    const s = this.state;
    if (s.busy || s.pending || s.recovery || !s.connected || !s.taskId || !s.runtime?.execution_enabled || s.runtime.active_run_id) return;
    try {
      const pending = Object.freeze({ version: 1, origin: s.origin, taskId: s.taskId, payload: runRequest(input) });
      this.storage.setItem(RUN_PENDING_KEY, JSON.stringify(pending));
      s.pending = pending; s.rejected = false;
    } catch (error) { s.error = `Nothing was sent. ${error.message}`; this.emit(); return; }
    await this.retry();
  }
  async retry() {
    const s = this.state, pending = s.pending;
    if (s.busy || s.recovery || !s.connected || !pending || s.origin !== pending.origin || s.taskId !== pending.taskId || s.rejected) return;
    const api = this.api;
    const generation = this.generation;
    s.busy = true; s.error = ''; s.notice = ''; this.emit();
    try {
      const run = await api.start(pending.taskId, pending.payload);
      this.storage.removeItem(RUN_PENDING_KEY);
      s.pending = null;
      if (generation === this.generation) { s.run = run; s.runs = [run, ...s.runs.filter((item) => item.id !== run.id)]; }
      s.notice = 'Run request confirmed. Its status and trusted checks determine the outcome.';
    } catch (error) {
      s.rejected = ([403, 404, 409, 422].includes(error.status) || (error.status === 503 && ['hermes_unavailable', 'execution_state_unresolved'].includes(error.code)));
      s.error = s.rejected ? `${error.message} HTTP ${error.status}. Run request retained for review.` : `${error.message} Run acknowledgement unknown. Retry only the exact saved run request.`;
    } finally { s.busy = false; this.emit(); if (generation === this.generation) await this.refresh(); }
  }
  reviewRejected() {
    if (!this.state.rejected || this.state.busy) return;
    try { this.storage.removeItem(RUN_PENDING_KEY); }
    catch { this.state.error = 'Cannot clear the rejected run identity. Restore browser storage first.'; this.emit(); return; }
    this.state.pending = null; this.state.rejected = false; this.state.error = '';
    this.state.notice = 'Rejected request returned to the form. Starting again is an explicit new run.';
    this.emit();
  }
  async cancel() {
    const s = this.state;
    if (s.busy || !s.connected || !s.run || TERMINAL.has(s.run.status)) return;
    const generation = this.generation, api = this.api, run = s.run;
    s.busy = true; s.error = ''; this.emit();
    try {
      const updated = await api.cancel(run.task_id, run.id);
      if (generation === this.generation) s.run = updated;
      s.notice = 'Cancellation requested. Waiting for the recorded terminal status; partial effects remain.';
    } catch (error) { s.notice = `Cancellation could not be confirmed. ${error.message} Inspect the latest status before trying again.`; }
    finally { s.busy = false; this.emit(); if (generation === this.generation) await this.refresh(); }
  }
}
