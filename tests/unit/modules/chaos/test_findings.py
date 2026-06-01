"""chaos finding-translation unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

from engine.domain.ids import IdGenerator

from modules.chaos.findings import findings_from_results
from modules.chaos.models import ChaosEvent, ChaosScenarioResult


def _event(observation, **overrides) -> ChaosEvent:
    payload = {
        "scenario_id": "network.api_500",
        "category": "network",
        "flow": "checkout",
        "observation": observation,
    }
    payload.update(overrides)
    return ChaosEvent(**payload)


def _result(*events: ChaosEvent, scenario_id: str | None = None, **kwargs) -> ChaosScenarioResult:
    base = {
        "scenario_id": scenario_id or events[0].scenario_id,
        "category": events[0].category,
        "flow": events[0].flow,
        "events": events,
    }
    base.update(kwargs)
    return ChaosScenarioResult(**base)


def test_findings_from_results_skips_skipped_results() -> None:
    result = ChaosScenarioResult(
        scenario_id="network.api_500",
        category="network",
        flow="checkout",
        events=(),
        skipped=True,
        skip_reason="no events",
    )
    findings = findings_from_results(
        results=(result,),
        run_id="RUN-FINDA1B2C3DE",
        target_base_url="http://127.0.0.1:8000",
        id_generator=IdGenerator(),
    )
    assert findings == ()


def test_findings_from_results_uses_default_artifact_path() -> None:
    result = _result(_event("no_error_state"))
    findings = findings_from_results(
        results=(result,),
        run_id="RUN-FINDA1B2C3DE",
        target_base_url="http://127.0.0.1:8000",
        id_generator=IdGenerator(),
        artifact_paths=None,
    )
    assert findings
    assert findings[0].evidence[0].path.as_posix().endswith("chaos/network.json")


def test_findings_from_results_uses_supplied_now() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    result = _result(_event("no_error_state"))
    findings = findings_from_results(
        results=(result,),
        run_id="RUN-FINDA1B2C3DE",
        target_base_url="http://127.0.0.1:8000",
        id_generator=IdGenerator(),
        now=timestamp,
    )
    assert findings[0].created_at == timestamp


def test_findings_include_extras_in_description() -> None:
    event = _event(
        "no_error_state",
        detail="page silent",
        evidence={"console_lines": "3", "status": "500"},
    )
    findings = findings_from_results(
        results=(_result(event),),
        run_id="RUN-FINDA1B2C3DE",
        target_base_url="http://127.0.0.1:8000",
        id_generator=IdGenerator(),
    )
    body = findings[0].description
    assert "console_lines=3" in body
    assert "status=500" in body
