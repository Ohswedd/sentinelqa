// Public API for `@sentinelqa/ts-runtime`. the documentation, the engineering guidelines
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

export {
  sentinelStep,
  captureEvidence,
  redactedNetwork,
  redactedConsole,
  captureDomSnapshot,
  harConfig,
} from './helpers.js';
export {
  auditLocatorBrittleness,
  bestLocator,
  describeLocator,
  renderStrategy,
} from './locators.js';
export type {
  BestLocatorResult,
  BrittlenessAudit,
  BrittlenessWarning,
  ElementTarget,
  EvaluableLocator,
  LocatorDescriptor,
  LocatorLike,
  LocatorStrategy,
  QueryablePage,
} from './locators.js';
export type {
  AccessibilityPage,
  CaptureEvidenceOptions,
  ConsoleEmitterPage,
  ConsoleMessage,
  DomSnapshotRef,
  EvidenceContext,
  EvidenceRef,
  HarConfig,
  NetworkInterceptor,
  NetworkRequest,
  NetworkResponse,
  PageLike,
  RoutablePage,
  StepContext,
} from './helpers.js';
