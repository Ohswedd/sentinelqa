// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.

import { describe, it, expect } from 'vitest';
import { validateLoopbackTarget } from './loopback';

describe('validateLoopbackTarget', () => {
  it('accepts 127.0.0.1', () => {
    const r = validateLoopbackTarget('http://127.0.0.1', 7333);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.normalised).toBe('http://127.0.0.1:7333');
  });

  it('accepts localhost', () => {
    const r = validateLoopbackTarget('http://localhost', 7333);
    expect(r.ok).toBe(true);
  });

  it('accepts an explicit IPv6 loopback host', () => {
    const r = validateLoopbackTarget('http://[::1]', 7333);
    expect(r.ok).toBe(true);
  });

  it('rejects a public hostname', () => {
    const r = validateLoopbackTarget('http://example.com', 7333);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('non_loopback_host');
  });

  it('rejects a non-http scheme', () => {
    const r = validateLoopbackTarget('ws://127.0.0.1', 7333);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('non_http_scheme');
  });

  it('rejects malformed URLs', () => {
    const r = validateLoopbackTarget('not-a-url', 7333);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('invalid_url');
  });

  it('rejects an out-of-range port', () => {
    const r = validateLoopbackTarget('http://127.0.0.1', 0);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('invalid_port');
    const r2 = validateLoopbackTarget('http://127.0.0.1', 70000);
    expect(r2.ok).toBe(false);
    if (!r2.ok) expect(r2.reason).toBe('invalid_port');
  });

  it('refuses to redirect a public host even via a localhost path', () => {
    // A user-submitted "http://localhost.attacker.example" must NOT pass.
    const r = validateLoopbackTarget('http://localhost.attacker.example', 7333);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe('non_loopback_host');
  });
});
