// Real HTTP, storage, supervisor and trusted checks; explicit test model/container actors.
import { test, expect } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const api = process.env.EPOCH_INTAKE_TEST_ORIGIN;
const origin = process.env.EPOCH_INTAKE_FRONTEND_ORIGIN;
async function connect(page) {
  await page.locator('.topbar [data-action=settings]').click();
  const field = page.locator('#api-origin');
  if (await field.isEnabled()) await field.fill(api);
  await page.locator('#connect').click();
  await expect(page.locator('.connection-state')).toHaveAttribute('title', 'Connected · local API');
}
async function create(page, message, project = `proof-${crypto.randomUUID()}`) {
  await page.goto(`${origin}/chat`);
  await connect(page);
  await page.locator('#request-message').fill(message);
  await page.locator('[data-key=project]>summary').click();
  await page.locator('#project-id').fill(project);
  await page.locator('[data-key=project]>summary').click();
  await page.locator('#save-request').click();
  await expect(page.locator('#start-release')).toBeEnabled();
  return { taskId: new URL(page.url()).searchParams.get('task'), project };
}
async function start(page, { repair = false, omission = false, release = '4.1' } = {}) {
  if (!(await page.locator('#release-value').isVisible())) await page.locator('[data-key=another-release]>summary').click();
  await page.locator('#release-value').fill(release);
  await page.locator('#release-supervised').check();
  if (repair) {
    await page.locator('#release-scenario').selectOption('broken_checklist');
    await expect(page.locator('#release-repair')).toBeEnabled();
    await page.locator('#release-repair').check();
  }
  if (omission) await page.locator('#release-omission').check();
  await page.locator('#start-release').click();
  await expect(page.locator('[data-run-id]')).toBeVisible();
  return page.locator('[data-run-id]').getAttribute('data-run-id');
}
const record = async (id) => (await fetch(`${api}/api/runs/${id}`)).json();
const snapshot = async (id) => (await fetch(`${api}/api/runs/${id}/state`)).json();
const environment = async (project) => (await fetch(`${api}/api/environments/${project}`)).json();
async function finish(page, status = 'completed') {
  await expect(page.locator('[data-run-status]')).toHaveText(status, { timeout: 25000 });
}
async function feedback(page, text) {
  const form = page.locator('#feedback-form');
  // Feedback is deliberately reachable in the normal workflow, without raw JSON controls.
  await expect(form).toBeVisible();
  await page.locator('#feedback-message').fill(text);
  await form.locator('button[type=submit], button:not([type])').click();
}
async function saveEvidence(page, id, project, name, info) {
  const [run, state, env, trace] = await Promise.all([record(id), snapshot(id), environment(project), fetch(`${api}/api/runs/${id}/trace`).then((r) => r.json())]);
  await writeFile(`evidence/phase7-${name}-${info.project.name}.json`, JSON.stringify({
    category: 'real-http-storage-supervisor-evaluator-with-explicit-test-actors',
    actual_hermes_invoked: false, actual_luna_invoked: false, actual_docker_invoked: false,
    verified_at: new Date().toISOString(), run, state, environment: env, trace,
  }, null, 2) + '\n');
  await page.screenshot({ path: `evidence/phase7-${name}-${info.project.name}.png`, fullPage: true });
}

test('supervisor continuation, feedback exact retry and retained revision evidence', async ({ page }, info) => {
  test.setTimeout(65000);
  const { project } = await create(page, 'Prepare release 4.1 for QA.');
  const id = await start(page, { omission: true });
  await finish(page);
  const initial = await record(id);
  expect(initial.supervision.operations).toHaveLength(1);
  expect(initial.supervision.operations[0].interventions.length).toBeGreaterThan(0);
  const before = await snapshot(id);
  await expect(page.locator('.execution-panel')).toContainText('Luna');
  let submitted;
  await page.route(`${api}/api/runs/${id}/feedback`, async (route) => {
    submitted = route.request().postDataJSON();
    const accepted = await route.fetch();
    expect(accepted.status()).toBe(202);
    await route.abort('failed');
  }, { times: 1 });
  await feedback(page, 'Add the checklist item Security review approved. Include Deployment starts at 10:00 UTC in the QA message.');
  await expect(page.locator('[data-action=operation-retry]')).toBeVisible();
  let posts = 0;
  page.on('request', (r) => { if (r.method() === 'POST') posts++; });
  await page.reload(); await connect(page);
  expect(posts).toBe(0);
  const acknowledged = page.waitForResponse((r) => r.url().endsWith(`/runs/${id}/feedback`) && r.request().method() === 'POST');
  await page.locator('[data-action=operation-retry]').click();
  const response = await acknowledged;
  expect(response.status()).toBe(200);
  expect(response.request().postDataJSON()).toEqual(submitted);
  await finish(page);
  await expect.poll(async () => (await record(id)).supervision.operations.length).toBe(2);
  const after = await snapshot(id), final = await record(id);
  for (const key of ['tickets', 'checklists', 'messages']) expect(after[key].map((x) => x.id)).toEqual(before[key].map((x) => x.id));
  expect(after.checklists[0].items).toContain('Security review approved');
  expect(after.messages[0].text).toContain('Deployment starts at 10:00 UTC');
  expect(final.supervision.operations[0]).toEqual(initial.supervision.operations[0]);
  await page.getByRole('link', { name: 'Open debugger', exact: true }).click();
  await expect(page.locator('.execution-panel')).toContainText('Security review approved');
  const sequences = await page.locator('[data-sequence]').evaluateAll((els) => els.map((x) => Number(x.dataset.sequence)));
  expect(sequences).toEqual(Array.from({ length: sequences.length }, (_, i) => i + 1));
  await saveEvidence(page, id, project, 'supervision', info);
});

test('clarification starts a new operation on the same run', async ({ page }) => {
  const { taskId } = await create(page, '[needs-input] Prepare release 4.1 for QA.');
  const id = await start(page);
  await finish(page, 'needs input');
  await feedback(page, 'Prepare the release ticket, linked checklist and QA notification.');
  await finish(page);
  const run = await record(id);
  expect(run.supervision.operations.map((x) => x.trigger)).toEqual(['initial', 'clarification']);
  expect(await (await fetch(`${api}/api/tasks/${taskId}/runs`)).json()).toHaveLength(1);
});

test('generated repair evidence, later reuse and rollback exact retry', async ({ page }, info) => {
  test.setTimeout(80000);
  const errors = []; page.on('pageerror', (e) => errors.push(e.message));
  const { project } = await create(page, 'Prepare release 4.1 for QA with the checklist.');
  const id = await start(page, { repair: true });
  await finish(page);
  const run = await record(id), env = await environment(project);
  expect(env.active_version).not.toBe('builtin');
  const attempts = run.supervision.operations.flatMap((o) => o.repairs.flatMap((r) => r.attempts));
  expect(attempts.some((x) => x.status === 'rejected')).toBe(true);
  const accepted = attempts.find((x) => x.status === 'published');
  expect(accepted).toBeTruthy();
  for (const name of ['component', 'isolation', 'original_replay', 'fresh_release', 'regression']) expect(accepted.proofs.find((proof) => proof.kind === name).passed).toBe(true);
  await page.getByRole('link', { name: 'Open debugger', exact: true }).click();
  await expect(page.locator('.execution-panel')).toContainText('Original');
  await expect(page.locator('.execution-panel')).toContainText('rejected');
  await expect(page.locator('.execution-panel')).toContainText(env.active_version);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await saveEvidence(page, id, project, 'repair', info);
  const laterId = await start(page, { release: '4.9' });
  await finish(page);
  expect((await record(laterId)).environment_version).toBe(env.active_version);
  let rollbackBody;
  await page.route(`${api}/api/environments/${project}/rollback`, async (route) => {
    rollbackBody = route.request().postDataJSON();
    expect((await route.fetch()).ok()).toBe(true);
    await route.abort('failed');
  }, { times: 1 });
  await page.locator('[data-action=environment-rollback]').click();
  await expect(page.locator('[data-action=operation-retry]')).toBeVisible();
  await page.reload(); await connect(page);
  const retryResponse = page.waitForResponse((r) => r.url().endsWith(`/environments/${project}/rollback`) && r.request().method() === 'POST');
  await page.locator('[data-action=operation-retry]').click();
  expect((await retryResponse).request().postDataJSON()).toEqual(rollbackBody);
  await expect.poll(async () => (await environment(project)).active_version).toBe('builtin');
  await expect(page.locator('[data-action=environment-rollback]')).toBeDisabled();
  expect((await record(laterId)).environment_version).toBe(env.active_version);
  expect((await record(id)).environment_version).toBe(env.active_version);
  expect(errors).toEqual([]);
});

test('failed repair retains candidates, failed checks and partial original effects', async ({ page }) => {
  const { project } = await create(page, '[reject-repair] Prepare release 4.1 for QA.');
  const id = await start(page, { repair: true });
  await expect.poll(async () => (await record(id)).status, { timeout: 25000 }).toMatch(/blocked|failed/);
  await page.locator('[data-action=run-refresh]').click();
  expect((await environment(project)).active_version).toBe('builtin');
  const state = await snapshot(id);
  expect(state.tickets).toHaveLength(1);
  expect(state.checklists).toHaveLength(0);
  await expect(page.locator('[data-verdict]')).toHaveText('Trusted checks: failed');
  await expect(page.locator('.execution-panel')).toContainText('rejected');
});
