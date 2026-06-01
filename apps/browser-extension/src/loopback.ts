// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 SentinelQA contributors.
//
// Loopback-only URL guard.
//
// The browser extension must never POST a URL anywhere except a local
// SentinelQA MCP server. The safety boundary is enforced here, in a
// pure module testable without the chrome runtime.

export type LoopbackValidationError =
  | 'invalid_url'
  | 'non_http_scheme'
  | 'non_loopback_host'
  | 'invalid_port';

export interface ValidationOk {
  readonly ok: true;
  readonly normalised: string;
}

export interface ValidationFail {
  readonly ok: false;
  readonly reason: LoopbackValidationError;
}

const LOOPBACK_HOSTS = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);

export function validateLoopbackTarget(host: string, port: number): ValidationOk | ValidationFail {
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    return { ok: false, reason: 'invalid_port' };
  }
  let parsed: URL;
  try {
    parsed = new URL(host);
  } catch {
    return { ok: false, reason: 'invalid_url' };
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { ok: false, reason: 'non_http_scheme' };
  }
  // Strip surrounding [] for IPv6 hosts before comparison.
  const hostname = parsed.hostname.replace(/^\[/, '').replace(/\]$/, '');
  if (!LOOPBACK_HOSTS.has(hostname) && !LOOPBACK_HOSTS.has(parsed.host)) {
    return { ok: false, reason: 'non_loopback_host' };
  }
  // Re-build the canonical URL: scheme + hostname + explicit port.
  const url = `${parsed.protocol}//${parsed.host.includes(':') ? parsed.host : `${parsed.hostname}:${port}`}`;
  return { ok: true, normalised: url };
}
