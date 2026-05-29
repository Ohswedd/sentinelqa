"""Translate chaos scenario results into PRD §18.2 :class:`Finding`s."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from engine.domain.evidence import Evidence
from engine.domain.finding import Finding, FindingLocation, Severity
from engine.domain.ids import IdGenerator

from modules.chaos.models import ChaosEvent, ChaosObservation, ChaosScenarioResult

# (rule_id, severity, recommendation). One row per *bad* observation
# in :data:`modules.chaos.models.ChaosObservation`. ``handled_gracefully``
# never reaches this mapping because :meth:`ChaosEvent.is_bad` filters
# it out before findings are emitted.
_RULES: Final[dict[ChaosObservation, tuple[str, Severity, str]]] = {
    "uncaught_error": (
        "chaos-uncaught-error",
        "high",
        "Wrap the chaos-affected flow in defensive UI: surface a user-visible "
        "error state when an underlying request fails or stalls.",
    ),
    "no_error_state": (
        "chaos-no-error-state",
        "high",
        "Render a user-visible error state when the affected request fails. "
        "Silent failures hide real outages from operators and users.",
    ),
    "no_redirect_on_expired_session": (
        "chaos-session-expired-no-redirect",
        "high",
        "Redirect to the login flow (or surface a reauthentication prompt) "
        "when the server returns 401 / token-expired errors. Blank-screening "
        "an expired session is a UX-grade outage.",
    ),
    "no_graceful_permission_denial": (
        "chaos-permission-missing-bad-ux",
        "medium",
        "Render a clear permission-denied state (with an actionable next step) "
        "when the user's token lacks the required claims. Hiding or crashing "
        "the affected view forces support tickets.",
    ),
    "duplicate_submit_accepted": (
        "chaos-duplicate-submit-accepted",
        "high",
        "Either disable the submit button after the first click or enforce "
        "server-side idempotency (request-id + dedup) so a double-click never "
        "creates duplicate records / orders / payments.",
    ),
    "lost_form_state_on_navigation": (
        "chaos-lost-form-state",
        "medium",
        "Persist multi-step form state to session storage or the URL so a "
        "back / forward / refresh does not silently discard user input.",
    ),
    "white_screen_on_refresh": (
        "chaos-white-screen-on-refresh",
        "high",
        "Restore the affected route on refresh without crashing. A white "
        "screen mid-payment / mid-checkout is a release-blocker.",
    ),
    "missing_empty_state": (
        "chaos-missing-empty-state",
        "high",
        "Render an explicit empty-state UI when the list payload is empty. "
        "A blank container reads as a broken page.",
    ),
    "dom_explosion_on_large_dataset": (
        "chaos-dom-explosion",
        "medium",
        "Paginate or virtualize lists that may grow past a few hundred rows. "
        "Rendering thousands of nodes degrades user experience and accessibility.",
    ),
    "crash_on_corrupted_storage": (
        "chaos-crash-on-corrupted-storage",
        "high",
        "Validate and discard corrupted localStorage values on read; do not "
        "crash the app when storage contains unexpected content.",
    ),
}


def _format_title(scenario_id: str, observation: ChaosObservation) -> str:
    return f"Chaos: {observation.replace('_', ' ')} during {scenario_id}"


def _event_to_finding(
    *,
    result: ChaosScenarioResult,
    event: ChaosEvent,
    run_id: str,
    target_base_url: str,
    artifact_path: str,
    id_generator: IdGenerator,
    timestamp: datetime,
) -> Finding:
    rule_id, severity, recommendation = _RULES[event.observation]
    location = FindingLocation(route=event.route)
    evidence = (
        Evidence(
            id=id_generator.new("EVD"),
            type="api_sample",
            path=Path(artifact_path),
        ),
    )
    extras_text = "; ".join(f"{k}={v}" for k, v in sorted(event.evidence.items()))
    body = event.detail or result.scenario_id
    body = f"Flow: {event.flow}\nScenario: {event.scenario_id}\n\n{body}"
    if extras_text:
        body = f"{body}\n\nEvidence: {extras_text}"
    return Finding(
        id=id_generator.new("FND"),
        run_id=run_id,
        module="chaos",
        category=f"chaos/{event.category}/{rule_id}",
        severity=severity,
        confidence=1.0,
        title=_format_title(event.scenario_id, event.observation),
        description=body,
        location=location,
        evidence=evidence,
        suggested_fix=recommendation,
        affected_target=target_base_url,
        recommendation=recommendation,
        created_at=timestamp,
    )


def findings_from_results(
    *,
    results: Iterable[ChaosScenarioResult],
    run_id: str,
    target_base_url: str,
    id_generator: IdGenerator,
    artifact_paths: dict[str, str] | None = None,
    now: datetime | None = None,
) -> tuple[Finding, ...]:
    """Convert every bad event in every result into a :class:`Finding`."""

    timestamp = now or datetime.now(UTC)
    artifact_paths = artifact_paths or {}
    out: list[Finding] = []
    for result in results:
        if result.skipped:
            continue
        artifact_path = artifact_paths.get(result.category, f"chaos/{result.category}.json")
        for event in result.bad_events:
            out.append(
                _event_to_finding(
                    result=result,
                    event=event,
                    run_id=run_id,
                    target_base_url=target_base_url,
                    artifact_path=artifact_path,
                    id_generator=id_generator,
                    timestamp=timestamp,
                )
            )
    return tuple(out)


__all__ = ["findings_from_results"]
