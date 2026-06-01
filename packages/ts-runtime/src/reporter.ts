// Custom Playwright reporter — translates Playwright's reporter
// callbacks into SentinelQA JSONL events. Loaded
// by Playwright via `--reporter=<path>`; sentinel-ts (04.03) wires this
// path through.
// The reporter writes events through an `EventEmitter` whose sink is
// `process.stdout` by default. Python (the parent process) reads stdout
// line by line and parses each event.
// Browser launching, evidence capture, etc. are Playwright's job — the
// reporter just observes and emits.

import type {
  FullConfig,
  FullResult,
  Reporter,
  Suite,
  TestCase,
  TestError,
  TestResult,
  TestStep,
} from '@playwright/test/reporter';

import type {
  EvidenceKind,
  EvidenceEvent,
  RunEndEvent,
  RunStartEvent,
  StepEndEvent,
  StepStartEvent,
  TestEndEvent,
  TestStartEvent,
  TestStatus,
  RunStatus,
  SerializedError,
} from './protocol.js';
import { EventEmitter } from './protocol.js';
import { redact } from './redact.js';

const ATTACHMENT_TO_EVIDENCE: Readonly<Record<string, EvidenceKind>> = {
  trace: 'trace',
  screenshot: 'screenshot',
  video: 'video',
};

function attachmentEvidenceKind(name: string, contentType: string): EvidenceKind | null {
  if (name in ATTACHMENT_TO_EVIDENCE) return ATTACHMENT_TO_EVIDENCE[name]!;
  if (name.startsWith('screenshot')) return 'screenshot';
  if (name.startsWith('trace')) return 'trace';
  if (name.startsWith('video')) return 'video';
  if (contentType === 'image/png' || contentType === 'image/jpeg') return 'screenshot';
  if (contentType === 'application/zip') return 'trace';
  if (contentType.startsWith('video/')) return 'video';
  if (contentType === 'application/json' && name.includes('har')) return 'har';
  return null;
}

function mapTestStatus(status: TestResult['status']): TestStatus {
  switch (status) {
    case 'passed':
      return 'passed';
    case 'failed':
    case 'interrupted':
      return 'failed';
    case 'timedOut':
      return 'timed_out';
    case 'skipped':
      return 'skipped';
  }
}

function mapRunStatus(status: FullResult['status']): RunStatus {
  switch (status) {
    case 'passed':
      return 'passed';
    case 'failed':
      return 'failed';
    case 'timedout':
      return 'timed_out';
    case 'interrupted':
      return 'interrupted';
  }
}

function serializeTestError(err: TestError): SerializedError {
  const name = 'TestError';
  const message = redact(err.message ?? '') as string;
  const stack = err.stack ? (redact(err.stack) as string) : undefined;
  return { name, message, ...(stack !== undefined ? { stack } : {}) };
}

/**
 * Reporter options. Defaults emit to stdout; the runner CLI (04.03)
 * always uses defaults so events naturally flow to Python.
 */
export interface SentinelReporterOptions {
  readonly emitter?: EventEmitter;
  readonly runId?: string;
  readonly target?: string;
  readonly emitPlaywrightInternals?: boolean;
}

/**
 * The reporter Playwright instantiates. Must be a class with a no-arg
 * constructor when loaded via `--reporter`, so we read the runner
 * config + emitter from env vars.
 */
export class SentinelReporter implements Reporter {
  private emitter: EventEmitter;
  private runId: string;
  private target: string;
  private emitInternals: boolean;
  private testsTotal = 0;
  private testsFailed = 0;
  private startedAt = '';
  private stepStartMap = new WeakMap<TestStep, string>();
  private stepCounter = 0;

  constructor(opts: SentinelReporterOptions = {}) {
    this.emitter = opts.emitter ?? new EventEmitter();
    this.runId = opts.runId ?? process.env['SENTINELQA_RUN_ID'] ?? `local-${Date.now()}`;
    this.target = opts.target ?? process.env['SENTINELQA_TARGET'] ?? 'unknown';
    this.emitInternals = opts.emitPlaywrightInternals ?? false;
  }

  /** Test-only: get the emitter for assertion. */
  get _emitter(): EventEmitter {
    return this.emitter;
  }

  printsToStdio(): boolean {
    return true;
  }

  onBegin(_config: FullConfig, suite: Suite): void {
    this.testsTotal = countTests(suite);
    this.startedAt = new Date().toISOString();
    this.emitter.emit<RunStartEvent>({
      type: 'run.start',
      run_id: this.runId,
      target: this.target,
      started_at: this.startedAt,
    });
  }

  onTestBegin(test: TestCase, _result: TestResult): void {
    this.emitter.emit<TestStartEvent>({
      type: 'test.start',
      test_id: test.id,
      title: test.title,
      file: test.location.file,
    });
  }

  onStepBegin(test: TestCase, _result: TestResult, step: TestStep): void {
    if (!this.shouldEmitStep(step)) return;
    this.stepCounter += 1;
    const stepId = `pw-step-${this.stepCounter.toString(36)}`;
    this.stepStartMap.set(step, stepId);
    this.emitter.emit<StepStartEvent>({
      type: 'step.start',
      test_id: test.id,
      step_id: stepId,
      name: step.title,
    });
  }

  onStepEnd(test: TestCase, _result: TestResult, step: TestStep): void {
    if (!this.shouldEmitStep(step)) return;
    const stepId = this.stepStartMap.get(step) ?? 'pw-step-unknown';
    this.emitter.emit<StepEndEvent>({
      type: 'step.end',
      test_id: test.id,
      step_id: stepId,
      duration_ms: Math.max(0, Math.round(step.duration)),
      ok: step.error === undefined,
      ...(step.error !== undefined ? { error: serializeTestError(step.error) } : {}),
    });
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const status = mapTestStatus(result.status);
    if (status === 'failed' || status === 'timed_out') this.testsFailed += 1;

    for (const attachment of result.attachments) {
      const kind = attachmentEvidenceKind(attachment.name, attachment.contentType);
      if (kind === null || attachment.path === undefined) continue;
      this.emitter.emit<EvidenceEvent>({
        type: 'evidence',
        test_id: test.id,
        step_id: null,
        evidence_kind: kind,
        path: attachment.path,
        label: attachment.name,
      });
    }

    const error = result.error !== undefined ? serializeTestError(result.error) : undefined;
    this.emitter.emit<TestEndEvent>({
      type: 'test.end',
      test_id: test.id,
      duration_ms: Math.max(0, Math.round(result.duration)),
      status,
      retries: result.retry,
      ...(error !== undefined ? { error } : {}),
    });
  }

  onEnd(result: FullResult): void {
    this.emitter.emit<RunEndEvent>({
      type: 'run.end',
      run_id: this.runId,
      finished_at: new Date().toISOString(),
      status: mapRunStatus(result.status),
      tests_total: this.testsTotal,
      tests_failed: this.testsFailed,
    });
  }

  private shouldEmitStep(step: TestStep): boolean {
    if (this.emitInternals) return true;
    // We default to user-authored test.step calls only. Playwright
    // internals (pw:api, hook, expect) are noisy and not what tests
    // want to telemeter to Python.
    return step.category === 'test.step';
  }
}

function countTests(suite: Suite): number {
  let n = 0;
  const walk = (s: Suite): void => {
    for (const child of s.suites) walk(child);
    n += s.tests.length;
  };
  walk(suite);
  return n;
}

// Playwright loads a reporter module by its default export OR by the
// `default` named export. We expose both so either resolution works.
export default SentinelReporter;
