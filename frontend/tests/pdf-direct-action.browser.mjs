// Read-only check against saved local HTTP evidence; no model calls or action clicks.
import { test, expect } from '@playwright/test';
test('PDF debugger uses saved context without an investigation form', async ({page}, info) => {
  test.skip(!process.env.EPOCH_PDF_DIRECT_CHAT, 'Requires a saved local PDF conversation');
  const writes = [];
  page.on('request', request => { if (request.method() === 'POST') writes.push(request.url()); });
  await page.addInitScript(() => sessionStorage.setItem('epoch.intake.origin.v1', 'http://127.0.0.1:8000'));
  await page.goto(`http://127.0.0.1:5173/debugger?chat=${process.env.EPOCH_PDF_DIRECT_CHAT}`);
  const panel = page.locator('.pdf-repair-action');
  await expect(panel).toBeVisible({timeout:30000});
  await expect(panel).toContainText('No additional description is needed');
  await expect(panel.getByRole('button', {name:'Fix PDF tool',exact:true})).toBeInViewport();
  await expect(page.locator('#debugger-question')).toHaveCount(0);
  await expect(page.locator('#investigate-chat')).toHaveCount(0);
  await expect(panel.getByRole('button', {name:'Fix PDF tool',exact:true})).toBeVisible();
  await expect(page.locator('[data-key="debugger-requirements"]')).not.toHaveAttribute('open');
  await page.screenshot({path:`evidence/pdf-direct-action-${info.project.name}.png`});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(writes).toEqual([]);
});
