"""LLM-NO-LOADING-STATE + LLM-NO-ERROR-STATE.

Pure function over :class:`LoadingErrorObservation` records. Each
observation describes a scripted probe that either delayed or failed a
target API call and reports what the UI did. Two finding types fire:

* ``LLM-NO-LOADING-STATE`` — the probe delayed the request and the UI
 showed no loading indicator within the observation window.
* ``LLM-NO-ERROR-STATE`` — the probe forced a 5xx and the UI either
 showed no error state, or worse, reported success.
"""

from __future__ import annotations

from collections.abc import Iterable

from engine.domain.finding import Severity

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import LoadingErrorObservation
from modules.llm_audit.rules import LLM_NO_ERROR_STATE, LLM_NO_LOADING_STATE


def check_loading_error_states(
    observations: Iterable[LoadingErrorObservation],
) -> tuple[CheckFinding, ...]:
    findings: list[CheckFinding] = []
    for observation in observations:
        if observation.forced_status is None and observation.delay_ms > 0:
            if observation.showed_loading_indicator:
                continue
            findings.append(
                CheckFinding(
                    rule_id=LLM_NO_LOADING_STATE.id,
                    title=(
                        f"No loading indicator on {observation.route_url} "
                        f"while {observation.probed_endpoint} was delayed"
                    ),
                    description=(
                        f"The runner delayed {observation.probed_endpoint} by "
                        f"{observation.delay_ms} ms while on "
                        f"{observation.route_url}; the UI rendered no skeleton, "
                        "spinner, or other loading indicator during the wait."
                    ),
                    route=observation.route_url,
                    extra_context=(
                        ("probed_endpoint", observation.probed_endpoint),
                        ("delay_ms", str(observation.delay_ms)),
                    ),
                )
            )
            continue
        if observation.forced_status is not None and observation.forced_status >= 500:
            if observation.showed_error_state and not observation.ui_reported_success:
                continue
            # Most severe: UI claimed success despite the 5xx.
            severity: Severity | None = "high" if observation.ui_reported_success else None
            findings.append(
                CheckFinding(
                    rule_id=LLM_NO_ERROR_STATE.id,
                    title=(
                        f"No error UI on {observation.route_url} after "
                        f"{observation.probed_endpoint} returned {observation.forced_status}"
                    ),
                    description=(
                        f"The runner forced {observation.probed_endpoint} to "
                        f"return HTTP {observation.forced_status} on "
                        f"{observation.route_url}; the UI "
                        + (
                            "reported success despite the failure."
                            if observation.ui_reported_success
                            else "rendered no error state."
                        )
                    ),
                    route=observation.route_url,
                    severity_override=severity,
                    extra_context=(
                        ("probed_endpoint", observation.probed_endpoint),
                        ("forced_status", str(observation.forced_status)),
                        ("ui_reported_success", str(observation.ui_reported_success).lower()),
                    ),
                )
            )
    return tuple(findings)


__all__ = ["check_loading_error_states"]
