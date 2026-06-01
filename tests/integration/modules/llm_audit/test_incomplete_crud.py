"""Integration tests for the incomplete-CRUD check."""

from __future__ import annotations

from modules.llm_audit.checks.incomplete_crud import check_incomplete_crud
from modules.llm_audit.models import ResourceCrudSignal


def test_complete_crud_is_clean() -> None:
    signal = ResourceCrudSignal(
        resource="orders",
        has_create=True,
        has_read=True,
        has_update=True,
        has_delete=True,
    )
    assert check_incomplete_crud([signal]) == ()


def test_create_only_with_ui_button_is_high() -> None:
    signal = ResourceCrudSignal(
        resource="orders",
        has_create=True,
        ui_has_create_button=True,
    )
    findings = check_incomplete_crud([signal])
    assert len(findings) == 1
    assert findings[0].severity_override == "high"
    assert "read" in findings[0].title
    assert "update" in findings[0].title
    assert "delete" in findings[0].title


def test_create_plus_read_missing_update_is_medium() -> None:
    signal = ResourceCrudSignal(
        resource="orders",
        has_create=True,
        has_read=True,
        ui_has_edit_button=False,
        ui_has_delete_button=True,
    )
    findings = check_incomplete_crud([signal])
    assert len(findings) == 1
    assert findings[0].severity_override == "medium"
    assert "update" in findings[0].title


def test_no_create_signal_is_silent() -> None:
    signal = ResourceCrudSignal(resource="orders", has_read=True)
    assert check_incomplete_crud([signal]) == ()
