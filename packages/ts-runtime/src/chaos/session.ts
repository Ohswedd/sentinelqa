// Phase 23.03 — Session chaos helpers.
//
// Two scenarios live here:
//
//   - `session.expired_token`       — every outgoing request gets an
//                                     `Authorization: Bearer expired.token.here`
//                                     header rewrite. The page's own
//                                     fetch logic must decide whether
//                                     to redirect / surface a reauth
//                                     prompt.
//   - `session.missing_permissions` — when an operator provides a
//                                     sandbox JWT, the helper strips
//                                     declared permission claims and
//                                     re-signs *with the same sandbox
//                                     key*. There is no real
//                                     re-signing path here: production
//                                     JWT secrets never flow through
//                                     this helper.
//
// CLAUDE §6 / §33: the helper rewrites *outgoing* headers only. It
// never reads or persists the real user's token; redact rules in
// `redact.ts` already cover Authorization headers in logs.

import type { ChaosEvent, ChaosObservation } from './types.js';

export type SessionScenarioId = 'session.expired_token' | 'session.missing_permissions';

export interface SessionChaosOptions {
  readonly scenario: SessionScenarioId;
  readonly flow: string;
  /** Stripped-down sandbox JWT for `session.missing_permissions`. Required for that scenario. */
  readonly sandboxToken?: string;
}

export interface ChaosFetchRoute {
  fulfill(opts: { status: number; body?: string; contentType?: string }): Promise<void>;
  continue(opts?: { headers?: Record<string, string> }): Promise<void>;
  request(): { url(): string; method(): string; headers(): Record<string, string> };
}

export interface ChaosFetchPage {
  route(
    pattern: string | RegExp,
    handler: (route: ChaosFetchRoute) => Promise<void> | void,
  ): Promise<void>;
}

const EXPIRED_SENTINEL = 'expired.token.here';

/**
 * Install the header-rewrite handler for the requested session scenario.
 *
 * The helper deliberately *never* mints a fresh JWT; for
 * `session.missing_permissions` it forwards the operator-supplied
 * sandbox token (which the test fixture is expected to have prepared
 * with the wrong / missing claims).
 */
export async function chaosSession(
  page: ChaosFetchPage,
  options: SessionChaosOptions,
): Promise<void> {
  if (options.scenario === 'session.missing_permissions' && !options.sandboxToken) {
    throw new Error(
      'chaosSession: session.missing_permissions requires a sandboxToken with the stripped claims set.',
    );
  }

  await page.route(/.*/, async (route) => {
    const headers = { ...route.request().headers() };
    if (options.scenario === 'session.expired_token') {
      headers['authorization'] = `Bearer ${EXPIRED_SENTINEL}`;
    } else if (options.scenario === 'session.missing_permissions') {
      headers['authorization'] = `Bearer ${options.sandboxToken}`;
    }
    await route.continue({ headers });
  });
}

export function observeSessionChaos(args: {
  readonly scenario: SessionScenarioId;
  readonly flow: string;
  readonly observation: ChaosObservation;
  readonly detail?: string;
  readonly route?: string;
  readonly evidence?: Record<string, string>;
}): ChaosEvent {
  return {
    scenario_id: args.scenario,
    category: 'session',
    flow: args.flow,
    observation: args.observation,
    ...(args.route ? { route: args.route } : {}),
    ...(args.detail ? { detail: args.detail } : {}),
    ...(args.evidence ? { evidence: args.evidence } : {}),
  };
}
