// Actual unchanged Phase 1 server + temporary SQLite data. No backend source edits.
import { spawn } from "node:child_process";
import { mkdtemp, rm, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import net from "node:net";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
const frontend = fileURLToPath(new URL("../", import.meta.url));
const backend = path.resolve(frontend, "../backend");
const data = await mkdtemp(path.join(tmpdir(), "epoch-intake-proof-"));
const port = await new Promise((resolve, reject) => {
  const server = net.createServer();
  server.on("error", reject);
  server.listen(0, "127.0.0.1", () => {
    const port = server.address().port;
    server.close(() => resolve(port));
  });
});
const origin = `http://127.0.0.1:${port}`;
const browserOrigin = `http://127.0.0.1:${process.env.EPOCH_FRONTEND_PORT || 5173}`;
let child;
let frontendChild;
let serverLog = "";
async function startFrontend() {
  frontendChild = spawn(
    process.execPath,
    [path.join(frontend, "scripts/dev.mjs")],
    { cwd: frontend, stdio: ["ignore", "pipe", "pipe"] },
  );
  let log = "";
  frontendChild.stderr.on("data", (chunk) => {
    log += chunk;
  });
  await new Promise((resolve, reject) => {
    const timeout = setTimeout(
      () => reject(new Error("Frontend startup timed out.")),
      10000,
    );
    frontendChild.on("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    frontendChild.once("exit", () => {
      clearTimeout(timeout);
      reject(new Error(`Frontend exited: ${log}`));
    });
    frontendChild.stdout.on("data", (chunk) => {
      if (chunk.toString().includes("Epoch frontend:")) {
        clearTimeout(timeout);
        resolve();
      }
    });
  });
  const response = await fetch(browserOrigin);
  assert.equal(response.status, 200);
  assert.match(await response.text(), /Epoch · Chat/);
  assert.equal((await fetch(`${browserOrigin}/src/intake.mjs`)).status, 200);
  for (const route of [
    "/chat",
    "/debugger",
    "/demo/chat",
    "/demo/debugger",
    "/fixtures.html",
    "/fonts/bodoni-moda.ttf",
  ])
    assert.equal((await fetch(browserOrigin + route)).status, 200);
  assert.match(
    await (await fetch(browserOrigin + "/demo/debugger")).text(),
    /connect-src 'none'/,
  );
  assert.equal(
    (await fetch(browserOrigin + "/fonts/../package.json")).status,
    404,
  );
  assert.equal((await fetch(`${browserOrigin}/.env`)).status, 404);
  assert.equal((await fetch(`${browserOrigin}/../backend/.env`)).status, 404);
  assert.equal((await fetch(browserOrigin, { method: "POST" })).status, 405);
}
async function start() {
  child = spawn(path.join(backend, ".venv/bin/epoch-backend"), ["serve"], {
    cwd: backend,
    env: {
      ...process.env,
      EPOCH_DATA_DIR: data,
      EPOCH_PORT: String(port),
      EPOCH_HOST: "127.0.0.1",
      EPOCH_CORS_ORIGINS: JSON.stringify([browserOrigin]),
      EPOCH_LOG_LEVEL: "warning",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.on("data", (chunk) => {
    serverLog += chunk;
  });
  child.stderr.on("data", (chunk) => {
    serverLog += chunk;
  });
  let spawnError;
  child.on("error", (error) => {
    spawnError = error;
  });
  for (let attempt = 0; attempt < 100; attempt++) {
    if (spawnError) throw spawnError;
    if (child.exitCode !== null)
      throw new Error(`Backend exited: ${serverLog}`);
    try {
      if ((await fetch(`${origin}/api/health`)).ok) return;
    } catch {
      /* bounded startup poll */
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Backend startup timed out: ${serverLog}`);
}
async function stop() {
  if (!child || child.exitCode !== null) return;
  await new Promise((resolve) => {
    child.once("exit", resolve);
    child.kill("SIGTERM");
  });
}
const http = async (route, body, headers = {}) => {
  const response = await fetch(origin + route, {
    method: body ? "POST" : "GET",
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  return { status: response.status, body: await response.json() };
};
try {
  await startFrontend();
  await start();
  const health = await http("/api/health");
  assert.deepEqual(health.body, {
    status: "ok",
    phase: 1,
    storage: "ok",
    execution_enabled: false,
  });
  const payload = {
    client_request_id: crypto.randomUUID(),
    message: "Persisted HTTP intake proof · no execution",
    project_id: "integration-proof",
  };
  const created = await http("/api/tasks", payload, { Origin: browserOrigin });
  assert.equal(created.status, 201);
  assert.equal(created.body.status, "pending");
  const retry = await http("/api/tasks", payload, { Origin: browserOrigin });
  assert.equal(retry.status, 200);
  assert.deepEqual(retry.body, created.body);
  const normalized = await http("/api/tasks", {
    ...payload,
    message: ` ${payload.message} `,
  });
  assert.equal(normalized.status, 200);
  const conflict = await http("/api/tasks", {
    ...payload,
    message: "Changed under the same ID",
  });
  assert.equal(conflict.status, 409);
  const invalid = await http("/api/tasks", {
    ...payload,
    client_request_id: crypto.randomUUID(),
    message: " ",
  });
  assert.equal(invalid.status, 422);
  const missing = await http(`/api/tasks/${crypto.randomUUID()}`);
  assert.equal(missing.status, 404);
  const denied = await http(
    "/api/tasks",
    { ...payload, client_request_id: crypto.randomUUID() },
    { Origin: "http://localhost:59999" },
  );
  assert.equal(denied.status, 403);
  const preflight = await fetch(`${origin}/api/tasks`, {
    method: "OPTIONS",
    headers: {
      Origin: browserOrigin,
      "Access-Control-Request-Method": "POST",
      "Access-Control-Request-Headers": "content-type",
    },
  });
  assert.equal(preflight.status, 200);
  assert.equal(
    preflight.headers.get("access-control-allow-origin"),
    browserOrigin,
  );
  assert.equal((await http("/api/tasks?limit=20&offset=0")).body.total, 1);
  await stop();
  await start();
  const restored = await http(`/api/tasks/${created.body.id}`);
  assert.deepEqual(restored.body, created.body);
  const restartedRetry = await http("/api/tasks", payload);
  assert.equal(restartedRetry.status, 200);
  console.log(
    "Real HTTP proof passed: health, 201/200 identical + normalized retry, 409/422/404/403, CORS, list/detail and restart persistence.",
  );
  const result = await new Promise((resolve, reject) => {
    const tests = spawn(
      process.execPath,
      [
        path.join(frontend, "node_modules/@playwright/test/cli.js"),
        "test",
        "--config",
        "playwright.intake.config.mjs",
      ],
      {
        cwd: frontend,
        env: {
          ...process.env,
          EPOCH_INTAKE_TEST_ORIGIN: origin,
          EPOCH_INTAKE_FRONTEND_ORIGIN: browserOrigin,
        },
        stdio: "inherit",
      },
    );
    tests.on("error", reject);
    tests.on("exit", resolve);
  });
  assert.equal(result, 0, "Browser intake checks failed");
  await mkdir(path.join(frontend, "evidence"), { recursive: true });
  await writeFile(
    path.join(frontend, "evidence/intake-http.json"),
    JSON.stringify(
      {
        verified_at: new Date().toISOString(),
        category: "actual-local-phase-1-http",
        backend_base: "0a062dde6fcf5f10f792cf77813fe8adbaf117e3",
        isolated_temporary_database: true,
        health: health.body,
        task: created.body,
        checks: {
          create: 201,
          identical_retry: 200,
          normalized_retry: 200,
          conflict: 409,
          validation: 422,
          missing: 404,
          disallowed_origin: 403,
          allowed_cors_preflight: 200,
          restart_record_unchanged: true,
          restart_identical_retry: 200,
        },
        execution_occurred: false,
        browser_origin: browserOrigin,
        limitations: [
          "Temporary local intake/storage only; no executor or repair",
          `Actual frontend dev server at ${browserOrigin} and unchanged backend; no source interception or security bypass`,
          "Unknown acknowledgement and offline browser cases inject transport faults, not backend failures",
        ],
      },
      null,
      2,
    ) + "\n",
  );
} finally {
  await stop();
  if (frontendChild && frontendChild.exitCode === null)
    await new Promise((resolve) => {
      frontendChild.once("exit", resolve);
      frontendChild.kill("SIGTERM");
    });
  await rm(data, { recursive: true, force: true });
}
