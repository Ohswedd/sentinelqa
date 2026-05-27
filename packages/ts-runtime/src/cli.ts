// `sentinel-ts` — the CLI Python orchestrates to run Playwright specs.
// PRD §15, CLAUDE.md §8 (Python ↔ TS contract).
//
// The Phase 04.01 surface is help/version only. `run`, `list-tests`,
// and `validate-helpers` land in 04.03; they exit 7 (internal error)
// with a "lands in Phase NN" message until then — CLAUDE.md §37, no
// fake completion.
import { stderr, stdout, argv, exit } from 'node:process';

import { PACKAGE_NAME, VERSION } from './version.js';

export const USAGE = `Usage: sentinel-ts <command> [options]

Commands:
  run                Run a Playwright spec set described by a run-config JSON.
                     (lands in Phase 04.03)
  list-tests         List Playwright tests matching a glob.
                     (lands in Phase 04.03)
  validate-helpers   Sanity-check that @sentinelqa/ts-runtime is wired in.
                     (lands in Phase 04.03)

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

const STUB_COMMANDS = new Set(['run', 'list-tests', 'validate-helpers']);

export function dispatch(args: readonly string[]): CliResult {
  if (args.length === 0 || args.includes('-h') || args.includes('--help')) {
    return { stdout: USAGE, stderr: '', exitCode: 0 };
  }
  if (args.includes('-V') || args.includes('--version')) {
    return { stdout: `${PACKAGE_NAME} ${VERSION}\n`, stderr: '', exitCode: 0 };
  }

  const [command, ...rest] = args;
  void rest;
  if (command === undefined) {
    return { stdout: USAGE, stderr: '', exitCode: 0 };
  }

  if (STUB_COMMANDS.has(command)) {
    return {
      stdout: '',
      stderr: `sentinel-ts: command \`${command}\` lands in Phase 04.03 (see plans/phase-04-typescript-playwright-runtime/03-runner-binary.md).\n`,
      exitCode: 7,
    };
  }

  return {
    stdout: '',
    stderr: `sentinel-ts: unknown command \`${command}\`.\n${USAGE}`,
    exitCode: 2,
  };
}

export function main(argvSlice: readonly string[]): number {
  const result = dispatch(argvSlice);
  if (result.stdout !== '') stdout.write(result.stdout);
  if (result.stderr !== '') stderr.write(result.stderr);
  return result.exitCode;
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
  exit(main(argv.slice(2)));
}
