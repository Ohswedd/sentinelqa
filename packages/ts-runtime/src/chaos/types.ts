// Phase 23 — wire types shared with `modules/chaos/models.py`.
//
// The TS-side `ChaosEvent` is the JSONL payload the helpers in this
// directory append to `<run-dir>/chaos/events.jsonl`. The Python module
// parses that file via `modules.chaos.ingestion`, so any change here
// must be mirrored on the Python side (and recorded in ADR-0028).

export type ChaosCategory = 'network' | 'session' | 'ux' | 'data';

export type ChaosObservation =
  | 'uncaught_error'
  | 'no_error_state'
  | 'no_redirect_on_expired_session'
  | 'no_graceful_permission_denial'
  | 'duplicate_submit_accepted'
  | 'lost_form_state_on_navigation'
  | 'white_screen_on_refresh'
  | 'missing_empty_state'
  | 'dom_explosion_on_large_dataset'
  | 'crash_on_corrupted_storage'
  | 'handled_gracefully';

export interface ChaosEvent {
  readonly scenario_id: string;
  readonly category: ChaosCategory;
  readonly flow: string;
  readonly observation: ChaosObservation;
  readonly route?: string;
  readonly detail?: string;
  readonly evidence?: Record<string, string>;
}

export const CHAOS_EVENT_SCHEMA_VERSION = '1';

/**
 * Serialise a ChaosEvent into the JSONL line format the Python ingestion
 * layer expects (one JSON object per line, no trailing whitespace).
 */
export function serialiseChaosEvent(event: ChaosEvent): string {
  return JSON.stringify(event);
}
