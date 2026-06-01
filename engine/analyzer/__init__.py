"""Analyzer module (the documentation).

Interprets failed-test signals from the Runner and the
lifecycle's module-error path (CLAUDE §10) and emits, per failure:

 * A typed :class:`~engine.analyzer.models.FailureClassification`.
 * A short :class:`~engine.analyzer.models.RootCauseHypothesis` with
 confidence + evidence pointers.
 * Reproducible step list (and an optional Playwright repro spec).
 * A :class:`~engine.analyzer.models.RetryDecision` consumed by the
 runner's retry/quarantine policy.
 * An optional LLM refinement that NEVER replaces the deterministic
 output (CLAUDE §23).

The Analyzer is deterministic by default. LLM refinement is opt-in
behind ``analyzer.llm.enabled`` and is bounded by a per-run USD budget
(ADR-0014).
"""

from engine.analyzer.categorize import (
    categorize,
    categorize_module_error,
)
from engine.analyzer.models import (
    AnalyzerResult,
    AttemptOutcome,
    ConsoleRecord,
    FailureCategory,
    FailureClassification,
    FailureSignal,
    NetworkRecord,
    RetryDecision,
    RetryDecisionKind,
    RootCauseHypothesis,
    StepRecord,
)
from engine.analyzer.pipeline import Analyzer
from engine.analyzer.repro import (
    REPRO_BANNER,
    build_repro_spec,
    reproduction,
)
from engine.analyzer.retry_decision import should_retry
from engine.analyzer.root_cause import hypothesize
from engine.analyzer.signals import (
    build_failure_signal,
    build_module_error_signal,
)

__all__ = [
    "Analyzer",
    "AnalyzerResult",
    "AttemptOutcome",
    "ConsoleRecord",
    "FailureCategory",
    "FailureClassification",
    "FailureSignal",
    "NetworkRecord",
    "REPRO_BANNER",
    "RetryDecision",
    "RetryDecisionKind",
    "RootCauseHypothesis",
    "StepRecord",
    "build_failure_signal",
    "build_module_error_signal",
    "build_repro_spec",
    "categorize",
    "categorize_module_error",
    "hypothesize",
    "reproduction",
    "should_retry",
]
