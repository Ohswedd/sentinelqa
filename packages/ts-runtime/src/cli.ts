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

import { listTests, runPlaywright, validateHelpers } from './runner.js';
import { PACKAGE_NAME, VERSION } from './version.js';

export const USAGE = `Usage: sentinel-ts <command> [options]

Commands:
  run                Run a Playwright spec set described by a run-config JSON.
                       --input <path>      Path to run-config JSON (required).
                       --run-dir <path>    Override run_dir from the config.
                       --browser <name>    chromium | firefox | webkit.
                       --ci                CI mode (no spinners, JSONL only).
  list-tests         List spec files matching a glob.
                       --pattern <glob>    Glob relative to cwd (required).
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

  const fn = opts.runFn ?? runPlaywright;
  try {
    const code = await fn({
      inputPath,
      ...(runDirOverride !== undefined ? { runDirOverride } : {}),
      ...(browser !== undefined ? { browserOverride: browser } : {}),
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
  if (command === 'run' || command === 'list-tests' || command === 'validate-helpers') {
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
