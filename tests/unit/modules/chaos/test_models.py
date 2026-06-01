"""unit tests for chaos wire types."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.chaos.models import (
    CHAOS_RESULT_SCHEMA_VERSION,
    ChaosCategoryReport,
    ChaosEvent,
    ChaosRunOutcome,
    ChaosScenarioResult,
)


def _bad_event() -> ChaosEvent:
    return ChaosEvent(
        scenario_id="network.api_500",
        category="network",
        flow="checkout",
        observation="no_error_state",
    )


def _good_event() -> ChaosEvent:
    return ChaosEvent(
        scenario_id="network.api_500",
        category="network",
        flow="checkout",
        observation="handled_gracefully",
    )


def test_event_is_bad_flag() -> None:
    assert _bad_event().is_bad is True
    assert _good_event().is_bad is False


def test_event_rejects_unknown_observation() -> None:
    with pytest.raises(ValidationError):
        ChaosEvent(
            scenario_id="network.api_500",
            category="network",
            flow="checkout",
            observation="bogus",  # type: ignore[arg-type]
        )


def test_event_extra_keys_rejected() -> None:
    with pytest.raises(ValidationError):
        ChaosEvent(
            scenario_id="network.api_500",
            category="network",
            flow="checkout",
            observation="handled_gracefully",
            extra_key="nope",  # type: ignore[call-arg]
        )


def test_scenario_result_aggregates_bad_events() -> None:
    result = ChaosScenarioResult(
        scenario_id="network.api_500",
        category="network",
        flow="checkout",
        events=(_bad_event(), _good_event(), _bad_event()),
    )
    assert len(result.bad_events) == 2


def test_category_report_default_skipped_false() -> None:
    report = ChaosCategoryReport(category="network", results=())
    assert report.skipped is False
    assert report.results == ()


def test_run_outcome_schema_version_stable() -> None:
    outcome = ChaosRunOutcome(duration_ms=0)
    assert outcome.schema_version == CHAOS_RESULT_SCHEMA_VERSION
    assert outcome.categories == ()
