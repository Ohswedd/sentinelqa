// Phase 23 — chaos helper re-exports.
//
// Importing `@sentinelqa/ts-runtime/chaos` gives a Playwright test the
// full helper surface for the four scenario categories (network /
// session / ux / data).

export {
  chaosNetwork,
  observeNetworkChaos,
  type NetworkChaosOptions,
  type NetworkScenarioId,
  type ChaosRoute,
  type ChaosRoutablePage,
} from './network.js';

export {
  chaosSession,
  observeSessionChaos,
  type SessionChaosOptions,
  type SessionScenarioId,
  type ChaosFetchPage,
  type ChaosFetchRoute,
} from './session.js';

export {
  chaosBackForward,
  chaosDoubleClickRace,
  chaosDuplicateSubmit,
  chaosRefreshMidFlow,
  observeUxChaos,
  type ClickableLocator,
  type NavigablePage,
  type UxScenarioId,
} from './ux.js';

export {
  chaosCorruptStorage,
  chaosEmptyDataset,
  chaosLargeDataset,
  observeDataChaos,
  type CorruptStorage,
  type DataScenarioId,
  type EmptyDatasetOptions,
  type LargeDatasetOptions,
} from './data.js';

export {
  CHAOS_EVENT_SCHEMA_VERSION,
  serialiseChaosEvent,
  type ChaosCategory,
  type ChaosEvent,
  type ChaosObservation,
} from './types.js';
