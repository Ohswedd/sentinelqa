"""LLM-VALIDATION-MISMATCH-* — frontend/backend validation mismatch.

Pure function over :class:`ValidationProbe` records. Two finding
types fire:

* ``LLM-VALIDATION-MISMATCH-BACKEND-ACCEPTS`` (high) — the frontend
 refused to submit a malformed payload, but the backend accepted it
 (status 2xx) when the runner POSTed it directly. The backend is the
 authoritative validator and is currently lax.
* ``LLM-VALIDATION-MISMATCH-FRONTEND-MISSING`` (medium-high) — the
 frontend would have submitted as-is, and the backend rejected it
 with a 4xx. The user gets bad UX (no fast feedback) but the data
 layer is at least safe.
"""

from __future__ import annotations

from collections.abc import Iterable

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import ValidationProbe
from modules.llm_audit.rules import LLM_VALIDATION_BACKEND_ACCEPTS, LLM_VALIDATION_FRONTEND_MISSING


def check_validation_mismatch(probes: Iterable[ValidationProbe]) -> tuple[CheckFinding, ...]:
    findings: list[CheckFinding] = []
    for probe in probes:
        backend_accepts = 200 <= probe.backend_status_code < 300
        backend_rejects = 400 <= probe.backend_status_code < 500
        if not probe.frontend_would_submit and backend_accepts:
            findings.append(
                CheckFinding(
                    rule_id=LLM_VALIDATION_BACKEND_ACCEPTS.id,
                    title=(
                        f"Backend accepts {probe.payload_kind} payload for "
                        f"{probe.endpoint_path}"
                    ),
                    description=(
                        f"The frontend would refuse to submit a {probe.payload_kind} "
                        f"payload for field {probe.field!r} on form {probe.form_id!r} "
                        f"({probe.route_url}), but the backend "
                        f"({probe.endpoint_path}) returned "
                        f"HTTP {probe.backend_status_code}. Server-side validation is missing."
                    ),
                    route=probe.route_url,
                    extra_context=(
                        ("form_id", probe.form_id),
                        ("endpoint", probe.endpoint_path),
                        ("field", probe.field),
                        ("payload_kind", probe.payload_kind),
                        ("backend_status", str(probe.backend_status_code)),
                    ),
                )
            )
            continue
        if probe.frontend_would_submit and backend_rejects:
            findings.append(
                CheckFinding(
                    rule_id=LLM_VALIDATION_FRONTEND_MISSING.id,
                    title=(
                        f"Frontend submits {probe.payload_kind} payload that "
                        f"backend rejects on {probe.endpoint_path}"
                    ),
                    description=(
                        f"The frontend submits a {probe.payload_kind} payload for "
                        f"field {probe.field!r} on form {probe.form_id!r} "
                        f"({probe.route_url}); the backend "
                        f"({probe.endpoint_path}) returned "
                        f"HTTP {probe.backend_status_code}. Mirror the rule client-side "
                        "for fast feedback."
                    ),
                    route=probe.route_url,
                    extra_context=(
                        ("form_id", probe.form_id),
                        ("endpoint", probe.endpoint_path),
                        ("field", probe.field),
                        ("payload_kind", probe.payload_kind),
                        ("backend_status", str(probe.backend_status_code)),
                    ),
                )
            )
    return tuple(findings)


__all__ = ["check_validation_mismatch"]
