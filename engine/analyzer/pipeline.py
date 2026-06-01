"""Top-level analyzer pipeline.

Wires the four stages together — categorize → hypothesize → reproduce →
retry decision — and optionally refines the hypothesis through an LLM
explainer adapter. The pipeline is the only surface module-level
consumers (CLI, SDK, lifecycle) need.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from engine.analyzer.categorize import categorize
from engine.analyzer.models import (
    AnalyzerResult,
    FailureSignal,
)
from engine.analyzer.repro import reproduction
from engine.analyzer.retry_decision import FailureHistory, should_retry
from engine.analyzer.root_cause import hypothesize

if TYPE_CHECKING:
    from engine.analyzer.llm_explainer import LlmExplainer


@dataclass
class AnalyzerContext:
    """Per-run configuration the analyzer needs (auth env vars, history)."""

    auth_env_vars: tuple[str, ...] = ()
    base_url: str | None = None
    history_by_test: dict[str, FailureHistory] = field(default_factory=dict)


@dataclass
class Analyzer:
    """Deterministic analyzer with optional LLM refinement.

    Usage:

    >>> analyzer = Analyzer
    >>> for result in analyzer.analyze(signals, context=AnalyzerContext):......

    The LLM explainer is injected via the ``llm`` argument so callers
    keep full control over budget enforcement and provider selection
    (see :func:`engine.analyzer.llm_explainer.build_llm_explainer`).
    """

    llm: LlmExplainer | None = None

    def analyze_one(
        self,
        signal: FailureSignal,
        *,
        context: AnalyzerContext | None = None,
    ) -> AnalyzerResult:
        """Return the :class:`AnalyzerResult` for a single signal."""

        ctx = context or AnalyzerContext()
        classification = categorize(signal)
        hypothesis = hypothesize(signal, classification)
        repro = reproduction(
            signal,
            auth_env_vars=ctx.auth_env_vars,
            base_url=ctx.base_url,
        )
        history = ctx.history_by_test.get(signal.test_id)
        decision = should_retry(signal, classification, history=history)

        if self.llm is not None:
            try:
                refined = self.llm.refine(signal, classification, hypothesis)
            except Exception:
                # LLM failures must never break the deterministic path.
                refined = None
            if refined is not None:
                hypothesis = hypothesis.model_copy(update={"llm_refinement": refined})

        return AnalyzerResult(
            test_id=signal.test_id,
            classification=classification,
            hypothesis=hypothesis,
            reproduction=repro,
            retry_decision=decision,
        )

    def analyze(
        self,
        signals: Iterable[FailureSignal],
        *,
        context: AnalyzerContext | None = None,
    ) -> tuple[AnalyzerResult, ...]:
        """Analyze every signal; deterministic ordering by ``test_id``."""

        results: list[AnalyzerResult] = [self.analyze_one(s, context=context) for s in signals]
        results.sort(key=lambda r: r.test_id)
        return tuple(results)


def sort_results(results: Sequence[AnalyzerResult]) -> tuple[AnalyzerResult, ...]:
    """Deterministic ordering for persistence / golden fixtures."""

    return tuple(sorted(results, key=lambda r: r.test_id))


def is_healer_candidate(result: AnalyzerResult) -> bool:
    """Return ``True`` if Healer should attempt a repair.

    The Healer is intentionally narrow: it operates only on
    ``test_bug``-categorized failures. App bugs, environment failures,
    flake, security/perf/a11y findings are out of scope (the Healer
    must not paper over them). Confidence below 0.5 is also out of
    scope — at that point the classifier itself isn't sure the failure
    is a test bug, and the Healer should not invent test changes from
    a guess.
    """

    if result.classification.category != "test_bug":
        return False
    return result.classification.confidence >= 0.5


__all__ = [
    "Analyzer",
    "AnalyzerContext",
    "is_healer_candidate",
    "sort_results",
]
