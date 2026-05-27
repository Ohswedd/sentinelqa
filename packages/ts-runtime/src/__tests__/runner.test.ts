import { EventEmitter as NodeEmitter } from 'node:events';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { dispatchAsync } from '../cli.js';
import {
  RunConfigError,
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
