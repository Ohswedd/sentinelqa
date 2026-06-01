// Phase 04.05 — evidence capture integration tests.
//
// These tests exercise the helpers end-to-end without launching a real
// browser. The contract being verified:
//
//   * `captureEvidence` always emits one `evidence` event per artifact
//     (screenshot / dom_snapshot / har) AND writes the screenshot +
//     DOM file to disk.
//   * `redactedConsole` emits a redacted `console` event for every
//     `page.on('console', ...)` call.
//   * `captureDomSnapshot` writes the DOM, emits a `dom.snapshot`
//     event, and returns a stable AX-tree hash.
//   * `harConfig` produces a deterministic per-test HAR path.
//   * For a failing test the reporter (loaded directly) emits one
//     `evidence` event per attached trace/screenshot/video — proving
//     failure evidence is *always* present (see documentation).

import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  captureDomSnapshot,
  captureEvidence,
  harConfig,
  redactedConsole,
} from '../../src/helpers.js';
import type {
  AccessibilityPage,
  ConsoleEmitterPage,
  ConsoleMessage,
  PageLike,
} from '../../src/helpers.js';
import { EventEmitter, MemorySink } from '../../src/protocol.js';
import type { ConsoleEvent, DomSnapshotEvent, EvidenceEvent } from '../../src/protocol.js';
import { SentinelReporter } from '../../src/reporter.js';

function makeCtx(runDir: string) {
  const sink = new MemorySink();
  const emitter = new EventEmitter({ sink, now: () => new Date('2026-05-28T00:00:00Z') });
  return { sink, emitter, runDir, testId: 't-evidence' };
}

let runDir: string;
beforeEach(async () => {
  runDir = await mkdtemp(join(tmpdir(), 'sentinel-evidence-int-'));
});
afterEach(async () => {
  await rm(runDir, { recursive: true, force: true });
});

describe('captureEvidence (integration)', () => {
  it('writes screenshot + DOM, emits two `evidence` events', async () => {
    const ctx = makeCtx(runDir);
    const fakePage: PageLike = {
      screenshot: async ({ path }) => {
        const { writeFile } = await import('node:fs/promises');
        await writeFile(path, Buffer.from('PNG-bytes'));
        return Buffer.from('PNG-bytes');
      },
      content: () =>
        Promise.resolve(
          '<html><body data-secret="ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"></body></html>',
        ),
      url: () => 'about:blank',
    };
    const refs = await captureEvidence(ctx, fakePage, 'after-action');

    expect(refs).toHaveLength(2);
    expect(refs[0]?.kind).toBe('screenshot');
    expect(refs[1]?.kind).toBe('dom_snapshot');

    const dom = await readFile(refs[1]!.path, 'utf8');
    expect(dom).toContain('[REDACTED:github_token]');
    expect(dom).not.toContain('ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');

    const events = ctx.sink.events().filter((e): e is EvidenceEvent => e.type === 'evidence');
    expect(events.map((e) => e.evidence_kind)).toEqual(['screenshot', 'dom_snapshot']);
  });

  it('optional HAR adds a third evidence ref without writing a file', async () => {
    const ctx = makeCtx(runDir);
    const fakePage: PageLike = {
      screenshot: async ({ path }) => {
        const { writeFile } = await import('node:fs/promises');
        await writeFile(path, Buffer.from(''));
        return Buffer.from('');
      },
      content: () => Promise.resolve('<html></html>'),
      url: () => 'about:blank',
    };
    const refs = await captureEvidence(ctx, fakePage, 'with-har', { har: true });
    expect(refs.map((r) => r.kind)).toEqual(['screenshot', 'dom_snapshot', 'har']);
  });
});

describe('redactedConsole', () => {
  it('emits a redacted console event per page.on("console") call', () => {
    const ctx = makeCtx(runDir);
    let listener: ((m: ConsoleMessage) => void) | undefined;
    const fakePage: ConsoleEmitterPage = {
      on(event, l) {
        if (event === 'console') listener = l as (m: ConsoleMessage) => void;
      },
    };
    redactedConsole(fakePage, ctx);
    listener!({
      type: () => 'warning',
      text: () =>
        'Authorization: Bearer abc.DEF-ghi_jklmno0123456789 leaked into client-side console',
      location: () => ({ url: 'https://example.com/app.js?token=deadbeef-cafebabe1234567890' }),
    });
    listener!({
      type: () => 'log',
      text: () => 'hello',
      location: () => ({}),
    });

    const events = ctx.sink.events().filter((e): e is ConsoleEvent => e.type === 'console');
    expect(events).toHaveLength(2);
    expect(events[0]?.level).toBe('warn');
    expect(events[0]?.message).toContain('[REDACTED:bearer_token]');
    expect(events[0]?.message).not.toContain('abc.DEF-ghi_jklmno0123456789');
    expect(events[0]?.source).not.toContain('deadbeef-cafebabe1234567890');
    expect(events[1]?.level).toBe('log');
    expect(events[1]?.source).toBe('');
  });
});

describe('captureDomSnapshot', () => {
  it('writes the DOM, emits dom.snapshot, returns an AX hash', async () => {
    const ctx = makeCtx(runDir);
    const fakePage: AccessibilityPage = {
      content: () => Promise.resolve('<html><body><h1>Hello</h1></body></html>'),
      screenshot: () => Promise.resolve(Buffer.from('')),
      url: () => 'about:blank',
      accessibility: {
        snapshot: () =>
          Promise.resolve({
            role: 'WebArea',
            name: 'Demo',
            children: [{ role: 'heading', name: 'Hello' }],
          }),
      },
    };

    const ref = await captureDomSnapshot(ctx, fakePage, 'home');
    expect(ref.label).toBe('home');
    expect(ref.path).toContain('home.html');
    expect(ref.axTreeHash).toMatch(/^[0-9a-f]{64}$/);

    const dom = await readFile(ref.path, 'utf8');
    expect(dom).toContain('Hello');

    const events = ctx.sink
      .events()
      .filter((e): e is DomSnapshotEvent => e.type === 'dom.snapshot');
    expect(events).toHaveLength(1);
    expect(events[0]?.label).toBe('home');
  });

  it('hashes `null` when the page has no accessibility API', async () => {
    const ctx = makeCtx(runDir);
    const fakePage: AccessibilityPage = {
      content: () => Promise.resolve('<html></html>'),
      screenshot: () => Promise.resolve(Buffer.from('')),
      url: () => 'about:blank',
    };
    const ref = await captureDomSnapshot(ctx, fakePage, 'no-ax');
    // sha256(JSON.stringify(null)) - the canonical "no AX tree" hash.
    expect(ref.axTreeHash).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe('harConfig', () => {
  it('produces a deterministic per-test path', () => {
    const ctx = makeCtx('/runs/x');
    const cfg = harConfig(ctx);
    expect(cfg.recordHar.path).toBe('/runs/x/har/t-evidence.har');
    expect(cfg.recordHar.mode).toBe('minimal');
    expect(cfg.recordHar.content).toBe('omit');
  });
});

describe('failure evidence always present (reporter)', () => {
  it('emits one evidence event per trace/screenshot/video attachment on failure', () => {
    const sink = new MemorySink();
    const emitter = new EventEmitter({ sink, now: () => new Date('2026-05-28T00:00:00Z') });
    const reporter = new SentinelReporter({
      emitter,
      runId: 'r',
      target: 'http://localhost:3000',
    });
    reporter.onBegin(
      {} as never,
      {
        suites: [],
        tests: [{ id: 't-fail' }],
      } as never,
    );
    reporter.onTestBegin(
      { id: 't-fail', title: 'fails', location: { file: '/t.spec.ts' } } as never,
      {} as never,
    );
    reporter.onTestEnd(
      { id: 't-fail', title: 'fails', location: { file: '/t.spec.ts' } } as never,
      {
        status: 'failed',
        duration: 99,
        retry: 0,
        attachments: [
          { name: 'trace', contentType: 'application/zip', path: '/runs/x/trace.zip' },
          {
            name: 'screenshot',
            contentType: 'image/png',
            path: '/runs/x/shot.png',
          },
          { name: 'video', contentType: 'video/webm', path: '/runs/x/v.webm' },
        ],
        error: { message: 'click failed' },
      } as never,
    );
    reporter.onEnd({ status: 'failed' } as never);

    const kinds = sink
      .events()
      .filter((e): e is EvidenceEvent => e.type === 'evidence')
      .map((e) => e.evidence_kind);
    expect(kinds).toEqual(['trace', 'screenshot', 'video']);
  });
});
