"""Analyzer pipeline tests (task 09.06)."""

from __future__ import annotations

from engine.analyzer.models import (
    FailureClassification,
    FailureSignal,
    NetworkRecord,
    RootCauseHypothesis,
)
from engine.analyzer.pipeline import Analyzer, AnalyzerContext
from engine.analyzer.retry_decision import FailureHistory

from tests.unit.analyzer.conftest import make_signal


class _StubExplainer:
    name = "stub"

    def __init__(self, refinement: str | None = "refined: looks plausible"):
        self._refinement = refinement
        self.calls = 0

    @property
    def usage(self):  # pragma: no cover - protocol stub
        class _U:
            cost_usd = 0.0
            input_tokens = 0
            output_tokens = 0
            requests = 0

        return _U()

    def refine(
        self,
        signal: FailureSignal,
        classification: FailureClassification,
        hypothesis: RootCauseHypothesis,
    ) -> str | None:
        self.calls += 1
        return self._refinement


def test_analyze_one_runs_all_stages():
    signal = make_signal(
        network=(NetworkRecord(url="https://x", method="GET", status_code=500, duration_ms=1),),
    )
    analyzer = Analyzer()
    result = analyzer.analyze_one(signal)
    assert result.test_id == signal.test_id
    assert result.classification.category == "app_bug"
    assert result.hypothesis.category == "app_bug"
    assert result.reproduction
    assert result.retry_decision.decision == "no_action"


def test_analyze_sorts_by_test_id():
    signals = [
        make_signal(test_id="test:zebra"),
        make_signal(test_id="test:alpha"),
        make_signal(test_id="test:mango"),
    ]
    analyzer = Analyzer()
    results = analyzer.analyze(signals)
    assert [r.test_id for r in results] == ["test:alpha", "test:mango", "test:zebra"]


def test_analyze_passes_history_per_test():
    signal = make_signal(
        test_id="test:flake",
        error_message="locator.click: Timeout 30000ms exceeded waiting for selector",
        network=(NetworkRecord(url="https://x", method="GET", status_code=200, duration_ms=1),),
    )
    ctx = AnalyzerContext(
        history_by_test={
            "test:flake": FailureHistory(
                total_recent_runs=5, failed_recent_runs=4, last_passed=False
            ),
        },
    )
    analyzer = Analyzer()
    result = analyzer.analyze_one(signal, context=ctx)
    assert result.retry_decision.decision == "quarantine_candidate"


def test_analyze_appends_llm_refinement_without_replacing_hypothesis():
    signal = make_signal(
        network=(NetworkRecord(url="https://x", method="GET", status_code=500, duration_ms=1),),
    )
    deterministic_text_marker = "Likely cause: a server-side defect"
    explainer = _StubExplainer("refined: API logs show DB connection pool exhausted")
    analyzer = Analyzer(llm=explainer)

    result = analyzer.analyze_one(signal)
    assert deterministic_text_marker in result.hypothesis.hypothesis
    assert result.hypothesis.llm_refinement == "refined: API logs show DB connection pool exhausted"
    assert explainer.calls == 1


def test_analyze_tolerates_failing_llm():
    class _BoomExplainer:
        name = "boom"

        @property
        def usage(self):  # pragma: no cover - protocol stub
            return None

        def refine(self, signal, classification, hypothesis):
            raise RuntimeError("explainer fell over")

    signal = make_signal()
    analyzer = Analyzer(llm=_BoomExplainer())
    result = analyzer.analyze_one(signal)
    assert result.hypothesis.llm_refinement is None


def test_analyze_passes_auth_env_vars_to_repro():
    signal = make_signal(fixture_failed=True, error_message="login failed")
    ctx = AnalyzerContext(auth_env_vars=("SENTINEL_TEST_USER",))
    analyzer = Analyzer()
    result = analyzer.analyze_one(signal, context=ctx)
    rendered = "\n".join(result.reproduction)
    assert "$SENTINEL_TEST_USER" in rendered
