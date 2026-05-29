"""Integration tests for the forms-no-submit check (task 19.05)."""

from __future__ import annotations

from modules.llm_audit.checks.forms_no_submit import check_forms_no_submit
from modules.llm_audit.models import FormSignal


def _form(**overrides: object) -> FormSignal:
    base = {
        "form_id": "FRM-AAAAAAAA",
        "route_url": "http://localhost:3000/contact",
        "action_url": None,
        "method": "POST",
        "submit_handler_present": True,
    }
    base.update(overrides)
    return FormSignal(**base)  # type: ignore[arg-type]


def test_form_without_submit_handler_is_flagged() -> None:
    findings = check_forms_no_submit([_form(submit_handler_present=False)])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-FORM-NO-SUBMIT"


def test_form_with_handler_not_exercised_is_silent() -> None:
    assert check_forms_no_submit([_form()]) == ()


def test_form_exercised_no_network_is_flagged() -> None:
    findings = check_forms_no_submit(
        [_form(was_exercised=True, produced_network_request=False)],
    )
    assert len(findings) == 1
    assert "without firing a request" in findings[0].title


def test_form_exercised_with_network_is_clean() -> None:
    findings = check_forms_no_submit(
        [_form(was_exercised=True, produced_network_request=True)],
    )
    assert findings == ()


def test_unexercised_form_not_punished() -> None:
    findings = check_forms_no_submit(
        [_form(was_exercised=False, produced_network_request=None)],
    )
    assert findings == ()
