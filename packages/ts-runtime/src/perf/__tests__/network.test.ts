import { describe, expect, it } from 'vitest';

import {
  ingestObservation,
  isApiResponse,
  isJavaScriptResponse,
  newCollectorState,
  summariseBundle,
} from '../network.js';

describe('isJavaScriptResponse', () => {
  it('matches by content-type', () => {
    expect(isJavaScriptResponse('application/javascript; charset=utf-8', 'https://x/app.js')).toBe(
      true,
    );
    expect(isJavaScriptResponse('text/javascript', 'https://x/a.js')).toBe(true);
  });
  it('matches by .js extension when content-type is opaque', () => {
    expect(isJavaScriptResponse('application/octet-stream', 'https://x/a.js')).toBe(true);
    expect(isJavaScriptResponse('application/octet-stream', 'https://x/a.mjs')).toBe(true);
  });
  it('rejects html / json', () => {
    expect(isJavaScriptResponse('text/html', 'https://x/index.html')).toBe(false);
    expect(isJavaScriptResponse('application/json', 'https://x/data')).toBe(false);
  });
});

describe('isApiResponse', () => {
  it('matches application/json', () => {
    expect(isApiResponse('application/json', 'https://x/users')).toBe(true);
  });
  it('matches /api/ path heuristic for html responses', () => {
    expect(isApiResponse('text/html', 'https://x/api/users')).toBe(true);
  });
  it('matches /graphql path', () => {
    expect(isApiResponse('text/html', 'https://x/graphql')).toBe(true);
  });
  it('rejects ordinary html', () => {
    expect(isApiResponse('text/html', 'https://x/index.html')).toBe(false);
  });
});

describe('ingestObservation', () => {
  it('routes JS responses to the bundle bucket', () => {
    const state = newCollectorState();
    ingestObservation(
      {
        method: 'GET',
        url: 'https://x/app.js',
        status: 200,
        durationMs: 30,
        contentType: 'application/javascript',
        transferSizeBytes: 100_000,
        decodedSizeBytes: 200_000,
      },
      state,
    );
    expect(state.bundleSamples.transferBytes).toBe(100_000);
    expect(state.bundleSamples.decodedBytes).toBe(200_000);
    expect(state.bundleSamples.count).toBe(1);
    expect(state.apiSamples).toHaveLength(0);
  });

  it('routes JSON responses to the API bucket', () => {
    const state = newCollectorState();
    ingestObservation(
      {
        method: 'GET',
        url: 'https://x/api/users/42?expand=posts',
        status: 200,
        durationMs: 75,
        contentType: 'application/json',
        transferSizeBytes: 500,
        decodedSizeBytes: 500,
      },
      state,
    );
    expect(state.apiSamples).toHaveLength(1);
    expect(state.apiSamples[0]?.endpoint).toBe('/api/users/42?expand=posts');
    expect(state.apiSamples[0]?.method).toBe('GET');
    expect(state.apiSamples[0]?.duration_ms).toBe(75);
  });

  it('clamps negative bytes to zero', () => {
    const state = newCollectorState();
    ingestObservation(
      {
        method: 'GET',
        url: 'https://x/app.js',
        status: 200,
        durationMs: 30,
        contentType: 'application/javascript',
        transferSizeBytes: -10,
        decodedSizeBytes: -20,
      },
      state,
    );
    expect(state.bundleSamples.transferBytes).toBe(0);
    expect(state.bundleSamples.decodedBytes).toBe(0);
  });
});

describe('summariseBundle', () => {
  it('reports kilobyte totals', () => {
    const state = newCollectorState();
    state.bundleSamples.transferBytes = 102_400; // 100 KB
    state.bundleSamples.decodedBytes = 204_800; // 200 KB
    state.bundleSamples.count = 3;
    const summary = summariseBundle(state);
    expect(summary.transfer_total_kb).toBe(100);
    expect(summary.decoded_total_kb).toBe(200);
    expect(summary.file_count).toBe(3);
  });
});
