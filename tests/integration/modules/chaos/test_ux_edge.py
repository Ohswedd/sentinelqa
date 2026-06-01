"""Phase 23.04 — UX edge case chaos integration tests.

Acceptance criterion (the build plan):

    Fixture allowing duplicate submits → finding.
"""

from __future__ import annotations

from typing import Any

from engine.domain.module_result import ModuleResult
from engine.modules.base import ModuleContext


def _run(make_chaos_module: Any, ctx: ModuleContext) -> ModuleResult:
    result: ModuleResult = make_chaos_module(ctx).run(ctx)
    return result


def test_duplicate_submit_produces_high_finding(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "ux.duplicate_submit",
                "category": "ux",
                "flow": "checkout",
                "observation": "duplicate_submit_accepted",
                "route": "POST /api/orders",
                "detail": "Two distinct POSTs landed; server created two orders.",
                "evidence": {"first_status": "201", "second_status": "201"},
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    finding = next(
        f for f in result.findings if f.category.endswith("chaos-duplicate-submit-accepted")
    )
    assert finding.severity == "high"
    assert "201" in finding.description


def test_back_forward_loses_form_state_is_medium(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "ux.back_forward",
                "category": "ux",
                "flow": "signup-step-2",
                "observation": "lost_form_state_on_navigation",
                "detail": "Form fields were empty after back/forward.",
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    finding = next(f for f in result.findings if f.category.endswith("chaos-lost-form-state"))
    assert finding.severity == "medium"


def test_refresh_mid_flow_white_screen_is_high(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "ux.refresh_mid_flow",
                "category": "ux",
                "flow": "checkout",
                "observation": "white_screen_on_refresh",
                "route": "/checkout/step-3",
                "detail": "Refresh during payment confirmation rendered an empty body.",
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    finding = next(
        f for f in result.findings if f.category.endswith("chaos-white-screen-on-refresh")
    )
    assert finding.severity == "high"


def test_double_click_race_observed(chaos_context, make_chaos_module, write_events_file) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "ux.double_click_race",
                "category": "ux",
                "flow": "checkout",
                "observation": "duplicate_submit_accepted",
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    titles = [f.title for f in result.findings]
    assert any("ux.double_click_race" in t for t in titles)
