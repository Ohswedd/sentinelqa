import { describe, expect, it } from 'vitest';

import {
  chaosSession,
  observeSessionChaos,
  type ChaosFetchPage,
  type ChaosFetchRoute,
} from '../session.js';

class StubFetchPage implements ChaosFetchPage {
  public capturedHeaders?: Record<string, string>;
  public registered = false;

  async route(
    pattern: string | RegExp,
    handler: (route: ChaosFetchRoute) => Promise<void> | void,
  ): Promise<void> {
    void pattern;
    this.registered = true;
    const route: ChaosFetchRoute = {
      fulfill: async () => undefined,
      continue: async (opts) => {
        if (opts?.headers) {
          this.capturedHeaders = opts.headers;
        }
      },
      request: () => ({
        url: () => 'http://stub/api/foo',
        method: () => 'GET',
        headers: () => ({ accept: 'application/json' }),
      }),
    };
    await handler(route);
  }
}

describe('chaosSession', () => {
  it('rewrites Authorization to the expired sentinel', async () => {
    const page = new StubFetchPage();
    await chaosSession(page, { scenario: 'session.expired_token', flow: 'profile' });
    expect(page.capturedHeaders?.['authorization']).toBe('Bearer expired.token.here');
  });

  it('refuses missing_permissions without a sandbox token', async () => {
    const page = new StubFetchPage();
    await expect(
      chaosSession(page, { scenario: 'session.missing_permissions', flow: 'admin' }),
    ).rejects.toThrow(/sandboxToken/);
  });

  it('forwards the supplied sandbox token for missing_permissions', async () => {
    const page = new StubFetchPage();
    await chaosSession(page, {
      scenario: 'session.missing_permissions',
      flow: 'admin',
      sandboxToken: 'sandbox.tok.short',
    });
    expect(page.capturedHeaders?.['authorization']).toBe('Bearer sandbox.tok.short');
  });
});

describe('observeSessionChaos', () => {
  it('produces a category-tagged ChaosEvent', () => {
    const event = observeSessionChaos({
      scenario: 'session.expired_token',
      flow: 'profile',
      observation: 'no_redirect_on_expired_session',
    });
    expect(event.category).toBe('session');
    expect(event.scenario_id).toBe('session.expired_token');
  });
});
