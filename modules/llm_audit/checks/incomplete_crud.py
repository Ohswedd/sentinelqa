"""LLM-INCOMPLETE-CRUD — resources with Create but missing Read / Update / Delete.

Pure function over :class:`ResourceCrudSignal` records. We emit one
finding per resource where create-style affordances exist (either an
API or a UI button) but at least one of read/update/delete is missing.
Severity bumps to ``high`` when the UI surfaces an Add button but
hides edit/delete entirely (a classic generated-MVP defect).
"""

from __future__ import annotations

from collections.abc import Iterable

from engine.domain.finding import Severity

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import ResourceCrudSignal
from modules.llm_audit.rules import LLM_INCOMPLETE_CRUD


def check_incomplete_crud(resources: Iterable[ResourceCrudSignal]) -> tuple[CheckFinding, ...]:
    findings: list[CheckFinding] = []
    for resource in resources:
        has_create_signal = resource.has_create or resource.ui_has_create_button
        if not has_create_signal:
            continue
        missing: list[str] = []
        if not resource.has_read:
            missing.append("read")
        if not resource.has_update and not resource.ui_has_edit_button:
            missing.append("update")
        if not resource.has_delete and not resource.ui_has_delete_button:
            missing.append("delete")
        if not missing:
            continue
        ui_only_create = (
            resource.ui_has_create_button
            and not resource.ui_has_edit_button
            and not resource.ui_has_delete_button
        )
        severity: Severity = "high" if ui_only_create else "medium"
        findings.append(
            CheckFinding(
                rule_id=LLM_INCOMPLETE_CRUD.id,
                title=f"Resource {resource.resource!r} is missing {', '.join(missing)}",
                description=(
                    f"The {resource.resource!r} resource exposes a create path "
                    f"but the run did not observe {', '.join(missing)}. "
                    "Incomplete CRUD is the most common scaffolding leak from "
                    "LLM-generated apps."
                ),
                severity_override=severity,
                extra_context=(
                    ("resource", resource.resource),
                    ("missing", ",".join(missing)),
                    ("sample_endpoint", resource.sample_endpoint or "(none)"),
                ),
            )
        )
    return tuple(findings)


__all__ = ["check_incomplete_crud"]
