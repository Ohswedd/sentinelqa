// Cross-language parity for the JSONL protocol. The fixture is
// produced by `scripts/export-ts-events-parity.py`; this test parses
// every line through the TS `parseEvent` and asserts:
// 1. The fixture covers every TsEvent kind (no event lost in
// translation).
// 2. The TS parser accepts every line without throwing.
// 3. seq is monotonically increasing.
// 4. schema_version matches PROTOCOL_VERSION on every event.

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { PROTOCOL_VERSION, parseEvent, ProtocolParseError } from '../protocol.js';
import type { TsEvent } from '../protocol.js';

function loadLines(): string[] {
  const here = dirname(fileURLToPath(import.meta.url));
  const path = resolve(
    here,
    '..',
    '..',
    '..',
    '..',
    'tests',
    'golden',
    'ts-events',
    'sample.jsonl',
  );
  return readFileSync(path, 'utf8')
    .split('\n')
    .filter((s) => s.length > 0);
}

const EXPECTED_KINDS = new Set<TsEvent['type']>([
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

describe('TS-events parity (TS ↔ Python)', () => {
  const lines = loadLines();

  it('loads a non-trivial fixture', () => {
    expect(lines.length).toBeGreaterThanOrEqual(14);
  });

  it('covers every event kind', () => {
    const types = new Set<string>();
    for (const line of lines) {
      const ev = JSON.parse(line) as { type: string };
      types.add(ev.type);
    }
    const missing = [...EXPECTED_KINDS].filter((t) => !types.has(t));
    expect(missing).toEqual([]);
  });

  it('TS parseEvent accepts every line', () => {
    const events = lines.map((l) => parseEvent(l));
    expect(events).toHaveLength(lines.length);
    expect(events[0]?.type).toBe('run.start');
    expect(events.at(-1)?.type).toBe('run.end');
  });

  it('PROTOCOL_VERSION matches every event', () => {
    for (const line of lines) {
      const ev = parseEvent(line);
      expect(ev.schema_version).toBe(PROTOCOL_VERSION);
    }
  });

  it('seq is monotonically increasing', () => {
    let prev = 0;
    for (const line of lines) {
      const ev = parseEvent(line);
      expect(ev.seq).toBeGreaterThan(prev);
      prev = ev.seq;
    }
  });

  it('rejects unknown event types via ProtocolParseError', () => {
    const bad = JSON.stringify({
      type: 'mystery.event',
      schema_version: PROTOCOL_VERSION,
      seq: 1,
      ts: '2026-05-28T00:00:00Z',
    });
    expect(() => parseEvent(bad)).toThrow(ProtocolParseError);
  });

  it('rejects malformed JSON', () => {
    expect(() => parseEvent('{not json}')).toThrow(ProtocolParseError);
  });
});
