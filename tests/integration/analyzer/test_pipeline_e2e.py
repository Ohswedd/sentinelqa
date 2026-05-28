"""End-to-end: a runner outcome containing failed tests → analyzer
results match the categorization, hypothesis, and repro contract."""

from __future__ import annotations

from typing import Any

from engine.analyzer.pipeline import Analyzer, AnalyzerContext
from engine.analyzer.signals import build_failure_signal, filter_failed
from engine.runner.results import RunnerOutcome, TestExecution


def _exec(**kwargs: Any) -> TestExecution:
    base: dict[str, Any] = dict(
        test_id="test:1",
        title="example",
        file="tests/e.spec.ts",
        status="failed",
        duration_ms=100,
        retries=0,
        evidence=(),
        error_message="boom",
    )
    base.update(kwargs)
    return TestExecution(**base)


def test_end_to_end_runs_analyzer_over_a_runner_outcome():
    """Build a RunnerOutcome with three failures of distinct categories,
    feed it through the analyzer pipeline, and assert each result
    matches the expected category + retry decision."""

    outcome = RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-FUNCAAAAAAAA",
        status="failed",
        tests=[
            # passing tests are filtered out before analysis.
            _exec(test_id="ok:1", status="passed", error_message=None),
            # app_bug surrogate — error_message simulates a 5xx assertion fail.
            _exec(
                test_id="fail:app_bug",
                status="failed",
                error_message="expect(received).toBeVisible() failed (server 502)",
            ),
            # test_bug surrogate.
            _exec(
                test_id="fail:locator_timeout",
                status="failed",
                error_message=("locator.click: Timeout 30000ms exceeded waiting for selector"),
            ),
            # flake surrogate.
            _exec(test_id="fail:flake", status="flaky", retries=1, error_message=None),
        ],
        duration_ms=400,
        environment=None,
    )
    failed = filter_failed(outcome)
    assert {t.test_id for t in failed} == {
        "fail:app_bug",
        "fail:locator_timeout",
        "fail:flake",
    }

    # Build signals from those failed executions (no live events for
    # this test — the analyzer falls back to the error_message hints).
    signals = []
    for t in failed:
        # Inject a fake network event that maps app_bug to a 5xx so its
        # rule fires (the error_message alone is not enough — categorize
        # needs the response code).
        from engine.analyzer.models import NetworkRecord

        if t.test_id == "fail:app_bug":
            sig = build_failure_signal(t, module="functional")
            from dataclasses import replace  # noqa: F401

            sig = sig.model_copy(
                update={
                    "network": (
                        NetworkRecord(
                            url="https://example.test/api",
                            method="GET",
                            status_code=502,
                            duration_ms=12,
                        ),
                    )
                }
            )
        elif t.test_id == "fail:locator_timeout":
            sig = build_failure_signal(t, module="functional")
            sig = sig.model_copy(
                update={
                    "network": (
                        NetworkRecord(
                            url="https://example.test/",
                            method="GET",
                            status_code=200,
                            duration_ms=8,
                        ),
                    )
                }
            )
        else:
            sig = build_failure_signal(t, module="functional")
        signals.append(sig)

    results = Analyzer().analyze(signals)
    by_id = {r.test_id: r for r in results}
    assert by_id["fail:app_bug"].classification.category == "app_bug"
    assert by_id["fail:locator_timeout"].classification.category == "test_bug"
    assert by_id["fail:flake"].classification.category == "flake"

    # Retry decisions align with each category.
    assert by_id["fail:app_bug"].retry_decision.decision == "no_action"
    assert by_id["fail:flake"].retry_decision.decision == "retry"

    # Every result carries reproduction steps and a non-empty hypothesis.
    for r in results:
        assert r.reproduction
        assert r.hypothesis.hypothesis
        assert r.hypothesis.next_actions


def test_analyzer_context_threads_through_pipeline():
    outcome = RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-FUNCAAAAAAAB",
        status="failed",
        tests=[_exec(test_id="fail:1", error_message="login failed; invalid credentials")],
        duration_ms=10,
        environment=None,
    )
    failed = filter_failed(outcome)
    signal = build_failure_signal(failed[0], module="functional", fixture_failed=True)
    ctx = AnalyzerContext(
        auth_env_vars=("SENTINEL_TEST_USER",), base_url="https://staging.example.test"
    )
    result = Analyzer().analyze_one(signal, context=ctx)
    repro = "\n".join(result.reproduction)
    assert "$SENTINEL_TEST_USER" in repro
    assert "staging.example.test" in repro
