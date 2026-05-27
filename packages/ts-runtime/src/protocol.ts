// Python ↔ TS JSONL event protocol — TS emitter side. ADR-0009 owns the
// rationale; `packages/shared-schema/ts-events.schema.json` is the wire
// contract (frozen in task 04.04; this module emits against that
// contract). Python parses these events via
// `engine/orchestrator/ts_bridge.py`.
//
// Every event carries:
//   schema_version  bumped via PROTOCOL_VERSION
//   seq             monotonic int per emitter
//   ts              RFC 3339 UTC timestamp
//   type            discriminator
// plus a `type`-specific payload.

import { stdout } from 'node:process';

export const PROTOCOL_VERSION = '1.0.0';

// ---------------------------------------------------------------------
// Event types — discriminated union on `type`. Field shapes are mirrored
// in the JSON Schema (task 04.04) and the Python parser.
// ---------------------------------------------------------------------

interface BaseEvent<TType extends string> {
  readonly type: TType;
  readonly schema_version: string;
  readonly seq: number;
  readonly ts: string;
}

export type RunStatus = 'passed' | 'failed' | 'timed_out' | 'interrupted' | 'errored';
export type TestStatus = 'passed' | 'failed' | 'timed_out' | 'skipped';
export type EvidenceKind =
  | 'trace'
  | 'screenshot'
  | 'video'
  | 'har'
  | 'dom_snapshot'
  | 'network_log'
  | 'console_log';
export type ConsoleLevel = 'log' | 'debug' | 'info' | 'warn' | 'error';
export type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface RunStartEvent extends BaseEvent<'run.start'> {
  readonly run_id: string;
  readonly target: string;
  readonly started_at: string;
}

export interface RunEndEvent extends BaseEvent<'run.end'> {
  readonly run_id: string;
  readonly finished_at: string;
  readonly status: RunStatus;
  readonly tests_total: number;
  readonly tests_failed: number;
}

export interface TestStartEvent extends BaseEvent<'test.start'> {
  readonly test_id: string;
  readonly title: string;
  readonly file: string;
}

export interface TestEndEvent extends BaseEvent<'test.end'> {
  readonly test_id: string;
  readonly duration_ms: number;
  readonly status: TestStatus;
  readonly retries: number;
  readonly error?: SerializedError;
}

export interface StepStartEvent extends BaseEvent<'step.start'> {
  readonly test_id: string | null;
  readonly step_id: string;
  readonly name: string;
}

export interface StepEndEvent extends BaseEvent<'step.end'> {
  readonly test_id: string | null;
  readonly step_id: string;
  readonly duration_ms: number;
  readonly ok: boolean;
  readonly error?: SerializedError;
}

export interface EvidenceEvent extends BaseEvent<'evidence'> {
  readonly test_id: string | null;
  readonly step_id: string | null;
  readonly evidence_kind: EvidenceKind;
  readonly path: string;
  readonly label: string;
}

export interface NetworkRequestEvent extends BaseEvent<'network.request'> {
  readonly test_id: string | null;
  readonly request_id: string;
  readonly url: string;
  readonly method: string;
  readonly content_length: number | null;
  readonly content_type: string | null;
}

export interface NetworkResponseEvent extends BaseEvent<'network.response'> {
  readonly test_id: string | null;
  readonly request_id: string;
  readonly url: string;
  readonly status: number;
  readonly duration_ms: number;
  readonly content_length: number | null;
  readonly content_type: string | null;
}

export interface ConsoleEvent extends BaseEvent<'console'> {
  readonly test_id: string | null;
  readonly level: ConsoleLevel;
  readonly message: string;
  readonly source: string;
}

export interface DomSnapshotEvent extends BaseEvent<'dom.snapshot'> {
  readonly test_id: string | null;
  readonly step_id: string | null;
  readonly path: string;
  readonly label: string;
}

export interface ModuleEventEvent extends BaseEvent<'module.event'> {
  readonly module: string;
  readonly name: string;
  readonly payload: Record<string, unknown>;
}

export interface LogEvent extends BaseEvent<'log'> {
  readonly level: LogLevel;
  readonly msg: string;
  readonly fields: Record<string, unknown>;
}

export interface ErrorEvent extends BaseEvent<'error'> {
  readonly code: string;
  readonly message: string;
  readonly stack?: string;
}

export interface SerializedError {
  readonly name: string;
  readonly message: string;
  readonly stack?: string;
}

export type TsEvent =
  | RunStartEvent
  | RunEndEvent
  | TestStartEvent
  | TestEndEvent
  | StepStartEvent
  | StepEndEvent
  | EvidenceEvent
  | NetworkRequestEvent
  | NetworkResponseEvent
  | ConsoleEvent
  | DomSnapshotEvent
  | ModuleEventEvent
  | LogEvent
  | ErrorEvent;

// ---------------------------------------------------------------------
// Emitter
// ---------------------------------------------------------------------

export interface EmitterSink {
  write(line: string): void;
}

export interface EmitterOptions {
  /**
   * Where to write event lines. Defaults to `process.stdout` so Python
   * (which spawns sentinel-ts) reads events line-by-line.
   */
  readonly sink?: EmitterSink;
  /**
   * Override the time source. Test-only.
   */
  readonly now?: () => Date;
}

/**
 * Stateful, ordered emitter for JSONL events. Each `emit*` call bumps
 * `seq`. Construct one per run; the runner (Phase 04.03) owns the
 * singleton.
 */
export class EventEmitter {
  private seq = 0;
  private readonly sink: EmitterSink;
  private readonly nowFn: () => Date;

  constructor(opts: EmitterOptions = {}) {
    this.sink = opts.sink ?? { write: (line: string) => stdout.write(line) };
    this.nowFn = opts.now ?? (() => new Date());
  }

  private nextSeq(): number {
    this.seq += 1;
    return this.seq;
  }

  private nowIso(): string {
    return this.nowFn().toISOString();
  }

  /**
   * Low-level: caller fills in every field except `schema_version`,
   * `seq`, `ts`. Returns the rendered event for inspection.
   */
  emit<E extends TsEvent>(payload: Omit<E, 'schema_version' | 'seq' | 'ts'>): E {
    const event = {
      ...(payload as object),
      schema_version: PROTOCOL_VERSION,
      seq: this.nextSeq(),
      ts: this.nowIso(),
    } as E;
    this.sink.write(JSON.stringify(event) + '\n');
    return event;
  }

  /** Current monotonic sequence number (test introspection). */
  get currentSeq(): number {
    return this.seq;
  }
}

/**
 * Capture-to-memory sink — used by tests to assert what was emitted.
 */
export class MemorySink implements EmitterSink {
  readonly lines: string[] = [];
  write(line: string): void {
    this.lines.push(line);
  }
  events(): TsEvent[] {
    return this.lines.map((line) => parseEvent(line));
  }
}

/**
 * Convenience constructor: returns `{ emitter, sink }` so callers can
 * inspect emitted events. Production code uses `new EventEmitter()`.
 */
export function createEmitter(opts: EmitterOptions = {}): {
  emitter: EventEmitter;
  sink: EmitterSink;
} {
  const sink = opts.sink ?? new MemorySink();
  return { emitter: new EventEmitter({ ...opts, sink }), sink };
}

// ---------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------

const VALID_TYPES = new Set<string>([
  'run.start',
  'run.end',
  'test.start',
  'test.end',
  'step.start',
  'step.end',
  'evidence',
  'network.request',
  'network.response',
  'console',
  'dom.snapshot',
  'module.event',
  'log',
  'error',
]);

export class ProtocolParseError extends Error {
  constructor(
    message: string,
    readonly line: string,
  ) {
    super(message);
    this.name = 'ProtocolParseError';
  }
}

/**
 * Parse a single JSONL line into a typed event. Throws
 * `ProtocolParseError` on invalid JSON, unknown `type`, or missing
 * envelope fields.
 *
 * The TS side is permissive about per-event payload fields (Python's
 * Pydantic parser is strict). The cross-language parity test in 04.04
 * proves that both halves agree on every event shape.
 */
export function parseEvent(line: string): TsEvent {
  let parsed: unknown;
  try {
    parsed = JSON.parse(line);
  } catch (err) {
    throw new ProtocolParseError(`invalid JSON: ${(err as Error).message}`, line);
  }
  if (typeof parsed !== 'object' || parsed === null) {
    throw new ProtocolParseError('event must be an object', line);
  }
  const ev = parsed as Record<string, unknown>;
  const type = ev['type'];
  if (typeof type !== 'string' || !VALID_TYPES.has(type)) {
    throw new ProtocolParseError(`unknown event type: ${String(type)}`, line);
  }
  if (typeof ev['schema_version'] !== 'string') {
    throw new ProtocolParseError('missing schema_version', line);
  }
  if (typeof ev['seq'] !== 'number') {
    throw new ProtocolParseError('missing or non-numeric seq', line);
  }
  if (typeof ev['ts'] !== 'string') {
    throw new ProtocolParseError('missing ts', line);
  }
  return ev as unknown as TsEvent;
}
