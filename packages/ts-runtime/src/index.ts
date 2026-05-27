// Public API for `@sentinelqa/ts-runtime`. PRD §15, CLAUDE.md §8/§21.
//
// Re-exports here are part of the package contract. Internal helpers
// must stay in their own modules and be reached through the subpath
// exports declared in `package.json` (`./protocol`, `./playwright`,
// `./locators`).
export { PACKAGE_NAME, VERSION } from './version.js';

export {
  PROTOCOL_VERSION,
  EventEmitter,
  MemorySink,
  createEmitter,
  parseEvent,
  ProtocolParseError,
} from './protocol.js';
export type {
  TsEvent,
  EmitterSink,
  EmitterOptions,
  RunStartEvent,
  RunEndEvent,
  TestStartEvent,
  TestEndEvent,
  StepStartEvent,
  StepEndEvent,
  EvidenceEvent,
  EvidenceKind,
  NetworkRequestEvent,
  NetworkResponseEvent,
  ConsoleEvent,
  ConsoleLevel,
  DomSnapshotEvent,
  ModuleEventEvent,
  LogEvent,
  LogLevel,
  ErrorEvent,
  SerializedError,
  RunStatus,
  TestStatus,
} from './protocol.js';

export { redact, redactString, redactHeaders, redactUrl, loadRedactionRules } from './redact.js';
export type { RedactionRules, ValueRuleSpec } from './redact.js';

export { sentinelStep, captureEvidence, redactedNetwork } from './helpers.js';
export type {
  StepContext,
  EvidenceContext,
  CaptureEvidenceOptions,
  EvidenceRef,
  PageLike,
  RoutablePage,
  NetworkInterceptor,
  NetworkRequest,
  NetworkResponse,
} from './helpers.js';
