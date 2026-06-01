// /12.04 — network instrumentation: API timings + JS bundle size.
// We attach a Playwright `response` handler to the page; every response
// is classified as either an API call (matched by content-type / path
// heuristic) or a JS file (filtered by content-type). API durations are
// reported per request; JS bundle sizes (both wire bytes and decoded
// bytes) accumulate into a single summary.
// the engineering guidelines: the timings here are lab synthetic. The Python side carries
// the synthetic label through to every finding.

import type { ApiSample, BundleSummary } from './types.js';

export interface NetworkResponseObservation {
  readonly method: string;
  readonly url: string;
  readonly status: number;
  readonly durationMs: number;
  readonly contentType: string;
  readonly transferSizeBytes: number;
  readonly decodedSizeBytes: number;
}

export interface NetworkCollectorState {
  readonly apiSamples: ApiSample[];
  readonly bundleSamples: { transferBytes: number; decodedBytes: number; count: number };
}

export interface NetworkObserverPage {
  on(event: 'response', handler: (response: NetworkResponseHandle) => void | Promise<void>): void;
  off(event: 'response', handler: (response: NetworkResponseHandle) => void | Promise<void>): void;
}

export interface NetworkResponseHandle {
  url(): string;
  status(): number;
  request(): { method(): string; timing(): { responseEnd?: number; requestStart?: number } | null };
  headerValue(name: string): Promise<string | null>;
  body(): Promise<Buffer | Uint8Array | null>;
}

const JS_CONTENT_TYPES = ['application/javascript', 'text/javascript', 'application/x-javascript'];

export function isJavaScriptResponse(contentType: string, url: string): boolean {
  const ct = contentType.toLowerCase();
  for (const candidate of JS_CONTENT_TYPES) {
    if (ct.includes(candidate)) return true;
  }
  // Some CDNs serve js with application/octet-stream. Fall back to the URL.
  const u = url.toLowerCase().split('?')[0]?.split('#')[0] ?? '';
  return u.endsWith('.js') || u.endsWith('.mjs');
}

export function isApiResponse(contentType: string, url: string): boolean {
  const ct = contentType.toLowerCase();
  if (ct.includes('application/json')) return true;
  if (ct.includes('application/graphql')) return true;
  // Allowlist heuristic — paths with `/api/` are nearly always APIs in
  // practice. Anything else is treated as a static asset.
  try {
    const u = new URL(url);
    return u.pathname.includes('/api/') || u.pathname.startsWith('/graphql');
  } catch {
    return false;
  }
}

function extractPath(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.pathname + (parsed.search || '');
  } catch {
    return url;
  }
}

export function ingestObservation(
  obs: NetworkResponseObservation,
  state: NetworkCollectorState,
): void {
  if (isApiResponse(obs.contentType, obs.url)) {
    state.apiSamples.push({
      endpoint: extractPath(obs.url),
      method: obs.method.toUpperCase(),
      duration_ms: Math.max(0, obs.durationMs),
      status: obs.status,
    });
    return;
  }
  if (isJavaScriptResponse(obs.contentType, obs.url)) {
    state.bundleSamples.transferBytes += Math.max(0, obs.transferSizeBytes);
    state.bundleSamples.decodedBytes += Math.max(0, obs.decodedSizeBytes);
    state.bundleSamples.count += 1;
  }
}

export function summariseBundle(state: NetworkCollectorState): BundleSummary {
  return {
    transfer_total_kb: Math.round((state.bundleSamples.transferBytes / 1024) * 100) / 100,
    decoded_total_kb: Math.round((state.bundleSamples.decodedBytes / 1024) * 100) / 100,
    file_count: state.bundleSamples.count,
  };
}

export function newCollectorState(): NetworkCollectorState {
  return {
    apiSamples: [],
    bundleSamples: { transferBytes: 0, decodedBytes: 0, count: 0 },
  };
}
