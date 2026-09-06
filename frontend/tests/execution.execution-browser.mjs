// Real backend HTTP/SSE/storage/checks. The server runs an explicit test executor.
import { test, expect } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const api = process.env.EPOCH_INTAKE_TEST_ORIGIN;
const origin = process.env.EPOCH_INTAKE_FRONTEND_ORIGIN;
const pendingKey = 'epoch.execution.pending.v1';
async function connect(page) {
  await page.locator('.topbar').getByRole('button', { name: 'Connection settings' }).click();
  const field = page.getByRole('textbox', { name: 'API origin' });
  if (await field.isEnabled()) await field.fill(api);
  await page.getByRole('button', { name: 'Connect / reconnect' }).click();
  await expect(page.locator('.connection-state')).toHaveAttribute('title', 'Connected · local API');
}
async function create(page, message = 'Prepare the demo release <script>unsafe()</script>') {
  await page.goto(`${origin}/chat`);
  await connect(page);
  await page.getByRole('textbox', { name: 'What needs to be done?' }).fill(message);
  await page.getByRole('button', { name: 'Save request', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Saved request detail' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start release run' })).toBeEnabled();
  return new URL(page.url()).searchParams.get('task');
}
async function start(page, scenario = 'control', release = '2.4') {
  if (!(await page.getByRole('textbox', { name: 'Release', exact: true }).isVisible())) await page.locator('[data-key=another-release]>summary').click();
  await page.getByRole('textbox', { name: 'Release', exact: true }).fill(release);
  await page.getByLabel('Sandbox scenario').selectOption(scenario);
  await page.getByRole('button', { name: 'Start release run' }).click();
  await expect(page.locator('[data-run-id]')).toBeVisible();
  return page.locator('[data-run-id]').getAttribute('data-run-id');
}
async function runs(taskId) { return (await fetch(`${api}/api/tasks/${taskId}/runs`)).json(); }
async function finish(page, status) {
  await expect(page.locator('[data-run-status]')).toHaveText(status, { timeout: 15000 });
}

test('explicit release, named SSE, sourced checks, simulation objects, history and reload', async ({ page }, info) => {
  const errors = []; page.on('pageerror', (e) => errors.push(e.message));
  const taskId = await create(page);
  expect(await runs(taskId)).toEqual([]);
  let streams = 0;
  page.on('request', (r) => { if (r.url().includes('/events?after=')) streams++; });
  const runId = await start(page);
  await expect(page.locator('[data-run-status]')).toHaveText('running');
  await expect(page.locator('.live-checkpoints .badge')).toHaveText(['pending', 'pending', 'pending']);
  await page.getByRole('link', { name: 'Open debugger', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Release execution evidence' })).toBeVisible();
  await finish(page, 'completed');
  expect(streams).toBeGreaterThan(0);
  await expect(page.locator('[data-verdict]')).toHaveText('Trusted checks: passed');
  await expect(page.locator('.live-checkpoints .badge')).toHaveText(['verified', 'verified', 'verified']);
  await expect(page.locator('.simulated-effects')).toContainText('Tickets (1)');
  await expect(page.locator('.simulated-effects')).toContainText('Checklists (1)');
  await expect(page.locator('.simulated-effects')).toContainText('Messages (1)');
  await expect(page.locator('.executor-response')).toHaveText('Test double finished.');
  await expect(page.getByRole('heading', { name: 'Missing evidence' })).toBeVisible();
  expect(await page.locator('a[href^="simulated:"]').count()).toBe(0);
  const sequences = await page.locator('[data-sequence]').evaluateAll((els) => els.map((el) => Number(el.dataset.sequence)));
  expect(sequences).toEqual(Array.from({ length: sequences.length }, (_, i) => i + 1));
  expect(sequences.length).toBeGreaterThan(10);
  expect(errors).toEqual([]);
  await expect(page.getByText('Request saved. It is pending; execution has not started.', { exact: true })).toHaveCount(0);
  await expect(page.locator('.statusbar')).toContainText('Explicit release runs');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.evaluate(() => { document.querySelector('#page-scroll').scrollTop = 0; });
  await page.screenshot({ path: `evidence/phase3-execution-${info.project.name}.png`, fullPage: true });
  await page.locator('.trusted-result').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `evidence/phase3-results-${info.project.name}.png`, fullPage: true });
  let posts = 0; page.on('request', (r) => { if (r.method() === 'POST') posts++; });
  await page.reload(); await connect(page);
  await finish(page, 'completed');
  expect(await page.locator('[data-run-id]').getAttribute('data-run-id')).toBe(runId);
  expect(posts).toBe(0);
  expect(await runs(taskId)).toHaveLength(1);
  const secondId = await start(page, 'broken_checklist', '2.5');
  await finish(page, 'failed');
  await expect(page.locator('[data-verdict]')).toHaveText('Trusted checks: failed');
  await expect(page.locator('.simulated-effects')).toContainText('Tickets (1)');
  await expect(page.locator('.simulated-effects')).toContainText('Checklists (0)');
  expect(secondId).not.toBe(runId);
  const evidence = await Promise.all([runId, secondId].map(async (id) => ({
    record: await (await fetch(`${api}/api/runs/${id}`)).json(),
    state: await (await fetch(`${api}/api/runs/${id}/state`)).json(),
    trace: await (await fetch(`${api}/api/runs/${id}/trace`)).json(),
  })));
  await writeFile(`evidence/phase3-execution-runs-${info.project.name}.json`, JSON.stringify({
    category: 'real-local-api-with-explicit-test-executor', actual_hermes_invoked: false,
    verified_at: new Date().toISOString(), runs: evidence,
  }, null, 2) + '\n');
  await page.getByLabel('Run history').selectOption(runId);
  await finish(page, 'completed');
  await page.getByLabel('Run history').selectOption(secondId);
  await finish(page, 'failed');
});

test('lost run acknowledgement survives reload, no automatic POST and exact retry adopts the same run', async ({ page }) => {
  const taskId = await create(page, 'Run response-loss browser proof');
  let sent, runId;
  await page.route(`${api}/api/tasks/${taskId}/runs`, async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    sent = route.request().postDataJSON();
    const response = await route.fetch();
    expect(response.status()).toBe(202); runId = (await response.json()).id;
    await route.abort('failed');
  }, { times: 1 });
  await page.getByRole('textbox', { name: 'Release', exact: true }).fill('3.0');
  await page.getByRole('button', { name: 'Start release run' }).click();
  await expect(page.locator('.execution-panel [role=alert]')).toContainText('acknowledgement unknown');
  expect((await page.evaluate((key) => JSON.parse(sessionStorage.getItem(key)), pendingKey)).payload).toEqual(sent);
  let posts = 0; page.on('request', (r) => { if (r.method() === 'POST') posts++; });
  await page.reload(); await connect(page);
  expect(posts).toBe(0);
  const response = page.waitForResponse((r) => r.url() === `${api}/api/tasks/${taskId}/runs` && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Retry exact run request' }).click();
  expect((await response).status()).toBe(200);
  await finish(page, 'completed');
  expect(await runs(taskId)).toHaveLength(1);
  expect(await page.locator('[data-run-id]').getAttribute('data-run-id')).toBe(runId);
  expect(await page.evaluate((key) => sessionStorage.getItem(key), pendingKey)).toBeNull();
});

test('asynchronous cancellation has terminal evidence and never replays on reconnect', async ({ page }) => {
  const taskId = await create(page, 'Cancel test executor');
  await start(page);
  await page.getByRole('button', { name: 'Request cancellation' }).click();
  await finish(page, 'cancelled');
  await expect(page.locator('[data-run-notice]')).toContainText('Cancellation requested');
  await expect(page.locator('.executor-response')).toHaveText('Browser test executor cancelled.');
  await page.reload(); await connect(page); await finish(page, 'cancelled');
  expect(await runs(taskId)).toHaveLength(1);
});

test('offline stream recovers authoritative final state and contiguous trace without another execution', async ({ page, context }) => {
  const taskId = await create(page, 'Offline stream recovery');
  await start(page);
  await context.setOffline(true);
  await expect(page.locator('.live-run')).toContainText('reconnecting', { timeout: 10000 });
  // The test executor may finish while transport is unavailable. Reconnect only reads.
  await context.setOffline(false);
  await finish(page, 'completed');
  expect(await runs(taskId)).toHaveLength(1);
  await page.getByRole('link', { name: 'Open debugger', exact: true }).click();
  const sequences = await page.locator('[data-sequence]').evaluateAll((els) => els.map((el) => Number(el.dataset.sequence)));
  expect(sequences).toEqual(Array.from({ length: sequences.length }, (_, i) => i + 1));
  await expect(page.locator('.live-run')).toContainText('activity finished');
});
