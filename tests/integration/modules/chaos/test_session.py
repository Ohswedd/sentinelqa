"""Phase 23.03 — session chaos integration tests.

Acceptance criterion (`plans/phase-23-chaos-module/03-session-scenarios.md`):

    Fixture with bad UX on expired session triggers finding.
"""

from __future__ import annotations

from typing import Any

from engine.domain.module_result import ModuleResult
from engine.modules.base import ModuleContext


def _run(make_chaos_module: Any, ctx: ModuleContext) -> ModuleResult:
    result: ModuleResult = make_chaos_module(ctx).run(ctx)
    return result


def test_expired_session_without_redirect_produces_high_finding(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "session.expired_token",
                "category": "session",
                "flow": "profile",
                "observation": "no_redirect_on_expired_session",
                "route": "/profile",
                "detail": "Token expired; page stayed blank with no redirect or banner.",
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    finding = next(
        f for f in result.findings if f.category.endswith("chaos-session-expired-no-redirect")
    )
    assert finding.severity == "high"
    assert finding.location.route == "/profile"
    assert result.status == "failed"


def test_missing_permissions_bad_ux_produces_medium_finding(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "session.missing_permissions",
                "category": "session",
                "flow": "admin",
                "observation": "no_graceful_permission_denial",
                "route": "/admin",
                "detail": "Admin page crashed instead of rendering a permission-denied state.",
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    finding = next(
        f for f in result.findings if f.category.endswith("chaos-permission-missing-bad-ux")
    )
    assert finding.severity == "medium"
    # Medium finding alone should NOT escalate the module status to failed.
    assert result.status == "passed"


def test_session_graceful_is_silent(chaos_context, make_chaos_module, write_events_file) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "session.expired_token",
                "category": "session",
                "flow": "profile",
                "observation": "handled_gracefully",
                "detail": "Redirected to /login with banner.",
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    assert result.findings == ()
