// Phase 23.02 — Network chaos helpers.
//
// `chaosNetwork(page, options)` installs a Playwright `route()` handler
// that injects one of four bounded scenarios:
//
//   - `network.slow_3g`    — delay every response by RTT + payload/ms.
//   - `network.offline`    — abort every outgoing request.
//   - `network.api_500`    — match `apiPattern` and return HTTP 500.
//   - `network.api_timeout`— match `apiPattern` and stall, then abort
//                            after `timeoutAbortMs` ms.
//
// CLAUDE §6 / §29: the scenarios above are *bounded* — `slow_3g`
// cannot drop below 100 Kbps, `api_timeout` cannot exceed 120 s, and
// neither `offline` nor `api_500` exposes any "stealth" knob.
//
// The helper returns an `observeNetworkChaos()` callback the test caller
// invokes with the observed UI state (e.g. `'no_error_state'` if the
// page never rendered an error banner after a forced 500). The
// callback returns a typed `ChaosEvent` the caller appends to the
// chaos JSONL log; the helper never writes anywhere on its own.

import type { ChaosEvent, ChaosObservation } from './types.js';

export type NetworkScenarioId =
  | 'network.slow_3g'
  | 'network.offline'
  | 'network.api_500'
  | 'network.api_timeout';

export interface NetworkChaosOptions {
  readonly scenario: NetworkScenarioId;
  readonly flow: string;
  /** Pattern to match for `api_500` / `api_timeout`. Ignored for offline/slow. */
  readonly apiPattern?: string | RegExp;
  /** slow_3g throttle (default 400, floor 100, ceiling 10_000). */
  readonly slow3gKbps?: number;
  /** slow_3g extra RTT in ms (default 400, floor 50, ceiling 5_000). */
  readonly slow3gRttMs?: number;
  /** api_timeout abort horizon in ms (default 30_000, floor 1_000, ceiling 120_000). */
  readonly timeoutAbortMs?: number;
}

export interface ChaosRoute {
  fulfill(opts: { status: number; body?: string; contentType?: string }): Promise<void>;
  abort(reason?: string): Promise<void>;
  continue(opts?: { delay?: number }): Promise<void>;
  request(): { url(): string; method(): string };
}

export interface ChaosRoutablePage {
  route(
    pattern: string | RegExp,
    handler: (route: ChaosRoute) => Promise<void> | void,
  ): Promise<void>;
}

const DEFAULT_SLOW_3G_KBPS = 400;
const DEFAULT_SLOW_3G_RTT_MS = 400;
const DEFAULT_TIMEOUT_ABORT_MS = 30_000;

function clamp(value: number | undefined, fallback: number, min: number, max: number): number {
  const v = typeof value === 'number' && Number.isFinite(value) ? value : fallback;
  return Math.min(max, Math.max(min, Math.trunc(v)));
}

/**
 * Install the route handler for the requested scenario. The handler is
 * idempotent w.r.t. the page (each call adds one route) and never
 * touches global state.
 */
export async function chaosNetwork(
  page: ChaosRoutablePage,
  options: NetworkChaosOptions,
): Promise<void> {
  const slowKbps = clamp(options.slow3gKbps, DEFAULT_SLOW_3G_KBPS, 100, 10_000);
  const slowRtt = clamp(options.slow3gRttMs, DEFAULT_SLOW_3G_RTT_MS, 50, 5_000);
  const abortMs = clamp(options.timeoutAbortMs, DEFAULT_TIMEOUT_ABORT_MS, 1_000, 120_000);

  switch (options.scenario) {
    case 'network.offline':
      await page.route(/.*/, async (route) => {
        await route.abort('internetdisconnected');
      });
      return;
    case 'network.slow_3g':
      await page.route(/.*/, async (route) => {
        // Approximate throttling: hold the request, then forward.
        // Production runs lean on Playwright's CDP throttle; the
        // route delay below is a portable fallback used by tests.
        const delay = slowRtt + Math.ceil(8 / slowKbps);
        await new Promise<void>((resolve) => setTimeout(resolve, delay));
        await route.continue();
      });
      return;
    case 'network.api_500': {
      const pattern = options.apiPattern ?? /\/api\//;
      await page.route(pattern, async (route) => {
        await route.fulfill({
          status: 500,
          body: JSON.stringify({ error: 'chaos-injected-500' }),
          contentType: 'application/json',
        });
      });
      return;
    }
    case 'network.api_timeout': {
      const pattern = options.apiPattern ?? /\/api\//;
      await page.route(pattern, async (route) => {
        await new Promise<void>((resolve) => setTimeout(resolve, abortMs));
        await route.abort('timedout');
      });
      return;
    }
    default: {
      // Exhaustiveness guard — never reached.
      const exhaustive: never = options.scenario;
      throw new Error(`chaosNetwork: unknown scenario ${exhaustive as string}`);
    }
  }
}

/**
 * Build a typed ChaosEvent from a UI-side observation. Callers invoke
 * this after their assertions decide whether the app handled the chaos
 * gracefully. `evidence` is a flat string→string map so the JSONL line
 * stays trivially redactable (CLAUDE §33).
 */
export function observeNetworkChaos(args: {
  readonly scenario: NetworkScenarioId;
  readonly flow: string;
  readonly observation: ChaosObservation;
  readonly detail?: string;
  readonly route?: string;
  readonly evidence?: Record<string, string>;
}): ChaosEvent {
  return {
    scenario_id: args.scenario,
    category: 'network',
    flow: args.flow,
    observation: args.observation,
    ...(args.route ? { route: args.route } : {}),
    ...(args.detail ? { detail: args.detail } : {}),
    ...(args.evidence ? { evidence: args.evidence } : {}),
  };
}
