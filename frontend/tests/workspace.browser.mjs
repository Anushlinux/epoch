import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../", import.meta.url));
const origin = "https://epoch-fixture.invalid";
const types = {
  ".html": "text/html",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".ttf": "font/ttf",
};
const aliases = {
  "/chat": "/index.html",
  "/debugger": "/index.html",
  "/demo/chat": "/fixtures.html",
  "/demo/debugger": "/fixtures.html",
};
test.beforeEach(async ({ page }) => {
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) return route.abort();
    const file = path.resolve(
      root,
      `.${aliases[url.pathname] || url.pathname}`,
    );
    if (!file.startsWith(root)) return route.abort();
    try {
      return route.fulfill({
        body: await readFile(file),
        contentType: types[path.extname(file)] || "text/plain",
      });
    } catch {
      return route.fulfill({ status: 404, body: "Missing fixture file" });
    }
  });
  await page.goto(`${origin}/demo/chat`);
});
async function nav(page) {
  if (
    await page
      .locator("#sidebar")
      .evaluate(
        (el) => el.inert || getComputedStyle(el).visibility === "hidden",
      )
  )
    await page.getByRole("button", { name: "Toggle navigation" }).click();
}
async function newChat(page) {
  await nav(page);
  await page.getByRole("button", { name: /^New chat/ }).click();
}
async function debug(page) {
  await nav(page);
  await page.getByRole("link", { name: "Debugger", exact: true }).click();
}
async function controls(page) {
  const d = page.locator(".fixture-controls");
  if (!(await d.evaluate((el) => el.open))) await d.locator("summary").click();
}
async function advance(page, count = 1) {
  for (let i = 0; i < count; i++) {
    await controls(page);
    await page.getByRole("button", { name: "Advance fixture" }).click();
  }
}
async function create(page, text = "Prepare one checklist.") {
  await newChat(page);
  await page.getByLabel("Your request", { exact: true }).fill(text);
  await page.getByRole("button", { name: "Review clarification" }).click();
  await page.getByLabel("Where should the result be shared?").fill("Just here");
  await page.getByRole("button", { name: "Create fixture task" }).click();
}
async function loseAck(page) {
  await controls(page);
  await page.getByLabel("Lose the next submission acknowledgement").check();
}
async function feedback(page, text = "Include the rollback owner.") {
  await page.getByLabel("Your feedback", { exact: true }).fill(text);
  await page.getByRole("button", { name: "Create fixture revision" }).click();
}
async function tab(page, name) {
  await page.getByRole("tab", { name, exact: true }).click();
}
async function fits(page) {
  expect(
    await page.locator('.topbar').evaluate(el => el.scrollWidth <= el.clientWidth),
  ).toBe(true);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}

test("chat layout, empty state, source labels, keyboard skip link and responsive overflow", async ({
  page,
}, info) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await expect(
    page.getByRole("heading", { name: "Prepare the Atlas 2.4 release" }),
  ).toBeVisible();
  await expect(page.locator(".demo-strip")).toContainText("authored examples");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to workspace" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#workspace")).toBeFocused();
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
  await page.locator("#workspace").evaluate(el => el.blur());
  await fits(page);
  await page.screenshot({ path: `evidence/chat-${info.project.name}.png` });
  await page.goto(`${origin}/chat`);
  await expect(
    page.getByRole("heading", { name: "EPOCH", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save request" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("textbox", { name: "What needs to be done?" }),
  ).toBeEditable();
  await page.evaluate(() => document.fonts.ready);
  await fits(page);
  await page.screenshot({
    path: `evidence/empty-chat-${info.project.name}.png`,
  });
  expect(errors).toEqual([]);
});

test("separate debugger route, browser history, draft and scroll restoration", async ({
  page,
}) => {
  await page
    .getByLabel("Your feedback", { exact: true })
    .fill("Keep this unsent feedback");
  await page.locator('[data-key="chat-activity"]>summary').click();
  await page.locator("#page-scroll").evaluate((el) => (el.scrollTop = 200));
  const y = await page.locator("#page-scroll").evaluate((el) => el.scrollTop);
  await debug(page);
  await expect(page).toHaveURL(/\/demo\/debugger\?task=fixture-atlas$/);
  await expect(page.locator(".pipeline-stage")).toHaveCount(6);
  await page.goBack();
  await expect(page.getByLabel("Your feedback", { exact: true })).toHaveValue(
    "Keep this unsent feedback",
  );
  expect(
    await page.locator('[data-key="chat-activity"]').evaluate((el) => el.open),
  ).toBe(true);
  expect(
    await page.locator("#page-scroll").evaluate((el) => el.scrollTop),
  ).toBe(y);
  await page.goForward();
  await expect(page.locator(".pipeline-stage")).toHaveCount(6);
});

test("debugger tabs use arrow/Home/End keys; evidence dialog Escape returns focus", async ({
  page,
}, info) => {
  await debug(page);
  await expect(page.locator("#stage-2")).toContainText("Rejected");
  await fits(page);
  await page.screenshot({ path: `evidence/debugger-${info.project.name}.png` });
  const activity = page.getByRole("tab", { name: "Activity", exact: true });
  await activity.focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Checkpoints", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("End");
  await expect(
    page.getByRole("tab", { name: "History", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Home");
  await expect(activity).toBeFocused();
  await tab(page, "Checkpoints");
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
  await expect(inspect).toBeFocused();
});

test("custom request clarification preserves escaped input and never invents execution", async ({
  page,
}) => {
  await newChat(page);
  await page.getByRole("button", { name: "Review clarification" }).click();
  await expect(page.getByLabel("Your request", { exact: true })).toBeFocused();
  const text =
    "<script>window.compromised=true</script>\nPreserve all release notes.";
  await page.getByLabel("Your request", { exact: true }).fill(text);
  await page.locator('[data-key="constraints"]>summary').click();
  await page.getByLabel("Constraints (optional)").fill("Do not send messages.");
  await page.getByRole("button", { name: "Review clarification" }).click();
  await expect(page.locator("blockquote")).toHaveText(text);
  await page.getByRole("button", { name: "Edit request", exact: true }).click();
  await expect(page.getByLabel("Your request", { exact: true })).toHaveValue(
    text,
  );
  await page.getByRole("button", { name: "Review clarification" }).click();
  await page.getByLabel("Where should the result be shared?").fill("Just here");
  await page.getByRole("button", { name: "Create fixture task" }).click();
  await expect(
    page.getByText("Your request is preserved.", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("0 of 1 fixture passes")).toBeVisible();
  await page.locator('[data-key="brief"]>summary').click();
  await expect(
    page.getByText("Do not send messages.", { exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => window.compromised)).toBeUndefined();
  await controls(page);
  await expect(
    page.getByRole("button", { name: "Advance fixture" }),
  ).toBeDisabled();
});

test("uncertain creation freezes identity; read-only lookup reconciles one task", async ({
  page,
}) => {
  await loseAck(page);
  await create(page);
  await expect(page.getByRole("alert")).toContainText("acknowledgement lost");
  await expect(
    page.getByRole("button", { name: "Create fixture task" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Check submission status" }).click();
  await expect(page.getByText("0 of 1 fixture passes")).toBeVisible();
  await debug(page);
  await tab(page, "History");
  await expect(page.locator(".current-revision")).toContainText("Revision 1");
  await expect(page.locator(".history-record")).toHaveCount(0);
});

test("disconnect and failed reconnect preserve evidence and cursor without replay", async ({
  page,
}) => {
  await controls(page);
  const cursor = await page.locator(".fixture-cursor").textContent();
  await page.getByLabel("Fail the next fixture reconnect").check();
  await page.getByRole("button", { name: "Disconnect fixture" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Fixture updates are paused",
  );
  await expect(
    page.getByRole("button", { name: "Advance fixture" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Create fixture revision" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Reconnect fixture" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Fixture reconnect failed.",
  );
  await expect(page.getByText("1 of 3 fixture passes")).toBeVisible();
  await page.getByRole("button", { name: "Reconnect fixture" }).click();
  await expect(page.locator(".notice")).toContainText(
    "Fixture connection restored",
  );
  await expect(page.locator(".fixture-cursor")).toHaveText(cursor);
});

test("verification and activation never deliver the task; rejected candidates stay inspectable", async ({
  page,
}) => {
  await advance(page, 2);
  await expect(page.locator(".task-state")).not.toHaveText(
    "Delivered · fixture",
  );
  await debug(page);
  await expect(page.locator("#stage-4 summary")).toContainText("Active");
  await expect(page.locator("#stage-5 summary")).toContainText("Waiting");
  await page.locator("#stage-2>details>summary").click();
  await page.locator('[data-key="attempt-repair-01"]>summary').click();
  await expect(page.locator("#stage-2")).toContainText("duplicate ticket");
  await expect(
    page.locator(".context-column").getByRole("button", { name: /ATLAS-24/ }),
  ).toBeVisible();
});

test("artifact download labels fixture provenance; feedback retains delivered artifacts and resets checks", async ({
  page,
}) => {
  await advance(page, 5);
  await expect(page.locator(".task-state")).toHaveText("Delivered · fixture");
  await page.getByRole("button", { name: /MSG-24/ }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download fixture JSON" }).click();
  const file = await (await download).path();
  const data = JSON.parse(await readFile(file, "utf8"));
  expect(data.label).toContain("NOT EXECUTION EVIDENCE");
  expect(data.data.object.id).toBe("MSG-24");
  await page.keyboard.press("Escape");
  await feedback(page);
  await expect(page.getByText("0 of 4 fixture passes")).toBeVisible();
  await debug(page);
  await tab(page, "History");
  await expect(page.locator(".current-revision")).toContainText("Revision 2");
  await expect(page.locator(".history-record .artifact")).toHaveCount(3);
  await page
    .getByRole("button", { name: "Inspect complete revision & repair history" })
    .click();
  await expect(page.locator("#inspector-content")).toContainText("repair-01");
});

test("feedback acknowledgement loss reconciles exactly one revision", async ({
  page,
}) => {
  await loseAck(page);
  await feedback(page, "Use the release owner.");
  await expect(page.getByRole("alert")).toContainText("acknowledgement lost");
  await expect(
    page.getByLabel("Your feedback", { exact: true }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Check submission status" }).click();
  await debug(page);
  await tab(page, "History");
  await expect(page.locator(".history-record")).toHaveCount(1);
  await expect(page.locator(".current-revision")).toContainText("Revision 2");
});

test("planned reset, long content and reduced motion retain responsive layout", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await controls(page);
  await page.getByRole("button", { name: "Restart release example" }).click();
  await expect(page.getByText("0 of 3 fixture passes")).toBeVisible();
  await feedback(page, "Long feedback ".repeat(100));
  await expect(page.getByText("0 of 4 fixture passes")).toBeVisible();
  await fits(page);
  await debug(page);
  await fits(page);
});

test("unknown acknowledgement reload reports lost identity and never resubmits", async ({
  page,
}) => {
  await loseAck(page);
  await create(page, "Do not duplicate this request.");
  await expect(page.getByRole("alert")).toContainText(
    "Acknowledgement unknown",
  );
  await expect(
    page.getByLabel("Where should the result be shared?"),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Edit request", exact: true }),
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
    page.getByRole("button", { name: "Check submission status" }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Discard lost fixture session" })
    .click();
  expect(
    await page.evaluate(() => sessionStorage.getItem("epoch.fixture.pending")),
  ).toBeNull();
});

test("accepted feedback clears pending marker before reload", async ({
  page,
}) => {
  await feedback(page, "Keep the deadline.");
  expect(
    await page.evaluate(() => sessionStorage.getItem("epoch.fixture.pending")),
  ).toBeNull();
  await page.reload();
  await expect(
    page.getByText("Previous submission status is unknown"),
  ).toHaveCount(0);
});

test("storage refusal preserves draft and does not start a fixture command", async ({
  page,
}) => {
  await page.evaluate(() => {
    Storage.prototype.setItem = function () {
      throw new DOMException("Storage unavailable", "QuotaExceededError");
    };
  });
  await feedback(page, "Preserve this draft.");
  await expect(page.getByRole("alert")).toContainText(
    "This action was not submitted",
  );
  await expect(page.getByLabel("Your feedback", { exact: true })).toHaveValue(
    "Preserve this draft.",
  );
  await expect(page.getByLabel("Your feedback", { exact: true })).toBeEnabled();
  await debug(page);
  await tab(page, "History");
  await expect(page.locator(".current-revision")).toContainText("Revision 1");
  await expect(page.locator(".history-record")).toHaveCount(0);
});

test("disconnected composer refuses dispatched form submission", async ({
  page,
}) => {
  await newChat(page);
  await page
    .getByLabel("Your request", { exact: true })
    .fill("Keep this request");
  await page.getByRole("button", { name: "Review clarification" }).click();
  await page.getByLabel("Where should the result be shared?").fill("Just here");
  await controls(page);
  await page.getByRole("button", { name: "Disconnect fixture" }).click();
  await expect(
    page.getByRole("button", { name: "Create fixture task" }),
  ).toBeDisabled();
  await page.evaluate(async () => {
    const { FixtureAdapter } = await import("/src/fixtures.mjs");
    window.sent = 0;
    const original = FixtureAdapter.prototype.command;
    FixtureAdapter.prototype.command = function (...args) {
      window.sent++;
      return original.apply(this, args);
    };
    document
      .querySelector("#request-form")
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  expect(await page.evaluate(() => window.sent)).toBe(0);
  expect(
    await page.evaluate(() => sessionStorage.getItem("epoch.fixture.pending")),
  ).toBeNull();
  await expect(
    page.getByLabel("Where should the result be shared?"),
  ).toHaveValue("Just here");
});

test("post-delivery checkpoint change removes delivered presentation until a newer outcome", async ({
  page,
}) => {
  await advance(page, 5);
  await expect(page.locator(".task-state")).toHaveText("Delivered · fixture");
  await page.evaluate(async () => {
    const { FixtureAdapter } = await import("/src/fixtures.mjs");
    const { acceptEvent } = await import("/src/state.mjs");
    FixtureAdapter.prototype.reconnect = async function () {
      const s = this.state;
      this.state = acceptEvent(s, {
        taskId: s.taskId,
        runId: s.runId,
        revision: s.revision,
        category: "fixture",
        eventId: "after-delivery-check",
        seq: s.seq + 1,
        kind: "checkpoint",
        data: { ...s.checkpoints[0], status: "checking" },
      });
      return this.snapshot();
    };
  });
  await controls(page);
  await page.getByRole("button", { name: "Disconnect fixture" }).click();
  await page.getByRole("button", { name: "Reconnect fixture" }).click();
  await expect(page.locator(".task-state")).toHaveText(
    "Delivery needs confirmation · fixture",
  );
  await page.evaluate(async () => {
    const { FixtureAdapter } = await import("/src/fixtures.mjs");
    const { acceptEvent } = await import("/src/state.mjs");
    FixtureAdapter.prototype.reconnect = async function () {
      for (const [kind, data] of [
        ["checkpoint", { ...this.state.checkpoints[0], status: "passed" }],
        ["task-outcome", { status: "delivered", result: this.state.result }],
      ]) {
        const s = this.state;
        this.state = acceptEvent(s, {
          taskId: s.taskId,
          runId: s.runId,
          revision: s.revision,
          category: "fixture",
          eventId: `confirm-${s.seq + 1}`,
          seq: s.seq + 1,
          kind,
          data,
        });
      }
      return this.snapshot();
    };
  });
  await controls(page);
  await page.getByRole("button", { name: "Disconnect fixture" }).click();
  await page.getByRole("button", { name: "Reconnect fixture" }).click();
  await expect(page.locator(".task-state")).toHaveText("Delivered · fixture");
});

test("direct links and unknown demo task IDs never show another task as selected", async ({
  page,
}) => {
  await page.goto(`${origin}/demo/debugger?task=fixture-atlas`);
  await expect(page.locator(".pipeline-stage")).toHaveCount(6);
  await page.goto(`${origin}/demo/debugger?task=unavailable`);
  await expect(
    page.getByRole("heading", { name: "Demo session unavailable" }),
  ).toBeVisible();
  await expect(page.locator(".pipeline-stage")).toHaveCount(0);
});

test("a new draft survives conversation selection, Back/Forward, and debugger navigation", async ({
  page,
}) => {
  await newChat(page);
  await page
    .getByLabel("Your request", { exact: true })
    .fill("Keep this independent unsent draft.");
  await nav(page);
  await page.locator(".session-item").click();
  await expect(page.getByLabel("Your feedback", { exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByLabel("Your request", { exact: true })).toHaveValue(
    "Keep this independent unsent draft.",
  );
  await debug(page);
  await expect(
    page.getByRole("heading", { name: "Your request is still a draft" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Back to chat", exact: true }).click();
  await expect(page.getByLabel("Your request", { exact: true })).toHaveValue(
    "Keep this independent unsent draft.",
  );
});
