import { describe, expect, it } from 'vitest';

import {
  chaosCorruptStorage,
  chaosEmptyDataset,
  chaosLargeDataset,
  observeDataChaos,
  type CorruptStorage,
} from '../data.js';
import type { ChaosRoute, ChaosRoutablePage } from '../network.js';

class StubPage implements ChaosRoutablePage {
  public handler?: (route: ChaosRoute) => Promise<void> | void;
  async route(
    _pattern: string | RegExp,
    handler: (route: ChaosRoute) => Promise<void> | void,
  ): Promise<void> {
    this.handler = handler;
  }
}

class StubRoute implements ChaosRoute {
  public fulfilled?: { status: number; body?: string; contentType?: string };
  async fulfill(opts: { status: number; body?: string; contentType?: string }): Promise<void> {
    this.fulfilled = opts;
  }
  async abort(): Promise<void> {
    return undefined;
  }
  async continue(): Promise<void> {
    return undefined;
  }
  request() {
    return { url: () => '/api/items', method: () => 'GET' };
  }
}

class StubStorage implements CorruptStorage {
  public store: Record<string, string> = {};
  setItem(key: string, value: string): void {
    this.store[key] = value;
  }
}

describe('chaosEmptyDataset', () => {
  it('fulfills with an empty array', async () => {
    const page = new StubPage();
    await chaosEmptyDataset(page, { listPattern: /\/api\/items/ });
    const route = new StubRoute();
    await page.handler!(route);
    expect(route.fulfilled?.status).toBe(200);
    expect(route.fulfilled?.body).toBe('[]');
  });

  it('respects a caller-supplied response body', async () => {
    const page = new StubPage();
    await chaosEmptyDataset(page, {
      listPattern: /\/api\/items/,
      responseBody: '{"items":[]}',
    });
    const route = new StubRoute();
    await page.handler!(route);
    expect(route.fulfilled?.body).toBe('{"items":[]}');
  });
});

describe('chaosLargeDataset', () => {
  it('clamps below-floor item counts', async () => {
    const page = new StubPage();
    const count = await chaosLargeDataset(page, {
      listPattern: /\/api\/items/,
      itemCount: 1, // below floor of 100
    });
    expect(count).toBe(100);
  });

  it('clamps above-ceiling item counts', async () => {
    const page = new StubPage();
    const count = await chaosLargeDataset(page, {
      listPattern: /\/api\/items/,
      itemCount: 999_999,
    });
    expect(count).toBe(10_000);
  });

  it('uses caller-supplied item factory', async () => {
    const page = new StubPage();
    const count = await chaosLargeDataset(page, {
      listPattern: /\/api\/items/,
      itemCount: 100,
      itemFactory: (i) => ({ k: i }),
    });
    expect(count).toBe(100);
    const route = new StubRoute();
    await page.handler!(route);
    const body = JSON.parse(route.fulfilled!.body!);
    expect(body[0]).toEqual({ k: 0 });
    expect(body).toHaveLength(100);
  });
});

describe('chaosCorruptStorage', () => {
  it('overwrites every key with broken JSON', () => {
    const storage = new StubStorage();
    const corrupted = chaosCorruptStorage(storage, ['session', 'cart']);
    expect(corrupted).toBe(2);
    expect(storage.store['session']).toContain('chaos');
    // Verifying the payload is not valid JSON keeps the "garbage"
    // contract honest — JSON.parse on it throws.
    expect(() => JSON.parse(storage.store['session']!)).toThrow();
  });
});

describe('observeDataChaos', () => {
  it('tags with the data category', () => {
    const event = observeDataChaos({
      scenario: 'data.empty_dataset',
      flow: 'inventory',
      observation: 'missing_empty_state',
    });
    expect(event.category).toBe('data');
  });
});
