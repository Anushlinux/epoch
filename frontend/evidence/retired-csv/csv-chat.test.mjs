import test from 'node:test';
import assert from 'node:assert/strict';
import { ChatWorkspace, CHAT_PENDING_KEY } from '../src/chat-api.mjs';
import { IntakeError } from '../src/intake-api.mjs';
import { repairView } from '../src/chat-repair.mjs';
const memory = () => { const values = new Map(); return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }; };
function fixture(t, { loseCreate = false, mismatch = false, loseRepair = false } = {}) {
  const storage = memory(), calls = [], chats = new Map();
  let chat;
  const api = { health: async () => ({}), async call(path, payload) {
    calls.push({ path, payload: payload && structuredClone(payload) });
    if (path === '/api/chats' && payload) {
      chat = chats.get(payload.client_request_id);
      if (!chat) {
        chat = { id: crypto.randomUUID(), ...payload, environment: mismatch ? 'csv_healthy' : payload.environment ?? 'default', title: 'CSV import', messages: [], operations: [] };
        chats.set(payload.client_request_id, chat);
      }
      if (loseCreate) { loseCreate = false; throw new IntakeError('Creation acknowledgement lost'); }
      return { body: structuredClone(chat) };
    }
    if (path.endsWith('/messages') && payload) return { body: { id: crypto.randomUUID(), chat_id: chat.id, client_request_id: payload.client_request_id, kind: 'chat', status: 'completed' } };
    if (path.endsWith('/csv-repair') && payload) {
      if (loseRepair) { loseRepair = false; throw new IntakeError('Repair acknowledgement lost'); }
      return { body: { id: crypto.randomUUID(), chat_id: chat.id, client_request_id: payload.client_request_id, kind: 'debugger', action: 'repair', status: 'completed' } };
    }
    if (path.startsWith('/api/chats?')) return { body: { items: chat ? [chat] : [], total: chat ? 1 : 0 } };
    if (path === '/api/runtime') return { body: { execution_enabled: true, active_run_id: null } };
    if (path === `/api/chats/${chat?.id}`) return { body: structuredClone(chat) };
    if (path.endsWith('/environment')) return { body: { environment: chat.environment, simulated: true, adapter_mode: chat.environment === 'csv_broken' ? 'broken' : 'healthy', customers: [], imports: [], criteria: [], verification: { passed: false, checks: [] }, repair_capability: { supported: true, eligible: true } } };
    throw new Error(`Unexpected endpoint ${path}`);
  } };
  const workspace = new ChatWorkspace({ storage, apiFactory: () => api });
  t.after(() => workspace.stop());
  return { workspace, api, calls, chats, storage };
}

test('CSV creation acknowledgement loss freezes the chosen environment and retries exactly once under the same identity', async t => {
  const f = fixture(t, { loseCreate: true });
  await f.workspace.connect();
  assert.equal(await f.workspace.send('Import the sample CSV without changing existing customers.', 'customers', 'csv_broken'), false);
  const saved = JSON.parse(f.storage.getItem(CHAT_PENDING_KEY));
  assert.equal(saved.create.environment, 'csv_broken');
  assert.equal(saved.chatId, null);
  assert.equal(await f.workspace.send('Different task', 'other', 'csv_healthy'), false);
  const recovered = new ChatWorkspace({ storage: f.storage, apiFactory: () => f.api });
  t.after(() => recovered.stop());
  await recovered.connect();
  assert.equal(f.calls.filter(c => c.payload).length, 1, 'read-only reconnect does not create or send');
  assert.equal(await recovered.retry(), true);
  const writes = f.calls.filter(c => c.payload);
  assert.deepEqual(writes[0], writes[1]);
  assert.equal(writes[2].path, `/api/chats/${recovered.state.selected}/messages`);
  assert.equal(writes[2].payload.content, saved.message.content);
  assert.equal(f.chats.size, 1);
  assert.equal(recovered.state.chat.environment, 'csv_broken');
  assert.equal(f.storage.getItem(CHAT_PENDING_KEY), null);
  await recovered.send('Inspect the failed result.', 'customers', 'csv_healthy');
  assert.equal(f.calls.filter(c => c.payload && c.path === '/api/chats').length, 2, 'later messages do not recreate or change the environment');
  assert.equal(recovered.state.chat.environment, 'csv_broken');
});

test('repair acknowledgement recovery retains the exact repair endpoint and request identity', async t => {
  const f = fixture(t, { loseRepair: true });
  await f.workspace.connect();
  await f.workspace.send('Import sample customers.', 'demo', 'csv_broken');
  assert.equal(await f.workspace.repair(), false);
  const frozen = JSON.parse(f.storage.getItem(CHAT_PENDING_KEY));
  assert.equal(frozen.kind, 'repair');
  const recovered = new ChatWorkspace({ storage: f.storage, apiFactory: () => f.api });
  t.after(() => recovered.stop());
  const count = f.calls.filter(c => c.payload).length;
  await recovered.connect();
  assert.equal(f.calls.filter(c => c.payload).length, count, 'reload never executes repair');
  assert.equal(await recovered.retry(), true);
  const repairs = f.calls.filter(c => c.path.endsWith('/csv-repair') && c.payload);
  assert.equal(repairs.length, 2);
  assert.deepEqual(repairs[0], repairs[1]);
  assert.equal(f.calls.some(c => c.path.endsWith('/debugger')), false);
});

test('repair UI distinguishes old server, eligible action, verification and rejected or published results', () => {
  const state = { chat: { environment: 'csv_broken', operations: [] }, runtime: { debugger: { available: true }, execution_enabled: true }, environment: {} };
  assert.match(repairView(state, false), /Restart the backend/);
  assert.match(repairView(state, false), /data-action="repair-csv" disabled/);
  state.environment.repair_capability = { supported: true, eligible: true };
  assert.doesNotMatch(repairView(state, false), /data-action="repair-csv" disabled/);
  state.chat.operations.push({ action: 'repair', status: 'running', activity: 'Hermes is verifying the original task', analysis: { answer: 'A diagnosis is already available.' } });
  assert.match(repairView(state, true), /role="status" aria-live="polite">Hermes is verifying/);
  const operation = state.chat.operations[0];
  operation.status = 'completed';
  operation.analysis.repair_result = { status: 'rejected', error: '<untrusted>' };
  assert.match(repairView(state, false), /Repair rejected/);
  assert.match(repairView(state, false), /&lt;untrusted&gt;/);
  operation.analysis.repair_result.status = 'published';
  operation.analysis.recovery = { executor: { success: false }, verification: { passed: false } };
  assert.match(repairView(state, false), /Repair published/);
  assert.match(repairView(state, false), /recovery did not complete successfully/);
  assert.doesNotMatch(repairView(state, false), /customer checks passed/);
});

test('mismatched environment acknowledgement blocks the message and keeps recovery evidence', async t => {
  const f = fixture(t, { mismatch: true });
  await f.workspace.connect();
  assert.equal(await f.workspace.send('Import customers.', 'customers', 'csv_broken'), false);
  assert.equal(f.calls.filter(c => c.payload).length, 1);
  assert.equal(f.workspace.state.pending.create.environment, 'csv_broken');
  assert.ok(f.storage.getItem(CHAT_PENDING_KEY));
  assert.equal(f.calls.some(c => c.path.endsWith('/messages')), false);
});

test('unsupported environments are rejected before sending; default chat preserves the existing request shape', async t => {
  const f = fixture(t); await f.workspace.connect();
  assert.equal(await f.workspace.send('Import customers.', 'customers', 'csv_unknown'), false);
  assert.equal(f.calls.filter(c => c.payload).length, 0);
  assert.equal(await f.workspace.send('Hello', 'customers'), true);
  const create = f.calls.find(c => c.path === '/api/chats' && c.payload);
  assert.deepEqual(Object.keys(create.payload).sort(), ['client_request_id', 'project_id']);
  assert.equal(f.calls.some(c => c.path.endsWith('/environment')), false);
});

test('CSV evidence follows the host verdict and unavailable evidence never becomes a passing check', async t => {
  const f = fixture(t); await f.workspace.connect();
  await f.workspace.send('Import customers.', 'customers', 'csv_healthy');
  const original = f.api.call;
  const expected = { environment: 'csv_healthy', simulated: true, customers: [], imports: [], criteria: ['Preserve timestamps'], verification: { passed: false, checks: [{ name: 'Source timestamps preserved', passed: false }] } };
  f.api.call = async (path, payload) => path.endsWith('/environment') ? { body: expected } : original(path, payload);
  await f.workspace.refresh();
  assert.deepEqual(f.workspace.state.environment.verification, expected.verification, 'healthy selection alone cannot turn a failed backend check into success');
  f.api.call = async (path, payload) => { if (path.endsWith('/environment')) throw new IntakeError('Evidence unavailable', 503); return original(path, payload); };
  await f.workspace.refresh();
  assert.match(f.workspace.state.environmentError, /Evidence unavailable/);
  assert.notEqual(f.workspace.state.environment?.verification.passed, true);
  assert.equal(f.calls.filter(c => c.payload).length, 2);
});
