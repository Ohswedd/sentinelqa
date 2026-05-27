#!/usr/bin/env node
// Postbuild: make dist/cli.js executable with a node shebang.
// CLAUDE.md §21 — the TS runtime is owned by Node; the bin must be
// runnable directly when pnpm sets up symlinks (sentinel-ts → dist/cli.js).
import { chmodSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const cliPath = resolve(here, '..', 'dist', 'cli.js');

const original = readFileSync(cliPath, 'utf8');
const SHEBANG = '#!/usr/bin/env node\n';
const next = original.startsWith('#!') ? original : SHEBANG + original;
if (next !== original) {
  writeFileSync(cliPath, next, 'utf8');
}
chmodSync(cliPath, 0o755);
