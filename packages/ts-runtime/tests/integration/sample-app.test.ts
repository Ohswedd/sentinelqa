// Phase 04.07 — fixture sample-app integration.
//
// This test exercises the *fixture infrastructure* (HTTP server,
// known URLs, expected DOM) without launching a browser. The
// Chromium-launching smoke that runs the same fixture through
// Playwright lives in `playwright.smoke.spec.ts` and is gated by
// `SENTINELQA_HAS_CHROMIUM=1` so default CI doesn't need a browser
// install.

import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const serveScript = resolve(here, '..', '..', 'fixtures', 'serve.mjs');

let server: ChildProcessWithoutNullStreams | null = null;
let baseUrl = '';

async function readFirstJsonLine(child: ChildProcessWithoutNullStreams): Promise<{
  port: number;
}> {
  return new Promise((resolveFn, rejectFn) => {
    let buf = '';
    const onData = (chunk: Buffer): void => {
      buf += chunk.toString();
      const nl = buf.indexOf('\n');
      if (nl !== -1) {
        const line = buf.slice(0, nl);
        child.stdout.off('data', onData);
        try {
          resolveFn(JSON.parse(line) as { port: number });
        } catch (err) {
          rejectFn(err as Error);
        }
      }
    };
    child.stdout.on('data', onData);
    child.once('error', rejectFn);
  });
}

beforeAll(async () => {
  server = spawn('node', [serveScript, '--port', '0']);
  server.stderr.on('data', () => {
    /* ignore */
  });
  const { port } = await readFirstJsonLine(server);
  baseUrl = `http://127.0.0.1:${port}`;
});

afterAll(() => {
  if (server !== null) server.kill('SIGTERM');
});

describe('fixture sample-app HTTP server', () => {
  it('serves the landing page at /', async () => {
    const res = await fetch(baseUrl + '/');
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toContain('<h1>Sign in</h1>');
    expect(body).toContain('id="email"');
    expect(body).toContain('aria-label="Primary"');
  });

  it('serves /success.html', async () => {
    const res = await fetch(baseUrl + '/success.html');
    expect(res.status).toBe(200);
    const body = await res.text();
    expect(body).toContain('You are signed in');
  });

  it('returns 404 for unknown routes', async () => {
    const res = await fetch(baseUrl + '/does-not-exist');
    expect(res.status).toBe(404);
  });
});
