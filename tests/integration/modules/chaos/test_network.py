"""Phase 23.02 — network chaos integration tests.

These tests prove the round-trip from a TS chaos JSONL log to our product spec2
:class:`Finding`s. They never start a real browser — the JSONL fixture
*is* what the TS chaos helpers would emit. The acceptance criterion
from the build plan is:

    Fixture flow under api_500 produces a finding if no error state shown.
"""

from __future__ import annotations

import json
from typing import Any

from engine.domain.module_result import ModuleResult
from engine.modules.base import ModuleContext


def _build_run(make_chaos_module: Any, ctx: ModuleContext) -> tuple[Any, ModuleResult]:
    module = make_chaos_module(ctx)
    result = module.run(ctx)
    return module, result


def test_api_500_no_error_state_produces_finding(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "network.api_500",
                "category": "network",
                "flow": "checkout",
                "observation": "no_error_state",
                "route": "/api/checkout",
                "detail": "Checkout page rendered no error banner after forced 500.",
            }
        ],
    )
    _, result = _build_run(make_chaos_module, chaos_context)
    assert result.status == "failed"
    assert any(f.category.endswith("chaos-no-error-state") for f in result.findings)
    finding = next(f for f in result.findings if "no-error-state" in f.category)
    assert finding.severity == "high"
    assert finding.location.route == "/api/checkout"


def test_offline_uncaught_error_produces_finding(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "network.offline",
                "category": "network",
                "flow": "login",
                "observation": "uncaught_error",
                "detail": "TypeError: Failed to fetch",
                "evidence": {"console_lines": "3"},
            }
        ],
    )
    _, result = _build_run(make_chaos_module, chaos_context)
    finding = next(f for f in result.findings if f.category.endswith("chaos-uncaught-error"))
    assert finding.severity == "high"
    assert "Failed to fetch" in finding.description


def test_handled_gracefully_does_not_produce_finding(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "network.api_500",
                "category": "network",
                "flow": "checkout",
                "observation": "handled_gracefully",
                "detail": "Error banner present with retry button.",
            }
        ],
    )
    _, result = _build_run(make_chaos_module, chaos_context)
    assert result.findings == ()
    assert result.status == "passed"


def test_index_artifact_lists_every_category(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "network.api_500",
                "category": "network",
                "flow": "checkout",
                "observation": "no_error_state",
            }
        ],
    )
    _build_run(make_chaos_module, chaos_context)
    index_path = chaos_context.run_dir / "chaos" / "index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    # The network category executed; the other three are skipped.
    categories = {entry["category"]: entry for entry in payload["categories"]}
    assert "network" in categories
    assert categories["network"]["skipped"] is False
    assert categories["session"]["skipped"] is True


def test_malformed_event_marks_run_incomplete(chaos_context, make_chaos_module) -> None:
    chaos_dir = chaos_context.run_dir / "chaos"
    chaos_dir.mkdir(parents=True, exist_ok=True)
    (chaos_dir / "events.jsonl").write_text("{not valid json\n", encoding="utf-8")
    _, result = _build_run(make_chaos_module, chaos_context)
    assert result.status == "incomplete"


def test_filter_by_scenario_drops_other_categories(
    chaos_context, make_chaos_module, write_events_file
) -> None:
    write_events_file(
        chaos_context.run_dir,
        [
            {
                "scenario_id": "network.api_500",
                "category": "network",
                "flow": "checkout",
                "observation": "no_error_state",
            },
            {
                "scenario_id": "ux.duplicate_submit",
                "category": "ux",
                "flow": "checkout",
                "observation": "duplicate_submit_accepted",
            },
        ],
    )
    # Tell the module to only run network scenarios.
    chaos_context.options.clear() if hasattr(chaos_context.options, "clear") else None
    # ModuleContext.options is a Mapping — rebuild the ctx via dataclasses.replace.
    from dataclasses import replace

    new_ctx = replace(
        chaos_context,
        options={"enabled_categories": ("network",)},
    )
    module = make_chaos_module(new_ctx)
    result = module.run(new_ctx)
    rules = {f.category for f in result.findings}
    assert any("chaos-no-error-state" in r for r in rules)
    assert all("ux" not in r for r in rules)
