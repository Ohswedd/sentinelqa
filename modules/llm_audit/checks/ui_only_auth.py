"""LLM-UI-ONLY-AUTH — UI hides a route the backend still serves.

Pure function over :class:`AuthRouteProbe` records. The probe is
populated outside this check (by an HTTP probe in the production
wiring or by the test fixture). A finding fires when the UI hid the
route from the role *and* the backend returned 2xx for the same role's
direct request — a classic IDOR-adjacent defect (the documentation).
"""

from __future__ import annotations

from collections.abc import Iterable

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import AuthRouteProbe
from modules.llm_audit.rules import LLM_UI_ONLY_AUTH


def check_ui_only_auth(probes: Iterable[AuthRouteProbe]) -> tuple[CheckFinding, ...]:
    findings: list[CheckFinding] = []
    for probe in probes:
        if probe.ui_visible:
            continue
        status = probe.backend_status_code
        if status is None or not (200 <= status < 300):
            continue
        findings.append(
            CheckFinding(
                rule_id=LLM_UI_ONLY_AUTH.id,
                title=(
                    f"{probe.method.upper()} {probe.route_path} served to "
                    f"{probe.role!r} despite UI hiding it"
                ),
                description=(
                    f"The UI does not surface {probe.route_path!r} to the "
                    f"{probe.role!r} role, but a direct {probe.method.upper()} "
                    f"request returned HTTP {status}. Authorization must be "
                    "enforced server-side."
                ),
                route=probe.route_path,
                extra_context=(
                    ("role", probe.role),
                    ("backend_status", str(status)),
                    ("method", probe.method.upper()),
                ),
            )
        )
    return tuple(findings)


__all__ = ["check_ui_only_auth"]
