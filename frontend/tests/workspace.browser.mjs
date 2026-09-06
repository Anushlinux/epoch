import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "https://epoch-fixture.invalid";
const contentType = {
  ".html": "text/html",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".md": "text/plain",
};
let external = [];
test.beforeEach(async ({ page }) => {
  external = [];
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      external.push(url.origin);
      return route.abort();
    }
    const file = path.resolve(root, `.${decodeURIComponent(url.pathname)}`);
    if (!file.startsWith(root)) return route.abort();
    try {
      return route.fulfill({
        body: await readFile(file),
        contentType: contentType[path.extname(file)] || "text/plain",
      });
    } catch {
      return route.fulfill({ status: 404, body: "Missing test fixture file" });
    }
  });
  await page.goto(`${origin}/fixtures.html`);
});
async function controls(page) {
  const details = page.locator(".fixture-controls");
  if (!(await details.evaluate((e) => e.open)))
    await details.locator("summary").click();
}
async function advance(page, count = 1) {
  for (let i = 0; i < count; i++) {
    await controls(page);
    await page.getByRole("button", { name: "Advance fixture" }).click();
  }
}

test("layout, fixture labeling, keyboard skip link, responsive overflow and no network", async ({
  page,
}, info) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await expect(
    page.getByRole("heading", { name: "Prepare the Atlas 2.4 release" }),
  ).toBeVisible();
  await expect(
    page.getByText("All states above are fixtures, including passed."),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to workspace" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#workspace")).toBeFocused();
  const dimensions = await page.evaluate(() => ({
    viewport: innerWidth,
    body: document.documentElement.scrollWidth,
  }));
  expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport);
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
  await page.getByRole("tab", { name: "Overview", exact: true }).click();
  await page.evaluate(() => {
    document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: `evidence/${info.project.name}.png`,
    fullPage: true,
  });
});

test("tabs support arrows, Home/End and evidence dialog Escape with focus return", async ({
  page,
}) => {
  const overview = page.getByRole("tab", { name: "Overview", exact: true });
  await overview.focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Activity", exact: true }),
  ).toBeFocused();
  await expect(
    page.getByRole("heading", { name: "Observable activity" }),
  ).toBeVisible();
  await page.keyboard.press("End");
  await expect(
    page.getByRole("tab", { name: "History", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Home");
  await expect(overview).toBeFocused();
  const inspect = page
    .getByRole("button", { name: "Inspect evidence & source" })
    .first();
  await inspect.click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Close", exact: true }),
  ).toBeFocused();
  await expect(page.locator("#inspector-content")).toContainText(
    "Original request",
  );
  await expect(page.locator("#inspector-content")).toContainText(
    '"category": "fixture"',
  );
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(inspect).toBeFocused();
});

test("request clarification preserves exact intent, accepts only valid input, and never invents execution", async ({
  page,
}) => {
  await page.getByRole("button", { name: "New request", exact: true }).click();
  await page.getByRole("button", { name: "Review clarification" }).click();
  await expect(page.getByLabel("Your request", { exact: true })).toBeFocused();
  const text =
    "<script>window.compromised=true</script>\nPreserve all release notes.";
  await page.getByLabel("Your request", { exact: true }).fill(text);
  await page.getByLabel("Constraints (optional)").fill("Do not send messages.");
  await page.getByRole("button", { name: "Review clarification" }).click();
  await expect(page.locator(".request-review")).toContainText(text);
  await expect(
    page.getByLabel("Where should the result be shared?"),
  ).toBeFocused();
  await page.getByRole("button", { name: "Edit request", exact: true }).click();
  await expect(page.getByLabel("Your request", { exact: true })).toHaveValue(
    text,
  );
  await page.getByRole("button", { name: "Review clarification" }).click();
  await page.getByLabel("Where should the result be shared?").fill("Just here");
  await page
    .getByRole("button", { name: "Create fixture task", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Your request is preserved." }),
  ).toBeVisible();
  await expect(page.locator("blockquote")).toHaveText(text);
  await expect(
    page.getByText("Do not send messages.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("0 of 1 fixture passes")).toBeVisible();
  expect(await page.evaluate(() => window.compromised)).toBeUndefined();
  await controls(page);
  await expect(
    page.getByRole("button", { name: "Advance fixture" }),
  ).toBeDisabled();
});

test("uncertain request acknowledgement retries the same submission without duplicate work", async ({
  page,
}) => {
  await controls(page);
  await page.getByLabel("Lose the next submission acknowledgement").check();
  await page.getByRole("button", { name: "New request", exact: true }).click();
  await page
    .getByLabel("Your request", { exact: true })
    .fill("Prepare one checklist.");
  await page.getByRole("button", { name: "Review clarification" }).click();
  await page.getByLabel("Where should the result be shared?").fill("Here");
  await page
    .getByRole("button", { name: "Create fixture task", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("acknowledgement lost");
  await expect(
    page.getByRole("button", { name: "Create fixture task", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Check submission status" }).click();
  await expect(page.getByText("0 of 1 fixture passes")).toBeVisible();
  await expect(
    page.getByText("Revision 1", { exact: false }).first(),
  ).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "The original request is intact" }),
  ).toBeVisible();
});

test("disconnect blocks changes; reconnect retains partial results and event cursor", async ({
  page,
}) => {
  await controls(page);
  const before = await page.locator(".fixture-cursor").textContent();
  await page
    .getByRole("button", { name: "Disconnect fixture", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Fixture updates are paused",
  );
  await controls(page);
  await expect(
    page.getByRole("button", { name: "Advance fixture" }),
  ).toBeDisabled();
  await page.getByRole("tab", { name: "Results", exact: true }).click();
  await expect(page.getByRole("button", { name: /ATLAS-24/ })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Create fixture revision" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Reconnect fixture", exact: true })
    .click();
  await expect(
    page.locator(".notice").filter({ hasText: /Fixture connection restored/ }),
  ).toBeVisible();
  await controls(page);
  await expect(page.locator(".fixture-cursor")).toHaveText(before);
  await expect(
    page.getByRole("button", { name: "Create fixture revision" }),
  ).toBeEnabled();
});

test("repair activity cannot finish task; rejected records and partial effects remain visible", async ({
  page,
}) => {
  await advance(page, 2);
  await page.getByRole("tab", { name: /Repairs/ }).click();
  await expect(
    page.getByText(
      "Fixture environment v2 active; previous v1 retained. Rollback not executed.",
    ),
  ).toBeVisible();
  await expect(page.getByText("Candidate 01 · retry only")).toBeVisible();
  await page.getByText("Candidate 01 · retry only").click();
  await expect(
    page.getByText("Authored example contains a second ticket."),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Results", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Partial results & gaps" }),
  ).toBeVisible();
  await expect(page.locator(".artifact")).toHaveCount(1);
  await expect(page.getByText("QA notification not sent.")).toBeVisible();
});

test("fixture artifacts download with provenance; feedback retains delivered result and resets new checks", async ({
  page,
}) => {
  await advance(page, 5);
  await page.getByRole("tab", { name: "Results", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Delivered fixture results" }),
  ).toBeVisible();
  await expect(page.locator(".artifact")).toHaveCount(3);
  await page.getByRole("button", { name: /MSG-24/ }).click();
  await expect(page.locator("#inspector-content")).toContainText(
    "no Slack message was sent",
  );
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download fixture JSON" }).click();
  const download = await pending;
  expect(download.suggestedFilename()).toBe("epoch-fixture-evidence.json");
  expect(await readFile(await download.path(), "utf8")).toContain(
    "NOT EXECUTION EVIDENCE",
  );
  await page.keyboard.press("Escape");
  await page
    .getByLabel("Your feedback", { exact: true })
    .fill("Include the rollback owner.");
  await page.getByRole("button", { name: "Create fixture revision" }).click();
  await expect(
    page.getByRole("tab", { name: "History", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".history-record .artifact")).toHaveCount(3);
  await page
    .getByRole("button", { name: "Inspect complete revision & repair history" })
    .click();
  await expect(page.locator("#inspector-content")).toContainText("repair-01");
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "Overview", exact: true }).click();
  await expect(page.getByText("0 of 4 fixture passes")).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Include the rollback owner.",
      exact: true,
    }),
  ).toBeVisible();
});

test("feedback acknowledgement loss retries one revision and preserves history", async ({
  page,
}) => {
  await controls(page);
  await page.getByLabel("Lose the next submission acknowledgement").check();
  await page.getByRole("tab", { name: "Results", exact: true }).click();
  await page
    .getByLabel("Your feedback", { exact: true })
    .fill("Use the release owner.");
  await page.getByRole("button", { name: "Create fixture revision" }).click();
  await expect(page.getByRole("alert")).toContainText("acknowledgement lost");
  await expect(
    page.getByRole("tab", { name: "Overview", exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Check submission status" }).click();
  await expect(page.locator(".history-record")).toHaveCount(1);
  await expect(page.locator(".current-revision")).toContainText("Revision 2");
});

test("planned reset, empty views, reduced motion and long input fit narrow screens", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await controls(page);
  await page.getByRole("button", { name: "Restart release example" }).click();
  await expect(page.getByText("0 of 3 fixture passes")).toBeVisible();
  await page.getByRole("tab", { name: "Results", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No result artifacts yet" }),
  ).toBeVisible();
  await page
    .getByLabel("Your feedback", { exact: true })
    .fill("Long feedback ".repeat(100));
  await page.getByRole("button", { name: "Create fixture revision" }).click();
  await page.getByRole("tab", { name: "Overview", exact: true }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await expect(page.getByText("0 of 4 fixture passes")).toBeVisible();
});

test("a failed reconnect preserves evidence and can be retried safely", async ({
  page,
}) => {
  await controls(page);
  await page.getByLabel("Fail the next fixture reconnect").check();
  await page
    .getByRole("button", { name: "Disconnect fixture", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Reconnect fixture", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Fixture reconnect failed.",
  );
  await expect(page.getByText("1 of 3 fixture passes")).toBeVisible();
  await page
    .getByRole("button", { name: "Reconnect fixture", exact: true })
    .click();
  await expect(page.locator(".notice")).toContainText(
    "Fixture connection restored.",
  );
  await expect(page.getByText("1 of 3 fixture passes")).toBeVisible();
});

test("unknown acknowledgement freezes input and reload reports unrecoverable local identity without resubmitting", async ({
  page,
}) => {
  await controls(page);
  await page.getByLabel("Lose the next submission acknowledgement").check();
  await page.getByRole("button", { name: "New request", exact: true }).click();
  await page
    .getByLabel("Your request", { exact: true })
    .fill("Do not duplicate this request.");
  await page.getByRole("button", { name: "Review clarification" }).click();
  await page.getByLabel("Where should the result be shared?").fill("Just here");
  await page
    .getByRole("button", { name: "Create fixture task", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Acknowledgement unknown",
  );
  await expect(
    page.getByLabel("Where should the result be shared?"),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Edit request", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "New request", exact: true }),
  ).toBeDisabled();
  const marker = await page.evaluate(() =>
    sessionStorage.getItem("epoch.fixture.pending"),
  );
  expect(marker).toContain("id");
  expect(marker).not.toContain("Do not duplicate");
  await page.reload();
  await expect(page.getByRole("alert")).toContainText(
    "Previous submission status is unknown",
  );
  await expect(page.getByRole("alert")).toContainText(
    "No request was resubmitted",
  );
  await expect(
    page.getByRole("button", { name: "New request", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Check submission status" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Discard lost fixture session" })
    .click();
  await expect(
    page.getByRole("button", { name: "New request", exact: true }),
  ).toBeEnabled();
  expect(
    await page.evaluate(() => sessionStorage.getItem("epoch.fixture.pending")),
  ).toBeNull();
  await expect(
    page.getByRole("heading", { name: "Prepare the Atlas 2.4 release" }),
  ).toBeVisible();
});

test("accepted submission clears the uncertainty marker before reload", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "Results", exact: true }).click();
  await page
    .getByLabel("Your feedback", { exact: true })
    .fill("Keep the deadline.");
  await page.getByRole("button", { name: "Create fixture revision" }).click();
  await expect(page.locator(".current-revision")).toContainText("Revision 2");
  expect(
    await page.evaluate(() => sessionStorage.getItem("epoch.fixture.pending")),
  ).toBeNull();
  await page.reload();
  await expect(
    page.getByText("Previous submission status is unknown"),
  ).toHaveCount(0);
});

test("unavailable marker storage refuses submission before any fixture action starts", async ({
  page,
}) => {
  await page.evaluate(() => {
    Storage.prototype.setItem = function () {
      throw new DOMException("Storage unavailable", "QuotaExceededError");
    };
  });
  await page.getByRole("tab", { name: "Results", exact: true }).click();
  await page
    .getByLabel("Your feedback", { exact: true })
    .fill("Preserve this draft.");
  await page.getByRole("button", { name: "Create fixture revision" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "This action was not submitted",
  );
  await expect(page.getByLabel("Your feedback", { exact: true })).toHaveValue(
    "Preserve this draft.",
  );
  await expect(page.getByLabel("Your feedback", { exact: true })).toBeEnabled();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.locator(".current-revision")).toContainText("Revision 1");
  await expect(page.locator(".history-record")).toHaveCount(0);
});

test('disconnected New request and an already-open composer cannot submit even through a dispatched form event', async ({ page }) => {
  await page.getByRole('button', { name: 'New request', exact: true }).click();
  await page.getByLabel('Your request', { exact: true }).fill('Keep this request while disconnected');
  await page.getByRole('button', { name: 'Review clarification' }).click();
  await page.getByLabel('Where should the result be shared?').fill('Just here');
  await controls(page);
  await page.getByRole('button', { name: 'Disconnect fixture' }).click();
  await expect(page.getByRole('button', { name: 'New request', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Create fixture task' })).toBeDisabled();
  await page.evaluate(async () => {
    const { FixtureAdapter } = await import('/src/fixtures.mjs');
    window.fixtureCommandsSent = 0;
    const original = FixtureAdapter.prototype.command;
    FixtureAdapter.prototype.command = function (...args) { window.fixtureCommandsSent++; return original.apply(this, args); };
    document.querySelector('#request-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
  expect(await page.evaluate(() => window.fixtureCommandsSent)).toBe(0);
  expect(await page.evaluate(() => sessionStorage.getItem('epoch.fixture.pending'))).toBeNull();
  await expect(page.getByLabel('Where should the result be shared?')).toHaveValue('Just here');
  await page.getByRole('button', { name: 'Reconnect fixture' }).click();
  await expect(page.getByRole('button', { name: 'Create fixture task' })).toBeEnabled();
});

test('post-delivery checkpoint updates hide stale Delivered labels until an explicit new task outcome', async ({ page }) => {
  await advance(page, 5);
  await expect(page.locator('.task-state')).toHaveText('Delivered · fixture');
  await page.evaluate(async () => {
    const { FixtureAdapter } = await import('/src/fixtures.mjs');
    const { acceptEvent } = await import('/src/state.mjs');
    FixtureAdapter.prototype.reconnect = async function () {
      const s = this.state;
      const data = { ...s.checkpoints[0], status: 'checking' };
      this.state = acceptEvent(s, { taskId: s.taskId, runId: s.runId, revision: s.revision, category: 'fixture', eventId: 'after-delivery-check', seq: s.seq + 1, kind: 'checkpoint', data });
      return this.snapshot();
    };
  });
  await controls(page); await page.getByRole('button', { name: 'Disconnect fixture' }).click();
  await page.getByRole('button', { name: 'Reconnect fixture' }).click();
  await expect(page.locator('.task-state')).toHaveText('Delivery needs confirmation · fixture');
  await page.getByRole('tab', { name: 'Results', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Delivered fixture results', exact: true })).toHaveCount(0);
  await page.evaluate(async () => {
    const { FixtureAdapter } = await import('/src/fixtures.mjs');
    const { acceptEvent } = await import('/src/state.mjs');
    FixtureAdapter.prototype.reconnect = async function () {
      for (const [kind, data] of [
        ['checkpoint', { ...this.state.checkpoints[0], status: 'passed' }],
        ['task-outcome', { status: 'delivered', result: this.state.result }],
      ]) {
        const s = this.state;
        this.state = acceptEvent(s, { taskId: s.taskId, runId: s.runId, revision: s.revision, category: 'fixture', eventId: `confirm-${s.seq + 1}`, seq: s.seq + 1, kind, data });
      }
      return this.snapshot();
    };
  });
  await controls(page); await page.getByRole('button', { name: 'Disconnect fixture' }).click();
  await page.getByRole('button', { name: 'Reconnect fixture' }).click();
  await expect(page.locator('.task-state')).toHaveText('Delivered · fixture');
});
