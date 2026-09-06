import test from 'node:test';
import assert from 'node:assert/strict';
import { ChatWorkspace, CHAT_PENDING_KEY } from '../src/chat-api.mjs';
import { IntakeError } from '../src/intake-api.mjs';

const memory = () => { const values = new Map(); return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }; };
function setup(t, { storage = memory(), loseAck = false, loseDebuggerAck = false } = {}) {
  const calls = [];
  let chat = null, operation = null;
  const api = {
    health: async () => ({}),
    async call(path, payload) {
      calls.push({ path, payload: payload && structuredClone(payload) });
      if (path === '/api/chats' && payload) {
        chat = { id: crypto.randomUUID(), ...payload, title: 'New chat', messages: [], operations: [] };
        return { body: chat };
      }
      if (path.endsWith('/messages') && payload) {
        if (operation?.client_request_id !== payload.client_request_id) operation = { id: crypto.randomUUID(), chat_id: chat.id, client_request_id: payload.client_request_id, status: 'completed' };
        if (loseAck) { loseAck = false; throw new IntakeError('Connection lost'); }
        return { body: operation };
      }
      if (path.endsWith('/debugger') && payload) {
        if (loseDebuggerAck) { loseDebuggerAck = false; throw new IntakeError('Connection lost'); }
        return { body: { id: crypto.randomUUID(), chat_id: chat.id, client_request_id: payload.client_request_id, status: 'completed', kind: 'debugger' } };
      }
      if (path.startsWith('/api/chats?')) return { body: { items: chat ? [chat] : [], total: chat ? 1 : 0 } };
      if (path === '/api/runtime') return { body: { execution_enabled: true, active_run_id: null } };
      if (path === `/api/chats/${chat?.id}`) return { body: chat };
      throw new Error(`Unexpected endpoint: ${path}`);
    },
  };
  const workspace = new ChatWorkspace({ storage, apiFactory: () => api, pollMs: 60000 });
  t.after(() => workspace.stop());
  return { workspace, calls, storage };
}

test('ordinary chat sends only conversation and message requests, never task, release or investigation commands', async t => {
  const { workspace: w, calls } = setup(t);
  await w.connect();
  assert.equal(calls.filter(c => c.payload).length, 0, 'connecting is read-only');
  assert.equal(await w.send('Explain why my data import failed.', 'research'), true);
  const writes = calls.filter(c => c.payload);
  assert.deepEqual(writes.map(c => c.path), ['/api/chats', `/api/chats/${w.state.selected}/messages`]);
  assert.deepEqual(Object.keys(writes[0].payload).sort(), ['client_request_id', 'project_id']);
  assert.deepEqual(Object.keys(writes[1].payload).sort(), ['client_request_id', 'content']);
  assert.equal(writes[1].payload.content, 'Explain why my data import failed.');
  assert.equal(writes[0].payload.project_id, 'research');
  await w.send('What should I check next?', 'research');
  assert.equal(calls.filter(c => c.payload).length, 3);
  assert.equal(calls.filter(c => c.payload).at(-1).path, `/api/chats/${w.state.selected}/messages`);
});

test('uncertain chat acknowledgement survives reload; reconnect never replays and exact retry keeps identity', async t => {
  const first = setup(t, { loseAck: true });
  await first.workspace.connect();
  assert.equal(await first.workspace.send('Keep my original question.'), false);
  const pending = JSON.parse(first.storage.getItem(CHAT_PENDING_KEY));
  assert.ok(pending.chatId);
  assert.equal(await first.workspace.send('A different question'), false);
  const restored = new ChatWorkspace({ storage: first.storage, apiFactory: () => first.workspace.api, pollMs: 60000 });
  t.after(() => restored.stop());
  const before = first.calls.filter(c => c.payload).length;
  await restored.connect();
  assert.equal(first.calls.filter(c => c.payload).length, before);
  assert.equal(await restored.retry(), true);
  const writes = first.calls.filter(c => c.payload);
  assert.deepEqual(writes.at(-1), writes.at(-2));
  assert.equal(first.storage.getItem(CHAT_PENDING_KEY), null);
});

test('invalid input and unreadable recovery storage cannot create chat operations', async t => {
  const { workspace: w, calls } = setup(t);
  await w.connect();
  assert.equal(await w.send(' '), false);
  assert.equal(await w.send('x'.repeat(16001)), false);
  assert.equal(await w.send('hello', '../other'), false);
  assert.equal(calls.filter(c => c.payload).length, 0);
  const storage = memory(); storage.setItem(CHAT_PENDING_KEY, '{broken');
  const recovered = setup(t, { storage }); await recovered.workspace.connect();
  assert.equal(await recovered.workspace.send('hello'), false);
  assert.equal(recovered.calls.filter(c => c.payload).length, 0);
});


test('debugger recovery retains its endpoint and identity, including an optional blank question', async t => {
  for (const question of ['', 'Why did the original import fail?']) {
    const first = setup(t, { loseDebuggerAck: true });
    await first.workspace.connect();
    await first.workspace.send('Preserve all imported records.');
    const chatId = first.workspace.state.chat.id;
    assert.equal(await first.workspace.investigate(question), false);
    const pending = JSON.parse(first.storage.getItem(CHAT_PENDING_KEY));
    assert.equal(pending.kind, 'debugger');
    assert.equal(pending.chatId, chatId);
    const original = first.calls.filter(c => c.payload).at(-1);
    assert.equal(original.path, `/api/chats/${chatId}/debugger`);
    assert.deepEqual(original.payload, { client_request_id: pending.message.client_request_id, ...(question ? { question } : {}) });
    const restored = new ChatWorkspace({ storage: first.storage, apiFactory: () => first.workspace.api, pollMs: 60000 });
    t.after(() => restored.stop());
    const before = first.calls.filter(c => c.payload).length;
    await restored.connect();
    assert.equal(first.calls.filter(c => c.payload).length, before, 'reload never investigates automatically');
    assert.equal(await restored.send('Do not change the pending operation'), false);
    assert.equal(await restored.retry(), true);
    assert.deepEqual(first.calls.filter(c => c.payload).at(-1), original);
    assert.equal(first.calls.filter(c => c.payload && c.path.endsWith('/messages')).length, 1);
    assert.equal(first.storage.getItem(CHAT_PENDING_KEY), null);
  }
});

test('polls only active chat detail, refreshes runtime once on failure, then stays idle', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const calls = [], id = crypto.randomUUID();
  const operation = { id: crypto.randomUUID(), chat_id: id, status: 'running' };
  const chat = { id, title: 'Question', messages: [], operations: [operation] };
  const api = { health: async () => ({}), call: async path => {
    calls.push(path);
    if (path.startsWith('/api/chats?')) return { body: { items: [chat], total: 1 } };
    if (path === '/api/runtime') return { body: { execution_enabled: true, active_run_id: operation.status === 'running' ? operation.id : null } };
    return { body: structuredClone(chat) };
  } };
  const w = new ChatWorkspace({ storage: memory(), apiFactory: () => api });
  t.after(() => w.stop());
  w.state.selected = id;
  await w.connect();
  assert.equal(calls.length, 3);
  t.mock.timers.tick(1500);
  await new Promise(setImmediate);
  assert.deepEqual(calls.slice(3), [`/api/chats/${id}`]);
  operation.status = 'failed';
  t.mock.timers.tick(1500);
  await new Promise(setImmediate);
  assert.deepEqual(calls.slice(4), [`/api/chats/${id}`, '/api/runtime']);
  assert.equal(w.state.chat.operations[0].status, 'failed');
  t.mock.timers.tick(60000);
  await new Promise(setImmediate);
  assert.equal(calls.length, 6, 'failed conversations schedule no background requests');
  await w.setVisible(false);
  await w.setVisible(true);
  assert.equal(calls.length, 9, 'returning to a visible tab refreshes read-only once');
  t.mock.timers.tick(60000);
  assert.equal(calls.length, 9);
});

test('hidden tabs pause active polling and overlapping refreshes never overlap HTTP batches', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const calls = [], id = crypto.randomUUID();
  const chat = { id, title: 'Question', messages: [], operations: [{ id: crypto.randomUUID(), chat_id: id, status: 'running' }] };
  let release, defer = false;
  const api = { health: async () => ({}), call: async path => {
    calls.push(path);
    if (path.startsWith('/api/chats?')) return { body: { items: [chat], total: 1 } };
    if (path === '/api/runtime') return { body: { active_run_id: chat.operations[0].id } };
    if (defer) await new Promise(resolve => { release = resolve; });
    return { body: structuredClone(chat) };
  } };
  const w = new ChatWorkspace({ storage: memory(), apiFactory: () => api });
  t.after(() => w.stop()); w.state.selected = id;
  await w.connect();
  await w.setVisible(false);
  t.mock.timers.tick(60000); await new Promise(setImmediate);
  assert.equal(calls.length, 3);
  await w.setVisible(true);
  assert.equal(calls.length, 6);
  defer = true;
  const first = w.refresh({ poll: true });
  const second = w.refresh({ poll: true });
  assert.equal(calls.length, 7, 'second poll shares the outstanding read');
  defer = false; release();
  await Promise.all([first, second]);
  assert.equal(calls.length, 7);
});
