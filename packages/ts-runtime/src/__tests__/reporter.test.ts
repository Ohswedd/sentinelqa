// Unit tests for the Playwright reporter — drive the reporter
// callbacks with hand-built test objects and assert the emitted JSONL
// stream matches the protocol.
//
// The "Playwright object" types are quite large; we cast a minimal
// payload to the interface so vitest can exercise the mapping logic
// without spinning up real Playwright.

import { describe, expect, it } from 'vitest';

import { EventEmitter, MemorySink } from '../protocol.js';
import type {
  EvidenceEvent,
  RunEndEvent,
  RunStartEvent,
  TestEndEvent,
  TestStartEvent,
  TsEvent,
  StepStartEvent,
} from '../protocol.js';
import { SentinelReporter } from '../reporter.js';

function build(): { reporter: SentinelReporter; sink: MemorySink } {
  const sink = new MemorySink();
  const emitter = new EventEmitter({ sink, now: () => new Date('2026-05-28T00:00:00Z') });
  const reporter = new SentinelReporter({
    emitter,
    runId: 'run-test-1',
    target: 'http://localhost:3000',
  });
  return { reporter, sink };
}

interface FakeSuite {
  suites: FakeSuite[];
  tests: { id: string }[];
}

function fakeSuite(tests: number, children: FakeSuite[] = []): FakeSuite {
  return {
    suites: children,
    tests: Array.from({ length: tests }, (_, i) => ({ id: `t-${i}` })),
  };
}

describe('SentinelReporter', () => {
  it('emits run.start + run.end with correct test counts', () => {
    const { reporter, sink } = build();
    const suite = fakeSuite(0, [fakeSuite(2), fakeSuite(1)]);

    reporter.onBegin({} as any, suite as any);

    reporter.onEnd({ status: 'passed' } as any);

    const events = sink.events();
    expect(events.map((e) => e.type)).toEqual(['run.start', 'run.end']);
    const start = events[0] as RunStartEvent;
    expect(start.run_id).toBe('run-test-1');
    expect(start.target).toBe('http://localhost:3000');
    const end = events[1] as RunEndEvent;
    expect(end.tests_total).toBe(3);
    expect(end.tests_failed).toBe(0);
    expect(end.status).toBe('passed');
  });

  it('emits test.start + test.end and counts failures', () => {
    const { reporter, sink } = build();

    reporter.onBegin({} as any, fakeSuite(2) as any);

    const test1 = { id: 'a', title: 'logs in', location: { file: '/a.spec.ts' } };
    const test2 = { id: 'b', title: 'fails', location: { file: '/b.spec.ts' } };

    reporter.onTestBegin(test1 as any, {} as any);

    reporter.onTestEnd(
      test1 as any,
      { status: 'passed', duration: 12, retry: 0, attachments: [] } as any,
    );

    reporter.onTestBegin(test2 as any, {} as any);
    reporter.onTestEnd(
      test2 as any,
      {
        status: 'failed',
        duration: 200,
        retry: 1,
        attachments: [],
        error: { message: 'boom Bearer abc.DEF-ghi_jklmno0123456789', stack: 'at /b:1:1' },
      } as any,
    );

    reporter.onEnd({ status: 'failed' } as any);

    const events = sink.events();
    const types = events.map((e) => e.type);
    expect(types).toEqual([
      'run.start',
      'test.start',
      'test.end',
      'test.start',
      'test.end',
      'run.end',
    ]);
    const startA = events[1] as TestStartEvent;
    expect(startA.test_id).toBe('a');
    expect(startA.file).toBe('/a.spec.ts');
    const endB = events[4] as TestEndEvent;
    expect(endB.status).toBe('failed');
    expect(endB.retries).toBe(1);
    expect(endB.error?.message).toContain('[REDACTED:bearer_token]');
    const runEnd = events[5] as RunEndEvent;
    expect(runEnd.tests_failed).toBe(1);
  });

  it('emits step events only for user `test.step` calls by default', () => {
    const { reporter, sink } = build();

    reporter.onBegin({} as any, fakeSuite(1) as any);
    const test = { id: 't', title: 'demo', location: { file: '/t.spec.ts' } };

    reporter.onTestBegin(test as any, {} as any);

    const userStep = { title: 'click submit', category: 'test.step', duration: 5 };
    const internalStep = { title: 'page.goto()', category: 'pw:api', duration: 8 };

    reporter.onStepBegin(test as any, {} as any, userStep as any);

    reporter.onStepEnd(test as any, {} as any, userStep as any);

    reporter.onStepBegin(test as any, {} as any, internalStep as any);

    reporter.onStepEnd(test as any, {} as any, internalStep as any);

    const stepEvents = sink
      .events()
      .filter((e): e is TsEvent => e.type === 'step.start' || e.type === 'step.end');
    expect(stepEvents).toHaveLength(2);
    const start = stepEvents[0] as StepStartEvent;
    expect(start.name).toBe('click submit');
  });

  it('translates trace/screenshot/video attachments into evidence events', () => {
    const { reporter, sink } = build();

    reporter.onBegin({} as any, fakeSuite(1) as any);
    const test = { id: 't', title: 'demo', location: { file: '/t.spec.ts' } };

    reporter.onTestBegin(test as any, {} as any);
    reporter.onTestEnd(
      test as any,
      {
        status: 'failed',
        duration: 99,
        retry: 0,
        attachments: [
          { name: 'trace', contentType: 'application/zip', path: '/runs/x/trace.zip' },
          { name: 'screenshot', contentType: 'image/png', path: '/runs/x/shot.png' },
          { name: 'video', contentType: 'video/webm', path: '/runs/x/v.webm' },
          // Should be ignored — unknown name + content type:
          { name: 'log', contentType: 'text/plain', path: '/runs/x/log.txt' },
        ],
      } as any,
    );

    const evidenceEvents = sink.events().filter((e): e is EvidenceEvent => e.type === 'evidence');
    expect(evidenceEvents.map((e) => e.evidence_kind)).toEqual(['trace', 'screenshot', 'video']);
  });
});
