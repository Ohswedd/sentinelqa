// CLI glue for `sentinel-ts discover` ( task 07).
// Keeps the config-loader + types out of `cli.ts` so the CLI module
// stays focused on argument routing. Importing this module never
// pulls in Chromium — the launcher type is the only Playwright-touching
// surface and it lives in `discover.ts`.

import { readFile } from 'node:fs/promises';
import { stdin } from 'node:process';

export {
  type DiscoverBrowser,
  type DiscoverConfig,
  type DiscoverContext,
  type DiscoverLauncher,
  type DiscoverPage,
  runDiscover,
} from './discover.js';

export const DEFAULT_CONFIG_STDIN_TOKEN = '-';

import type { DiscoverConfig } from './discover.js';

const REQUIRED_KEYS: readonly (keyof DiscoverConfig)[] = [
  'schema_version',
  'base_url',
  'run_id',
  'max_depth',
  'max_pages',
  'rate_limit_rps',
  'respect_robots',
  'same_host_only',
  'extra_allowed_hosts',
  'request_timeout_seconds',
  'user_agent',
  'cookies',
];

/**
 * Read a discover config from a file path or stdin (when path is `-`).
 * Throws `Error` for missing keys / wrong types so the dispatcher
 * surfaces exit code 2.
 */
export async function loadDiscoverConfig(path: string): Promise<DiscoverConfig> {
  const raw =
    path === DEFAULT_CONFIG_STDIN_TOKEN ? await readStdin() : await readFile(path, 'utf-8');
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(`config is not valid JSON (${(err as Error).message}).`);
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new Error('config must be a JSON object.');
  }
  const obj = parsed as Record<string, unknown>;
  for (const key of REQUIRED_KEYS) {
    if (!(key in obj)) {
      throw new Error(`config missing required key \`${String(key)}\`.`);
    }
  }
  return {
    schema_version: assertString(obj['schema_version'], 'schema_version'),
    base_url: assertString(obj['base_url'], 'base_url'),
    run_id: assertString(obj['run_id'], 'run_id'),
    max_depth: assertNumber(obj['max_depth'], 'max_depth'),
    max_pages: assertNumber(obj['max_pages'], 'max_pages'),
    rate_limit_rps: assertNumber(obj['rate_limit_rps'], 'rate_limit_rps'),
    respect_robots: assertBoolean(obj['respect_robots'], 'respect_robots'),
    same_host_only: assertBoolean(obj['same_host_only'], 'same_host_only'),
    extra_allowed_hosts: assertStringArray(obj['extra_allowed_hosts'], 'extra_allowed_hosts'),
    request_timeout_seconds: assertNumber(
      obj['request_timeout_seconds'],
      'request_timeout_seconds',
    ),
    user_agent: assertString(obj['user_agent'], 'user_agent'),
    cookies: assertStringStringMap(obj['cookies'], 'cookies'),
  };
}

async function readStdin(): Promise<string> {
  const chunks: Uint8Array[] = [];
  for await (const chunk of stdin) {
    chunks.push(
      Buffer.isBuffer(chunk) ? new Uint8Array(chunk) : Buffer.from(chunk as Uint8Array | string),
    );
  }
  return Buffer.concat(chunks).toString('utf-8');
}

function assertString(value: unknown, field: string): string {
  if (typeof value !== 'string')
    throw new Error(`config field \`${field}\` must be a string (got ${describeType(value)}).`);
  return value;
}

function assertNumber(value: unknown, field: string): number {
  if (typeof value !== 'number')
    throw new Error(`config field \`${field}\` must be a number (got ${describeType(value)}).`);
  return value;
}

function assertBoolean(value: unknown, field: string): boolean {
  if (typeof value !== 'boolean')
    throw new Error(`config field \`${field}\` must be a boolean (got ${describeType(value)}).`);
  return value;
}

function assertStringArray(value: unknown, field: string): readonly string[] {
  if (!Array.isArray(value))
    throw new Error(`config field \`${field}\` must be a string[] (got ${describeType(value)}).`);
  return value.map((entry, idx) => {
    if (typeof entry !== 'string')
      throw new Error(`config field \`${field}[${idx}]\` must be a string.`);
    return entry;
  });
}

function assertStringStringMap(value: unknown, field: string): Record<string, string> {
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    throw new Error(`config field \`${field}\` must be a Record<string, string>.`);
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (typeof v !== 'string') throw new Error(`config field \`${field}.${k}\` must be a string.`);
    out[k] = v;
  }
  return out;
}

function describeType(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  return typeof value;
}
