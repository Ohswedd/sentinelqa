import { describe, expect, it } from 'vitest';

import {
  chaosBackForward,
  chaosDoubleClickRace,
  chaosDuplicateSubmit,
  chaosRefreshMidFlow,
  observeUxChaos,
  type ClickableLocator,
  type NavigablePage,
} from '../ux.js';

class StubLocator implements ClickableLocator {
  public clicks = 0;
  async click(_opts?: { delay?: number }): Promise<void> {
    this.clicks += 1;
  }
}

class StubPage implements NavigablePage {
  public order: string[] = [];
  async goBack(): Promise<undefined> {
    this.order.push('back');
    return undefined;
  }
  async goForward(): Promise<undefined> {
    this.order.push('forward');
    return undefined;
  }
  async reload(): Promise<undefined> {
    this.order.push('reload');
    return undefined;
  }
}

describe('UX chaos helpers', () => {
  it('chaosDuplicateSubmit clicks twice', async () => {
    const locator = new StubLocator();
    const clicks = await chaosDuplicateSubmit(locator);
    expect(clicks).toBe(2);
    expect(locator.clicks).toBe(2);
  });

  it('chaosDoubleClickRace fires both clicks concurrently', async () => {
    const locator = new StubLocator();
    const clicks = await chaosDoubleClickRace(locator);
    expect(clicks).toBe(2);
    expect(locator.clicks).toBe(2);
  });

  it('chaosBackForward navigates back then forward', async () => {
    const page = new StubPage();
    await chaosBackForward(page);
    expect(page.order).toEqual(['back', 'forward']);
  });

  it('chaosRefreshMidFlow reloads the page', async () => {
    const page = new StubPage();
    await chaosRefreshMidFlow(page);
    expect(page.order).toEqual(['reload']);
  });
});

describe('observeUxChaos', () => {
  it('tags event with the ux category', () => {
    const event = observeUxChaos({
      scenario: 'ux.duplicate_submit',
      flow: 'checkout',
      observation: 'duplicate_submit_accepted',
    });
    expect(event.category).toBe('ux');
    expect(event.observation).toBe('duplicate_submit_accepted');
  });
});
