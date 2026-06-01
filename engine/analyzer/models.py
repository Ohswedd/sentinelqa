"""Analyzer wire types (the documentation, ADR-0014).

These are the inputs and outputs the analyzer pipeline operates on.
``FailureSignal`` is the only mutable-shape input — every other model is
frozen and Pydantic-validated so analyzer output can be persisted, sent
over the SDK boundary, or fed back into the runner's retry policy
without re-shaping.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums / literals
# ---------------------------------------------------------------------------

FailureCategory = Literal[
    "app_bug",
    "test_bug",
    "environment_failure",
    "flake",
    "data_setup_failure",
    "auth_failure",
    "api_failure",
    "performance_regression",
    "security_finding",
    "accessibility_violation",
    "unknown",
]
"""Closed set per the documentation. ``unknown`` is reserved for signals that
slip past every rule — those carry the lowest confidence and the
recommendation to inspect manually."""

RetryDecisionKind = Literal["retry", "quarantine_candidate", "no_action"]


# ---------------------------------------------------------------------------
# Per-failure raw signal (input)
# ---------------------------------------------------------------------------


class AttemptOutcome(BaseModel):
    """One Playwright retry of a single test."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt: int = Field(ge=0, le=10)
    status: Literal["passed", "failed", "timed_out", "skipped"]
    duration_ms: int = Field(ge=0)
    error_message: str | None = Field(default=None, max_length=2_048)


class StepRecord(BaseModel):
    """One ``step.start``/``step.end`` pair from the TS runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=512)
    duration_ms: int = Field(ge=0)
    ok: bool
    error_message: str | None = Field(default=None, max_length=2_048)


class NetworkRecord(BaseModel):
    """One ``network.response`` event captured while the test ran.

    URLs are passed through redaction by the caller; the
    analyzer never re-redacts but never logs them either.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(min_length=1, max_length=4_096)
    method: str = Field(min_length=1, max_length=16)
    status_code: int = Field(ge=0, le=999)
    duration_ms: int = Field(ge=0)


class ConsoleRecord(BaseModel):
    """One ``console`` event captured while the test ran."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: Literal["log", "debug", "info", "warn", "error"]
    message: str = Field(max_length=2_048)
    source: str = Field(default="", max_length=512)


class FailureSignal(BaseModel):
    """All evidence about ONE failed test the analyzer reasons over.

    The signal is built once per failed (or errored / timed_out) test by
    :mod:`engine.analyzer.signals` from the runner's
    :class:`engine.runner.results.RunnerOutcome` plus the captured event
    stream. Once frozen, every analyzer stage is a pure function of the
    signal — no I/O, no clocks, no random.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str = Field(min_length=1, max_length=256)
    title: str = Field(min_length=1, max_length=512)
    file: str = Field(min_length=1, max_length=512)
    status: Literal["failed", "timed_out", "errored", "flaky"]
    duration_ms: int = Field(ge=0)
    retries: int = Field(ge=0, le=10)
    attempts: tuple[AttemptOutcome, ...] = Field(default_factory=tuple)
    error_message: str | None = Field(default=None, max_length=2_048)
    error_name: str | None = Field(default=None, max_length=128)
    error_stack: str | None = Field(default=None, max_length=16_384)
    steps: tuple[StepRecord, ...] = Field(default_factory=tuple)
    network: tuple[NetworkRecord, ...] = Field(default_factory=tuple)
    console: tuple[ConsoleRecord, ...] = Field(default_factory=tuple)
    evidence: tuple[str, ...] = Field(default_factory=tuple)
    module: str = Field(min_length=1, max_length=64)
    route: str | None = Field(default=None, max_length=2_048)
    fixture_failed: bool = False
    """True when the failure originated in setup/auth fixtures, not the
    test body. The runner sets this when a beforeAll / fixture hook
    raised — repro must replay the fixture, not the test."""


# ---------------------------------------------------------------------------
# Analyzer outputs
# ---------------------------------------------------------------------------


class FailureClassification(BaseModel):
    """The categorize-stage verdict for one signal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: FailureCategory
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=512)
    secondary: tuple[tuple[FailureCategory, float], ...] = Field(default_factory=tuple)
    """Other categories the rules matched, ranked by confidence. Empty
    when only one rule fired."""


class RootCauseHypothesis(BaseModel):
    """Short, plain-English hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: FailureCategory
    hypothesis: str = Field(min_length=1, max_length=1_024)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    next_actions: tuple[str, ...] = Field(default_factory=tuple)
    llm_refinement: str | None = Field(default=None, max_length=4_000)


class RetryDecision(BaseModel):
    """Whether the runner should retry this failure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: RetryDecisionKind
    reason: str = Field(min_length=1, max_length=512)
    confidence: float = Field(ge=0.0, le=1.0)


class AnalyzerResult(BaseModel):
    """Bundled output for ONE failure — what Reporter / Healer / SDK read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    test_id: str = Field(min_length=1, max_length=256)
    classification: FailureClassification
    hypothesis: RootCauseHypothesis
    reproduction: tuple[str, ...] = Field(default_factory=tuple)
    retry_decision: RetryDecision


__all__ = [
    "AnalyzerResult",
    "AttemptOutcome",
    "ConsoleRecord",
    "FailureCategory",
    "FailureClassification",
    "FailureSignal",
    "NetworkRecord",
    "RetryDecision",
    "RetryDecisionKind",
    "RootCauseHypothesis",
    "StepRecord",
]
