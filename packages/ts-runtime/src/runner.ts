// `sentinel-ts run` — spawn Playwright, route reporter events to
// stdout. Python (engine/runner Phase 08) invokes this binary.
//
// Design:
//   - `--input <path>` points to a run-config JSON described by the
//     `RunConfigSchema` below. The shape is locked here (TS) and
//     mirrored in `engine/orchestrator/ts_bridge.py` (Phase 04.04).
//   - We spawn `playwright test` via the Playwright bin resolved from
//     `node_modules`, with `--reporter=<our reporter path>` and the
//     test files from the run-config. The reporter (reporter.ts) writes
//     JSONL events to stdout; the child's stdout is inherited so events
//     flow straight to the parent (Python).
//   - Stderr is captured and re-emitted only when the run fails — this
//     keeps the JSONL stream clean.
//
// Exit codes:
//   0  all tests passed
//   1  at least one test failed / timed_out
//   2  Playwright itself errored, config invalid, or spawn failed
//
// CLAUDE §21: no stealth, no evasion, no arbitrary sleeps.

import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { resolve as resolvePath } from 'node:path';

import { z } from 'zod';

const RunConfigSchema = z
  .object({
    schema_version: z.string().default('1.0.0'),
    run_id: z.string().min(1),
    target: z.string().min(1),
    run_dir: z.string().min(1),
    spec_files: z.array(z.string()).default([]),
    workers: z.number().int().positive().optional(),
    shard: z
      .object({ current: z.number().int().positive(), total: z.number().int().positive() })
      .optional(),
    browser: z.enum(['chromium', 'firefox', 'webkit']).default('chromium'),
    headless: z.boolean().default(true),
    timeout_ms: z.number().int().positive().default(30_000),
    retries: z.number().int().min(0).default(0),
    env: z.record(z.string()).default({}),
  })
  .strict();

export type RunConfig = z.infer<typeof RunConfigSchema>;

export interface RunnerOptions {
  /** Path to the run-config JSON. Required. */
  readonly inputPath: string;
  /** Override `run_dir` from the config. Useful for CLI flags. */
  readonly runDirOverride?: string;
  /** Override the browser. */
  readonly browserOverride?: 'chromium' | 'firefox' | 'webkit';
  /** Spawn function (for tests). */
  readonly spawnFn?: typeof spawn;
  /** Override the reporter path (for tests). */
  readonly reporterPathOverride?: string;
  /** Workspace root for resolving the Playwright bin (for tests). */
  readonly cwd?: string;
  /** Stderr sink (defaults to process.stderr). */
  readonly stderr?: NodeJS.WriteStream;
}

export class RunConfigError extends Error {
  constructor(
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = 'RunConfigError';
  }
}

export function loadRunConfig(path: string): RunConfig {
  if (!existsSync(path)) {
    throw new RunConfigError(`run-config not found: ${path}`);
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(readFileSync(path, 'utf8'));
  } catch (err) {
    throw new RunConfigError(`run-config is not valid JSON: ${(err as Error).message}`);
  }
  const result = RunConfigSchema.safeParse(parsed);
  if (!result.success) {
    throw new RunConfigError(`run-config failed schema validation`, result.error.flatten());
  }
  return result.data;
}

/**
 * Locate the Playwright CLI bin. Looks at the workspace's local
 * `node_modules/.bin/playwright`. Returns null if not found so the
 * caller can fall back to `npx`.
 */
export function resolvePlaywrightBin(cwd: string = process.cwd()): string | null {
  const candidates = [
    resolvePath(cwd, 'node_modules', '.bin', 'playwright'),
    resolvePath(cwd, '..', '..', 'node_modules', '.bin', 'playwright'),
  ];
  for (const p of candidates) if (existsSync(p)) return p;
  return null;
}

/**
 * Resolve the path to the compiled reporter.js. In dev (running from
 * src/) we point at the source TS; in prod (running from dist/cli.js)
 * we point at dist/reporter.js. Pre-resolved via the `import.meta.url`.
 */
export function resolveReporterPath(here: string): string {
  // here is the directory of cli.js / runner.ts. Sibling reporter.js
  // lives next to it.
  return resolvePath(here, 'reporter.js');
}

export async function runPlaywright(opts: RunnerOptions): Promise<number> {
  const config = loadRunConfig(opts.inputPath);
  const cwd = opts.cwd ?? process.cwd();
  const runDir = opts.runDirOverride ?? config.run_dir;
  const browser = opts.browserOverride ?? config.browser;

  const spawnImpl = opts.spawnFn ?? spawn;
  const stderr = opts.stderr ?? process.stderr;

  const reporterPath = opts.reporterPathOverride ?? resolveReporterPath(cwd);
  if (!existsSync(reporterPath) && opts.reporterPathOverride === undefined) {
    stderr.write(
      `sentinel-ts: reporter module missing at ${reporterPath}. ` +
        `Run \`pnpm --filter @sentinelqa/ts-runtime build\` first.\n`,
    );
    return 2;
  }

  const bin = resolvePlaywrightBin(cwd);
  const cmd = bin ?? 'npx';
  const baseArgs = bin === null ? ['playwright', 'test'] : ['test'];
  const args = [
    ...baseArgs,
    `--reporter=${reporterPath}`,
    `--project=${browser}`,
    `--workers=${(config.workers ?? 1).toString()}`,
    `--retries=${config.retries.toString()}`,
    `--timeout=${config.timeout_ms.toString()}`,
  ];
  if (config.shard !== undefined) {
    args.push(`--shard=${config.shard.current}/${config.shard.total}`);
  }
  for (const spec of config.spec_files) args.push(spec);

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    ...config.env,
    SENTINELQA_RUN_ID: config.run_id,
    SENTINELQA_RUN_DIR: runDir,
    SENTINELQA_TARGET: config.target,
  };

  return await new Promise<number>((resolveFn) => {
    const child = spawnImpl(cmd, args, {
      cwd,
      env,
      stdio: ['ignore', 'inherit', 'pipe'],
    });
    const stderrChunks: Buffer[] = [];
    child.stderr?.on('data', (chunk: Buffer) => stderrChunks.push(chunk));
    child.on('error', (err) => {
      stderr.write(`sentinel-ts: failed to spawn ${cmd}: ${err.message}\n`);
      resolveFn(2);
    });
    child.on('close', (code) => {
      // Code 0 = pass, 1 = at least one test failed, anything else =
      // Playwright crashed. Forward stderr only on non-zero so the
      // JSONL stream stays clean on success.
      if (code !== 0 && stderrChunks.length > 0) {
        stderr.write(Buffer.concat(stderrChunks).toString());
      }
      if (code === 0) resolveFn(0);
      else if (code === 1) resolveFn(1);
      else resolveFn(2);
    });
  });
}

/**
 * `sentinel-ts list-tests` — list spec files matching a glob.
 * Implemented without Playwright (just fs+glob) so it works in CI even
 * before Playwright browser install.
 */
export async function listTests(
  pattern: string,
  cwd: string = process.cwd(),
): Promise<readonly string[]> {
  // Use Node's built-in fs/promises#glob (Node ≥ 22) when available;
  // fall back to a manual walk for Node 20. We declared `engines.node`
  // ≥ 20 so we cannot rely on the native glob.
  const fsp = await import('node:fs/promises');
  const hasNativeGlob = 'glob' in fsp && typeof (fsp as { glob?: unknown }).glob === 'function';

  const iter: AsyncIterable<string> = hasNativeGlob
    ? (fsp as unknown as { glob: (p: string, o?: { cwd?: string }) => AsyncIterable<string> }).glob(
        pattern,
        { cwd },
      )
    : fallbackGlob(pattern, cwd);

  const out: string[] = [];
  for await (const file of iter) out.push(file);
  out.sort();
  return out;
}

async function* fallbackGlob(pattern: string, cwd: string): AsyncGenerator<string> {
  // Minimal recursive glob — supports `**/*.spec.ts` style only.
  const { readdir } = await import('node:fs/promises');
  // Compile to a Regex once.
  const escaped = pattern
    .replace(/[.+^${}()|[\]\\]/g, '\\$&')
    .replace(/\*\*\//g, '(?:.+/)?')
    .replace(/\*\*/g, '.+')
    .replace(/\*/g, '[^/]*')
    .replace(/\?/g, '[^/]');
  const re = new RegExp(`^${escaped}$`);
  async function* walk(dir: string, rel: string): AsyncGenerator<string> {
    let entries;
    try {
      entries = await readdir(resolvePath(cwd, dir), { withFileTypes: true });
    } catch {
      return;
    }
    for (const ent of entries) {
      if (ent.name === 'node_modules' || ent.name === 'dist' || ent.name === '.git') continue;
      const childRel = rel === '' ? ent.name : `${rel}/${ent.name}`;
      if (ent.isDirectory()) {
        yield* walk(resolvePath(cwd, childRel), childRel);
      } else if (re.test(childRel)) {
        yield childRel;
      }
    }
  }
  yield* walk(cwd, '');
}

/**
 * `sentinel-ts validate-helpers` — confirms `@sentinelqa/ts-runtime`
 * loads, the redaction-rules JSON is readable, and PROTOCOL_VERSION is
 * exported. Returns a structured result; the CLI renders it as
 * human-readable text or JSON.
 */
export interface ValidationCheck {
  readonly name: string;
  readonly ok: boolean;
  readonly detail: string;
}

export async function validateHelpers(): Promise<readonly ValidationCheck[]> {
  const checks: ValidationCheck[] = [];

  try {
    const mod = await import('./index.js');
    checks.push({
      name: 'package-identity',
      ok: mod.PACKAGE_NAME === '@sentinelqa/ts-runtime',
      detail: `PACKAGE_NAME=${mod.PACKAGE_NAME}, VERSION=${mod.VERSION}`,
    });
    checks.push({
      name: 'protocol-version',
      ok: typeof mod.PROTOCOL_VERSION === 'string' && /^\d+\.\d+\.\d+$/.test(mod.PROTOCOL_VERSION),
      detail: `PROTOCOL_VERSION=${mod.PROTOCOL_VERSION}`,
    });
  } catch (err) {
    checks.push({
      name: 'package-load',
      ok: false,
      detail: `failed to import index: ${(err as Error).message}`,
    });
    return checks;
  }

  try {
    const { loadRedactionRules } = await import('./redact.js');
    const rules = loadRedactionRules();
    checks.push({
      name: 'redaction-rules',
      ok: rules.value_rules.length > 0 && rules.secret_key_names.length > 0,
      detail: `rules=${rules.value_rules.length} secret_keys=${rules.secret_key_names.length}`,
    });
  } catch (err) {
    checks.push({
      name: 'redaction-rules',
      ok: false,
      detail: `failed to load redaction-rules.json: ${(err as Error).message}`,
    });
  }

  try {
    const { sentinelStep, captureEvidence, redactedNetwork } = await import('./helpers.js');
    checks.push({
      name: 'helpers-exported',
      ok:
        typeof sentinelStep === 'function' &&
        typeof captureEvidence === 'function' &&
        typeof redactedNetwork === 'function',
      detail: 'sentinelStep, captureEvidence, redactedNetwork',
    });
  } catch (err) {
    checks.push({
      name: 'helpers-exported',
      ok: false,
      detail: `failed to import helpers: ${(err as Error).message}`,
    });
  }

  return checks;
}
