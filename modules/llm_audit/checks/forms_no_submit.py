"""LLM-FORM-NO-SUBMIT — forms whose submit path does not function (task 19.05).

Pure function over :class:`FormSignal` records. We flag a form when:

* it has no submit handler (Phase 05 sets ``submit_handler_present=False``
  when neither ``action`` nor ``onsubmit`` is present), OR
* the planner actually exercised the form and we observed no network
  request when it submitted.

We only emit a finding for forms the planner *attempted*; un-exercised
forms get no finding so we don't punish forms the run never reached.
"""

from __future__ import annotations

from collections.abc import Iterable

from modules.llm_audit.findings import CheckFinding
from modules.llm_audit.models import FormSignal
from modules.llm_audit.rules import LLM_FORM_NO_SUBMIT


def check_forms_no_submit(forms: Iterable[FormSignal]) -> tuple[CheckFinding, ...]:
    """Return one CheckFinding per form whose submit path is broken."""

    findings: list[CheckFinding] = []
    for form in forms:
        # Case 1: form structurally has no submit handler.
        if not form.submit_handler_present:
            findings.append(
                CheckFinding(
                    rule_id=LLM_FORM_NO_SUBMIT.id,
                    title=f"Form {form.form_id} has no submit handler",
                    description=(
                        f"The form on {form.route_url} has neither an "
                        "``action`` attribute nor an ``onsubmit`` handler, so "
                        "pressing submit does nothing."
                    ),
                    route=form.route_url,
                    extra_context=(
                        ("form_id", form.form_id),
                        ("method", form.method),
                    ),
                )
            )
            continue
        # Case 2: planner exercised the form, no network request fired.
        if form.was_exercised and form.produced_network_request is False:
            findings.append(
                CheckFinding(
                    rule_id=LLM_FORM_NO_SUBMIT.id,
                    title=f"Form {form.form_id} submitted without firing a request",
                    description=(
                        f"The form on {form.route_url} appears to have a "
                        "submit handler, but the planner submitted it and the "
                        "runner observed no network activity."
                    ),
                    route=form.route_url,
                    extra_context=(
                        ("form_id", form.form_id),
                        ("method", form.method),
                        ("action", form.action_url or "(none)"),
                    ),
                )
            )
    return tuple(findings)


__all__ = ["check_forms_no_submit"]
