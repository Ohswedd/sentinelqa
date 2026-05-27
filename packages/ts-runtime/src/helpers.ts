// Helpers consumed by SentinelQA-generated tests and by the runner
// (PRD §15.2, CLAUDE.md §21). Each helper is fully decoupled from
// Playwright's test-runner state — they take an `EventEmitter`
// explicitly. Generated tests pull the emitter from the `sentinelTest`
// fixture (see ./playwright.ts).

import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';

import type {
  EvidenceEvent,
  EvidenceKind,
  NetworkRequestEvent,
  NetworkResponseEvent,
  StepEndEvent,
  StepStartEvent,
} from './protocol.js';
import type { EventEmitter } from './protocol.js';
import { redactHeaders, redactUrl, redact } from './redact.js';

let stepCounter = 0;

function nextStepId(): string {
  stepCounter += 1;
  return `step-${stepCounter.toString(36)}`;
}

/** Test-only — resets the step ID counter. */
export function _resetStepCounterForTests(): void {
  stepCounter = 0;
}

export interface StepContext {
  readonly emitter: EventEmitter;
  /** Optional test ID to associate events with the active test. */
  readonly testId?: string;
}

/**
 * Wrap an async block as a step. Emits `step.start` before and
 * `step.end` after, regardless of whether the block threw. If the block
 * throws, the error is serialized into the `step.end` event (stack
 * redacted) and re-thrown.
 *
 * `sentinelStep` does NOT call `test.step()` itself — that wiring lives
 * in `playwright.ts` so this module stays runtime-agnostic and
 * unit-testable without spinning up Playwright.
 */
export async function sentinelStep<T>(
  ctx: StepContext,
  name: string,
  fn: () => Promise<T>,
): Promise<T> {
  const stepId = nextStepId();
  const startNs = process.hrtime.bigint();
  const testId = ctx.testId ?? null;
  ctx.emitter.emit<StepStartEvent>({
    type: 'step.start',
    test_id: testId,
    step_id: stepId,
    name,
  });
  try {
    const result = await fn();
    const durationMs = elapsedMs(startNs);
    ctx.emitter.emit<StepEndEvent>({
      type: 'step.end',
      test_id: testId,
      step_id: stepId,
      duration_ms: durationMs,
      ok: true,
    });
    return result;
  } catch (err) {
    const durationMs = elapsedMs(startNs);
    const serialized = serializeError(err);
    ctx.emitter.emit<StepEndEvent>({
      type: 'step.end',
      test_id: testId,
      step_id: stepId,
      duration_ms: durationMs,
      ok: false,
      error: serialized,
    });
    throw err;
  }
}

function elapsedMs(startNs: bigint): number {
  const nowNs = process.hrtime.bigint();
  // Truncate to integer ms — JSON has no fractional-int policy and the
  // Python side stores duration_ms as int.
  return Number((nowNs - startNs) / 1_000_000n);
}

function serializeError(err: unknown): { name: string; message: string; stack?: string } {
  if (err instanceof Error) {
    const stack = err.stack ? (redact(err.stack) as string) : undefined;
    return {
      name: err.name,
      message: redact(err.message) as string,
      ...(stack !== undefined ? { stack } : {}),
    };
  }
  return { name: 'NonError', message: redact(String(err)) as string };
}

// ---------------------------------------------------------------------
// Evidence capture
// ---------------------------------------------------------------------

export interface EvidenceContext extends StepContext {
  /** Directory the run lifecycle handed us (e.g. `.sentinel/runs/<id>/`). */
  readonly runDir: string;
  /** Optional active step id (correlates the evidence with a step). */
  readonly stepId?: string;
}

export interface CaptureEvidenceOptions {
  readonly screenshot?: boolean;
  readonly dom?: boolean;
  readonly har?: boolean;
}

export interface EvidenceRef {
  readonly kind: EvidenceKind;
  readonly path: string;
  readonly label: string;
}

/**
 * Minimal Playwright `Page` surface we actually use. Keeping this
 * interface narrow lets vitest fake it without `@playwright/test`'s
 * massive type graph.
 */
export interface PageLike {
  screenshot(opts: { path: string; fullPage?: boolean }): Promise<Buffer>;
  content(): Promise<string>;
  url(): string;
}

/**
 * Always-on evidence capture. Writes the requested artifacts into the
 * run directory and emits one `evidence` event per artifact. The
 * default writes a screenshot + DOM snapshot — matching the
 * `captureEvidence(page, label)` contract in PRD §15.2.
 */
export async function captureEvidence(
  ctx: EvidenceContext,
  page: PageLike,
  label: string,
  opts: CaptureEvidenceOptions = {},
): Promise<EvidenceRef[]> {
  const wantsScreenshot = opts.screenshot ?? true;
  const wantsDom = opts.dom ?? true;
  const wantsHar = opts.har ?? false;
  const refs: EvidenceRef[] = [];
  const labelSlug = slugify(label);

  if (wantsScreenshot) {
    const path = join(ctx.runDir, 'screenshots', `${labelSlug}.png`);
    await ensureDir(dirname(path));
    await page.screenshot({ path, fullPage: true });
    refs.push({ kind: 'screenshot', path, label });
  }
  if (wantsDom) {
    const path = join(ctx.runDir, 'dom', `${labelSlug}.html`);
    const html = await page.content();
    await ensureDir(dirname(path));
    // DOM is redacted via the string pipeline — value-level rules catch
    // tokens that might appear in inline scripts or data-* attrs.
    await writeFile(path, redact(html) as string, 'utf8');
    refs.push({ kind: 'dom_snapshot', path, label });
  }
  if (wantsHar) {
    // Playwright HAR is configured at context creation (`recordHar`).
    // We only emit the reference here; the file is written by Playwright
    // on context close. The runner (04.03) wires the recordHar option
    // when `evidence.har: true` is set in sentinel.config.yaml.
    const path = join(ctx.runDir, 'har', `${labelSlug}.har`);
    refs.push({ kind: 'har', path, label });
  }

  for (const ref of refs) {
    ctx.emitter.emit<EvidenceEvent>({
      type: 'evidence',
      test_id: ctx.testId ?? null,
      step_id: ctx.stepId ?? null,
      evidence_kind: ref.kind,
      path: ref.path,
      label: ref.label,
    });
  }
  return refs;
}

function slugify(label: string): string {
  return label
    .toLowerCase()
    .replace(/[^a-z0-9-_]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

async function ensureDir(path: string): Promise<void> {
  await mkdir(path, { recursive: true });
}

export function _resolveRunDir(p: string): string {
  return resolve(p);
}

// ---------------------------------------------------------------------
// Redacted network interception
// ---------------------------------------------------------------------

/**
 * Minimal Playwright surface for installing route handlers + listeners.
 */
export interface RoutablePage {
  on(event: 'request', listener: (req: NetworkRequest) => void): void;
  on(event: 'response', listener: (res: NetworkResponse) => void): void;
}

export interface NetworkRequest {
  url(): string;
  method(): string;
  headers(): Record<string, string>;
  postDataBuffer(): Buffer | null;
  resourceType(): string;
}

export interface NetworkResponse {
  url(): string;
  status(): number;
  headers(): Record<string, string>;
  request(): NetworkRequest;
}

export interface NetworkInterceptor {
  readonly inflight: Map<string, { startNs: bigint; requestId: string }>;
}

let requestCounter = 0;
function nextRequestId(): string {
  requestCounter += 1;
  return `req-${requestCounter.toString(36)}`;
}

/** Test-only — resets the request ID counter. */
export function _resetRequestCounterForTests(): void {
  requestCounter = 0;
}

/**
 * Attach request/response listeners to `page`. For every network event
 * we emit a redacted `network.request` / `network.response` JSONL line
 * — URL is run through `redactUrl`, headers through `redactHeaders`.
 *
 * The returned interceptor exposes an `inflight` map keyed by request
 * URL so callers can correlate latencies. The runner (04.03) consumes
 * the JSONL stream and does the same correlation; this map is for
 * in-process callers (and tests).
 */
export function redactedNetwork(page: RoutablePage, ctx: StepContext): NetworkInterceptor {
  const inflight = new Map<string, { startNs: bigint; requestId: string }>();
  const testId = ctx.testId ?? null;

  page.on('request', (req) => {
    const requestId = nextRequestId();
    inflight.set(req.url(), { startNs: process.hrtime.bigint(), requestId });
    const headers = redactHeaders(req.headers());
    const postBuffer = req.postDataBuffer();
    const length = postBuffer === null ? null : postBuffer.byteLength;
    ctx.emitter.emit<NetworkRequestEvent>({
      type: 'network.request',
      test_id: testId,
      request_id: requestId,
      url: redactUrl(req.url()),
      method: req.method(),
      content_length: length,
      content_type: extractContentType(headers),
    });
  });

  page.on('response', (res) => {
    const url = res.url();
    const entry = inflight.get(url);
    inflight.delete(url);
    const headers = redactHeaders(res.headers());
    const durationMs =
      entry === undefined ? 0 : Number((process.hrtime.bigint() - entry.startNs) / 1_000_000n);
    const contentLengthHeader = headers['content-length'] ?? headers['Content-Length'];
    const contentLength =
      contentLengthHeader === undefined ? null : safeParseInt(contentLengthHeader);
    ctx.emitter.emit<NetworkResponseEvent>({
      type: 'network.response',
      test_id: testId,
      request_id: entry?.requestId ?? 'unknown',
      url: redactUrl(url),
      status: res.status(),
      duration_ms: durationMs,
      content_length: contentLength,
      content_type: extractContentType(headers),
    });
  });

  return { inflight };
}

function extractContentType(headers: Record<string, string>): string | null {
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === 'content-type') return v;
  }
  return null;
}

function safeParseInt(value: string): number | null {
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : null;
}
