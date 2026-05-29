"""Integration tests for the UI-only-auth check (task 19.07)."""

from __future__ import annotations

from modules.llm_audit.checks.ui_only_auth import check_ui_only_auth
from modules.llm_audit.models import AuthRouteProbe


def test_ui_visible_route_not_flagged() -> None:
    probe = AuthRouteProbe(route_path="/admin", ui_visible=True, backend_status_code=200)
    assert check_ui_only_auth([probe]) == ()


def test_backend_404_means_authorized_correctly() -> None:
    probe = AuthRouteProbe(route_path="/admin", ui_visible=False, backend_status_code=403)
    assert check_ui_only_auth([probe]) == ()


def test_missing_backend_response_skipped() -> None:
    probe = AuthRouteProbe(route_path="/admin", ui_visible=False, backend_status_code=None)
    assert check_ui_only_auth([probe]) == ()


def test_ui_hidden_backend_200_is_critical() -> None:
    probe = AuthRouteProbe(
        route_path="/admin",
        ui_visible=False,
        backend_status_code=200,
        role="user",
    )
    findings = check_ui_only_auth([probe])
    assert len(findings) == 1
    assert findings[0].rule_id == "LLM-UI-ONLY-AUTH"
    assert "user" in findings[0].title
