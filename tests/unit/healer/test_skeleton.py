"""Healer skeleton tests.

Asserts the public surface is shaped the way the rest of the
codebase consumes it (Analyzer pipeline, CLI, MCP). The Healer
returns proposals via a frozen dataclass facade and never mutates
its inputs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.analyzer.models import FailureSignal
from engine.healer import (
    Healer,
    HealerContext,
    HealerInputs,
    RepairProposal,
)


def _signal() -> FailureSignal:
    return FailureSignal(
        test_id="tests/sentinel/login.spec.ts:7",
        title="signs in with valid credentials",
        file="tests/sentinel/login.spec.ts",
        status="failed",
        duration_ms=1200,
        retries=0,
        module="functional",
    )


def test_healer_facade_returns_empty_tuple_when_no_inputs() -> None:
    healer = Healer()
    out = healer.propose(_signal(), HealerInputs(test_path=Path("a.spec.ts"), test_source=""))
    assert out == ()


def test_healer_returns_repair_proposal_tuple() -> None:
    healer = Healer()
    src = (
        "await page.waitForTimeout(2000);\nawait expect(page.getByRole('heading')).toBeVisible();\n"
    )
    out = healer.propose(
        _signal(),
        HealerInputs(test_path=Path("x.spec.ts"), test_source=src, wait_line=1),
    )
    assert len(out) == 1
    assert isinstance(out[0], RepairProposal)
    assert out[0].kind == "wait"


def test_healer_orders_proposals_deterministically() -> None:
    # Both wait + fixture proposals get returned; sorted by (kind, id).
    healer = Healer()
    src = (
        "await page.waitForTimeout(500);\n"
        "await expect(page.getByRole('button', { name: /next/i })).toBeVisible();\n"
        "const row = await seededRecord('user');\n"
    )
    out = healer.propose(
        _signal(),
        HealerInputs(
            test_path=Path("x.spec.ts"),
            test_source=src,
            wait_line=1,
            fixture_call_line=3,
            fixture_failure_kind="missing_entity",
        ),
    )
    kinds = [p.kind for p in out]
    assert kinds == sorted(kinds)


def test_healer_context_default_threshold() -> None:
    ctx = HealerContext()
    assert ctx.auto_apply_threshold == pytest.approx(0.9)


def test_healer_locator_path_with_full_context() -> None:
    from engine.healer.locator_repair import DomCandidate
    from engine.healer.models import LocatorDescriptor

    healer = Healer()
    src = (
        "import { test, expect } from '@playwright/test';\n"
        "test('signs in', async ({ page }) => {\n"
        "  await page.getByRole('button', { name: /sign in/i }).click();\n"
        "});\n"
    )
    proposals = healer.propose(
        _signal(),
        HealerInputs(
            test_path=Path("login.spec.ts"),
            test_source=src,
            locator_line=3,
            descriptor=LocatorDescriptor(
                role="button", accessible_name="Sign in", landmarks=("form",)
            ),
            dom_candidates=(
                DomCandidate(
                    role="button",
                    accessible_name="Sign in",
                    text="Sign in",
                    landmarks=("form",),
                ),
            ),
        ),
    )
    assert any(p.kind == "locator" for p in proposals)


def test_healer_fixture_path_emits_proposal() -> None:
    healer = Healer()
    src = "const row = await seededRecord('user');\n"
    proposals = healer.propose(
        _signal(),
        HealerInputs(
            test_path=Path("a.spec.ts"),
            test_source=src,
            fixture_call_line=1,
            fixture_failure_kind="missing_entity",
        ),
    )
    assert any(p.kind == "fixture" for p in proposals)


def test_healer_unknown_fixture_kind_is_ignored() -> None:
    healer = Healer()
    proposals = healer.propose(
        _signal(),
        HealerInputs(
            test_path=Path("a.spec.ts"),
            test_source="x = 1;\n",
            fixture_call_line=1,
            fixture_failure_kind="weather_too_hot",
        ),
    )
    assert proposals == ()
