// Tiny static file server for the Phase 04.07 fixture sample-app.
// No external deps — just node:http + node:fs.
//
// Usage:
//   node fixtures/serve.mjs [--port 4173] [--root fixtures/sample-app]
//
// Writes the listening port to stdout as a single JSON line so the
// spawning test can `JSON.parse(line)` and grab `{ port }`.

import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

function parseArgs(argv) {
  const out = { port: 0, root: 'sample-app' };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--port') {
      out.port = Number(argv[++i]);
    } else if (argv[i] === '--root') {
      out.root = argv[++i];
    }
  }
  return out;
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
};

const args = parseArgs(process.argv.slice(2));
const rootPath = resolve(here, args.root);

const server = createServer(async (req, res) => {
  try {
    const urlPath = (req.url ?? '/').split('?')[0];
    const cleaned = urlPath === '/' ? '/index.html' : urlPath;
    const filePath = join(rootPath, cleaned);
    // Prevent path traversal.
    if (!filePath.startsWith(rootPath)) {
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

server.listen(args.port, '127.0.0.1', () => {
  const addr = server.address();
  const port = typeof addr === 'object' && addr !== null ? addr.port : args.port;
  process.stdout.write(JSON.stringify({ port }) + '\n');
});

const shutdown = () => {
  server.close(() => process.exit(0));
};
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
