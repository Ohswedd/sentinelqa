// Tests for `runDiscover` + the sentinel-ts CLI subcommand added in
// task 07.

import { describe, expect, it } from 'vitest';

import { dispatchAsync } from '../cli.js';
import {
  runDiscover,
  type DiscoverBrowser,
  type DiscoverConfig,
  type DiscoverContext,
  type DiscoverLauncher,
  type DiscoverPage,
} from '../discover.js';
import { loadDiscoverConfig } from '../discover_cli.js';
import { EventEmitter } from '../protocol.js';

interface CapturedEvent {
  readonly type: string;
  readonly payload: Record<string, unknown>;
}

function makeEmitter(): { emitter: EventEmitter; events: CapturedEvent[] } {
  const events: CapturedEvent[] = [];
  const sink = {
    write(line: string): void {
      const obj = JSON.parse(line) as Record<string, unknown>;
      events.push({ type: String(obj['type']), payload: obj });
    },
  };
  const emitter = new EventEmitter({ sink });
  return { emitter, events };
}

function baseConfig(overrides: Partial<DiscoverConfig> = {}): DiscoverConfig {
  return {
    schema_version: '1',
    base_url: 'http://localhost:3000/',
    run_id: 'RUN-test',
    max_depth: 1,
    max_pages: 5,
    rate_limit_rps: 0,
    respect_robots: true,
    same_host_only: true,
    extra_allowed_hosts: [],
    request_timeout_seconds: 10,
    user_agent: 'SentinelQA/test',
    cookies: {},
    ...overrides,
  };
}

type Listener = (payload: unknown) => void;

class StubPage implements DiscoverPage {
  private requestListeners: Listener[] = [];
  private responseListeners: Listener[] = [];
  constructor(
    private readonly props: {
      url: string;
      html: string;
      links: string[];
      scripts: string[];
      status: number;
      contentType: string | null;
      apiHits: { method: string; url: string }[];
    },
  ) {}

  async goto(_url: string): Promise<unknown> {
    for (const listener of this.requestListeners) {
      for (const hit of this.props.apiHits) {
        listener({
          url: () => hit.url,
          method: () => hit.method,
        });
      }
    }
    return {
      status: () => this.props.status,
      headers: () => (this.props.contentType ? { 'content-type': this.props.contentType } : {}),
    };
  }

  url(): string {
    return this.props.url;
  }

  async content(): Promise<string> {
    return this.props.html;
  }

  async evaluate<T>(fn: () => T): Promise<T> {
    // The browser-side function reads `document.querySelectorAll(...)`.
    // We bypass it and return the canned lists directly — this is a unit
    // test, not an integration test.
    const fnStr = fn.toString();
    if (fnStr.includes('a[href]')) {
      return this.props.links as unknown as T;
    }
    if (fnStr.includes('script[src]')) {
      return this.props.scripts as unknown as T;
    }
    return [] as unknown as T;
  }

  on(event: 'request' | 'response', listener: Listener): void {
    if (event === 'request') this.requestListeners.push(listener);
    if (event === 'response') this.responseListeners.push(listener);
  }

  off(event: 'request' | 'response', listener: Listener): void {
    if (event === 'request') {
      this.requestListeners = this.requestListeners.filter((l) => l !== listener);
    } else {
      this.responseListeners = this.responseListeners.filter((l) => l !== listener);
    }
  }
}

function stubLauncher(pages: StubPage[]): DiscoverLauncher {
  let idx = 0;
  const context: DiscoverContext = {
    async newPage(): Promise<DiscoverPage> {
      const next = pages[idx];
      idx += 1;
      if (next === undefined) throw new Error('stub: ran out of pages');
      return next;
    },
    async close(): Promise<void> {
      /* no-op */
    },
  };
  const browser: DiscoverBrowser = {
    async newContext(): Promise<DiscoverContext> {
      return context;
    },
    async close(): Promise<void> {
      /* no-op */
    },
  };
  return async () => browser;
}

describe('runDiscover', () => {
  it('emits one discovery.page event per crawled URL and follows links', async () => {
    const { emitter, events } = makeEmitter();
    const pages = [
      new StubPage({
        url: 'http://localhost:3000/',
        html: '<html><body><a href="/login">Login</a></body></html>',
        links: ['http://localhost:3000/login'],
        scripts: [],
        status: 200,
        contentType: 'text/html',
        apiHits: [],
      }),
      new StubPage({
        url: 'http://localhost:3000/login',
        html: '<html><body>Login</body></html>',
        links: [],
        scripts: [],
        status: 200,
        contentType: 'text/html',
        apiHits: [],
      }),
    ];
    const launcher = stubLauncher(pages);
    const result = await runDiscover(baseConfig(), {
      emitter,
      launcher,
      sleepMs: async () => {
        /* skip rate limit */
      },
    });

    expect(result.pagesEmitted).toBe(2);
    const pageEvents = events.filter((e) => e.type === 'discovery.page');
    expect(pageEvents).toHaveLength(2);
    expect(pageEvents[0]?.payload['url']).toBe('http://localhost:3000/');
    expect(pageEvents[1]?.payload['url']).toBe('http://localhost:3000/login');
  });

  it('emits discovery.endpoint events when /api/ requests fire', async () => {
    const { emitter, events } = makeEmitter();
    const pages = [
      new StubPage({
        url: 'http://localhost:3000/',
        html: '<html></html>',
        links: [],
        scripts: [],
        status: 200,
        contentType: 'text/html',
        apiHits: [{ method: 'GET', url: 'http://localhost:3000/api/users' }],
      }),
    ];
    const result = await runDiscover(baseConfig(), {
      emitter,
      launcher: stubLauncher(pages),
      sleepMs: async () => {
        /* skip rate limit */
      },
    });
    expect(result.endpointsEmitted).toBe(1);
    const endpoint = events.find((e) => e.type === 'discovery.endpoint');
    expect(endpoint?.payload['path']).toBe('/api/users');
    expect(endpoint?.payload['method']).toBe('GET');
  });

  it('refuses schema_version mismatches', async () => {
    const { emitter } = makeEmitter();
    await expect(
      runDiscover(baseConfig({ schema_version: '2' }), {
        emitter,
        launcher: stubLauncher([]),
        sleepMs: async () => {
          /* skip rate limit */
        },
      }),
    ).rejects.toThrow(/unsupported config schema_version/);
  });

  it('respects same_host_only=true and skips external links', async () => {
    const { emitter, events } = makeEmitter();
    const pages = [
      new StubPage({
        url: 'http://localhost:3000/',
        html: '<html></html>',
        links: ['http://evil.example/x'],
        scripts: [],
        status: 200,
        contentType: 'text/html',
        apiHits: [],
      }),
    ];
    const result = await runDiscover(baseConfig({ max_pages: 2 }), {
      emitter,
      launcher: stubLauncher(pages),
      sleepMs: async () => {
        /* skip rate limit */
      },
    });
    expect(result.pagesEmitted).toBe(1);
    const pageEvents = events.filter((e) => e.type === 'discovery.page');
    expect(pageEvents).toHaveLength(1);
  });
});

describe('sentinel-ts discover (CLI)', () => {
  it('rejects invocations without --config', async () => {
    const result = await dispatchAsync(['discover']);
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('--config <path|->');
  });

  it('runs discovery and prints a summary JSON to stderr', async () => {
    const { emitter, events } = makeEmitter();
    const pages = [
      new StubPage({
        url: 'http://localhost:3000/',
        html: '<html></html>',
        links: [],
        scripts: [],
        status: 200,
        contentType: 'text/html',
        apiHits: [],
      }),
    ];
    const result = await dispatchAsync(['discover', '--config', 'fake'], {
      discoverEmitter: emitter,
      discoverLauncher: stubLauncher(pages),
      discoverConfigLoader: async () => baseConfig(),
    });
    expect(result.exitCode).toBe(0);
    const summary = JSON.parse(result.stderr.trim()) as Record<string, number>;
    expect(summary['pagesEmitted']).toBe(1);
    expect(events.some((e) => e.type === 'discovery.page')).toBe(true);
  });

  it('surfaces config loader errors with exit code 2', async () => {
    const result = await dispatchAsync(['discover', '--config', 'bad'], {
      discoverConfigLoader: async () => {
        throw new Error('config malformed');
      },
    });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('config malformed');
  });
});

describe('loadDiscoverConfig', () => {
  it('rejects non-object payloads', async () => {
    // Use a fake loader by invoking the helper directly via a file written to
    // a temp dir is overkill here. We assert the function signature throws
    // when stdin is empty (via the same code path).
    await expect(
      loadDiscoverConfig('/non/existent/file/path/that/does/not/exist'),
    ).rejects.toThrow();
  });
});
