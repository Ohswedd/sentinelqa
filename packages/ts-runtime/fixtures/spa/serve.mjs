// Tiny static server for the CSR SPA fixture (Phase 17 task 07).
// No external deps — mirrors fixtures/serve.mjs but bound to a single
// root directory so tests can spawn it with `node serve.mjs <port>`.

import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here);
const port = Number(process.argv[2] ?? '4174');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
};

const server = createServer(async (req, res) => {
  try {
    const urlPath = (req.url ?? '/').split('?')[0];
    const cleaned = urlPath === '/' ? '/index.html' : urlPath;
    const filePath = join(root, cleaned);
    if (!filePath.startsWith(root)) {
      res.statusCode = 403;
      res.end('forbidden');
      return;
    }
    const body = await readFile(filePath);
    const ext = filePath.slice(filePath.lastIndexOf('.'));
    res.setHeader('content-type', MIME[ext] ?? 'application/octet-stream');
    res.statusCode = 200;
    res.end(body);
  } catch (err) {
    res.statusCode = 404;
    res.end(`not found: ${err.message}`);
  }
});

server.listen(port, '127.0.0.1', () => {
  // Emit a single line for the spawning test to parse if needed.
  process.stdout.write(JSON.stringify({ port }) + '\n');
});

const shutdown = () => server.close(() => process.exit(0));
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
