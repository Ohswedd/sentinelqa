import { EventEmitter as NodeEmitter } from 'node:events';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { dispatchAsync } from '../cli.js';
import {
  RunConfigError,
  _fallbackGlobForTests,
  compileGlob,
  listTests,
  loadRunConfig,
  resolvePlaywrightBin,
  runPlaywright,
  validateHelpers,
} from '../runner.js';

let workDir: string;

beforeEach(async () => {
  workDir = await mkdtemp(join(tmpdir(), 'sentinel-runner-'));
});

afterEach(async () => {
  await rm(workDir, { recursive: true, force: true });
});

async function writeJson(path: string, body: unknown): Promise<void> {
  await writeFile(path, JSON.stringify(body), 'utf8');
}

describe('loadRunConfig', () => {
  it('parses a valid config', async () => {
    const path = join(workDir, 'config.json');
    await writeJson(path, {
      run_id: 'r-1',
      target: 'http://localhost:3000',
      run_dir: join(workDir, 'run'),
      spec_files: ['tests/x.spec.ts'],
      browser: 'firefox',
      timeout_ms: 5000,
    });
    const cfg = loadRunConfig(path);
    expect(cfg.run_id).toBe('r-1');
    expect(cfg.browser).toBe('firefox');
    expect(cfg.timeout_ms).toBe(5000);
    expect(cfg.retries).toBe(0);
    expect(cfg.headless).toBe(true);
  });

  it('throws RunConfigError on missing required fields', async () => {
    const path = join(workDir, 'config.json');
    await writeJson(path, { run_id: 'r-1' });
    expect(() => loadRunConfig(path)).toThrow(RunConfigError);
  });

  it('throws RunConfigError on unknown keys (strict mode)', async () => {
    const path = join(workDir, 'config.json');
    await writeJson(path, {
      run_id: 'r-1',
      target: 'http://x',
      run_dir: '/tmp',
      extra_key: 'nope',
    });
    expect(() => loadRunConfig(path)).toThrow(RunConfigError);
  });

  it('rejects missing files cleanly', () => {
    expect(() => loadRunConfig(join(workDir, 'missing.json'))).toThrow(/run-config not found/);
  });
});

describe('compileGlob', () => {
  it('matches `**/*.spec.ts` against nested + top-level paths', () => {
    const re = compileGlob('**/*.spec.ts');
    expect(re.test('a/b/two.spec.ts')).toBe(true);
    expect(re.test('one.spec.ts')).toBe(true);
    expect(re.test('a/one.spec.ts')).toBe(true);
    expect(re.test('not-a-spec.ts')).toBe(false);
    expect(re.test('a.spec.tsx')).toBe(false);
  });

  it('preserves literal regex meta characters', () => {
    const re = compileGlob('foo.spec.ts');
    expect(re.test('foo.spec.ts')).toBe(true);
    // `.` was escaped, so a different char in that slot must not match.
    expect(re.test('fooXspec.ts')).toBe(false);
  });

  it('expands `?` to single-char (non-slash) matcher', () => {
    const re = compileGlob('a?.ts');
    expect(re.test('ab.ts')).toBe(true);
    expect(re.test('a.ts')).toBe(false);
    expect(re.test('a/.ts')).toBe(false);
  });
});

describe('listTests', () => {
  it('finds spec files via glob', async () => {
    await mkdir(join(workDir, 'tests'), { recursive: true });
    await writeFile(join(workDir, 'tests', 'a.spec.ts'), '// a');
    await writeFile(join(workDir, 'tests', 'b.spec.ts'), '// b');
    await writeFile(join(workDir, 'tests', 'helper.ts'), '// not a spec');

    const out = await listTests('tests/**/*.spec.ts', workDir);
    expect(Array.from(out).sort()).toEqual(['tests/a.spec.ts', 'tests/b.spec.ts']);
  });

  it('returns empty list for no matches', async () => {
    const out = await listTests('does-not-exist/*.spec.ts', workDir);
    expect(Array.from(out)).toEqual([]);
  });

  it('_fallbackGlobForTests directly: traverses, regex-filters, skips vendored dirs', async () => {
    await mkdir(join(workDir, 'a', 'b'), { recursive: true });
    await mkdir(join(workDir, 'node_modules'), { recursive: true });
    await writeFile(join(workDir, 'a', 'one.spec.ts'), '// 1');
    await writeFile(join(workDir, 'a', 'b', 'two.spec.ts'), '// 2');
    await writeFile(join(workDir, 'a', 'helper.ts'), '// h');
    await writeFile(join(workDir, 'node_modules', 'skip.spec.ts'), '// skipped');

    const out: string[] = [];
    for await (const f of _fallbackGlobForTests('**/*.spec.ts', workDir)) out.push(f);
    out.sort();
    expect(out).toEqual(['a/b/two.spec.ts', 'a/one.spec.ts']);
  });

  it('_fallbackGlobForTests: returns nothing for an unreadable cwd', async () => {
    const out: string[] = [];
    for await (const f of _fallbackGlobForTests('**/*.spec.ts', join(workDir, 'nope'))) out.push(f);
    expect(out).toEqual([]);
  });

  it('recurses into subdirectories and skips node_modules / dist / .git', async () => {
    await mkdir(join(workDir, 'tests', 'nested', 'deep'), { recursive: true });
    await mkdir(join(workDir, 'node_modules', 'should-skip'), { recursive: true });
    await mkdir(join(workDir, 'dist'), { recursive: true });
    await mkdir(join(workDir, '.git'), { recursive: true });
    await writeFile(join(workDir, 'tests', 'nested', 'deep', 'a.spec.ts'), '// nested');
    await writeFile(join(workDir, 'node_modules', 'should-skip', 'x.spec.ts'), '// skipped');
    await writeFile(join(workDir, 'dist', 'b.spec.ts'), '// skipped');
    await writeFile(join(workDir, '.git', 'c.spec.ts'), '// skipped');

    const out = await listTests('**/*.spec.ts', workDir);
    expect(Array.from(out)).toEqual(['tests/nested/deep/a.spec.ts']);
  });
});

describe('resolvePlaywrightBin', () => {
  it('returns null when no Playwright is installed in cwd or parents', () => {
    // workDir is a tmpdir with no node_modules; should resolve null.
    expect(resolvePlaywrightBin(workDir)).toBeNull();
  });
});

describe('validateHelpers', () => {
  it('returns ok checks against the installed package', async () => {
    const checks = await validateHelpers();
    expect(checks.length).toBeGreaterThanOrEqual(3);
    expect(checks.every((c) => c.ok)).toBe(true);
    expect(checks.map((c) => c.name)).toContain('redaction-rules');
  });

  it('returns a package-load failure check and short-circuits when index throws', async () => {
    const checks = await validateHelpers({
      importIndex: () => Promise.reject(new Error('ENOENT index')),
    });
    expect(checks).toHaveLength(1);
    expect(checks[0]?.name).toBe('package-load');
    expect(checks[0]?.ok).toBe(false);
    expect(checks[0]?.detail).toContain('ENOENT index');
  });

  it('records a redaction-rules failure check when loadRedactionRules throws', async () => {
    const checks = await validateHelpers({
      importRedact: () =>
        Promise.resolve({
          loadRedactionRules: () => {
            throw new Error('ruleset missing on disk');
          },
        }),
    });
    const fail = checks.find((c) => c.name === 'redaction-rules');
    expect(fail?.ok).toBe(false);
    expect(fail?.detail).toContain('ruleset missing on disk');
    // The function does NOT short-circuit on this branch — helpers-exported
    // still runs against the real helpers module.
    expect(checks.find((c) => c.name === 'helpers-exported')?.ok).toBe(true);
  });

  it('records a helpers-exported failure check when import throws', async () => {
    const checks = await validateHelpers({
      importHelpers: () => Promise.reject(new Error('helpers module missing')),
    });
    const fail = checks.find((c) => c.name === 'helpers-exported');
    expect(fail?.ok).toBe(false);
    expect(fail?.detail).toContain('helpers module missing');
  });
});

interface MockChildSpec {
  readonly exitCode: number;
  readonly stderr?: string;
}

function buildSpawnMock(spec: MockChildSpec): {
  fn: (...args: unknown[]) => NodeEmitter & { stderr: NodeEmitter };
  calls: { cmd: string; args: string[]; env: NodeJS.ProcessEnv }[];
} {
  const calls: { cmd: string; args: string[]; env: NodeJS.ProcessEnv }[] = [];
  function fn(...args: unknown[]) {
    const [cmd, cmdArgs, opts] = args as [
      string,
      string[],
      { env?: NodeJS.ProcessEnv } | undefined,
    ];
    calls.push({ cmd, args: cmdArgs, env: opts?.env ?? {} });
    const child = new NodeEmitter() as NodeEmitter & { stderr: NodeEmitter };
    const stderrEv = new NodeEmitter();
    child.stderr = stderrEv;
    queueMicrotask(() => {
      if (spec.stderr !== undefined) stderrEv.emit('data', Buffer.from(spec.stderr));
      child.emit('close', spec.exitCode);
    });
    return child;
  }
  return { fn, calls };
}

describe('runPlaywright', () => {
  it('returns 0 when the spawned child exits with 0', async () => {
    const cfgPath = join(workDir, 'cfg.json');
    await writeJson(cfgPath, {
      run_id: 'r',
      target: 'http://x',
      run_dir: join(workDir, 'run'),
      spec_files: ['tests/a.spec.ts'],
    });
    const stderrSink = new NodeEmitter() as unknown as NodeJS.WriteStream;
    let stderrOut = '';
    Object.assign(stderrSink, {
      write: (chunk: string) => {
        stderrOut += chunk;
        return true;
      },
    });
    const mock = buildSpawnMock({ exitCode: 0 });
    const code = await runPlaywright({
      inputPath: cfgPath,

      spawnFn: mock.fn as any,
      reporterPathOverride: '/dev/null/reporter.js',
      cwd: workDir,
      stderr: stderrSink,
    });
    expect(code).toBe(0);
    expect(stderrOut).toBe('');
    expect(mock.calls).toHaveLength(1);
    const call = mock.calls[0]!;
    // The reporter flag must always be present.
    expect(call.args.some((a) => a.startsWith('--reporter='))).toBe(true);
    // Env carries our envelope variables.
    expect(call.env['SENTINELQA_RUN_ID']).toBe('r');
    expect(call.env['SENTINELQA_TARGET']).toBe('http://x');
  });

  it('forwards --shard, --browser, --run-dir overrides into the Playwright args', async () => {
    const cfgPath = join(workDir, 'cfg.json');
    await writeJson(cfgPath, {
      run_id: 'r',
      target: 'http://x',
      run_dir: join(workDir, 'run'),
      shard: { current: 2, total: 3 },
      workers: 4,
      retries: 2,
      timeout_ms: 15000,
    });
    const stderrSink = new NodeEmitter() as unknown as NodeJS.WriteStream;
    Object.assign(stderrSink, { write: () => true });
    const mock = buildSpawnMock({ exitCode: 0 });
    const code = await runPlaywright({
      inputPath: cfgPath,
      browserOverride: 'firefox',
      runDirOverride: '/other/run',

      spawnFn: mock.fn as any,
      reporterPathOverride: '/dev/null/reporter.js',
      cwd: workDir,
      stderr: stderrSink,
    });
    expect(code).toBe(0);
    const call = mock.calls[0]!;
    expect(call.args).toContain('--shard=2/3');
    expect(call.args).toContain('--project=firefox');
    expect(call.args).toContain('--workers=4');
    expect(call.args).toContain('--retries=2');
    expect(call.args).toContain('--timeout=15000');
    expect(call.env['SENTINELQA_RUN_DIR']).toBe('/other/run');
  });

  it('returns 1 on test failure and forwards stderr', async () => {
    const cfgPath = join(workDir, 'cfg.json');
    await writeJson(cfgPath, {
      run_id: 'r',
      target: 'http://x',
      run_dir: join(workDir, 'run'),
    });
    const stderrSink = new NodeEmitter() as unknown as NodeJS.WriteStream;
    let stderrOut = '';
    Object.assign(stderrSink, {
      write: (chunk: string) => {
        stderrOut += chunk;
        return true;
      },
    });
    const mock = buildSpawnMock({ exitCode: 1, stderr: 'test failed\n' });
    const code = await runPlaywright({
      inputPath: cfgPath,

      spawnFn: mock.fn as any,
      reporterPathOverride: '/dev/null/reporter.js',
      cwd: workDir,
      stderr: stderrSink,
    });
    expect(code).toBe(1);
    expect(stderrOut).toContain('test failed');
  });

  it('returns 2 when the reporter module is missing and no override is set', async () => {
    const cfgPath = join(workDir, 'cfg.json');
    await writeJson(cfgPath, {
      run_id: 'r',
      target: 'http://x',
      run_dir: join(workDir, 'run'),
    });
    const stderrSink = new NodeEmitter() as unknown as NodeJS.WriteStream;
    let stderrOut = '';
    Object.assign(stderrSink, {
      write: (chunk: string) => {
        stderrOut += chunk;
        return true;
      },
    });
    // workDir is a tmpdir with no `dist/` next to it, so the auto-resolved
    // reporter path won't exist. spawnFn should never be called.
    let spawned = false;
    const code = await runPlaywright({
      inputPath: cfgPath,

      spawnFn: ((..._args: unknown[]) => {
        spawned = true;
        return new NodeEmitter();
      }) as any,
      cwd: workDir,
      stderr: stderrSink,
    });
    expect(code).toBe(2);
    expect(spawned).toBe(false);
    expect(stderrOut).toContain('reporter module missing');
    expect(stderrOut).toContain('pnpm --filter @sentinelqa/ts-runtime build');
  });

  it('returns 2 on spawn error', async () => {
    const cfgPath = join(workDir, 'cfg.json');
    await writeJson(cfgPath, {
      run_id: 'r',
      target: 'http://x',
      run_dir: join(workDir, 'run'),
    });
    const stderrSink = new NodeEmitter() as unknown as NodeJS.WriteStream;
    let stderrOut = '';
    Object.assign(stderrSink, {
      write: (chunk: string) => {
        stderrOut += chunk;
        return true;
      },
    });
    function fakeSpawn(): NodeEmitter & { stderr: NodeEmitter } {
      const c = new NodeEmitter() as NodeEmitter & { stderr: NodeEmitter };
      c.stderr = new NodeEmitter();
      queueMicrotask(() => c.emit('error', new Error('ENOENT: cmd not found')));
      return c;
    }
    const code = await runPlaywright({
      inputPath: cfgPath,

      spawnFn: fakeSpawn as any,
      reporterPathOverride: '/dev/null/reporter.js',
      cwd: workDir,
      stderr: stderrSink,
    });
    expect(code).toBe(2);
    expect(stderrOut).toContain('failed to spawn');
  });
});

describe('CLI subcommands', () => {
  it('list-tests dispatches and returns 0', async () => {
    await mkdir(join(workDir, 'tests'), { recursive: true });
    await writeFile(join(workDir, 'tests', 'x.spec.ts'), '// x');
    const result = await dispatchAsync(['list-tests', '--pattern', 'tests/**/*.spec.ts'], {
      cwd: workDir,
    });
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('tests/x.spec.ts');
  });

  it('list-tests without --pattern returns exit 2', async () => {
    const result = await dispatchAsync(['list-tests']);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('--pattern');
  });

  it('validate-helpers returns 0 and emits checks', async () => {
    const result = await dispatchAsync(['validate-helpers']);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('package-identity');
  });

  it('validate-helpers --json emits parseable JSON', async () => {
    const result = await dispatchAsync(['validate-helpers', '--json']);
    expect(result.exitCode).toBe(0);
    const parsed = JSON.parse(result.stdout) as { ok: boolean; checks: { ok: boolean }[] };
    expect(parsed.ok).toBe(true);
    expect(parsed.checks.length).toBeGreaterThanOrEqual(3);
  });

  it('run without --input returns exit 2', async () => {
    const result = await dispatchAsync(['run']);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('--input');
  });

  it('run with --browser=invalid returns exit 2', async () => {
    const result = await dispatchAsync(['run', '--input', '/x', '--browser', 'safari']);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('chromium|firefox|webkit');
  });
});
