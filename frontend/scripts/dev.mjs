// Local frontend development host for the backend's documented CORS origin.
// No API proxy, dependencies, credentials or backend behavior are provided here.
import http from 'node:http';
import { readFile, realpath } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
export const frontendRoot = fileURLToPath(new URL('../', import.meta.url));
const types = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.md': 'text/plain; charset=utf-8' };
const entries = new Set(['/index.html', '/fixtures.html', '/mark.svg', '/README.md', '/CONTRACT-PROPOSAL.md']);
export function createDevServer() {
  return http.createServer(async (request, response) => {
    const reply = (status, body, contentType = 'text/plain; charset=utf-8') => {
      response.writeHead(status, { 'Content-Type': contentType, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' });
      response.end(request.method === 'HEAD' ? undefined : body);
    };
    if (!['127.0.0.1:5173', 'localhost:5173'].includes(request.headers.host)) return reply(403, 'Use http://127.0.0.1:5173 or http://localhost:5173.');
    if (!['GET', 'HEAD'].includes(request.method)) return reply(405, 'Only frontend GET and HEAD requests are supported.');
    try {
      const url = new URL(request.url, 'http://127.0.0.1:5173');
      const pathname = url.pathname === '/' ? '/index.html' : decodeURIComponent(url.pathname);
      const source = /^\/src\/[a-zA-Z0-9_-]+\.(mjs|css)$/.test(pathname);
      if (!entries.has(pathname) && !source) return reply(404, 'Frontend resource not found.');
      const file = await realpath(path.resolve(frontendRoot, `.${pathname}`));
      if (!file.startsWith(frontendRoot)) return reply(404, 'Frontend resource not found.');
      return reply(200, await readFile(file), types[path.extname(file)]);
    } catch { return reply(404, 'Frontend resource not found.'); }
  });
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const server = createDevServer();
  server.on('error', (error) => {
    console.error(error.code === 'EADDRINUSE' ? 'Port 5173 is occupied. Stop your existing frontend explicitly before starting this workspace.' : error.message);
    process.exitCode = 1;
  });
  server.listen(5173, '127.0.0.1', () => console.log('Epoch frontend: http://127.0.0.1:5173 — connect to your local Phase 1 API in the app.'));
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close());
}
