import { describe, expect, it } from 'vitest';

import * as chaos from '../index.js';
import { CHAOS_EVENT_SCHEMA_VERSION, serialiseChaosEvent } from '../types.js';

describe('chaos package re-exports', () => {
  it('exposes every public helper', () => {
    const expected = [
      'chaosNetwork',
      'observeNetworkChaos',
      'chaosSession',
      'observeSessionChaos',
      'chaosBackForward',
      'chaosDoubleClickRace',
      'chaosDuplicateSubmit',
      'chaosRefreshMidFlow',
      'observeUxChaos',
      'chaosCorruptStorage',
      'chaosEmptyDataset',
      'chaosLargeDataset',
      'observeDataChaos',
      'CHAOS_EVENT_SCHEMA_VERSION',
      'serialiseChaosEvent',
    ];
    for (const name of expected) {
      expect((chaos as Record<string, unknown>)[name]).toBeTruthy();
    }
  });
});

describe('serialiseChaosEvent', () => {
  it('produces a one-line JSON payload', () => {
    const line = serialiseChaosEvent({
      scenario_id: 'network.api_500',
      category: 'network',
      flow: 'checkout',
      observation: 'no_error_state',
    });
    expect(line).not.toContain('\n');
    expect(JSON.parse(line)).toMatchObject({ scenario_id: 'network.api_500' });
  });

  it('exposes a stable schema version', () => {
    expect(CHAOS_EVENT_SCHEMA_VERSION).toBe('1');
  });
});
