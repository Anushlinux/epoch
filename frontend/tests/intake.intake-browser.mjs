import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
const api = process.env.EPOCH_INTAKE_TEST_ORIGIN;
const origin = 'http://localhost:5173';
const key = 'epoch.intake.pending.v1';
const mime = { '.html': 'text/html', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };
const payload = (message) => ({ client_request_id: crypto.randomUUID(), message, project_id: 'browser-proof' });
async function post(data) {
  const response = await fetch(`${api}/api/tasks`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  return { status: response.status, task: await response.json() };
}
async function total() { return (await (await fetch(`${api}/api/tasks?limit=20&offset=0`)).json()).total; }
async function connect(page) {
  const field = page.getByRole('textbox', { name: 'API origin' });
  if (await field.isEnabled()) await field.fill(api);
  await page.getByRole('button', { name: 'Connect / reconnect' }).click();
  await expect(page.getByText('Connected · local API', { exact: true })).toBeVisible();
}
async function open(page) {
  await page.goto(`${origin}/index.html`);
}
test.beforeEach(async ({ page, context }) => {
  await context.grantPermissions(['local-network-access'], { origin });
  await page.route(`${origin}/**`, async (route) => {
    const url = new URL(route.request().url());
    const file = path.resolve(root, `.${decodeURIComponent(url.pathname)}`);
    if (!file.startsWith(root)) return route.abort();
    try { return route.fulfill({ body: await readFile(file), contentType: mime[path.extname(file)] || 'text/plain' }); }
    catch { return route.fulfill({ status: 404, body: 'Missing frontend source' }); }
  });
});

test('actual intake/list/detail, form validation, saved text, keyboard and responsive layout', async ({ page }, info) => {
  const errors = []; page.on('pageerror', (error) => errors.push(error.message));
  await open(page);
  await page.keyboard.press('Tab'); await expect(page.getByRole('link', { name: 'Skip to workspace' })).toBeFocused();
  await page.keyboard.press('Enter'); await expect(page.locator('#workspace')).toBeFocused();
  await expect(page.getByRole('button', { name: 'Save request', exact: true })).toBeDisabled();
  await connect(page);
  await expect(page.getByText('Persisted HTTP intake proof · no execution', { exact: true })).toBeVisible();
  const message = `Prepare the Atlas release checklist · ${info.project.name}\nKeep QA ownership and rollback steps. <script>unsafe()</script>`;
  const input = page.getByRole('textbox', { name: 'What needs to be done?' });
  await input.fill(' '); await page.getByRole('button', { name: 'Save request', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('1–16,000');
  await input.fill(message); await page.getByRole('textbox', { name: 'Project label' }).fill('Atlas 2.4');
  const before = await total();
  await page.getByRole('button', { name: 'Save request', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Saved request detail', exact: true })).toBeVisible();
  await expect(page.locator('.intake-detail blockquote')).toHaveText(message);
  await expect(input).toHaveValue('');
  expect(await total()).toBe(before + 1);
  await expect(page.locator('.intake-detail')).toContainText('Pending · no execution');
  await page.getByText('Inspect API record · intake only', { exact: true }).click();
  const task = JSON.parse(await page.locator('#task-record').textContent());
  expect(task.status).toBe('pending'); expect(task.request.message).toBe(message);
  const actual = await (await fetch(`${api}/api/tasks/${task.id}`)).json(); expect(actual).toEqual(task);
  await page.getByText('Inspect API record · intake only', { exact: true }).click();
  await page.getByRole('button', { name: 'Reload detail' }).click();
  await expect(page.locator('.intake-detail blockquote')).toHaveText(message);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.evaluate(() => { document.activeElement.blur(); window.scrollTo(0, 0); });
  await page.screenshot({ path: `evidence/intake-${info.project.name}.png`, fullPage: true });
  await page.reload(); await connect(page);
  await page.getByRole('button').filter({ hasText: message }).click();
  await expect(page.locator('.intake-detail blockquote')).toHaveText(message);
  await expect(page.getByRole('heading', { name: 'Saved request detail', exact: true })).toBeFocused();
});

test('actual 201 acknowledgement is dropped; reload/reconnect sends no POST; frozen retry returns same task with 200', async ({ page }) => {
  await open(page); await connect(page);
  const before = await total(); let sent, createdID;
  await page.route(`${api}/api/tasks`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    sent = route.request().postDataJSON();
    const response = await route.fetch(); expect(response.status()).toBe(201); createdID = (await response.json()).id;
    await route.abort('failed');
  }, { times: 1 });
  await page.getByRole('textbox', { name: 'What needs to be done?' }).fill('Keep this exact pending request');
  await page.getByRole('button', { name: 'Save request', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Acknowledgement unknown');
  await expect(page.getByRole('textbox', { name: 'What needs to be done?' })).toBeDisabled();
  const stored = await page.evaluate((key) => JSON.parse(sessionStorage.getItem(key)), key);
  expect(stored.payload).toEqual(sent);
  let posts = 0; page.on('request', (r) => { if (r.method() === 'POST') posts++; });
  await page.reload(); await connect(page); expect(posts).toBe(0);
  const response = page.waitForResponse((r) => r.url() === `${api}/api/tasks` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Retry exact submission' }).click();
  expect((await response).status()).toBe(200);
  await expect(page.locator('.intake-notice').filter({ hasText: 'Existing request confirmed by an identical retry. No new task was created.' })).toBeVisible();
  expect(await total()).toBe(before + 1);
  expect(await page.evaluate((key) => sessionStorage.getItem(key), key)).toBeNull();
  await page.getByText('Inspect API record · intake only').click();
  expect(JSON.parse(await page.locator('#task-record').textContent()).id).toBe(createdID);
});

test('real 409 conflict keeps identity until explicit edit; corrupted reload blocks all submissions', async ({ page }) => {
  const original = payload('Original already saved'); const saved = await post(original); expect(saved.status).toBe(201);
  await page.addInitScript(({ key, api, original }) => sessionStorage.setItem(key, JSON.stringify({ version: 1, origin: api, payload: { ...original, message: 'Changed content under existing ID' } })), { key, api, original });
  await open(page); await connect(page);
  const before = await total();
  await page.getByRole('button', { name: 'Retry exact submission' }).click();
  await expect(page.getByRole('alert')).toContainText('HTTP 409');
  await expect(page.getByRole('textbox', { name: 'What needs to be done?' })).toBeDisabled();
  expect(await total()).toBe(before);
  await page.getByRole('button', { name: 'Return rejected content to draft' }).click();
  await expect(page.getByRole('textbox', { name: 'What needs to be done?' })).toBeFocused();
  await expect(page.getByRole('textbox', { name: 'What needs to be done?' })).toHaveValue('Changed content under existing ID');
  await page.addInitScript((key) => sessionStorage.setItem(key, '{broken'), key);
  await page.reload(); await connect(page);
  await expect(page.getByText(/Recovery identity is unavailable/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save request', exact: true })).toBeDisabled();
  expect(await total()).toBe(before);
});

test('browser offline read keeps stale records and draft; reconnect uses real health/list and sends no work', async ({ page, context }) => {
  await open(page); await connect(page);
  await page.getByRole('textbox', { name: 'What needs to be done?' }).fill('Unsaved draft survives disconnection');
  const before = await total();
  await context.setOffline(true);
  await page.getByRole('button', { name: 'Refresh list', exact: true }).click();
  await expect(page.getByText('Last loaded records · connection unavailable')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save request', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Connect / reconnect' }).click();
  await expect(page.getByRole('alert')).toContainText('could not be reached');
  await context.setOffline(false); await connect(page);
  await expect(page.getByRole('textbox', { name: 'What needs to be done?' })).toHaveValue('Unsaved draft survives disconnection');
  expect(await total()).toBe(before);
});

test('actual server 422 after a deliberately fault-mutated body is displayed without success or replacement', async ({ page }) => {
  await open(page); await connect(page);
  const before = await total();
  await page.route(`${api}/api/tasks`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    const body = route.request().postDataJSON();
    const response = await route.fetch({ postData: JSON.stringify({ ...body, message: ' ' }) });
    expect(response.status()).toBe(422); await route.fulfill({ response });
  }, { times: 1 });
  await page.getByRole('textbox', { name: 'What needs to be done?' }).fill('Preserve the input despite a rejected transport payload');
  await page.getByRole('button', { name: 'Save request', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('HTTP 422');
  await expect(page.getByRole('heading', { name: 'Saved request detail', exact: true })).toHaveCount(0);
  expect(await total()).toBe(before);
});

test('a missing-detail response marks the retained receipt unavailable without blocking health/list reconnect', async ({ page }) => {
  const saved = await post(payload('Retain this receipt if the detail becomes unavailable'));
  await open(page); await connect(page);
  await page.locator(`[data-task="${saved.task.id}"]`).click();
  await page.route(`${api}/api/tasks/${saved.task.id}`, async (route) => {
    // Deliberately substitute a real server 404; no stored task is deleted.
    const response = await route.fetch({ url: `${api}/api/tasks/${crypto.randomUUID()}` });
    expect(response.status()).toBe(404); await route.fulfill({ response });
  });
  const before = await total();
  await page.getByRole('button', { name: 'Reload detail' }).click();
  await expect(page.getByText('Unavailable · last loaded record', { exact: true })).toBeVisible();
  await expect(page.locator('.intake-detail')).toContainText('not a current stored record');
  await page.locator('.intake-connection > summary').click();
  await page.getByRole('button', { name: 'Refresh connection' }).click();
  await expect(page.getByText('Connected · local API', { exact: true })).toBeVisible();
  await expect(page.getByText('Unavailable · last loaded record', { exact: true })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('HTTP 404');
  await expect(page.getByRole('button', { name: 'Save request', exact: true })).toBeEnabled();
  expect(await total()).toBe(before);
  await page.unroute(`${api}/api/tasks/${saved.task.id}`);
  await page.getByRole('button', { name: 'Reload detail' }).click();
  await expect(page.getByText('Unavailable · last loaded record', { exact: true })).toHaveCount(0);
  await expect(page.locator('.intake-detail')).toContainText('Pending · no execution');
});
