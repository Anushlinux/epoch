import { test, expect } from "@playwright/test";
const api = process.env.EPOCH_INTAKE_TEST_ORIGIN;
const origin =
  process.env.EPOCH_INTAKE_FRONTEND_ORIGIN || "http://127.0.0.1:5173";
const key = "epoch.intake.pending.v1";
const payload = (message) => ({
  client_request_id: crypto.randomUUID(),
  message,
  project_id: "browser-proof",
});
async function post(data) {
  const response = await fetch(`${api}/api/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return { status: response.status, task: await response.json() };
}
async function total() {
  return (await (await fetch(`${api}/api/tasks?limit=20&offset=0`)).json())
    .total;
}
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
async function closeNav(page) {
  if (
    await page
      .locator("#sidebar")
      .evaluate((el) => matchMedia("(max-width: 760px)").matches && !el.inert)
  )
    await page.locator(".mobile-close").click();
}
async function settings(page) {
  if (!(await page.getByRole("textbox", { name: "API origin" }).isVisible()))
    await page
      .locator(".topbar")
      .getByRole("button", { name: "Connection settings" })
      .click();
}
async function connect(page) {
  await settings(page);
  const field = page.getByRole("textbox", { name: "API origin" });
  if (await field.isEnabled()) await field.fill(api);
  await page.getByRole("button", { name: "Connect / reconnect" }).click();
  await expect(page.locator(".connection-state")).toHaveAttribute(
    "title",
    "Connected · local API",
  );
}
async function open(page) {
  await page.goto(`${origin}/index.html`);
}
test("actual intake/list/detail, form validation, saved text, keyboard and responsive layout", async ({
  page,
}, info) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await open(page);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to workspace" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#workspace")).toBeFocused();
  await expect(
    page.getByRole("button", { name: "Save request", exact: true }),
  ).toBeDisabled();
  await connect(page);
  await nav(page);
  await expect(
    page.getByText("Persisted HTTP intake proof · no execution", {
      exact: true,
    }),
  ).toBeVisible();
  await closeNav(page);
  const message = `Prepare the Atlas release checklist · ${info.project.name}\nKeep QA ownership and rollback steps. <script>unsafe()</script>`;
  const input = page.getByRole("textbox", { name: "What needs to be done?" });
  await input.fill(" ");
  await page.getByRole("button", { name: "Save request", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("1–16,000");
  await input.fill(message);
  await page.locator("[data-key=project]>summary").click();
  await page.getByRole("textbox", { name: "Project label" }).fill("Atlas 2.4");
  await page.locator("[data-key=project]>summary").click();
  const before = await total();
  await page.getByRole("button", { name: "Save request", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Saved request detail", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".conversation blockquote")).toHaveText(message);
  await expect(input).toHaveValue("");
  expect(await total()).toBe(before + 1);
  await expect(page.locator(".intake-detail")).toContainText(
    "Pending · no execution",
  );
  await page
    .getByText("Inspect API record · intake only", { exact: true })
    .click();
  const task = JSON.parse(await page.locator("#task-record").textContent());
  expect(task.status).toBe("pending");
  expect(task.request.message).toBe(message);
  const actual = await (await fetch(`${api}/api/tasks/${task.id}`)).json();
  expect(actual).toEqual(task);
  await page
    .getByText("Inspect API record · intake only", { exact: true })
    .click();
  await page.getByRole("button", { name: "Reload detail" }).click();
  await expect(page.locator(".conversation blockquote")).toHaveText(message);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.evaluate(() => {
    document.activeElement.blur();
    window.scrollTo(0, 0);
  });
  await page.screenshot({
    path: `evidence/phase7-intake-${info.project.name}.png`,
    fullPage: true,
  });
  await page.reload();
  await connect(page);
  await nav(page);
  await page.getByRole("link").filter({ hasText: message }).click();
  await expect(page.locator(".conversation blockquote")).toHaveText(message);
  await expect(
    page.getByRole("heading", { name: "Saved request detail", exact: true }),
  ).toBeFocused();
});

test("actual 201 acknowledgement is dropped; reload/reconnect sends no POST; frozen retry returns same task with 200", async ({
  page,
}) => {
  await open(page);
  await connect(page);
  const before = await total();
  let sent, createdID;
  await page.route(
    `${api}/api/tasks`,
    async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      sent = route.request().postDataJSON();
      const response = await route.fetch();
      expect(response.status()).toBe(201);
      createdID = (await response.json()).id;
      await route.abort("failed");
    },
    { times: 1 },
  );
  await page
    .getByRole("textbox", { name: "What needs to be done?" })
    .fill("Keep this exact pending request");
  await page.getByRole("button", { name: "Save request", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Acknowledgement unknown",
  );
  await expect(
    page.getByRole("textbox", { name: "What needs to be done?" }),
  ).toBeDisabled();
  const stored = await page.evaluate(
    (key) => JSON.parse(sessionStorage.getItem(key)),
    key,
  );
  expect(stored.payload).toEqual(sent);
  let posts = 0;
  page.on("request", (r) => {
    if (r.method() === "POST") posts++;
  });
  await page.reload();
  await connect(page);
  expect(posts).toBe(0);
  const response = page.waitForResponse(
    (r) => r.url() === `${api}/api/tasks` && r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Retry exact submission" }).click();
  expect((await response).status()).toBe(200);
  await expect(
    page
      .locator(".intake-notice")
      .filter({
        hasText:
          "Existing request confirmed by an identical retry. No new task was created.",
      }),
  ).toBeVisible();
  expect(await total()).toBe(before + 1);
  expect(
    await page.evaluate((key) => sessionStorage.getItem(key), key),
  ).toBeNull();
  await page.getByText("Inspect API record · intake only").click();
  expect(JSON.parse(await page.locator("#task-record").textContent()).id).toBe(
    createdID,
  );
});

test("real 409 conflict keeps identity until explicit edit; corrupted reload blocks all submissions", async ({
  page,
}) => {
  const original = payload("Original already saved");
  const saved = await post(original);
  expect(saved.status).toBe(201);
  await page.addInitScript(
    ({ key, api, original }) =>
      sessionStorage.setItem(
        key,
        JSON.stringify({
          version: 1,
          origin: api,
          payload: {
            ...original,
            message: "Changed content under existing ID",
          },
        }),
      ),
    { key, api, original },
  );
  await open(page);
  await connect(page);
  const before = await total();
  await page.getByRole("button", { name: "Retry exact submission" }).click();
  await expect(page.getByRole("alert")).toContainText("HTTP 409");
  await expect(
    page.getByRole("textbox", { name: "What needs to be done?" }),
  ).toBeDisabled();
  expect(await total()).toBe(before);
  await page
    .getByRole("button", { name: "Return rejected content to draft" })
    .click();
  await expect(
    page.getByRole("textbox", { name: "What needs to be done?" }),
  ).toBeFocused();
  await expect(
    page.getByRole("textbox", { name: "What needs to be done?" }),
  ).toHaveValue("Changed content under existing ID");
  await page.addInitScript(
    (key) => sessionStorage.setItem(key, "{broken"),
    key,
  );
  await page.reload();
  await connect(page);
  await expect(
    page.getByText(/Recovery identity is unavailable/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save request", exact: true }),
  ).toBeDisabled();
  expect(await total()).toBe(before);
});

test("browser offline read keeps stale records and draft; reconnect uses real health/list and sends no work", async ({
  page,
  context,
}) => {
  await open(page);
  await connect(page);
  await page
    .getByRole("textbox", { name: "What needs to be done?" })
    .fill("Unsaved draft survives disconnection");
  const before = await total();
  await context.setOffline(true);
  await nav(page);
  await page.getByRole("button", { name: "Refresh list", exact: true }).click();
  await closeNav(page);
  await nav(page);
  await expect(
    page.getByText("Last loaded records · connection unavailable"),
  ).toBeVisible();
  await closeNav(page);
  await expect(
    page.getByRole("button", { name: "Save request", exact: true }),
  ).toBeDisabled();
  await settings(page);
  await page.getByRole("button", { name: "Connect / reconnect" }).click();
  await expect(page.getByRole("alert")).toContainText("could not be reached");
  await context.setOffline(false);
  await connect(page);
  await expect(
    page.getByRole("textbox", { name: "What needs to be done?" }),
  ).toHaveValue("Unsaved draft survives disconnection");
  expect(await total()).toBe(before);
});

test("actual server 422 after a deliberately fault-mutated body is displayed without success or replacement", async ({
  page,
}) => {
  await open(page);
  await connect(page);
  const before = await total();
  await page.route(
    `${api}/api/tasks`,
    async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      const body = route.request().postDataJSON();
      const response = await route.fetch({
        postData: JSON.stringify({ ...body, message: " " }),
      });
      expect(response.status()).toBe(422);
      await route.fulfill({ response });
    },
    { times: 1 },
  );
  await page
    .getByRole("textbox", { name: "What needs to be done?" })
    .fill("Preserve the input despite a rejected transport payload");
  await page.getByRole("button", { name: "Save request", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("HTTP 422");
  await expect(
    page.getByRole("heading", { name: "Saved request detail", exact: true }),
  ).toHaveCount(0);
  expect(await total()).toBe(before);
});

test("a missing-detail response marks the retained receipt unavailable without blocking health/list reconnect", async ({
  page,
}) => {
  const saved = await post(
    payload("Retain this receipt if the detail becomes unavailable"),
  );
  await open(page);
  await connect(page);
  await nav(page);
  await page.locator(`[data-task="${saved.task.id}"]`).click();
  await page.route(`${api}/api/tasks/${saved.task.id}`, async (route) => {
    // Deliberately substitute a real server 404; no stored task is deleted.
    const response = await route.fetch({
      url: `${api}/api/tasks/${crypto.randomUUID()}`,
    });
    expect(response.status()).toBe(404);
    await route.fulfill({ response });
  });
  const before = await total();
  await page.getByRole("button", { name: "Reload detail" }).click();
  await expect(
    page.getByText("Unavailable · last loaded record", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".intake-detail")).toContainText(
    "not a current stored record",
  );
  await settings(page);
  await page.getByRole("button", { name: "Refresh connection" }).click();
  await expect(page.locator(".connection-state")).toHaveAttribute(
    "title",
    "Connected · local API",
  );
  await expect(
    page.getByText("Unavailable · last loaded record", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("HTTP 404");
  await expect(
    page.getByRole("button", { name: "Save request", exact: true }),
  ).toBeDisabled(); // This selected chat is one saved request; New chat remains available.
  expect(await total()).toBe(before);
  await page.unroute(`${api}/api/tasks/${saved.task.id}`);
  await page.getByRole("button", { name: "Reload detail" }).click();
  await expect(
    page.getByText("Unavailable · last loaded record", { exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".intake-detail")).toContainText(
    "Pending · no execution",
  );
});

test("real chat and debugger retain task selection and an independent unsent draft", async ({
  page,
}) => {
  const saved = await post(payload("A saved request for the navigation check"));
  let posts = 0;
  page.on("request", (request) => {
    if (request.method() === "POST") posts++;
  });
  await open(page);
  await connect(page);
  await page
    .getByRole("textbox", { name: "What needs to be done?" })
    .fill("Keep this separate unsent request");
  await nav(page);
  await page.locator(`[data-task="${saved.task.id}"]`).click();
  await expect(
    page.getByRole("textbox", { name: "What needs to be done?" }),
  ).toHaveValue("");
  await page.getByRole("link", { name: "Open debugger", exact: true }).click();
  await expect(page).toHaveURL(`${origin}/debugger?task=${saved.task.id}`);
  await expect(
    page.getByRole("heading", { name: "No execution recorded" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Start release run" })).toBeDisabled();
  await expect(page.locator(".context-column")).toContainText(
    "Saving a request does not start execution.",
  );
  await page.goBack();
  await expect(page.locator(".conversation blockquote")).toHaveText(
    saved.task.request.message,
  );
  await page.goBack();
  await expect(
    page.getByRole("textbox", { name: "What needs to be done?" }),
  ).toHaveValue("Keep this separate unsent request");
  await page.goForward();
  await expect(page.locator(".conversation blockquote")).toHaveText(
    saved.task.request.message,
  );
  await page.goto(`${origin}/debugger?task=${saved.task.id}`);
  await connect(page);
  await expect(page.locator(".context-column blockquote")).toHaveText(
    saved.task.request.message,
  );
  await page.getByRole("link", { name: "Back to chat", exact: true }).click();
  await expect(page).toHaveURL(`${origin}/chat?task=${saved.task.id}`);
  expect(posts).toBe(0);
});
