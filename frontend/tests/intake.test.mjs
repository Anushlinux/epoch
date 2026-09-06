import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { IntakeAPI, IntakeError, IntakeWorkspace, apiOrigin, taskRecord, requestPayload, PENDING_KEY } from '../src/intake-api.mjs';
const published = JSON.parse(readFileSync(new URL('../../backend/fixtures/development.json', import.meta.url)));
const model = (name) => structuredClone(published.examples.find((x) => x.model === name).value);
const memory = () => { const values = new Map(); return { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) }; };
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const taskFor = (payload) => ({ ...model('Task'), request: { ...payload, message: payload.message.trim(), project_id: payload.project_id.trim() } });
function setup(options = {}) {
  const storage = options.storage || memory();
  const calls = [];
  const api = { health: async () => model('HealthResponse'), list: async () => model('TaskList'), detail: async () => model('Task'), create: async (payload) => { calls.push(payload); return { task: taskFor(payload), status: 201 }; }, ...options.api };
  const workspace = new IntakeWorkspace({ storage, apiFactory: () => api });
  return { workspace, api, storage, calls };
}
test('published pending fixture maps exactly; future states/evidence never enter the intake view', () => {
  assert.deepEqual(taskRecord(model('Task')), model('Task'));
  for (const change of [{ status: 'completed' }, { schema_version: 2 }, { fixture_only: true }, { created_at: 'yesterday' }, { request: { ...model('TaskCreate'), revision: 1 } }])
    assert.throws(() => taskRecord({ ...model('Task'), ...change }), /contract/);
  assert.throws(() => taskRecord(model('Run')), /contract/);
});
test('loopback-only origin and input limits reject remote origins, credentials, blank and oversized content', () => {
  assert.equal(apiOrigin('http://127.0.0.1:8123/'), 'http://127.0.0.1:8123');
  for (const origin of ['https://example.com', 'http://localhost:80/path', 'http://u:p@localhost', 'http://localhost/?x=1']) assert.throws(() => apiOrigin(origin));
  for (const args of [[' ', 'demo'], ['a'.repeat(16001), 'demo'], ['a', 'x'.repeat(101)]]) assert.throws(() => requestPayload(...args));
  assert.equal(requestPayload('😀'.repeat(16000), 'demo').message.length, 32000);
});
test('API uses documented paths, exact submitted payload and no credentials; rejects mismatched acknowledgements', async () => {
  const calls = [];
  const payload = requestPayload(' keep this ', ' demo ');
  const api = new IntakeAPI('http://localhost:8000', async (url, opts) => { calls.push({ url, opts }); return new Response(JSON.stringify(taskFor(payload)), { status: 200 }); });
  assert.equal((await api.create(payload)).status, 200);
  assert.equal(calls[0].url, 'http://localhost:8000/api/tasks');
  assert.equal(calls[0].opts.body, JSON.stringify(payload));
  assert.equal(calls[0].opts.credentials, 'omit');
  api.fetcher = async () => new Response(JSON.stringify(model('Task')), { status: 201 });
  await assert.rejects(api.create(payload), /does not match/);
  await assert.rejects(api.detail(crypto.randomUUID()), /another task/);
});
test('HTTP error envelope preserves status/message; unsupported health and malformed bodies fail closed', async () => {
  const api = new IntakeAPI('http://localhost:8000', async () => new Response(JSON.stringify(model('ErrorEnvelope')), { status: 404 }));
  await assert.rejects(api.detail(model('Task').id), (e) => e.status === 404 && e.message === 'Task not found');
  api.fetcher = async () => new Response(JSON.stringify({ ...model('HealthResponse'), execution_enabled: true }));
  await assert.rejects(api.health(), /Unsupported/);
  api.fetcher = async () => new Response('not json');
  await assert.rejects(api.health(), /unreadable/);
});
test('submission freezes identity/payload before send; duplicate calls and edits cannot replace unresolved work', async () => {
  const wait = deferred();
  const { workspace: w, storage } = setup({ api: { create: () => wait.promise } });
  await w.connect();
  const send = w.submit('original', 'demo');
  const pending = w.state.pending;
  assert.equal(JSON.parse(storage.getItem(PENDING_KEY)).payload.message, 'original');
  assert.ok(Object.isFrozen(pending.payload));
  await w.submit('edited', 'new-project');
  assert.equal(w.state.pending, pending);
  wait.reject(new IntakeError('Connection lost'));
  await send;
  assert.equal(w.state.submission, 'unknown');
  await w.submit('edited', 'demo');
  assert.equal(w.state.pending, pending);
});
test('unknown acknowledgement survives reload; reconnect is read-only and identical retry reconciles 200', async () => {
  const { workspace: w, storage, calls } = setup();
  await w.connect();
  w.api.create = async (payload) => { calls.push(payload); throw new IntakeError('lost'); };
  await w.submit('original', 'demo');
  const frozen = w.state.pending.payload;
  const recovered = setup({ storage });
  assert.equal(recovered.workspace.state.submission, 'unknown');
  assert.deepEqual(recovered.workspace.state.pending.payload, frozen);
  await recovered.workspace.connect();
  assert.equal(recovered.calls.length, 0);
  recovered.api.create = async (payload) => { recovered.calls.push(payload); return { task: taskFor(payload), status: 200 }; };
  await recovered.workspace.retry();
  assert.deepEqual(recovered.calls, [frozen]);
  assert.match(recovered.workspace.state.notice, /No new task/);
  assert.equal(storage.getItem(PENDING_KEY), null);
});
test('unrecoverable identity blocks submission; storage failure refuses before HTTP and preserves draft inputs', async () => {
  const storage = memory(); storage.setItem(PENDING_KEY, '{broken');
  const corrupt = setup({ storage }); await corrupt.workspace.connect(); await corrupt.workspace.submit('text', 'demo');
  assert.equal(corrupt.workspace.state.recovery, true); assert.equal(corrupt.calls.length, 0);
  const working = setup(); await working.workspace.connect();
  working.storage.setItem = () => { throw new Error('full'); };
  await working.workspace.submit('keep draft', 'demo');
  assert.equal(working.calls.length, 0); assert.match(working.workspace.state.error, /Nothing was sent/);
});
test('409 and 422 require explicit return to draft; new ID is never issued automatically', async () => {
  for (const status of [409, 422]) {
    const { workspace: w, api } = setup({ api: { create: async () => { throw new IntakeError('Rejected', status); } } });
    await w.connect(); await w.submit('text', 'demo'); const id = w.state.pending.payload.client_request_id;
    assert.equal(w.state.submission, 'rejected');
    await w.submit('changed', 'demo'); await w.retry(); assert.equal(w.state.pending.payload.client_request_id, id);
    w.editRejected(); api.create = async (payload) => ({ task: taskFor(payload), status: 201 });
    await w.submit('changed', 'demo'); assert.notEqual(w.state.task.request.client_request_id, id);
  }
});
test('pending identity is bound to its API origin; reconnect failure preserves uncertainty and stored evidence', async () => {
  const { workspace: w, api } = setup({ api: { create: async () => { throw new IntakeError('lost'); } } });
  await w.connect(); await w.read(model('Task').id); await w.submit('text', 'demo');
  await w.connect('http://localhost:9999');
  assert.equal(w.state.origin, 'http://127.0.0.1:8000');
  api.health = async () => { throw new IntakeError('server stopped'); };
  await w.connect(); assert.equal(w.state.connected, false); assert.equal(w.state.task.id, model('Task').id); assert.ok(w.state.pending);
});
test('late duplicate/stale detail responses cannot replace a newer selection', async () => {
  const { workspace: w, api } = setup(); await w.connect();
  const older = deferred(), newer = deferred(); const firstID = crypto.randomUUID(), secondID = crypto.randomUUID();
  api.detail = (id) => id === firstID ? older.promise : newer.promise;
  const a = w.read(firstID), b = w.read(secondID);
  newer.resolve({ ...model('Task'), id: secondID }); await b;
  older.resolve({ ...model('Task'), id: firstID }); await a;
  assert.equal(w.state.task.id, secondID);
});
test('failed acknowledgement validation is uncertain and never becomes task success', async () => {
  const { workspace: w } = setup({ api: { create: async () => { throw new IntakeError('mismatched acknowledgement', 0, 'contract'); } } });
  await w.connect(); await w.submit('text', 'demo');
  assert.equal(w.state.submission, 'unknown'); assert.equal(w.state.task, null); assert.ok(w.state.pending);
});
test('missing selected task does not block a healthy reconnect; old detail stays explicitly unavailable until read again', async () => {
  const { workspace: w, api, calls } = setup();
  await w.connect(); await w.read(model('Task').id);
  const old = structuredClone(w.state.task);
  api.detail = async () => { throw new IntakeError('Task not found', 404); };
  await w.read(old.id);
  assert.equal(w.state.taskUnavailable, true);
  await w.connect();
  assert.equal(w.state.connected, true);
  assert.deepEqual(w.state.task, old);
  assert.equal(w.state.taskUnavailable, true);
  assert.match(w.state.error, /404/);
  assert.equal(calls.length, 0);
  api.detail = async () => old;
  await w.read(old.id);
  assert.equal(w.state.taskUnavailable, false);
});
test('changing API origin clears the previous servers saved notice and selected receipt', async () => {
  const { workspace: w } = setup(); await w.connect(); await w.submit('Saved on first server', 'demo');
  assert.match(w.state.notice, /Request saved/);
  await w.connect('http://localhost:8999');
  assert.equal(w.state.connected, true);
  assert.equal(w.state.task, null);
  assert.equal(w.state.notice, '');
  assert.equal(w.state.submission, 'idle');
});
