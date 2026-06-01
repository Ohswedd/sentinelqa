"""LLM-DEAD-BTN — buttons with no observed handler (the documentation, ).

Pure function over :class:`ButtonObservation` records. The check is
intentionally conservative: it flags a button only when

* it is not disabled,
* it is not decorative / a disclosure widget (accordions, ``<details>``,
 carousel indicators),
* it has neither a static handler nor any runtime effect — no network
 call within 2 s, no navigation, no DOM change, and no console error.

When runtime signals are missing (the runner did not capture them),
the check requires the static-handler heuristic on its own to fail;
"not observed" is treated as "no positive evidence of activity" but
*not* enough to confidently flag absent the static absence.
"""

from __future__ import annotations

from collections.abc import Iterable

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import ButtonObservation
from modules.llm_audit.rules import LLM_DEAD_BTN


def check_dead_buttons(buttons: Iterable[ButtonObservation]) -> tuple[CheckFinding, ...]:
    """Return one CheckFinding per dead button."""

    findings: list[CheckFinding] = []
    for button in buttons:
        if button.disabled or button.is_decorative or button.is_disclosure:
            continue
        if button.has_static_handler:
            continue
        runtime_observed = (
            button.observed_network_within_2s,
            button.observed_navigation,
            button.observed_console_error,
            button.observed_dom_change,
        )
        # Runtime not captured at all → only static absence is in play;
        # confidence is lower to avoid false positives on rich SPAs.
        if all(signal is None for signal in runtime_observed):
            confidence = 0.55
        else:
            # At least one runtime signal exists. If any of them is
            # positive, the button is not dead.
            if (
                button.observed_network_within_2s
                or button.observed_navigation
                or button.observed_console_error
                or button.observed_dom_change
            ):
                continue
            confidence = 0.9
        findings.append(
            CheckFinding(
                rule_id=LLM_DEAD_BTN.id,
                title=f"Button {button.label!r} has no observed handler",
                description=(
                    f"The button labeled {button.label!r} on {button.route_url} "
                    "has no static handler attribute and produced no observable "
                    "effect within 2 s of being clicked (no network request, no "
                    "navigation, no DOM change, no console error)."
                ),
                route=button.route_url,
                selector=button.selector,
                confidence_override=confidence,
                extra_context=(
                    ("static_handler", "absent"),
                    (
                        "runtime_signals",
                        "not_observed" if confidence < 0.6 else "observed_silence",
                    ),
                ),
            )
        )
    return tuple(findings)


__all__ = ["check_dead_buttons"]
