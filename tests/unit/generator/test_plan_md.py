"""Tests for the generated plan markdown emitter (task 07.05)."""

from __future__ import annotations

from pathlib import Path

from engine.domain.flow import Flow, FlowStep
from engine.domain.ids import IdGenerator
from engine.generator.plan_md import (
    GeneratedPlanInputs,
    read_prior_spec_paths,
    render_generated_plan_md,
)


def _flow(ids: IdGenerator, *, name: str, priority: str = "P0") -> Flow:
    return Flow(
        id=ids.new("FLW"),
        name=name,
        steps=(FlowStep(description="x", expected_outcome="y"),),
        priority=priority,  # type: ignore[arg-type]
    )


def test_banner_and_basic_counts() -> None:
    ids = IdGenerator()
    body = render_generated_plan_md(
        GeneratedPlanInputs(
            plan_id="PLN-1",
            run_id="RUN-1",
            target_url="https://staging.example.com/",
            flows=[_flow(ids, name="login")],
            spec_paths=[Path("a.spec.ts"), Path("b.spec.ts")],
            page_object_paths=[Path("pages/LoginPage.ts")],
            fixture_paths=[Path("fixtures/auth.ts")],
            audit_warnings=0,
        )
    )
    assert "<!-- SentinelQA Generated" in body
    assert "Specs generated: **2**" in body
    assert "Page objects generated: **1**" in body
    assert "Fixtures generated: **1**" in body
    assert "PLN-1" in body
    assert "login" in body


def test_diff_section_when_prior_specs_changed(tmp_path: Path) -> None:
    body = render_generated_plan_md(
        GeneratedPlanInputs(
            plan_id="PLN-1",
            run_id="RUN-1",
            target_url="https://x/",
            flows=[],
            spec_paths=[Path("b.spec.ts"), Path("c.spec.ts")],
            page_object_paths=[],
            fixture_paths=[],
            prior_spec_paths=[Path("a.spec.ts"), Path("b.spec.ts")],
        )
    )
    assert "## Diff vs previous generation" in body
    assert "### Added" in body
    assert "`c.spec.ts`" in body
    assert "### Removed" in body
    assert "`a.spec.ts`" in body


def test_diff_no_changes_message() -> None:
    body = render_generated_plan_md(
        GeneratedPlanInputs(
            plan_id="x",
            run_id="x",
            target_url="x",
            flows=[],
            spec_paths=[Path("a.spec.ts")],
            page_object_paths=[],
            fixture_paths=[],
            prior_spec_paths=[Path("a.spec.ts")],
        )
    )
    assert "No changes vs previous generation" in body


def test_read_prior_spec_paths_round_trip(tmp_path: Path) -> None:
    body = render_generated_plan_md(
        GeneratedPlanInputs(
            plan_id="x",
            run_id="x",
            target_url="x",
            flows=[],
            spec_paths=[Path("a.spec.ts"), Path("nested/b.spec.ts")],
            page_object_paths=[],
            fixture_paths=[],
        )
    )
    md = tmp_path / "plan.md"
    md.write_text(body, encoding="utf-8")
    prior = read_prior_spec_paths(md)
    assert sorted(p.as_posix() for p in prior) == ["a.spec.ts", "nested/b.spec.ts"]


def test_read_prior_spec_paths_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_prior_spec_paths(tmp_path / "nope.md") == []


def test_render_is_deterministic_for_same_input() -> None:
    ids = IdGenerator()
    inputs = GeneratedPlanInputs(
        plan_id="x",
        run_id="x",
        target_url="x",
        flows=[_flow(ids, name="a"), _flow(ids, name="b")],
        spec_paths=[Path("a.spec.ts")],
        page_object_paths=[],
        fixture_paths=[],
    )
    assert render_generated_plan_md(inputs) == render_generated_plan_md(inputs)
