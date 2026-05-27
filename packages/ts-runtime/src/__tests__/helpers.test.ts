import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  _resetRequestCounterForTests,
  _resetStepCounterForTests,
  captureEvidence,
  redactedNetwork,
  sentinelStep,
} from '../helpers.js';
import type { PageLike, NetworkRequest, NetworkResponse, RoutablePage } from '../helpers.js';
import { MemorySink, EventEmitter, parseEvent } from '../protocol.js';
import type { LogEvent, TsEvent } from '../protocol.js';

function makeCtx(): { emitter: EventEmitter; sink: MemorySink; testId: string } {
  const sink = new MemorySink();
  const emitter = new EventEmitter({ sink, now: () => new Date('2026-05-28T00:00:00Z') });
  return { emitter, sink, testId: 't-1' };
}

beforeEach(() => {
  _resetStepCounterForTests();
  _resetRequestCounterForTests();
});

describe('sentinelStep', () => {
  it('emits step.start + step.end on success', async () => {
    const ctx = makeCtx();
    const result = await sentinelStep(ctx, 'click submit', () => Promise.resolve('ok'));
    expect(result).toBe('ok');

    const events = ctx.sink.events();
    expect(events.map((e) => e.type)).toEqual(['step.start', 'step.end']);
    expect(events[0]).toMatchObject({ type: 'step.start', name: 'click submit', test_id: 't-1' });
    const end = events[1] as Extract<TsEvent, { type: 'step.end' }>;
    expect(end.ok).toBe(true);
    expect(end.duration_ms).toBeGreaterThanOrEqual(0);
  });

  it('serializes thrown errors with redacted stack and re-throws', async () => {
    const ctx = makeCtx();
    const boom = (): Promise<never> =>
      Promise.reject(new Error('Bearer abc.DEF-ghi_jklmno0123456789 leaked'));

    await expect(sentinelStep(ctx, 'failing step', boom)).rejects.toThrow(/leaked/);

    const events = ctx.sink.events();
    const end = events[1] as Extract<TsEvent, { type: 'step.end' }>;
    expect(end.ok).toBe(false);
    expect(end.error?.message).toContain('[REDACTED:bearer_token]');
    expect(end.error?.message).not.toContain('abc.DEF-ghi_jklmno0123456789');
  });

  it('assigns monotonically increasing step ids', async () => {
    const ctx = makeCtx();
    await sentinelStep(ctx, 'a', () => Promise.resolve());
    await sentinelStep(ctx, 'b', () => Promise.resolve());

    const events = ctx.sink.events();
    const ids = events
      .filter((e): e is Extract<TsEvent, { type: 'step.start' }> => e.type === 'step.start')
      .map((e) => e.step_id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe('captureEvidence', () => {
  let runDir: string;
  beforeEach(async () => {
    runDir = await mkdtemp(join(tmpdir(), 'sentinel-evidence-'));
  });
  afterEach(async () => {
    await rm(runDir, { recursive: true, force: true });
  });

  it('writes a screenshot + DOM snapshot and emits evidence events', async () => {
    const ctx = makeCtx();
    const screenshotCalls: { path: string }[] = [];
    const fakePage: PageLike = {
      screenshot: async (opts: { path: string }) => {
        screenshotCalls.push({ path: opts.path });
        const { writeFile } = await import('node:fs/promises');
        await writeFile(opts.path, Buffer.from('PNG-bytes'));
        return Buffer.from('PNG-bytes');
      },
      content: () =>
        Promise.resolve(
          '<html><body><script>const token = "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";</script></body></html>',
        ),
      url: () => 'about:blank',
    };

    const refs = await captureEvidence({ ...ctx, runDir }, fakePage, 'login-screen');

    expect(refs).toHaveLength(2);
    expect(refs[0]?.kind).toBe('screenshot');
    expect(refs[1]?.kind).toBe('dom_snapshot');
    expect(screenshotCalls).toHaveLength(1);

    const dom = await readFile(refs[1]!.path, 'utf8');
    expect(dom).toContain('[REDACTED:github_token]');
    expect(dom).not.toContain('ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');

    const events = ctx.sink.events();
    expect(events.map((e) => e.type)).toEqual(['evidence', 'evidence']);
  });

  it('respects opts.screenshot=false', async () => {
    const ctx = makeCtx();
    let called = false;
    const fakePage: PageLike = {
      screenshot: () => {
        called = true;
        return Promise.resolve(Buffer.from(''));
      },
      content: () => Promise.resolve('<html></html>'),
      url: () => 'about:blank',
    };

    const refs = await captureEvidence({ ...ctx, runDir }, fakePage, 'no-shot', {
      screenshot: false,
      dom: true,
    });
    expect(refs).toHaveLength(1);
    expect(refs[0]?.kind).toBe('dom_snapshot');
    expect(called).toBe(false);
  });
});

describe('redactedNetwork', () => {
  it('emits network.request and network.response with redacted URL + headers', () => {
    const ctx = makeCtx();
    let requestListener: ((req: NetworkRequest) => void) | undefined;
    let responseListener: ((res: NetworkResponse) => void) | undefined;
    const fakePage: RoutablePage = {
      on(event, listener) {
        if (event === 'request') requestListener = listener as (req: NetworkRequest) => void;
        if (event === 'response') responseListener = listener as (res: NetworkResponse) => void;
      },
    };

    redactedNetwork(fakePage, ctx);

    const req: NetworkRequest = {
      url: () => 'https://api.example.com/?token=deadbeef-cafebabe1234567890&q=1',
      method: () => 'POST',
      headers: () => ({ Authorization: 'Bearer xyz', 'X-Trace': 'abc' }),
      postDataBuffer: () => Buffer.from('hello'),
      resourceType: () => 'fetch',
    };
    requestListener!(req);

    const res: NetworkResponse = {
      url: () => 'https://api.example.com/?token=deadbeef-cafebabe1234567890&q=1',
      status: () => 200,
      headers: () => ({ 'content-length': '42', 'content-type': 'application/json' }),
      request: () => req,
    };
    responseListener!(res);

    const events = ctx.sink.events();
    expect(events.map((e) => e.type)).toEqual(['network.request', 'network.response']);

    const reqEv = events[0] as Extract<TsEvent, { type: 'network.request' }>;
    expect(reqEv.method).toBe('POST');
    expect(reqEv.url).not.toContain('deadbeef-cafebabe1234567890');
    expect(reqEv.url).toContain('REDACTED');
    expect(reqEv.content_length).toBe(5);

    const resEv = events[1] as Extract<TsEvent, { type: 'network.response' }>;
    expect(resEv.status).toBe(200);
    expect(resEv.content_length).toBe(42);
    expect(resEv.content_type).toBe('application/json');
    expect(resEv.request_id).toBe(reqEv.request_id);
  });
});

describe('EventEmitter envelope contract', () => {
  it('bumps seq and stamps schema_version + ts on every event', () => {
    const sink = new MemorySink();
    const emitter = new EventEmitter({ sink, now: () => new Date('2026-05-28T12:34:56Z') });
    emitter.emit<LogEvent>({ type: 'log', level: 'info', msg: 'hi', fields: {} });
    emitter.emit<LogEvent>({ type: 'log', level: 'warn', msg: 'oh', fields: {} });

    expect(sink.lines).toHaveLength(2);
    const e1 = parseEvent(sink.lines[0]!);
    const e2 = parseEvent(sink.lines[1]!);
    expect(e1.seq).toBe(1);
    expect(e2.seq).toBe(2);
    expect(e1.schema_version).toBe('1.0.0');
    expect(e1.ts).toBe('2026-05-28T12:34:56.000Z');
  });
});
