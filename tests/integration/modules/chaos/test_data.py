"""Phase 23.05 — data chaos integration tests.

Acceptance criterion (the build plan):

    Fixture without empty state → finding.
"""

from __future__ import annotations

from typing import Any

from engine.domain.module_result import ModuleResult
from engine.modules.base import ModuleContext


def _run(make_chaos_module: Any, ctx: ModuleContext) -> ModuleResult:
    result: ModuleResult = make_chaos_module(ctx).run(ctx)
    return result


def test_missing_empty_state_produces_high_finding(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "data.empty_dataset",
                "category": "data",
                "flow": "inventory",
                "observation": "missing_empty_state",
                "route": "GET /api/items",
                "detail": "List page rendered a blank container with no empty-state copy.",
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    finding = next(f for f in result.findings if f.category.endswith("chaos-missing-empty-state"))
    assert finding.severity == "high"
    assert finding.recommendation is not None
    assert "empty-state" in finding.recommendation


def test_large_dataset_dom_explosion_is_medium(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "data.large_dataset",
                "category": "data",
                "flow": "inventory",
                "observation": "dom_explosion_on_large_dataset",
                "detail": "Rendered 1000 rows without pagination; tab froze for ~3s.",
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    finding = next(f for f in result.findings if f.category.endswith("chaos-dom-explosion"))
    assert finding.severity == "medium"


def test_storage_corruption_crash_is_high(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "data.storage_corruption",
                "category": "data",
                "flow": "session-resume",
                "observation": "crash_on_corrupted_storage",
                "detail": (
                    "App crashed with 'Unexpected token' when parsing " "corrupted localStorage."
                ),
            }
        ],
    )
    result = _run(make_chaos_module, chaos_context)
    finding = next(
        f for f in result.findings if f.category.endswith("chaos-crash-on-corrupted-storage")
    )
    assert finding.severity == "high"
