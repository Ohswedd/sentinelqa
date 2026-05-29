"""Integration tests for the validation-mismatch check (task 19.11)."""

from __future__ import annotations

from modules.llm_audit.checks.validation_mismatch import check_validation_mismatch
from modules.llm_audit.models import ValidationProbe


def _probe(**overrides: object) -> ValidationProbe:
    base = {
        "form_id": "FRM-AAAA",
        "route_url": "http://localhost:3000/signup",
        "endpoint_path": "/api/users",
        "field": "email",
        "payload_kind": "missing",
        "frontend_would_submit": False,
        "backend_status_code": 201,
    }
    base.update(overrides)
    return ValidationProbe(**base)  # type: ignore[arg-type]


def test_backend_accepts_what_frontend_rejects_is_high() -> None:
    findings = check_validation_mismatch([_probe()])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-VALIDATION-MISMATCH-BACKEND-ACCEPTS"


def test_frontend_submits_backend_rejects_is_medium() -> None:
    findings = check_validation_mismatch(
        [_probe(frontend_would_submit=True, backend_status_code=400)],
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-VALIDATION-MISMATCH-FRONTEND-MISSING"


def test_both_reject_is_clean() -> None:
    findings = check_validation_mismatch(
        [_probe(frontend_would_submit=False, backend_status_code=400)],
    )
    assert findings == ()


def test_both_accept_is_clean() -> None:
    findings = check_validation_mismatch(
        [_probe(frontend_would_submit=True, backend_status_code=200)],
    )
    assert findings == ()
