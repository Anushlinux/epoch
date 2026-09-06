import { IntakeAPI, IntakeError, apiOrigin } from './intake-api.mjs';

export const RUN_PENDING_KEY = 'epoch.execution.pending.v1';
export const OPERATION_PENDING_KEY = 'epoch.operation.pending.v1';
export const TERMINAL = new Set(['completed', 'needs_input', 'blocked', 'failed', 'cancelled', 'interrupted']);
export const RUN_STATUSES = ['planning', 'running', 'verifying', 'repairing', ...TERMINAL];
export const EVENT_NAMES = [
  'sandbox.initialized', 'sandbox.reset', 'state.changed', 'brief.created',
  'run.started', 'run.verifying', 'run.finished', 'run.interrupted', 'run.cancellation_requested',
  'tool.discovery', 'tool.described', 'tool.called', 'tool.result', 'tool.error',
  'context.supplied', 'mcp.invalid_call', 'executor.started', 'executor.step', 'executor.message',
  'executor.tool_started', 'executor.tool_completed', 'executor.baseline', 'executor.error',
  'verification.completed', 'checkpoint.updated', 'brief.template_prepared',
  'supervisor.requested', 'supervisor.plan', 'supervisor.decision', 'debugger.started', 'debugger.completed',
  'supervisor.intervention', 'intent.submitted', 'intent.revised', 'requirements.revised',
  'clarification.requested', 'budget.turn_authorized', 'supervision.finished', 'demo.omission_requested',
  'repair.triggered', 'repair.budget_authorized', 'repair.candidate_staged', 'repair.candidate_rejected',
  'repair.blocked', 'environment.published',
];
const object = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
const uuid = (x) => typeof x === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(x);
const strings = (x) => Array.isArray(x) && x.every((item) => typeof item === 'string');
const ids = (x) => Array.isArray(x) && x.every(uuid);
const date = (x) => typeof x === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(x) && Number.isFinite(Date.parse(x));
export function supportsRepair(runtime, scenario = 'control') {
  if (!runtime?.automatic_repair || !runtime?.repair_opt_in) return false;
  const target = { broken_checklist: 'checklist_serializer.py', missing_lookup: 'qa_lookup.py', outdated_context: 'runbook_selector.py' }[scenario];
  const targets = runtime.repair_targets || (runtime.phase === 5 ? ['checklist_serializer.py'] : []);
  return target ? targets.includes(target) : targets.length > 0;
}
const ensure = (condition, message = 'The execution response does not match the published contract.') => {
  if (!condition) throw new IntakeError(message, 0, 'contract');
};
export function runRequest(input, id = crypto.randomUUID()) {
  const result = { client_request_id: id, workflow: 'release', release: input.release?.trim(),
    scenario: input.scenario ?? 'control', max_turns: Number(input.max_turns ?? 20), timeout_seconds: Number(input.timeout_seconds ?? 600),
    supervised: input.supervised ?? true, demo_omit_notification: input.demo_omit_notification ?? false, repair_enabled: input.repair_enabled ?? false };
  ensure(validRunRequest(result), 'Enter a release of 1–80 characters, 1–20 turns and a timeout of 10–600 seconds. Repair requires supervision and cannot use the omission demonstration.');
  return Object.freeze(result);
}
export function validStoredRunRequest(x) {
  return object(x) && Object.keys(x).every((k) => ['client_request_id', 'workflow', 'release', 'scenario', 'max_turns', 'timeout_seconds', 'supervised', 'demo_omit_notification', 'repair_enabled'].includes(k)) &&
    uuid(x.client_request_id) && x.workflow === 'release' && typeof x.release === 'string' && x.release.trim().length > 0 && [...x.release].length <= 80 &&
    ['control', 'broken_checklist', 'missing_lookup', 'outdated_context'].includes(x.scenario) &&
    Number.isInteger(x.max_turns) && x.max_turns >= 1 && x.max_turns <= 30 &&
    Number.isInteger(x.timeout_seconds) && x.timeout_seconds >= 10 && x.timeout_seconds <= 600 &&
    ['supervised', 'demo_omit_notification', 'repair_enabled'].every((k) => x[k] === undefined || typeof x[k] === 'boolean');
}
export function validRunRequest(x) {
  return validStoredRunRequest(x) && x.max_turns <= 20 && (!x.demo_omit_notification || x.supervised === true) &&
    (!x.repair_enabled || (x.supervised === true && !x.demo_omit_notification));
}
export function sameRunRequest(a, b) {
  return validStoredRunRequest(a) && validStoredRunRequest(b) && ['client_request_id', 'workflow', 'scenario', 'max_turns', 'timeout_seconds'].every((k) => a[k] === b[k]) &&
    ['supervised', 'demo_omit_notification', 'repair_enabled'].every((k) => (a[k] ?? false) === (b[k] ?? false)) && a.release.trim() === b.release.trim();
}
export function validFeedbackRequest(x) {
  return object(x) && Object.keys(x).every((k) => ['client_request_id', 'expected_revision_id', 'message', 'max_turns', 'timeout_seconds'].includes(k)) &&
    uuid(x.client_request_id) && uuid(x.expected_revision_id) && typeof x.message === 'string' && x.message.trim().length > 0 && [...x.message].length <= 16000 &&
    Number.isInteger(x.max_turns) && x.max_turns >= 1 && x.max_turns <= 20 && Number.isInteger(x.timeout_seconds) && x.timeout_seconds >= 10 && x.timeout_seconds <= 600;
}
export function feedbackRequest(message, expectedRevision, { max_turns = 20, timeout_seconds = 600 } = {}, id = crypto.randomUUID()) {
  const payload = { client_request_id: id, expected_revision_id: expectedRevision, message: message?.trim(), max_turns: Number(max_turns), timeout_seconds: Number(timeout_seconds) };
  ensure(validFeedbackRequest(payload), 'Enter feedback of 1–16,000 characters with the current revision, 1–20 turns and 10–600 seconds.');
  return Object.freeze(payload);
}
const sameFeedback = (a, b) => validFeedbackRequest(a) && validFeedbackRequest(b) &&
  ['client_request_id', 'expected_revision_id', 'max_turns', 'timeout_seconds'].every((k) => a[k] === b[k]) && a.message.trim() === b.message.trim();
export function supervisionOperation(x) {
  ensure(object(x) && uuid(x.id) && uuid(x.client_request_id) && (x.previous_revision_id === null || uuid(x.previous_revision_id)) &&
    ['initial', 'feedback', 'clarification'].includes(x.trigger) && typeof x.user_input === 'string' && object(x.request) && RUN_STATUSES.includes(x.status) && date(x.created_at) &&
    strings(x.questions) && strings(x.missing_evidence) && ['debugger_calls', 'executor_passes', 'interventions'].every((k) => Array.isArray(x[k]) && x[k].every(object)) &&
    (x.repairs === undefined || (Array.isArray(x.repairs) && x.repairs.every(object))));
  return structuredClone(x);
}
export function environmentRecord(x, project) {
  ensure(object(x) && x.project === project && (x.active_version === 'builtin' || uuid(x.active_version)) &&
    ['versions', 'repairs', 'history'].every((k) => Array.isArray(x[k]) && x[k].every(object)));
  return structuredClone(x);
}
function operationIdentity(p) {
  ensure(object(p) && p.version === 1 && ['feedback', 'clarification', 'rollback'].includes(p.kind) && uuid(p.taskId) &&
    (p.runId === null || uuid(p.runId)) && typeof p.projectId === 'string' && p.projectId.trim().length > 0);
  const expected = p.kind === 'rollback' ? `/api/environments/${encodeURIComponent(p.projectId)}/rollback` : `/api/runs/${p.runId}/${p.kind === 'clarification' ? 'clarifications' : 'feedback'}`;
  ensure(p.endpoint === expected && (p.kind === 'rollback' ? object(p.payload) && Object.keys(p.payload).length === 2 && uuid(p.payload.client_request_id) && uuid(p.payload.expected_version) : uuid(p.runId) && validFeedbackRequest(p.payload)));
  return Object.freeze({ ...p, origin: apiOrigin(p.origin), payload: Object.freeze(p.payload) });
}
const explicitlyRejected = (error) => [403, 404, 409, 422].includes(error.status) || (error.status === 503 && ['hermes_unavailable', 'debugger_unavailable', 'execution_state_unresolved'].includes(error.code));
export function executionRecord(x, taskId, runId) {
  ensure(object(x) && x.schema_version === 1 && uuid(x.id) && uuid(x.task_id) &&
    (!taskId || x.task_id === taskId) && (!runId || x.id === runId) && validStoredRunRequest(x.request) &&
    RUN_STATUSES.includes(x.status) && date(x.created_at) && date(x.updated_at) &&
    (x.final_response === null || typeof x.final_response === 'string') &&
    (x.executor_success === null || typeof x.executor_success === 'boolean') &&
    object(x.baseline) && strings(x.missing_evidence) && (x.error === null || object(x.error)) &&
    (x.verification === null || (object(x.verification) && typeof x.verification.passed === 'boolean' && Array.isArray(x.verification.checks) && x.verification.checks.every((c) => object(c) && typeof c.name === 'string' && typeof c.passed === 'boolean'))));
  if (x.supervision !== undefined && x.supervision !== null) {
    const supervision = x.supervision;
    ensure(object(supervision) && supervision.debugger_model === 'gpt-5.6-luna' && uuid(supervision.current_revision_id) && Array.isArray(supervision.operations));
    supervision.operations.forEach(supervisionOperation);
    ensure(supervision.operations.some((op) => op.id === supervision.current_revision_id));
  }
  ensure(x.environment_version === undefined || x.environment_version === 'builtin' || uuid(x.environment_version));
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
    ensure(status === 200 && object(x) && [3, 4, 5, 6, 7].includes(x.phase) && typeof x.execution_enabled === 'boolean' && typeof x.hermes_available === 'boolean' &&
      (x.active_run_id === null || uuid(x.active_run_id)) && x.workflow === 'release' && x.simulation_only === true &&
      typeof x.automatic_supervision === 'boolean' && typeof x.automatic_repair === 'boolean' &&
      (x.repair_opt_in === undefined || typeof x.repair_opt_in === 'boolean') &&
      (x.repair_targets === undefined || strings(x.repair_targets)));
    return x;
  }
  async repairRuntime() {
    const { body, status } = await this.call('/api/repair/runtime');
    ensure(status === 200 && object(body) && typeof body.available === 'boolean' && typeof body.image === 'string' && typeof body.runner_version === 'string');
    return body;
  }
  async environment(projectId) {
    ensure(typeof projectId === 'string' && projectId.trim().length > 0);
    const { body, status } = await this.call(`/api/environments/${encodeURIComponent(projectId)}`);
    ensure(status === 200);
    return environmentRecord(body, projectId);
  }
  async revisions(runId) {
    ensure(uuid(runId));
    const { body, status } = await this.call(`/api/runs/${runId}/revisions`);
    ensure(status === 200 && Array.isArray(body));
    return body.map(supervisionOperation);
  }
  async operation(pending) {
    const p = operationIdentity(pending);
    const { body, status } = await this.call(p.endpoint, p.payload);
    ensure([200, 202].includes(status));
    if (p.kind === 'rollback') {
      ensure(status === 200 && object(body) && body.type === 'environment.rolled_back' && body.project === p.projectId && body.previous === p.payload.expected_version &&
        (body.version_id === 'builtin' || uuid(body.version_id)) && date(body.created_at), 'Rollback acknowledgement does not match the frozen request.');
      return body;
    }
    const run = executionRecord(body, p.taskId, p.runId);
    const op = run.supervision?.operations.find((item) => item.client_request_id === p.payload.client_request_id);
    ensure(op && op.trigger === p.kind && op.previous_revision_id === p.payload.expected_revision_id && sameFeedback(op.request, p.payload), 'Operation acknowledgement does not match the frozen request. Retain its ID for recovery.');
    return run;
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
    ensure(uuid(taskId) && validStoredRunRequest(payload));
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
      loading: false, busy: false, error: '', notice: '', stream: 'idle', pending: null, recovery: false, rejected: false, repairRuntime: null, environment: null, revisions: [], optionalErrors: [], projectId: '', operationPending: null, operationRejected: false, operationRecovery: false };
    try {
      const raw = storage.getItem(RUN_PENDING_KEY);
      if (raw !== null) {
        const p = JSON.parse(raw);
        ensure(object(p) && p.version === 1 && uuid(p.taskId) && validStoredRunRequest(p.payload));
        this.state.pending = Object.freeze({ version: 1, origin: apiOrigin(p.origin), taskId: p.taskId, payload: Object.freeze(p.payload) });
        this.state.notice = 'A run submission is awaiting confirmation. Connect to its original server and retry the exact run request.';
      }
    } catch { this.state.recovery = true; this.state.error = 'Run recovery storage is unavailable or corrupt. New executions are blocked; saved runs remain inspectable.'; }
    try {
      const raw = storage.getItem(OPERATION_PENDING_KEY);
      if (raw !== null) this.state.operationPending = operationIdentity(JSON.parse(raw));
    } catch { this.state.operationRecovery = true; this.state.error = 'Operation recovery storage is unavailable or corrupt. New writes are blocked; saved evidence remains inspectable.'; }

  }
    // A separate operation journal protects feedback and rollback across reloads.
  emit() { this.onChange(this.state); }
  stopStream() { this.source?.close(); this.source = null; this.sourceRun = ''; }
  stop() { clearTimeout(this.timer); clearTimeout(this.eventTimer); this.eventTimer = null; this.stopStream(); this.generation++; this.refreshing = null; }
  setContext(origin, taskId, connected) {
    const key = `${origin}|${taskId}|${connected}`;
    if (this.context === key) return;
    const changed = origin !== this.state.origin || taskId !== this.state.taskId;
    this.stop(); this.context = key;
    Object.assign(this.state, { origin, taskId, connected, loading: false, stream: connected ? 'idle' : 'disconnected' });
    if (changed) Object.assign(this.state, { runtime: null, runs: [], run: null, snapshot: null, events: [], cursor: 0, repairRuntime: null, environment: null, revisions: [], projectId: '', optionalErrors: [] });
    if (!this.state.pending && !this.state.recovery && !this.state.operationPending && !this.state.operationRecovery) this.state.error = '';
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
        this.state.runtime = runtime; this.state.runs = runs; this.state.projectId = task?.request.project_id || '';
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
        if (!this.state.pending && !this.state.recovery && !this.state.operationPending && !this.state.operationRecovery) this.state.error = '';
        if (task) this.onTask(task);
        this.emit(); // Core evidence must remain usable while optional inspection runs.
        const reads = [
          ['repairRuntime', () => api.repairRuntime?.()],
          ['environment', () => task ? api.environment?.(task.request.project_id) : null],
          ['revisions', () => chosen ? api.revisions?.(chosen.id) : []],
        ];
        const extra = await Promise.allSettled(reads.map(([, read]) => read()));
        if (generation !== this.generation) return;
        this.state.optionalErrors = [];
        extra.forEach((result, index) => {
          const key = reads[index][0];
          if (result.status === 'fulfilled' && result.value !== undefined) this.state[key] = result.value;
          else if (result.status === 'rejected') {
            this.state[key] = key === 'revisions' ? [] : null;
            this.state.optionalErrors.push(`${key}: ${result.reason.message}`);
          }
        });
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
    if (s.busy || s.pending || s.recovery || s.operationPending || s.operationRecovery || !s.connected || !s.taskId || !s.runtime?.execution_enabled || s.runtime.active_run_id) return;
    try {
      const payload = runRequest(input);
      ensure(!payload.supervised || s.runtime.supervision_enabled === true, 'Supervision is unavailable. Inspect the debugger runtime or select direct execution.');
      ensure(!payload.repair_enabled || (supportsRepair(s.runtime, payload.scenario) && s.repairRuntime?.available === true), 'Repair requires an advertised repair capability for this scenario and an available isolated runner.');
      const pending = Object.freeze({ version: 1, origin: s.origin, taskId: s.taskId, payload });
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
      s.rejected = explicitlyRejected(error);
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
  canWriteOperation() {
    const s = this.state;
    return !s.busy && !s.pending && !s.recovery && !s.operationPending && !s.operationRecovery && s.connected && s.taskId && !s.runtime?.active_run_id;
  }
  async submitFeedback(message, { clarification = false, max_turns = 20, timeout_seconds = 600 } = {}) {
    const s = this.state, run = s.run;
    if (!this.canWriteOperation() || !run?.supervision || !TERMINAL.has(run.status) || (clarification && run.status !== 'needs_input')) return false;
    try {
      ensure(s.runtime?.supervision_enabled === true, 'Supervision is unavailable. Inspect the debugger runtime.');
      const kind = clarification ? 'clarification' : 'feedback';
      const payload = feedbackRequest(message, run.supervision.current_revision_id, { max_turns, timeout_seconds });
      return await this.persistOperation({ version: 1, kind, origin: s.origin, taskId: s.taskId, runId: run.id, projectId: s.projectId, payload,
        endpoint: `/api/runs/${run.id}/${clarification ? 'clarifications' : 'feedback'}` });
    } catch (error) { s.error = `Nothing was sent. ${error.message}`; this.emit(); return false; }
  }
  async rollback() {
    const s = this.state;
    if (!this.canWriteOperation() || !uuid(s.environment?.active_version)) return;
    try {
      await this.persistOperation({ version: 1, kind: 'rollback', origin: s.origin, taskId: s.taskId, runId: s.run?.id || null, projectId: s.projectId,
        endpoint: `/api/environments/${encodeURIComponent(s.projectId)}/rollback`,
        payload: { client_request_id: crypto.randomUUID(), expected_version: s.environment.active_version } });
    } catch (error) { s.error = `Nothing was sent. ${error.message}`; this.emit(); return false; }
  }
  async persistOperation(value) {
    const pending = operationIdentity(value);
    this.storage.setItem(OPERATION_PENDING_KEY, JSON.stringify(pending));
    this.state.operationPending = pending; this.state.operationRejected = false;
    return this.retryOperation();
  }
  async retryOperation() {
    const s = this.state, pending = s.operationPending;
    if (s.busy || s.pending || s.recovery || s.operationRecovery || s.operationRejected || !s.connected || !pending || s.origin !== pending.origin || s.taskId !== pending.taskId ||
      (pending.kind !== 'rollback' && s.run?.id !== pending.runId)) return false;
    const generation = this.generation, api = this.api;
    s.busy = true; s.error = ''; s.notice = ''; this.emit();
    try {
      const result = await api.operation(pending);
      this.storage.removeItem(OPERATION_PENDING_KEY);
      s.operationPending = null;
      if (generation === this.generation && pending.kind !== 'rollback') {
        // Invalidate an earlier in-flight read and reopen this run at its retained cursor.
        this.stop(); s.run = result; s.runs = [result, ...s.runs.filter((item) => item.id !== result.id)];
      }
      s.notice = pending.kind === 'rollback' ? 'Rollback confirmed. New runs use the restored version; existing runs remain pinned.' : 'Operation confirmed. Observe its trusted checks and retained revision history.';
      return true;
    } catch (error) {
      s.operationRejected = explicitlyRejected(error);
      s.error = s.operationRejected ? `${error.message} HTTP ${error.status}. Review the latest revision or version before submitting a new request.` : `${error.message} Operation acknowledgement unknown. Retry only the exact saved operation.`;
      return false;
    } finally { s.busy = false; this.emit(); if (s.origin === pending.origin && s.taskId === pending.taskId) await this.refresh(); }
  }
  reviewRejectedOperation() {
    const s = this.state;
    if (!s.operationRejected || s.busy) return;
    try { this.storage.removeItem(OPERATION_PENDING_KEY); }
    catch { s.error = 'Cannot clear the rejected operation identity. Restore browser storage first.'; this.emit(); return; }
    s.operationPending = null; s.operationRejected = false; s.error = '';
    s.notice = 'Rejected operation returned for review. A changed submission receives a new request ID.'; this.emit();
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
