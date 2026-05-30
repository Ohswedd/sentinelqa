// Phase 23.04 — UX edge case helpers.
//
// Four scenarios:
//
//   - `ux.duplicate_submit`  — click the supplied locator twice with no
//                              delay; the test asserts the server saw
//                              either one request OR responded with the
//                              same idempotency key both times.
//   - `ux.double_click_race` — variant that fires both clicks inside a
//                              single microtask. Observable as
//                              `duplicate_submit_accepted` if the app
//                              issues two distinct network calls.
//   - `ux.back_forward`      — navigate back/forward through a
//                              multi-step form; the test asserts form
//                              state is preserved.
//   - `ux.refresh_mid_flow`  — reload the current page during a flow;
//                              the test asserts the page restores
//                              without a white screen.

import type { ChaosEvent, ChaosObservation } from './types.js';

export type UxScenarioId =
  | 'ux.duplicate_submit'
  | 'ux.double_click_race'
  | 'ux.back_forward'
  | 'ux.refresh_mid_flow';

export interface ClickableLocator {
  click(opts?: { delay?: number }): Promise<void>;
}

export interface NavigablePage {
  goBack(opts?: { waitUntil?: string }): Promise<unknown>;
  goForward(opts?: { waitUntil?: string }): Promise<unknown>;
  reload(opts?: { waitUntil?: string }): Promise<unknown>;
}

/**
 * Click `locator` twice in rapid succession. Returns the number of
 * clicks issued (always 2) so tests can assert against
 * server-side dedup expectations.
 */
export async function chaosDuplicateSubmit(locator: ClickableLocator): Promise<number> {
  await locator.click();
  await locator.click();
  return 2;
}

/**
 * Trigger a double-click race: both clicks resolve before the first's
 * navigation / network round-trip can complete.
 */
export async function chaosDoubleClickRace(locator: ClickableLocator): Promise<number> {
  await Promise.all([locator.click({ delay: 0 }), locator.click({ delay: 0 })]);
  return 2;
}

/**
 * Drive the browser through `back → forward` on the current history
 * entry. The test caller is responsible for asserting form-state
 * survival.
 */
export async function chaosBackForward(page: NavigablePage): Promise<void> {
  await page.goBack({ waitUntil: 'domcontentloaded' });
  await page.goForward({ waitUntil: 'domcontentloaded' });
}

/**
 * Reload the current page mid-flow. The test caller asserts the route
 * restores without a white screen.
 */
export async function chaosRefreshMidFlow(page: NavigablePage): Promise<void> {
  await page.reload({ waitUntil: 'domcontentloaded' });
}

export function observeUxChaos(args: {
  readonly scenario: UxScenarioId;
  readonly flow: string;
  readonly observation: ChaosObservation;
  readonly detail?: string;
  readonly route?: string;
  readonly evidence?: Record<string, string>;
}): ChaosEvent {
  return {
    scenario_id: args.scenario,
    category: 'ux',
    flow: args.flow,
    observation: args.observation,
    ...(args.route ? { route: args.route } : {}),
    ...(args.detail ? { detail: args.detail } : {}),
    ...(args.evidence ? { evidence: args.evidence } : {}),
  };
}
