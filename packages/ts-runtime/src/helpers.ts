// Helpers consumed by SentinelQA-generated tests and by the runner
//. Each helper is fully decoupled from
// Playwright's test-runner state — they take an `EventEmitter`
// explicitly. Generated tests pull the emitter from the `sentinelTest`
// fixture (see ./playwright.ts).

import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';

import type {
  ConsoleEvent,
  ConsoleLevel,
  DomSnapshotEvent,
  EvidenceEvent,
  EvidenceKind,
  NetworkFailureEvent,
  NetworkRequestEvent,
  NetworkResponseEvent,
  PageErrorEvent,
  StepEndEvent,
  StepStartEvent,
} from './protocol.js';
import type { EventEmitter } from './protocol.js';
import { redact, redactHeaders, redactUrl } from './redact.js';

const FAILURE_BODY_PREVIEW_BYTES = 2048;

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
 * `captureEvidence(page, label)` contract in the documentation
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
  // v1.3.0: ``inflight`` now also retains the request-side method +
  // redacted headers so the ``network.failure`` event has everything
  // it needs without a second listener traversal.
  const inflight = new Map<
    string,
    {
      startNs: bigint;
      requestId: string;
      method: string;
      requestHeaders: Record<string, string>;
    }
  >();
  const testId = ctx.testId ?? null;

  page.on('request', (req) => {
    const requestId = nextRequestId();
    const requestHeaders = redactHeaders(req.headers());
    inflight.set(req.url(), {
      startNs: process.hrtime.bigint(),
      requestId,
      method: req.method(),
      requestHeaders,
    });
    const postBuffer = req.postDataBuffer();
    const length = postBuffer === null ? null : postBuffer.byteLength;
    ctx.emitter.emit<NetworkRequestEvent>({
      type: 'network.request',
      test_id: testId,
      request_id: requestId,
      url: redactUrl(req.url()),
      method: req.method(),
      content_length: length,
      content_type: extractContentType(requestHeaders),
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
    const status = res.status();
    ctx.emitter.emit<NetworkResponseEvent>({
      type: 'network.response',
      test_id: testId,
      request_id: entry?.requestId ?? 'unknown',
      url: redactUrl(url),
      status,
      duration_ms: durationMs,
      content_length: contentLength,
      content_type: extractContentType(headers),
    });

    // v1.3.0 — network forensics: when a 5xx happens during a test
    // we capture the request + response (redacted) and a bounded body
    // preview so the failure isn't opaque downstream. Body capture is
    // best-effort — Playwright's ``body()`` rejects after redirects or
    // when the response has been consumed; the catch keeps the
    // listener silent on those paths.
    if (status >= 500 && status < 600) {
      void capturePreview(res).then((preview) => {
        ctx.emitter.emit<NetworkFailureEvent>({
          type: 'network.failure',
          test_id: testId,
          request_id: entry?.requestId ?? 'unknown',
          url: redactUrl(url),
          method: entry?.method ?? 'UNKNOWN',
          status,
          request_headers: entry?.requestHeaders ?? {},
          response_headers: headers,
          response_body_preview: preview,
          duration_ms: durationMs,
        });
      });
    }
  });

  return { inflight };
}

interface BodyCapableResponse {
  body?(): Promise<Buffer>;
}

async function capturePreview(res: BodyCapableResponse): Promise<string> {
  if (typeof res.body !== 'function') return '';
  try {
    const buffer = await res.body();
    const slice = buffer.subarray(0, FAILURE_BODY_PREVIEW_BYTES).toString('utf8');
    return redact(slice) as string;
  } catch {
    return '';
  }
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

// ---------------------------------------------------------------------
// Redacted console interception
// ---------------------------------------------------------------------

/**
 * Minimal Playwright `ConsoleMessage` surface.
 */
export interface ConsoleMessage {
  type(): string;
  text(): string;
  location(): { url?: string };
}

/**
 * Minimal Playwright surface for the `console` listener.
 */
export interface ConsoleEmitterPage {
  on(event: 'console', listener: (msg: ConsoleMessage) => void): void;
}

const VALID_CONSOLE_LEVELS = new Set<ConsoleLevel>(['log', 'debug', 'info', 'warn', 'error']);

function mapConsoleLevel(playwrightType: string): ConsoleLevel {
  // Playwright uses 'warning' where we use 'warn'.
  if (playwrightType === 'warning') return 'warn';
  if (VALID_CONSOLE_LEVELS.has(playwrightType as ConsoleLevel)) {
    return playwrightType as ConsoleLevel;
  }
  return 'log';
}

/**
 * Listen for browser `console` events, redact each message, and emit a
 * `console` JSONL event per call. the engineering guidelines: every message passes
 * through `redact()` so secrets in console.log output never reach
 * Python.
 */
export function redactedConsole(page: ConsoleEmitterPage, ctx: StepContext): void {
  const testId = ctx.testId ?? null;
  page.on('console', (msg) => {
    const level = mapConsoleLevel(msg.type());
    const message = redact(msg.text()) as string;
    const sourceRaw = msg.location().url ?? '';
    const source = sourceRaw === '' ? '' : redactUrl(sourceRaw);
    ctx.emitter.emit<ConsoleEvent>({
      type: 'console',
      test_id: testId,
      level,
      message,
      source,
    });
  });
}

// ---------------------------------------------------------------------
// v1.3.0 — Unhandled page errors
// ---------------------------------------------------------------------

/**
 * Minimal Playwright surface for `pageerror`. Listeners receive a
 * native ``Error`` whose ``stack`` is best-effort populated by the
 * browser. Both ``message`` and ``stack`` pass through ``redact()``
 * before emission so secrets that surface in stack traces stay local.
 */
export interface PageErrorEmitterPage {
  on(event: 'pageerror', listener: (err: Error) => void): void;
}

/**
 * Attach a ``pageerror`` listener that emits one ``page.error`` JSONL
 * event for every unhandled browser exception during the run.
 *
 * The shape mirrors :class:`PageErrorEvent` (protocol.ts). The
 * underlying Playwright ``pageerror`` fires for window-level
 * exceptions; unhandled promise rejections that surface as
 * ``unhandledrejection`` are emitted too on modern Playwright builds.
 */
export function redactedPageErrors(page: PageErrorEmitterPage, ctx: StepContext): void {
  const testId = ctx.testId ?? null;
  page.on('pageerror', (err) => {
    const message = redact(err.message ?? '') as string;
    const stack = redact(err.stack ?? '') as string;
    const sourceUrl = extractSourceFromStack(stack);
    ctx.emitter.emit<PageErrorEvent>({
      type: 'page.error',
      test_id: testId,
      name: err.name ?? 'Error',
      message,
      stack,
      source_url: sourceUrl,
    });
  });
}

const STACK_FILE_RE = /\(?((?:https?|file|chrome-extension|webpack):\/\/[^\s)]+)/;

function extractSourceFromStack(stack: string): string {
  const match = STACK_FILE_RE.exec(stack);
  if (match === null) return '';
  return redactUrl(match[1] ?? '');
}

// ---------------------------------------------------------------------
// DOM snapshot helper
// ---------------------------------------------------------------------

/**
 * Minimal Playwright surface for accessibility snapshots.
 */
export interface AccessibilityPage extends PageLike {
  accessibility?: {
    snapshot(): Promise<unknown>;
  };
}

export interface DomSnapshotRef {
  readonly path: string;
  readonly label: string;
  readonly axTreeHash: string;
}

/**
 * Capture a full HTML snapshot plus a hash of the accessibility tree.
 * The hash is the *content* digest the Healer () compares
 * against when deciding whether a locator change is legitimate.
 *
 * `axTreeHash` is `sha256` of the JSON-stringified accessibility tree
 * with sorted keys. When the page implements no `accessibility` (our
 * fake `PageLike` in unit tests), the hash is the digest of `null`.
 */
export async function captureDomSnapshot(
  ctx: EvidenceContext,
  page: AccessibilityPage,
  label: string,
): Promise<DomSnapshotRef> {
  const labelSlug = slugify(label);
  const path = join(ctx.runDir, 'dom', `${labelSlug}.html`);
  const html = await page.content();
  await ensureDir(dirname(path));
  await writeFile(path, redact(html) as string, 'utf8');

  let axTree: unknown = null;
  if (page.accessibility !== undefined) {
    try {
      axTree = await page.accessibility.snapshot();
    } catch {
      axTree = null;
    }
  }
  const axTreeHash = sha256(JSON.stringify(axTree ?? null));

  ctx.emitter.emit<DomSnapshotEvent>({
    type: 'dom.snapshot',
    test_id: ctx.testId ?? null,
    step_id: ctx.stepId ?? null,
    path,
    label,
  });
  return { path, label, axTreeHash };
}

function sha256(input: string): string {
  return createHash('sha256').update(input).digest('hex');
}

// ---------------------------------------------------------------------
// HAR config — opt-in per-context HAR recording
// ---------------------------------------------------------------------

/**
 * Build the `recordHar` snippet a sentinelTest fixture passes to
 * `context()`. The runner (04.03) sets `evidence.har: true` in the
 * run-config when the user opted in; the fixture reads it and merges
 * with the rest of the context options.
 *
 * The path is deterministic: `<runDir>/har/<test-id>.har`. the engineering guidelines
 * — per-run isolation, no cross-run bleed.
 */
export interface HarConfig {
  readonly recordHar: {
    readonly path: string;
    readonly mode: 'minimal' | 'full';
    readonly content: 'omit' | 'embed' | 'attach';
  };
}

export function harConfig(ctx: EvidenceContext): HarConfig {
  const testId = ctx.testId ?? 'unknown-test';
  return {
    recordHar: {
      path: join(ctx.runDir, 'har', `${testId}.har`),
      mode: 'minimal',
      content: 'omit',
    },
  };
}
