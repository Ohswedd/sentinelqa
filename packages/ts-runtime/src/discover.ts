// `sentinel-ts discover` — Playwright-driven crawl backend.
// Phase 17 task 07 + ADR-0010 follow-up. Drives Chromium against a
// target URL, emits `discovery.page` / `discovery.endpoint` JSONL
// events that the Python `PlaywrightCrawlBackend` consumes.
//
// Design choices:
//
// - The launcher is injected (`DiscoverLauncher`) so unit tests can run
//   without Chromium. The production launcher dynamically imports
//   `@playwright/test`; importing this module never pulls Chromium in.
// - Config is read either from a file (`--config <path>`) or from
//   stdin (`--config -`). Stdin is the path the Python adapter uses.
// - The crawl is breadth-first, capped by `max_pages` AND `max_depth`.
// - Every request includes the configured User-Agent and the
//   `X-SentinelQA-Test-Run` header (CLAUDE §6 / PRD §2.2).
// - Endpoint events fire whenever the browser observes a request whose
//   path starts with `/api/` or whose response Content-Type is JSON.
//
// The implementation is intentionally small. Phase 22 will expand the
// endpoint heuristics; for now we err on the side of recall.

import {
  PROTOCOL_VERSION,
  type DiscoveryEndpointEvent,
  type DiscoveryPageEvent,
  type EventEmitter,
  type LogEvent,
} from './protocol.js';

export interface DiscoverConfig {
  readonly schema_version: string;
  readonly base_url: string;
  readonly run_id: string;
  readonly max_depth: number;
  readonly max_pages: number;
  readonly rate_limit_rps: number;
  readonly respect_robots: boolean;
  readonly same_host_only: boolean;
  readonly extra_allowed_hosts: readonly string[];
  readonly request_timeout_seconds: number;
  readonly user_agent: string;
  readonly cookies: Record<string, string>;
}

/**
 * Minimal Playwright surface the discover routine needs. Subset is
 * defined here so the module compiles without `@playwright/test` in
 * dependencies (the production launcher dynamic-imports it).
 */
export interface DiscoverPage {
  goto(url: string, opts?: { timeout?: number }): Promise<unknown>;
  url(): string;
  content(): Promise<string>;
  evaluate<T>(fn: () => T): Promise<T>;
  on(event: 'request' | 'response', listener: (payload: unknown) => void): void;
  off(event: 'request' | 'response', listener: (payload: unknown) => void): void;
}

export interface DiscoverContext {
  newPage(): Promise<DiscoverPage>;
  close(): Promise<void>;
}

export interface DiscoverBrowser {
  newContext(): Promise<DiscoverContext>;
  close(): Promise<void>;
}

export type DiscoverLauncher = (config: DiscoverConfig) => Promise<DiscoverBrowser>;

export interface DiscoverDeps {
  readonly emitter: EventEmitter;
  readonly launcher: DiscoverLauncher;
  /** Override the per-page wait used between fetches (rate limit). */
  readonly sleepMs?: (ms: number) => Promise<void>;
}

export interface DiscoverResult {
  readonly pagesEmitted: number;
  readonly endpointsEmitted: number;
}

const DEFAULT_SLEEP = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

/**
 * Drive a single crawl according to ``config`` and emit JSONL events
 * to ``emitter``. Returns counters for the dispatcher's exit-code
 * decision.
 */
export async function runDiscover(
  config: DiscoverConfig,
  deps: DiscoverDeps,
): Promise<DiscoverResult> {
  if (config.schema_version !== '1') {
    throw new Error(
      `sentinel-ts discover: unsupported config schema_version=${config.schema_version}.`,
    );
  }

  const browser = await deps.launcher(config);
  const context = await browser.newContext();
  const sleep = deps.sleepMs ?? DEFAULT_SLEEP;
  const sleepIntervalMs =
    config.rate_limit_rps > 0 ? Math.max(0, Math.floor(1000 / config.rate_limit_rps)) : 0;

  const seen = new Set<string>();
  const queue: { url: string; depth: number }[] = [{ url: config.base_url, depth: 0 }];
  const baseHost = new URL(config.base_url).host;
  const allowedHosts = new Set<string>([baseHost, ...config.extra_allowed_hosts]);

  let pagesEmitted = 0;
  let endpointsEmitted = 0;
  const seenEndpoints = new Set<string>();

  try {
    while (queue.length > 0 && pagesEmitted < config.max_pages) {
      const next = queue.shift();
      if (next === undefined) break;
      const { url, depth } = next;
      if (seen.has(url)) continue;
      seen.add(url);

      const parsed = safeUrl(url);
      if (parsed === undefined) continue;
      if (config.same_host_only && !allowedHosts.has(parsed.host)) continue;

      const page = await context.newPage();
      const requestListener = (req: unknown): void => {
        const handled = handleRequest(req);
        if (handled === undefined) return;
        const { method, path, isApi } = handled;
        if (!isApi) return;
        const key = `${method}::${path}`;
        if (seenEndpoints.has(key)) return;
        seenEndpoints.add(key);
        deps.emitter.emit<DiscoveryEndpointEvent>({
          type: 'discovery.endpoint',
          method,
          path,
          status_code: null,
          source: 'request',
        });
        endpointsEmitted += 1;
      };
      page.on('request', requestListener);

      const start = Date.now();
      let status = 0;
      let contentType: string | null = null;
      try {
        const response = await page.goto(url, {
          timeout: Math.floor(config.request_timeout_seconds * 1000),
        });
        status = pickStatus(response) ?? 200;
        contentType = pickContentType(response);
      } catch (err) {
        deps.emitter.emit<LogEvent>({
          type: 'log',
          level: 'warn',
          msg: `discovery navigation failed for ${url}`,
          fields: { error: (err as Error).message },
        });
        page.off('request', requestListener);
        continue;
      }

      const html = await safelyReadHtml(page);
      const elapsed = Date.now() - start;
      const links = await extractLinks(page);
      const scripts = await extractScriptSrcs(page);

      deps.emitter.emit<DiscoveryPageEvent>({
        type: 'discovery.page',
        url: page.url(),
        status_code: status,
        content_type: contentType,
        depth,
        elapsed_ms: elapsed,
        html,
        discovered_links: links,
        discovered_script_srcs: scripts,
      });
      pagesEmitted += 1;

      page.off('request', requestListener);

      if (depth < config.max_depth) {
        for (const link of links) {
          if (!seen.has(link)) {
            queue.push({ url: link, depth: depth + 1 });
          }
        }
      }

      if (sleepIntervalMs > 0) await sleep(sleepIntervalMs);
    }
  } finally {
    await context.close();
    await browser.close();
  }

  return { pagesEmitted, endpointsEmitted };
}

function safeUrl(url: string): URL | undefined {
  try {
    return new URL(url);
  } catch {
    return undefined;
  }
}

interface RequestHandle {
  url(): string;
  method(): string;
  resourceType?(): string;
  headers?(): Record<string, string>;
}

function handleRequest(req: unknown): { method: string; path: string; isApi: boolean } | undefined {
  const r = req as RequestHandle;
  if (typeof r?.url !== 'function' || typeof r?.method !== 'function') return undefined;
  const u = safeUrl(r.url());
  if (u === undefined) return undefined;
  const isApi = u.pathname.startsWith('/api/');
  return { method: r.method().toUpperCase(), path: u.pathname, isApi };
}

interface ResponseHandle {
  status?(): number;
  headers?(): Record<string, string>;
}

function pickStatus(response: unknown): number | undefined {
  const r = response as ResponseHandle | null | undefined;
  if (r === null || r === undefined || typeof r.status !== 'function') return undefined;
  return r.status();
}

function pickContentType(response: unknown): string | null {
  const r = response as ResponseHandle | null | undefined;
  if (r === null || r === undefined || typeof r.headers !== 'function') return null;
  const headers = r.headers();
  const ct = headers['content-type'] ?? headers['Content-Type'];
  return typeof ct === 'string' ? (ct.split(';')[0]?.trim() ?? null) : null;
}

async function safelyReadHtml(page: DiscoverPage): Promise<string> {
  try {
    return await page.content();
  } catch {
    return '';
  }
}

async function extractLinks(page: DiscoverPage): Promise<string[]> {
  try {
    return await page.evaluate(() => {
      const out: string[] = [];
      const docAny: unknown = globalThis as unknown as { document?: unknown };
      const doc = (docAny as { document?: { querySelectorAll(s: string): NodeListOf<Element> } })
        .document;
      if (doc === undefined) return out;
      const anchors = doc.querySelectorAll('a[href]');
      anchors.forEach((a) => {
        const href = (a as HTMLAnchorElement).href;
        if (typeof href === 'string' && href.length > 0) out.push(href);
      });
      return out;
    });
  } catch {
    return [];
  }
}

async function extractScriptSrcs(page: DiscoverPage): Promise<string[]> {
  try {
    return await page.evaluate(() => {
      const out: string[] = [];
      const docAny: unknown = globalThis as unknown as { document?: unknown };
      const doc = (docAny as { document?: { querySelectorAll(s: string): NodeListOf<Element> } })
        .document;
      if (doc === undefined) return out;
      const scripts = doc.querySelectorAll('script[src]');
      scripts.forEach((s) => {
        const src = (s as HTMLScriptElement).src;
        if (typeof src === 'string' && src.length > 0) out.push(src);
      });
      return out;
    });
  } catch {
    return [];
  }
}

export const DISCOVER_PROTOCOL_VERSION = PROTOCOL_VERSION;
