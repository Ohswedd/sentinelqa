"""Retry / quarantine decision (PRD §9.5, task 09.04).

The runner (Phase 08) already retries up to ``runner.retries.max`` times
per the configured policy. The analyzer's job is to advise:

* whether retrying is *still* useful for a given failure (a known 5xx is
  not worth another attempt),
* when a failure looks like a stable test bug, flag it as a quarantine
  candidate so the user can decide.

Decisions are deterministic and depend only on the signal +
classification + optional history snapshot. They never mutate state —
the caller (runner / SDK) applies them.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from engine.analyzer.models import (
    FailureClassification,
    FailureSignal,
    RetryDecision,
)


class FailureHistory(BaseModel):
    """Optional history of prior runs for the same test.

    The runner persists per-test history under
    ``.sentinel/runs/<run-id>/module-results/<module>.json`` (Phase 08);
    the SDK aggregates them when calling the analyzer with a richer
    snapshot. The analyzer only uses two numbers — total recent runs and
    failed runs — so the history payload stays compact.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_recent_runs: int = Field(default=0, ge=0, le=1_000)
    failed_recent_runs: int = Field(default=0, ge=0, le=1_000)
    last_passed: bool = Field(default=True)


_MAX_AUTO_RETRIES: Final[int] = 2
"""Hard cap on additional retries the analyzer will recommend regardless
of category. Matches CLAUDE §23 — auto-loops must be conservative."""


def should_retry(
    signal: FailureSignal,
    classification: FailureClassification,
    *,
    history: FailureHistory | None = None,
) -> RetryDecision:
    """Return the :class:`RetryDecision` for ``signal``."""

    if signal.retries >= _MAX_AUTO_RETRIES:
        return RetryDecision(
            decision="no_action",
            reason=(
                f"Already retried {signal.retries} time(s); further auto-retries "
                "would violate the conservative auto-loop boundary (CLAUDE §23)."
            ),
            confidence=0.95,
        )

    category = classification.category

    if category == "flake":
        return RetryDecision(
            decision="retry",
            reason="Pass-on-retry pattern observed; another attempt is informative.",
            confidence=0.85,
        )

    if category == "environment_failure":
        # Browser crash or transient network/host glitch. Retry once.
        return RetryDecision(
            decision="retry",
            reason="Environment/runtime fault is often transient; retry once.",
            confidence=0.8,
        )

    if category == "auth_failure":
        if signal.fixture_failed:
            return RetryDecision(
                decision="no_action",
                reason=(
                    "Auth fixture failed; retrying re-runs the same fixture and is "
                    "unlikely to succeed without a config fix."
                ),
                confidence=0.85,
            )
        return RetryDecision(
            decision="retry",
            reason=(
                "Auth surfaced mid-test; one retry distinguishes session "
                "timeout from a true block."
            ),
            confidence=0.6,
        )

    if category == "app_bug":
        return RetryDecision(
            decision="no_action",
            reason="App returned a 5xx; retrying will not change a server-side defect.",
            confidence=0.9,
        )

    if category == "api_failure":
        return RetryDecision(
            decision="no_action",
            reason="API contract / input mismatch is deterministic; do not retry.",
            confidence=0.8,
        )

    if category in {"performance_regression", "security_finding", "accessibility_violation"}:
        return RetryDecision(
            decision="no_action",
            reason=f"{category.replace('_', ' ').capitalize()} is deterministic; do not retry.",
            confidence=0.85,
        )

    if category == "test_bug":
        # Healthy app + consistent locator timeout across attempts → quarantine
        # candidate (let a human review the locator before mass-running again).
        if (
            history
            and history.failed_recent_runs >= 3
            and history.failed_recent_runs >= history.total_recent_runs - 1
        ):
            return RetryDecision(
                decision="quarantine_candidate",
                reason=(
                    f"Failed {history.failed_recent_runs}/{history.total_recent_runs} of the most "
                    "recent runs against a healthy app; locator is likely stale."
                ),
                confidence=0.8,
            )
        if signal.retries >= 1:
            return RetryDecision(
                decision="quarantine_candidate",
                reason=(
                    "Locator-timeout pattern reproduced across attempts against a healthy app; "
                    "review the locator before re-enabling."
                ),
                confidence=0.7,
            )
        return RetryDecision(
            decision="no_action",
            reason="Likely test-side defect; a fresh retry rarely helps a stale locator.",
            confidence=0.6,
        )

    if category == "data_setup_failure":
        return RetryDecision(
            decision="no_action",
            reason="Data/setup fixture errors are configuration-bound; fix the fixture.",
            confidence=0.75,
        )

    # unknown
    return RetryDecision(
        decision="no_action",
        reason=(
            "No rule matched; defaulting to no_action so a human can categorise the "
            "failure before any auto-retry."
        ),
        confidence=0.5,
    )


__all__ = ["FailureHistory", "RetryDecision", "should_retry"]
