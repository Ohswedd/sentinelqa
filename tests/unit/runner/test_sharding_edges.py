"""Coverage for the rarer merge_outcomes paths."""

from __future__ import annotations

from engine.runner.results import (
    EnvironmentContext,
    RunnerOutcome,
    TestExecution,
)
from engine.runner.sharding import merge_outcomes


def _outcome(module_status: str, *, env: EnvironmentContext | None = None) -> RunnerOutcome:
    tests = (
        TestExecution(
            test_id="t1",
            title="t",
            file="t.spec.ts",
            status="passed" if module_status == "passed" else "skipped",
            duration_ms=100,
            retries=0,
        ),
    )
    return RunnerOutcome.build(
        module_name="functional",
        module_id="MOD-MERGAAAAAAAA",
        status=module_status,  # type: ignore[arg-type]
        tests=tests,
        duration_ms=100,
        environment=env,
    )


def test_merge_outcomes_errored_status_wins() -> None:
    pre = _outcome("passed")
    err = _outcome("errored")
    merged = merge_outcomes([pre, err], module_name="functional")
    assert merged.module_result.status == "errored"


def test_merge_outcomes_skipped_only() -> None:
    merged = merge_outcomes([_outcome("skipped"), _outcome("skipped")], module_name="functional")
    assert merged.module_result.status == "skipped"


def test_merge_outcomes_picks_first_non_none_environment() -> None:
    env = EnvironmentContext(browser="firefox", browser_version="bundled", os="Linux")
    merged = merge_outcomes(
        [_outcome("passed"), _outcome("passed", env=env)], module_name="functional"
    )
    assert merged.environment is not None
    assert merged.environment.browser == "firefox"


def test_merge_outcomes_default_environment_when_all_none() -> None:
    merged = merge_outcomes([_outcome("passed"), _outcome("passed")], module_name="functional")
    assert merged.environment is not None
    # Default fallback browser is chromium.
    assert merged.environment.browser == "chromium"
