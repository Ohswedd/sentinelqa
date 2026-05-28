import { describe, expect, it } from 'vitest';

import { handleResponseEvent } from '../audit.js';
import { newCollectorState, type NetworkResponseHandle } from '../network.js';

function makeResponse(opts: {
  method?: string;
  url: string;
  status?: number;
  contentType?: string;
  contentLength?: string;
  requestStart?: number;
  responseEnd?: number;
  body?: Buffer | null;
  bodyThrows?: boolean;
}): NetworkResponseHandle {
  return {
    url: () => opts.url,
    status: () => opts.status ?? 200,
    request: () => ({
      method: () => opts.method ?? 'GET',
      timing: () => ({
        requestStart: opts.requestStart ?? 0,
        responseEnd: opts.responseEnd ?? 100,
      }),
    }),
    headerValue: async (name: string) => {
      if (name === 'content-type') return opts.contentType ?? '';
      if (name === 'content-length') return opts.contentLength ?? null;
      return null;
    },
    body: async () => {
      if (opts.bodyThrows) throw new Error('cross-origin');
      return opts.body ?? null;
    },
  } as NetworkResponseHandle;
}

describe('handleResponseEvent', () => {
  it('records a JS bundle response with transfer + decoded sizes', async () => {
    const state = newCollectorState();
    const obs = await handleResponseEvent(
      makeResponse({
        url: 'https://x/app.js',
        contentType: 'application/javascript',
        contentLength: '50000',
        body: Buffer.alloc(120_000),
      }),
      state,
    );
    expect(obs).not.toBeNull();
    expect(state.bundleSamples.transferBytes).toBe(50_000);
    expect(state.bundleSamples.decodedBytes).toBe(120_000);
    expect(state.bundleSamples.count).toBe(1);
  });

  it('records an API response with duration from timing()', async () => {
    const state = newCollectorState();
    await handleResponseEvent(
      makeResponse({
        method: 'POST',
        url: 'https://x/api/users',
        contentType: 'application/json',
        requestStart: 100,
        responseEnd: 250,
      }),
      state,
    );
    expect(state.apiSamples).toHaveLength(1);
    expect(state.apiSamples[0]?.duration_ms).toBe(150);
    expect(state.apiSamples[0]?.method).toBe('POST');
  });

  it('uses transferBytes when body() throws (cross-origin path)', async () => {
    const state = newCollectorState();
    await handleResponseEvent(
      makeResponse({
        url: 'https://cdn/lib.js',
        contentType: 'application/javascript',
        contentLength: '7000',
        bodyThrows: true,
      }),
      state,
    );
    expect(state.bundleSamples.transferBytes).toBe(7000);
    expect(state.bundleSamples.decodedBytes).toBe(7000);
  });

  it('returns null when the response object throws', async () => {
    const state = newCollectorState();
    const broken = {
      url: () => 'https://x/a',
      status: () => 200,
      request: () => {
        throw new Error('broken');
      },
      headerValue: async () => null,
      body: async () => null,
    } as unknown as NetworkResponseHandle;
    const obs = await handleResponseEvent(broken, state);
    expect(obs).toBeNull();
  });

  it('treats missing content-length as zero transfer bytes', async () => {
    const state = newCollectorState();
    await handleResponseEvent(
      makeResponse({
        url: 'https://x/inline.js',
        contentType: 'application/javascript',
        body: Buffer.alloc(0),
      }),
      state,
    );
    expect(state.bundleSamples.transferBytes).toBe(0);
  });
});
