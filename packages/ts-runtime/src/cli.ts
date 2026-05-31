// `sentinel-ts` — the CLI Python orchestrates to run Playwright specs.
// PRD §15, CLAUDE.md §8 (Python ↔ TS contract).
//
// Commands:
//   sentinel-ts --help / --version
//   sentinel-ts run --input <path> [--run-dir <path>] [--browser ...]
//   sentinel-ts list-tests --pattern <glob>
//   sentinel-ts validate-helpers [--json]
//
// `--ci` is accepted on every subcommand. In CI mode we never write
// progress spinners or non-JSONL chatter to stdout (CLAUDE §13/§39).
import { stderr, stdout, argv, exit } from 'node:process';

import { auditA11y, type AuditA11yLauncher } from './a11y/audit.js';
import { runDiscover } from './discover.js';
import {
  DEFAULT_CONFIG_STDIN_TOKEN,
  loadDiscoverConfig,
  type DiscoverConfig,
  type DiscoverLauncher,
} from './discover_cli.js';
import { auditPerf, type AuditPerfLauncher } from './perf/audit.js';
import { EventEmitter } from './protocol.js';
import { auditLocators, listTests, runPlaywright, validateHelpers } from './runner.js';
import { PACKAGE_NAME, VERSION } from './version.js';

export const USAGE = `Usage: sentinel-ts <command> [options]

Commands:
  run                Run a Playwright spec set described by a run-config JSON.
                       --input <path>      Path to run-config JSON (required).
                       --run-dir <path>    Override run_dir from the config.
                       --browser <name>    chromium | firefox | webkit.
                       --storage-state <path>
                                           Override storage_state_path (Phase
                                           31, ADR-0043). Forwarded to
                                           Playwright via the env var
                                           SENTINELQA_STORAGE_STATE. Pass an
                                           empty string to disable.
                       --ci                CI mode (no spinners, JSONL only).
  list-tests         List spec files matching a glob.
                       --pattern <glob>    Glob relative to cwd (required).
  audit-locators     Brittleness audit of generated spec files.
                       --file <path>       Spec to audit. Repeat for multiple
                                           files (e.g. --file a.ts --file b.ts).
                       --json              Emit JSON (default for this command).
  audit-a11y         Run accessibility checks (axe + keyboard + landmarks +
                     accessible-name) against routes listed in a JSON config.
                       --input <path>      Run-config JSON (required). See
                                           a11y/audit.ts for the schema.
  audit-perf         Run synthetic performance checks (LCP/CLS/INP/TTFB +
                     API latencies + JS bundle + long tasks + nav stability)
                     against routes listed in a JSON config.
                       --input <path>      Run-config JSON (required). See
                                           perf/audit.ts for the schema.
  discover           Playwright-driven crawl backend (PRD §9.1, ADR-0010).
                       --config <path|->   Discovery-config JSON. Use a
                                           dash to read from stdin (the
                                           Python PlaywrightCrawlBackend
                                           default).
  validate-helpers   Sanity-check that @sentinelqa/ts-runtime is wired in.
                       --json              Emit JSON instead of text.

Options:
  -h, --help         Show this help text and exit.
  -V, --version      Print the package version (semver) and exit.

See ADR-0009 for the Python ↔ TS protocol contract.
`;

export interface CliResult {
  readonly stdout: string;
  readonly stderr: string;
  readonly exitCode: number;
}

function takeFlag(args: readonly string[], flag: string): string | undefined {
  const idx = args.indexOf(flag);
  if (idx === -1) return undefined;
  return args[idx + 1];
}

function hasFlag(args: readonly string[], flag: string): boolean {
  return args.includes(flag);
}

export interface DispatchOptions {
  readonly runFn?: typeof runPlaywright;
  readonly listTestsFn?: typeof listTests;
  readonly validateFn?: typeof validateHelpers;
  readonly auditLocatorsFn?: typeof auditLocators;
  readonly auditA11yFn?: typeof auditA11y;
  readonly auditA11yLauncher?: AuditA11yLauncher;
  readonly auditPerfFn?: typeof auditPerf;
  readonly auditPerfLauncher?: AuditPerfLauncher;
  readonly discoverFn?: typeof runDiscover;
  readonly discoverLauncher?: DiscoverLauncher;
  readonly discoverEmitter?: EventEmitter;
  readonly discoverConfigLoader?: (path: string) => Promise<DiscoverConfig>;
  readonly cwd?: string;
}

export async function dispatchAsync(
  args: readonly string[],
  opts: DispatchOptions = {},
): Promise<CliResult> {
  if (args.length === 0 || hasFlag(args, '-h') || hasFlag(args, '--help')) {
    return { stdout: USAGE, stderr: '', exitCode: 0 };
  }
  if (hasFlag(args, '-V') || hasFlag(args, '--version')) {
    return { stdout: `${PACKAGE_NAME} ${VERSION}\n`, stderr: '', exitCode: 0 };
  }

  const [command, ...rest] = args;
  if (command === undefined) {
    return { stdout: USAGE, stderr: '', exitCode: 0 };
  }

  switch (command) {
    case 'run':
      return await handleRun(rest, opts);
    case 'list-tests':
      return await handleListTests(rest, opts);
    case 'audit-locators':
      return await handleAuditLocators(rest, opts);
    case 'audit-a11y':
      return await handleAuditA11y(rest, opts);
    case 'audit-perf':
      return await handleAuditPerf(rest, opts);
    case 'discover':
      return await handleDiscover(rest, opts);
    case 'validate-helpers':
      return await handleValidateHelpers(rest, opts);
    default:
      return {
        stdout: '',
        stderr: `sentinel-ts: unknown command \`${command}\`.\n${USAGE}`,
        exitCode: 2,
      };
  }
}

async function handleRun(args: readonly string[], opts: DispatchOptions): Promise<CliResult> {
  const inputPath = takeFlag(args, '--input');
  if (inputPath === undefined) {
    return {
      stdout: '',
      stderr: 'sentinel-ts run: --input <path> is required.\n',
      exitCode: 2,
    };
  }
  const runDirOverride = takeFlag(args, '--run-dir');
  const browser = takeFlag(args, '--browser') as 'chromium' | 'firefox' | 'webkit' | undefined;
  if (browser !== undefined && !['chromium', 'firefox', 'webkit'].includes(browser)) {
    return {
      stdout: '',
      stderr: `sentinel-ts run: --browser must be chromium|firefox|webkit (got: ${browser}).\n`,
      exitCode: 2,
    };
  }
  // Phase 31 / ADR-0043. CLI override for the storage_state path.
  // Empty string is a valid value: it disables the env var even when
  // the run-config carried a path.
  const storageStateOverride = takeFlag(args, '--storage-state');

  const fn = opts.runFn ?? runPlaywright;
  try {
    const code = await fn({
      inputPath,
      ...(runDirOverride !== undefined ? { runDirOverride } : {}),
      ...(browser !== undefined ? { browserOverride: browser } : {}),
      ...(storageStateOverride !== undefined ? { storageStateOverride } : {}),
      ...(opts.cwd !== undefined ? { cwd: opts.cwd } : {}),
    });
    return { stdout: '', stderr: '', exitCode: code };
  } catch (err) {
    return {
      stdout: '',
      stderr: `sentinel-ts run: ${(err as Error).message}\n`,
      exitCode: 2,
    };
  }
}

async function handleListTests(args: readonly string[], opts: DispatchOptions): Promise<CliResult> {
  const pattern = takeFlag(args, '--pattern');
  if (pattern === undefined) {
    return {
      stdout: '',
      stderr: 'sentinel-ts list-tests: --pattern <glob> is required.\n',
      exitCode: 2,
    };
  }
  const fn = opts.listTestsFn ?? listTests;
  try {
    const files = await fn(pattern, opts.cwd);
    const out = files.length === 0 ? '' : files.join('\n') + '\n';
    return { stdout: out, stderr: '', exitCode: 0 };
  } catch (err) {
    return {
      stdout: '',
      stderr: `sentinel-ts list-tests: ${(err as Error).message}\n`,
      exitCode: 2,
    };
  }
}

function takeMultiFlag(args: readonly string[], flag: string): string[] {
  const out: string[] = [];
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === flag && i + 1 < args.length) {
      const v = args[i + 1];
      if (v !== undefined) out.push(v);
    }
  }
  return out;
}

async function handleAuditLocators(
  args: readonly string[],
  opts: DispatchOptions,
): Promise<CliResult> {
  const files = takeMultiFlag(args, '--file');
  if (files.length === 0) {
    return {
      stdout: '',
      stderr: 'sentinel-ts audit-locators: at least one --file <path> is required.\n',
      exitCode: 2,
    };
  }
  const fn = opts.auditLocatorsFn ?? auditLocators;
  try {
    const report = await fn({ files, ...(opts.cwd !== undefined ? { cwd: opts.cwd } : {}) });
    const body = JSON.stringify(report) + '\n';
    return {
      stdout: body,
      stderr: '',
      exitCode: report.findings.length === 0 ? 0 : 1,
    };
  } catch (err) {
    return {
      stdout: '',
      stderr: `sentinel-ts audit-locators: ${(err as Error).message}\n`,
      exitCode: 2,
    };
  }
}

async function handleAuditA11y(args: readonly string[], opts: DispatchOptions): Promise<CliResult> {
  const inputPath = takeFlag(args, '--input');
  if (inputPath === undefined) {
    return {
      stdout: '',
      stderr: 'sentinel-ts audit-a11y: --input <path> is required.\n',
      exitCode: 2,
    };
  }
  const fn = opts.auditA11yFn ?? auditA11y;
  const launcher = opts.auditA11yLauncher ?? defaultChromiumLauncher;
  try {
    const result = await fn({ inputPath, launcher });
    return {
      stdout: `${result.indexPath}\n`,
      stderr: '',
      exitCode: 0,
    };
  } catch (err) {
    return {
      stdout: '',
      stderr: `sentinel-ts audit-a11y: ${(err as Error).message}\n`,
      exitCode: 2,
    };
  }
}

// Production launcher — only resolved when the subcommand is dispatched
// for real (tests inject `opts.auditA11yLauncher`). The Playwright
// import is dynamic so importing the CLI module never pulls Chromium
// in the test environment.
const defaultChromiumLauncher: AuditA11yLauncher = async () => {
  const { chromium } = await import('@playwright/test');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  return {
    newPage: async () => {
      const page = await context.newPage();
      return page as unknown as Awaited<
        ReturnType<AuditA11yLauncher>
      >['newPage'] extends () => Promise<infer P>
        ? P
        : never;
    },
    close: async () => {
      await context.close();
      await browser.close();
    },
  };
};

const defaultPerfLauncher: AuditPerfLauncher = async () => {
  const { chromium } = await import('@playwright/test');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  return {
    newPage: async () => {
      const page = await context.newPage();
      return page as unknown as Awaited<
        ReturnType<AuditPerfLauncher>
      >['newPage'] extends () => Promise<infer P>
        ? P
        : never;
    },
    close: async () => {
      await context.close();
      await browser.close();
    },
  };
};

async function handleAuditPerf(args: readonly string[], opts: DispatchOptions): Promise<CliResult> {
  const inputPath = takeFlag(args, '--input');
  if (inputPath === undefined) {
    return {
      stdout: '',
      stderr: 'sentinel-ts audit-perf: --input <path> is required.\n',
      exitCode: 2,
    };
  }
  const fn = opts.auditPerfFn ?? auditPerf;
  const launcher = opts.auditPerfLauncher ?? defaultPerfLauncher;
  try {
    const result = await fn({ inputPath, launcher });
    return {
      stdout: `${result.indexPath}\n`,
      stderr: '',
      exitCode: 0,
    };
  } catch (err) {
    return {
      stdout: '',
      stderr: `sentinel-ts audit-perf: ${(err as Error).message}\n`,
      exitCode: 2,
    };
  }
}

async function handleDiscover(args: readonly string[], opts: DispatchOptions): Promise<CliResult> {
  const configPath = takeFlag(args, '--config');
  if (configPath === undefined) {
    return {
      stdout: '',
      stderr: 'sentinel-ts discover: --config <path|-> is required.\n',
      exitCode: 2,
    };
  }
  const loader = opts.discoverConfigLoader ?? loadDiscoverConfig;
  const emitter = opts.discoverEmitter ?? new EventEmitter();
  const launcher = opts.discoverLauncher ?? defaultDiscoverLauncher;
  const fn = opts.discoverFn ?? runDiscover;
  try {
    const config = await loader(configPath);
    const result = await fn(config, { emitter, launcher });
    const summary = JSON.stringify({
      pagesEmitted: result.pagesEmitted,
      endpointsEmitted: result.endpointsEmitted,
    });
    return { stdout: '', stderr: `${summary}\n`, exitCode: 0 };
  } catch (err) {
    return {
      stdout: '',
      stderr: `sentinel-ts discover: ${(err as Error).message}\n`,
      exitCode: 2,
    };
  }
}

const defaultDiscoverLauncher: DiscoverLauncher = async (_config) => {
  const { chromium } = await import('@playwright/test');
  const browser = await chromium.launch({ headless: true });
  return {
    newContext: async () => {
      const context = await browser.newContext({
        userAgent: _config.user_agent,
        extraHTTPHeaders: { 'X-SentinelQA-Test-Run': _config.run_id },
      });
      if (Object.keys(_config.cookies).length > 0) {
        await context.addCookies(
          Object.entries(_config.cookies).map(([name, value]) => ({
            name,
            value,
            url: _config.base_url,
          })),
        );
      }
      return {
        newPage: async () => {
          const page = await context.newPage();
          return page as unknown as Awaited<ReturnType<DiscoverLauncher>> extends infer Br
            ? Br extends { newContext: () => Promise<infer C> }
              ? C extends { newPage: () => Promise<infer P> }
                ? P
                : never
              : never
            : never;
        },
        close: async () => {
          await context.close();
        },
      };
    },
    close: async () => {
      await browser.close();
    },
  };
};

// Silence unused-import lint if this is the only place DEFAULT_CONFIG_STDIN_TOKEN
// is referenced (it lives in the loader module).
void DEFAULT_CONFIG_STDIN_TOKEN;

async function handleValidateHelpers(
  args: readonly string[],
  opts: DispatchOptions,
): Promise<CliResult> {
  const asJson = hasFlag(args, '--json');
  const fn = opts.validateFn ?? validateHelpers;
  const checks = await fn();
  const allOk = checks.every((c) => c.ok);
  let body: string;
  if (asJson) {
    body = JSON.stringify({ ok: allOk, checks }, null, 2) + '\n';
  } else {
    body = checks.map((c) => `${c.ok ? '✓' : '✗'} ${c.name}: ${c.detail}`).join('\n') + '\n';
  }
  return { stdout: body, stderr: '', exitCode: allOk ? 0 : 1 };
}

export async function main(argvSlice: readonly string[]): Promise<number> {
  const result = await dispatchAsync(argvSlice);
  if (result.stdout !== '') stdout.write(result.stdout);
  if (result.stderr !== '') stderr.write(result.stderr);
  return result.exitCode;
}

// Backwards-compatible synchronous dispatch for tests that don't need
// the async commands.
export function dispatch(args: readonly string[]): CliResult {
  if (args.length === 0 || hasFlag(args, '-h') || hasFlag(args, '--help')) {
    return { stdout: USAGE, stderr: '', exitCode: 0 };
  }
  if (hasFlag(args, '-V') || hasFlag(args, '--version')) {
    return { stdout: `${PACKAGE_NAME} ${VERSION}\n`, stderr: '', exitCode: 0 };
  }
  const [command] = args;
  if (command === undefined) return { stdout: USAGE, stderr: '', exitCode: 0 };
  if (
    command === 'run' ||
    command === 'list-tests' ||
    command === 'validate-helpers' ||
    command === 'audit-locators' ||
    command === 'audit-a11y' ||
    command === 'audit-perf' ||
    command === 'discover'
  ) {
    return {
      stdout: '',
      stderr: `sentinel-ts: \`${command}\` requires async dispatch (use dispatchAsync).\n`,
      exitCode: 7,
    };
  }
  return {
    stdout: '',
    stderr: `sentinel-ts: unknown command \`${command}\`.\n${USAGE}`,
    exitCode: 2,
  };
}

// Entry-point guard: only execute when the file is run directly. Vitest
// imports the module for unit tests and must NOT trigger process.exit.
const invokedDirectly = (() => {
  if (typeof argv[1] !== 'string') return false;
  const entry = argv[1];
  const url = new URL(import.meta.url).pathname;
  return entry === url || entry.endsWith('/cli.js') || entry.endsWith('/cli.ts');
})();

if (invokedDirectly) {
  void main(argv.slice(2)).then((code) => exit(code));
}
