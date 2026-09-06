// Real local HTTP, SQLite, uploaded PDF bytes and container-rendered previews.
// This browser test does not call models. The separate acceptance harness does.
import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
const api = process.env.EPOCH_PDF_TEST_API || 'http://127.0.0.1:8011';
test('PDF files survive reload and preview real bytes without an agent call', async ({ page, request }, info) => {
  test.setTimeout(120000);
  const response = await request.post(`${api}/api/chats`, {data:{client_request_id:crypto.randomUUID(),environment:'pdf_workshop',project_id:'browser-proof'}});
  expect(response.ok()).toBe(true);
  const chat = await response.json();
  const errors=[]; page.on('pageerror', e=>errors.push(e.message));
  await page.addInitScript(origin=>sessionStorage.setItem('epoch.intake.origin.v1',origin),api);
  await page.goto(`http://127.0.0.1:5173/chat?chat=${chat.id}`);
  await expect(page.getByRole('button',{name:'Add retreat files'})).toBeEnabled();
  await page.getByRole('button',{name:'Add retreat files'}).click();
  await expect(page.locator('.pdf-files')).toContainText('venue-map.pdf',{timeout:90000});
  await page.locator('.pdf-file').filter({hasText:'venue-map.pdf'}).getByRole('button',{name:'Preview'}).click();
  const image=page.locator('.pdf-preview img');
  await expect(image).toBeVisible();
  await expect.poll(()=>image.evaluate(el=>el.complete && el.naturalWidth>0),{timeout:60000}).toBe(true);
  expect(await image.getAttribute('src')).toContain(`/api/chats/${chat.id}/assets/`);
  await image.scrollIntoViewIfNeeded();
  await page.screenshot({path:`evidence/pdf-preview-${info.project.name}.png`});
  await page.getByRole('button',{name:'Close preview'}).click();
  await page.locator('#pdf-upload').setInputFiles({name:'invalid.pdf',mimeType:'application/pdf',buffer:Buffer.from('not a PDF')});
  await expect(page.locator('.chat-alert')).toBeVisible({timeout:60000});
  await page.locator('#pdf-upload').setInputFiles({name:'uploaded-proposal.pdf',mimeType:'application/pdf',buffer:await readFile('../backend/data/pdf-first-check/test_real_pdf_clipping_and_run0/broken.pdf')});
  await expect(page.locator('.pdf-files')).toContainText('uploaded-proposal.pdf',{timeout:60000});
  await page.reload();
  await expect(page.locator('.pdf-files')).toContainText('uploaded-proposal.pdf');
  const saved=await (await request.get(`${api}/api/chats/${chat.id}`)).json();
  expect(saved.operations).toEqual([]);
  expect(saved.messages).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await page.goto(`http://127.0.0.1:5173/debugger?chat=${chat.id}`);
  await expect(page.getByRole('heading',{name:'Debugger',exact:true})).toBeVisible();
  await expect(page.locator('.pdf-files')).toContainText('uploaded-proposal.pdf');
  await page.screenshot({path:`evidence/pdf-debugger-${info.project.name}.png`});
  if (await page.locator('#sidebar').evaluate(el=>el.inert || getComputedStyle(el).visibility==='hidden'))
    await page.getByRole('button',{name:'Toggle navigation'}).click();
  await page.locator('[data-action="new"]').click();
  await page.locator('.project-menu summary').click();
  await expect(page.locator('#chat-project')).toHaveValue('browser-proof');
  await expect(page.locator('.pdf-files')).toHaveCount(0);
});
