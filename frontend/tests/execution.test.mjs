import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { IntakeAPI, IntakeError } from '../src/intake-api.mjs';
import { ExecutionAPI, ExecutionWorkspace, executionRecord, runEvent, runRequest, sameRunRequest, supportsRepair, EVENT_NAMES, RUN_PENDING_KEY } from '../src/execution-api.mjs';
const fixtures = JSON.parse(readFileSync(new URL('../../backend/fixtures/development.json', import.meta.url)));
const model = (name) => structuredClone(fixtures.examples.find((x) => x.model === name).value);
const task = model('Task');
const runtime = { phase: 3, execution_enabled: true, hermes_available: true, active_run_id: null, workflow: 'release', simulation_only: true, automatic_supervision: true, automatic_repair: true, supervision_enabled: true };
const record = (changes = {}) => ({ schema_version: 1, id: crypto.randomUUID(), task_id: task.id, request: runRequest({ release: '2.4' }), status: 'running', brief: { ...model('TaskBrief'), task_id: task.id }, created_at: task.created_at, updated_at: task.updated_at, final_response: null, executor_success: null, baseline: {}, verification: null, missing_evidence: [], error: null, ...changes });
const event = (run, sequence, type = 'tool.result') => ({ id: crypto.randomUUID(), task_id: task.id, run_id: run.id, sequence, type, payload: { new_field: true }, emitted_at: task.created_at });
const memory = () => { const map = new Map(); return { getItem: (k) => map.get(k) ?? null, setItem: (k, v) => map.set(k, v), removeItem: (k) => map.delete(k) }; };
const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r; }); return { promise, resolve }; };
test('Phase 7 connects and repair follows advertised targets rather than phase alone', async () => {
  const current = { ...runtime, phase: 7, repair_opt_in: true, repair_targets: ['qa_lookup.py'] };
  const api = new ExecutionAPI('http://localhost:8000', async (url) => new Response(JSON.stringify(url.endsWith('/health') ? { status: 'ok', storage: 'ok', phase: 7, execution_enabled: true } : current)));
  assert.equal((await api.health()).phase, 7);
  assert.equal((await api.runtime()).phase, 7);
  assert.equal(supportsRepair(current, 'missing_lookup'), true);
  assert.equal(supportsRepair(current, 'outdated_context'), false);
  assert.equal(supportsRepair({ ...current, automatic_repair: false }, 'missing_lookup'), false);
  assert.equal(supportsRepair({ ...current, repair_opt_in: false }, 'missing_lookup'), false);
});
function setup(t, options = {}) {
  const storage = options.storage || memory(), calls = [], sources = [];
  let current = options.run || null;
  const api = { origin: 'http://127.0.0.1:8000', runtime: async () => runtime, detail: async () => task, runs: async () => current ? [current] : [], run: async () => current,
    snapshot: async () => ({ simulated: true, project_id: 'demo', generation: 0, tickets: [], checklists: [], messages: [], directory: [], runbooks: [] }), trace: async () => [],
    start: async (taskId, payload) => { calls.push({ taskId, payload }); current = record({ request: payload }); return current; }, ...options.api };
  const w = new ExecutionWorkspace({ storage, apiFactory: () => api, pollMs: 60000, sourceFactory: (url) => {
    const source = { url, listeners: {}, addEventListener(name, handler) { this.listeners[name] = handler; }, close() { this.closed = true; } }; sources.push(source); return source;
  } });
  t.after(() => w.stop());
  w.setContext(api.origin, task.id, true);
  return { w, api, storage, calls, sources };
}
test('Phase 3 health accepts both enablement values and every execution status binds task/run identity', async () => {
  for (const execution_enabled of [true, false]) {
    const api = new IntakeAPI('http://localhost:8000', async () => new Response(JSON.stringify({ status: 'ok', storage: 'ok', phase: 3, execution_enabled })));
    assert.equal((await api.health()).execution_enabled, execution_enabled);
  }
  for (const status of ['running', 'verifying', 'failed', 'cancelled', 'interrupted']) assert.equal(executionRecord(record({ status })).status, status);
  assert.throws(() => executionRecord(record({ status: 'completed' })), /completed run/);
  const completed = record({ status: 'completed', executor_success: true, verification: { passed: true, checks: [] } });
  assert.equal(executionRecord(completed).status, 'completed');
  assert.throws(() => executionRecord(completed, crypto.randomUUID()), /contract/);
  assert.throws(() => executionRecord(completed, task.id, crypto.randomUUID()), /contract/);
  const b = record(); b.brief.checkpoints[0].status = 'verified'; b.brief.checkpoints[0].evidence_refs = [];
  assert.throws(() => executionRecord(b), /contract/);
});
test('run inputs use backend limits and normalized identity; events accept unknown types but require correct identities', () => {
  const request = runRequest({ release: ' 2.4 ' }); assert.equal(request.release, '2.4');
  assert.ok(sameRunRequest(request, { ...request, release: ' 2.4' }));
  for (const input of [{ release: ' ' }, { release: 'a'.repeat(81) }, { release: 'ok', max_turns: 31 }, { release: 'ok', timeout_seconds: 9 }, { release: 'ok', scenario: 'fake' }]) assert.throws(() => runRequest(input));
  const run = record(), e = event(run, 1, 'future.event'); assert.deepEqual(runEvent(e, task.id, run.id), e);
  assert.throws(() => runEvent(e, task.id, crypto.randomUUID()));
});
test('HTTP paths and response identities are validated; trace gaps/duplicates and false simulation fail closed', async () => {
  const run = record(), calls = [];
  const api = new ExecutionAPI('http://localhost:8000', async (url, options) => { calls.push({ url, options }); return new Response(JSON.stringify(run), { status: 202 }); });
  assert.equal((await api.start(task.id, run.request)).id, run.id);
  assert.equal(calls[0].url, `http://localhost:8000/api/tasks/${task.id}/runs`);
  assert.equal(calls[0].options.credentials, 'omit');
  await assert.rejects(api.start(task.id, runRequest({ release: 'changed' })), /acknowledgement/);
  await api.cancel(task.id, run.id);
  assert.equal(calls.at(-1).options.method, 'POST');
  api.fetcher = async () => new Response(JSON.stringify([event(run, 2)]));
  await assert.rejects(api.trace(task.id, run.id), /sequence gap/);
  assert.equal((await api.trace(task.id, run.id, 1))[0].sequence, 2);
  api.fetcher = async () => new Response(JSON.stringify([event(run, 1), event(run, 1)]));
  await assert.rejects(api.trace(task.id, run.id), /sequence gap/);
  api.fetcher = async () => new Response(JSON.stringify({ simulated: false }));
  await assert.rejects(api.snapshot(run.id), /contract/);
});
test('run request persists before dispatch; lost response and reload permit only exact explicit retry even when executor busy', async (t) => {
  const first = setup(t, { api: { start: async () => { throw new IntakeError('lost'); } } }); await first.w.refresh();
  await first.w.start({ release: '2.4' }); const pending = first.w.state.pending;
  assert.deepEqual(JSON.parse(first.storage.getItem(RUN_PENDING_KEY)).payload, pending.payload);
  assert.match(first.w.state.error, /acknowledgement unknown/);
  const recovered = setup(t, { storage: first.storage, api: { runtime: async () => ({ ...runtime, active_run_id: crypto.randomUUID() }) } }); await recovered.w.refresh();
  assert.equal(recovered.calls.length, 0);
  await recovered.w.start({ release: 'different' }); assert.equal(recovered.calls.length, 0);
  await recovered.w.retry(); assert.deepEqual(recovered.calls[0].payload, pending.payload);
  assert.equal(recovered.storage.getItem(RUN_PENDING_KEY), null);
});
test('corrupt storage and pre-send storage failure block new runs', async (t) => {
  const storage = memory(); storage.setItem(RUN_PENDING_KEY, '{bad');
  const corrupt = setup(t, { storage }); await corrupt.w.refresh(); await corrupt.w.start({ release: '2.4' });
  assert.equal(corrupt.calls.length, 0); assert.equal(corrupt.w.state.recovery, true);
  const fresh = setup(t); await fresh.w.refresh(); fresh.storage.setItem = () => { throw Error('storage full'); };
  await fresh.w.start({ release: '2.4' }); assert.equal(fresh.calls.length, 0); assert.match(fresh.w.state.error, /Nothing was sent/);
});
test('uncertain 503 storage errors retain identity; explicit busy rejection requires review; double start is suppressed', async (t) => {
  const { w, api, calls } = setup(t); await w.refresh();
  api.start = async () => { throw new IntakeError('storage unavailable', 503, 'storage_unavailable'); };
  await w.start({ release: '2.4' }); assert.equal(w.state.rejected, false);
  const id = w.state.pending.payload.client_request_id;
  api.start = async () => { throw new IntakeError('busy', 409, 'executor_busy'); };
  await w.retry(); assert.equal(w.state.rejected, true); assert.equal(w.state.pending.payload.client_request_id, id);
  w.reviewRejected(); assert.equal(w.state.pending, null);
  const wait = deferred(); api.start = async (taskId, payload) => { calls.push(payload); return wait.promise; };
  const sending = w.start({ release: '2.5' }); await w.start({ release: 'duplicate' }); assert.equal(calls.length, 1);
  wait.resolve(record({ request: calls[0] })); await sending;
});
test('pending run is bound to original task and server across navigation', async (t) => {
  const { w, calls } = setup(t, { api: { start: async () => { throw new IntakeError('lost'); } } }); await w.refresh();
  await w.start({ release: '2.4' }); const saved = w.state.pending;
  w.setContext('http://localhost:8999', crypto.randomUUID(), true); await w.refresh(); await w.retry();
  assert.equal(calls.length, 0); assert.equal(w.state.pending, saved);
});
test('named SSE listeners recover persisted trace, terminal closes stream and stale reads cannot replace selection', async (t) => {
  const run = record(), { w, api, sources } = setup(t, { run }); await w.refresh();
  assert.equal(sources.length, 1); assert.deepEqual(Object.keys(sources[0].listeners), EVENT_NAMES);
  let traceAfter;
  api.trace = async (taskId, runId, after) => { traceAfter = after; return after ? [] : [event(run, 1, 'future.event')]; };
  await w.refresh(); assert.equal(w.state.cursor, 1);
  await w.refresh(); assert.equal(traceAfter, 1); assert.equal(w.state.events.length, 1);
  api.run = async () => ({ ...run, status: 'failed' }); await w.refresh();
  assert.equal(sources[0].closed, true); assert.equal(w.state.stream, 'finished');
  const wait = deferred(); api.runtime = () => wait.promise;
  const reading = w.refresh(); await Promise.resolve();
  w.setContext(api.origin, '', false); wait.resolve(runtime); await reading;
  assert.equal(w.state.run, null); assert.equal(w.state.events.length, 0);
});
test('disconnect retains evidence, reconnect resumes its saved cursor and changing servers clears it', async (t) => {
  const run = record(), { w, api } = setup(t, { run }); await w.refresh();
  api.trace = async (taskId, runId, after) => after ? [] : [event(run, 1)]; await w.refresh();
  w.setContext(api.origin, task.id, false);
  assert.equal(w.state.run.id, run.id); assert.equal(w.state.events.length, 1); assert.equal(w.state.stream, 'disconnected');
  let afterRead; api.trace = async (taskId, runId, after) => { afterRead = after; return []; };
  w.setContext(api.origin, task.id, true); await w.refresh(); assert.equal(afterRead, 1);
  w.setContext('http://localhost:8999', task.id, false); assert.equal(w.state.run, null); assert.equal(w.state.events.length, 0);
});
