// Browser controller regression with intercepted API responses. No Hermes, Luna or release run executes.
import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
const origin = 'http://127.0.0.1:5173', api = 'http://127.0.0.1:8000';
const types = { '.html': 'text/html', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.ttf': 'font/ttf' };
const timestamp = '2026-09-06T12:00:00Z';
// Replay genuine local sandbox snapshots to verify rendering; this browser run does not execute tools.
const csvEvidence = JSON.parse(await readFile(new URL('../../backend/fixtures/csv/local-evidence.json', import.meta.url), 'utf8'));
async function mockWorkspace(page) {
  const calls = [], errors = [];
  let chat, environment;
  const environmentFor = selected => {
    const snapshot = structuredClone(csvEvidence.results.find(result => result.mode === selected.replace('csv_', '')));
    const { mode, first_import, exact_retry, ...environment } = snapshot;
    return { ...environment, environment: selected, repair_capability: { supported: true, eligible: selected === 'csv_broken' } };
  };
  const runtime = { execution_enabled: true, hermes_available: true, supervision_enabled: true, debugger: { available: true }, active_run_id: null, automatic_repair: false, phase: 7 };
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin === api) {
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers: { 'access-control-allow-origin': origin, 'access-control-allow-methods': 'GET, POST', 'access-control-allow-headers': 'content-type' } });
      const payload = request.method() === 'POST' ? request.postDataJSON() : null;
      calls.push({ path: url.pathname, payload });
      let body, status = 200;
      if (url.pathname === '/api/health') body = { status: 'ok', phase: 7, storage: 'ok', execution_enabled: true };
      else if (url.pathname === '/api/runtime') body = runtime;
      else if (url.pathname === '/api/chats' && payload) {
        chat = { id: crypto.randomUUID(), ...payload, title: 'New chat', created_at: timestamp, updated_at: timestamp, messages: [], operations: [] };
        if (payload.environment?.startsWith('csv_')) environment = environmentFor(payload.environment);
        body = chat; status = 201;
      } else if (url.pathname === '/api/chats') body = { items: chat ? [chat] : [], total: chat ? 1 : 0, limit: 20, offset: 0 };
      else if (url.pathname === '/api/tasks') body = { items: [], total: 0, limit: 20, offset: 0 };
      else if (url.pathname === `/api/chats/${chat?.id}`) body = chat;
      else if (url.pathname === `/api/chats/${chat?.id}/environment`) body = environment;
      else if (url.pathname === `/api/chats/${chat?.id}/messages` && payload) {
        const operation = { id: crypto.randomUUID(), chat_id: chat.id, client_request_id: payload.client_request_id, status: 'completed', kind: 'chat', activity: 'Completed', created_at: timestamp, finished_at: timestamp };
        chat.messages.push({ id: crypto.randomUUID(), role: 'user', content: payload.content, operation_id: operation.id, created_at: timestamp }, { id: crypto.randomUUID(), role: 'assistant', agent: 'hermes', content: 'I will inspect the import error while preserving the source data.', operation_id: operation.id, created_at: timestamp });
        chat.title = chat.messages[0].content.slice(0, 100); chat.operations.push(operation); body = operation; status = 202;
      } else if (url.pathname === `/api/chats/${chat?.id}/debugger` && payload) {
        const operation = { id: crypto.randomUUID(), chat_id: chat.id, client_request_id: payload.client_request_id, status: 'completed', kind: 'debugger', activity: 'Completed', created_at: timestamp, finished_at: timestamp };
        chat.operations.push(operation); body = operation; status = 202;
      } else if (url.pathname === `/api/chats/${chat?.id}/csv-repair` && payload) {
        const operation = { id: crypto.randomUUID(), chat_id: chat.id, client_request_id: payload.client_request_id, status: 'running', kind: 'debugger', action: 'repair', activity: 'Hermes is verifying the original task in isolated state', analysis: { answer: 'The adapter mapping is incorrect.' } };
        chat.operations.push(operation); body = operation; status = 202;
      } else { status = 404; body = { error: { message: `Unmocked endpoint: ${url.pathname}` } }; }
      return route.fulfill({ status, json: body, headers: { 'access-control-allow-origin': origin } });
    }
    if (url.origin !== origin) return route.abort();
    const relative = ['/', '/chat', '/debugger', '/incidents'].includes(url.pathname) ? '/index.html' : url.pathname;
    const file = path.resolve(root, `.${relative}`);
    if (!file.startsWith(root)) return route.abort();
    try { return route.fulfill({ body: await readFile(file), contentType: types[path.extname(file)] || 'text/plain' }); }
    catch { return route.fulfill({ status: 404, body: 'Missing local file' }); }
  });
  return { calls, errors, runtime, environment: () => environment, chat: () => chat, writes: () => calls.filter(c => c.payload) };
}

test('CSV repair button executes only explicitly, shows progress and explains an old backend', async ({ page }, info) => {
  const state = await mockWorkspace(page);
  await page.goto(`${origin}/chat`);
  await page.locator('#chat-environment').selectOption('csv_broken');
  await page.getByRole('button', { name: 'Use sample task', exact: true }).click();
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await navigateDebugger(page);
  const action = page.locator('[data-action="repair-csv"]');
  await expect(action).toBeEnabled();
  const count = state.writes().length;
  await page.reload();
  await expect(action).toBeEnabled();
  expect(state.writes()).toHaveLength(count);
  await action.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `evidence/csv-repair-action-${info.project.name}.png` });
  await action.click();
  await expect(page.locator('.csv-repair-action')).toContainText('Hermes is verifying the original task');
  await expect(action).toBeDisabled();
  expect(state.writes().filter(c => c.path.endsWith('/csv-repair'))).toHaveLength(1);
  expect(state.writes().some(c => c.path.endsWith('/debugger'))).toBe(false);
  const operation = state.chat().operations.at(-1);
  operation.status = 'completed';
  operation.analysis.repair_result = { status: 'rejected', error: 'Fresh task verification failed.', checks: [{ name: 'fresh_hermes', passed: false }] };
  state.environment().repair_capability = { supported: true, eligible: false, reason: 'A repair was already attempted. Review its result below.' };
  await page.reload();
  await expect(page.locator('.csv-repair-action')).toContainText('Repair rejected');
  await expect(page.locator('.csv-repair-action')).toContainText('Fresh task verification failed.');
  delete state.environment().repair_capability;
  await page.reload();
  await expect(page.locator('.csv-repair-action')).toContainText('Restart the backend');
  await expect(action).toBeDisabled();
  expect(state.errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
async function navigateDebugger(page) {
  if (await page.locator('#sidebar').evaluate(el => el.inert || getComputedStyle(el).visibility === 'hidden'))
    await page.getByRole('button', { name: 'Toggle navigation' }).click();
  await page.locator('.primary-nav a[href^="/debugger"]').click();
}

test('normal chat and reload never start release or debugger; explicit investigation preserves the conversation', async ({ page }, info) => {
  const state = await mockWorkspace(page);
  await page.goto(`${origin}/chat`);
  await expect(page.getByRole('button', { name: 'Send message', exact: true })).toBeEnabled();
  expect(state.writes()).toEqual([]);
  const original = 'Investigate my CSV import failure. Preserve the source rows and do not delete records.';
  await page.locator('#chat-message').fill(original);
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('.chat-transcript')).toContainText(original);
  await page.locator('#chat-message').fill('Also preserve the original timestamps.');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('.chat-transcript')).toContainText('Also preserve the original timestamps.');
  await page.screenshot({ path: `evidence/generic-chat-${info.project.name}.png`, fullPage: true });
  const chatId = state.chat().id;
  expect(state.writes().map(c => c.path)).toEqual(['/api/chats', `/api/chats/${chatId}/messages`, `/api/chats/${chatId}/messages`]);
  expect(await page.locator('#release-form').count()).toBe(0);
  await page.reload();
  await expect(page.locator('.chat-transcript')).toContainText(original);
  expect(state.writes()).toHaveLength(3);
  await navigateDebugger(page);
  await expect(page).toHaveURL(new RegExp(`/debugger\\?chat=${chatId}$`));
  await expect(page.locator('#investigate-chat')).toBeEnabled();
  expect(state.writes()).toHaveLength(3);
  expect(await page.locator('#release-form').count()).toBe(0);
  await expect(page.locator('#workspace')).toContainText(original);
  await expect(page.locator('#workspace')).toContainText('Also preserve the original timestamps.');
  await page.locator('#page-scroll').evaluate(el => { el.scrollTop = 0; });
  await page.screenshot({ path: `evidence/manual-debugger-${info.project.name}.png`, fullPage: true });
  const messagesBefore = structuredClone(state.chat().messages);
  await page.locator('#debugger-question').fill('Why did the import fail under these existing requirements?');
  await page.locator('#investigate-chat').click();
  await expect.poll(() => state.writes().length).toBe(4);
  expect(state.writes().at(-1).path).toBe(`/api/chats/${chatId}/debugger`);
  expect(state.writes().at(-1).payload.question).toBe('Why did the import fail under these existing requirements?');
  expect(state.chat().messages).toEqual(messagesBefore);
  await page.reload();
  await expect(page.locator('#investigate-chat')).toBeVisible();
  expect(state.writes()).toHaveLength(4);
  expect(state.writes().some(c => /\/tasks|\/runs|release/.test(c.path))).toBe(false);
  expect(state.errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('default debugger is generic and release controls appear only in the separate demo', async ({ page }) => {
  const state = await mockWorkspace(page);
  await page.goto(`${origin}/debugger`);
  await expect(page.getByRole('heading', { name: /Debugger/, exact: true })).toBeVisible();
  expect(await page.locator('#release-form').count()).toBe(0);
  expect(state.writes()).toEqual([]);
  await page.goto(`${origin}/debugger?mode=release`);
  await expect(page.locator('#release-form')).toBeVisible();
  expect(state.writes()).toEqual([]);
  expect(state.errors).toEqual([]);
});


test('manual investigation remains available when the executor is disabled', async ({ page }) => {
  const state = await mockWorkspace(page);
  await page.goto(`${origin}/chat`);
  await page.locator('#chat-message').fill('Diagnose the existing import failure.');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect(page.locator('.chat-transcript')).toContainText('Diagnose the existing import failure.');
  state.runtime.execution_enabled = false;
  state.runtime.hermes_available = false;
  state.runtime.supervision_enabled = false;
  await page.goto(`${origin}/debugger?chat=${state.chat().id}`);
  await expect(page.locator('#investigate-chat')).toBeEnabled();
  expect(state.writes()).toHaveLength(2);
  await page.locator('#investigate-chat').click();
  await expect.poll(() => state.writes().length).toBe(3);
  expect(state.writes().at(-1).path).toBe(`/api/chats/${state.chat().id}/debugger`);
  expect(Object.keys(state.writes().at(-1).payload)).toEqual(['client_request_id']);
  expect(state.errors).toEqual([]);
});


for (const selected of ['csv_broken', 'csv_healthy']) {
  test(`CSV ${selected} requires explicit send, keeps its environment and displays backend checks in chat/debugger`, async ({ page }, info) => {
    const state = await mockWorkspace(page);
    await page.goto(`${origin}/chat`);
    await page.locator('#chat-environment').selectOption(selected);
    expect(state.writes()).toEqual([]);
    await page.getByRole('button', { name: 'Use sample task', exact: true }).click();
    const sample = await page.locator('#chat-message').inputValue();
    expect(sample).toMatch(/customers\.read_sample/);
    expect(sample).toMatch(/customers\.list/);
    expect(sample).toMatch(/names and email addresses/);
    expect(state.writes()).toEqual([]);
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    await expect(page.locator('[data-csv-environment]')).toBeVisible();
    const chatId = state.chat().id;
    expect(state.writes().map(c => c.path)).toEqual(['/api/chats', `/api/chats/${chatId}/messages`]);
    expect(state.writes()[0].payload.environment).toBe(selected);
    expect(state.writes()[1].payload.content).toBe(sample);
    expect(await page.locator('#chat-environment').count()).toBe(0);
    const panel = page.locator('[data-csv-environment]');
    await expect(panel.locator('.csv-verification')).toContainText('All source customers saved');
    await expect(panel.locator('.csv-verification')).toContainText('No duplicate email addresses');
    await expect(panel.locator('[data-csv-verdict]')).toHaveText(selected === 'csv_healthy' ? 'Passed' : 'Not passed');
    expect(state.environment().verification.passed).toBe(selected === 'csv_healthy');
    await expect(panel.locator('[data-customer-count]')).toHaveText(`Expected: 3 customers · Actually saved: ${selected === 'csv_healthy' ? 3 : 0}`);
    await page.locator('#page-scroll').evaluate(el => { el.scrollTop = 0; });
    await page.screenshot({ path: `evidence/csv-${selected}-${info.project.name}.png`, fullPage: true });
    await navigateDebugger(page);
    await expect(page.locator('[data-csv-environment] .csv-verification')).toContainText('Rejected imports saved no customers');
    await expect(page.locator('#investigate-chat')).toBeEnabled();
    expect(state.writes()).toHaveLength(2);
    await page.reload();
    await expect(page.locator('[data-csv-environment] .csv-verification')).toContainText('All source customers saved');
    expect(state.writes()).toHaveLength(2);
    expect(state.chat().environment).toBe(selected);
    expect(state.writes().some(c => /repair|publish|debugger|release/.test(c.path))).toBe(false);
    await expect(page.locator('[data-csv-environment]')).not.toContainText('Repair published');
    expect(state.errors).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
