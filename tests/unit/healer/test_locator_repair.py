"""Locator repair tests.

Covers the confidence tiers documented in the task spec:

- Exact role + name + landmark → 0.95 (auto-apply candidate).
- Fuzzy name match → 0.7..0.75 (review-required at the default
 threshold of 0.9).
- Role-only match → 0.5 (review-required).
- No role match → no proposal.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.healer.locator_repair import (
    DomCandidate,
    LocatorRepairInputs,
    propose_locator_repair,
)
from engine.healer.models import LocatorDescriptor

SPEC_SRC = """\
import { test, expect } from '@playwright/test';

test('signs in', async ({ page }) => {
  await page.goto('/login');
  const btn = page.getByRole('button', { name: /sign in/i });
  await btn.click();
});
"""


def _inputs(*, candidates: list[DomCandidate]) -> LocatorRepairInputs:
    return LocatorRepairInputs(
        test_path=Path("tests/sentinel/login.spec.ts"),
        test_source=SPEC_SRC,
        locator_line=5,
        descriptor=LocatorDescriptor(
            role="button",
            accessible_name="Sign in",
            text="Sign in",
            landmarks=("main", "form"),
            tag_name="button",
        ),
        dom_candidates=candidates,
    )


def test_exact_role_name_landmark_match_yields_high_confidence() -> None:
    candidates = [
        DomCandidate(
            role="button",
            accessible_name="Sign in",
            text="Sign in",
            landmarks=("main", "form"),
            tag_name="button",
        )
    ]
    proposal = propose_locator_repair(_inputs(candidates=candidates))
    assert proposal is not None
    assert proposal.kind == "locator"
    assert proposal.confidence == pytest.approx(0.95)
    assert proposal.requires_human_review is False
    # The diff rewrites the name regex with the new accessible name.
    assert "Sign\\ in" in proposal.unified_diff or "Sign in" in proposal.unified_diff


def test_fuzzy_name_match_demotes_to_review_required() -> None:
    candidates = [
        DomCandidate(
            role="button",
            accessible_name="Log in",
            text="Log in",
            landmarks=("main", "form"),
            tag_name="button",
        )
    ]
    proposal = propose_locator_repair(_inputs(candidates=candidates))
    # "Sign in" vs "Log in" similarity ~0.43, so it falls through to
    # role-only match (0.5).
    assert proposal is not None
    assert proposal.confidence <= 0.75
    assert proposal.requires_human_review is True


def test_fuzzy_name_above_threshold_with_landmark_yields_0_75() -> None:
    candidates = [
        DomCandidate(
            role="button",
            accessible_name="Sign-in",  # high similarity vs "Sign in"
            text="Sign-in",
            landmarks=("main", "form"),
            tag_name="button",
        )
    ]
    proposal = propose_locator_repair(_inputs(candidates=candidates))
    assert proposal is not None
    assert proposal.confidence == pytest.approx(0.75)


def test_role_only_match_yields_0_5() -> None:
    candidates = [
        DomCandidate(
            role="button",
            accessible_name="Submit form",
            text="Submit form",
            landmarks=("aside",),
            tag_name="button",
        )
    ]
    proposal = propose_locator_repair(_inputs(candidates=candidates))
    assert proposal is not None
    assert proposal.confidence == pytest.approx(0.5)
    assert proposal.requires_human_review is True


def test_no_role_match_returns_none() -> None:
    candidates = [
        DomCandidate(
            role="link",
            accessible_name="Sign in",
            text="Sign in",
            landmarks=("nav",),
            tag_name="a",
        )
    ]
    assert propose_locator_repair(_inputs(candidates=candidates)) is None


def test_empty_candidates_returns_none() -> None:
    assert propose_locator_repair(_inputs(candidates=[])) is None


def test_invalid_locator_line_returns_none() -> None:
    inputs = LocatorRepairInputs(
        test_path=Path("tests/sentinel/login.spec.ts"),
        test_source=SPEC_SRC,
        locator_line=999,
        descriptor=LocatorDescriptor(role="button", accessible_name="Sign in", landmarks=("form",)),
        dom_candidates=[
            DomCandidate(
                role="button",
                accessible_name="Sign in",
                text="Sign in",
                landmarks=("form",),
            )
        ],
    )
    assert propose_locator_repair(inputs) is None


def test_line_without_getbyrole_returns_none() -> None:
    inputs = LocatorRepairInputs(
        test_path=Path("x.spec.ts"),
        test_source="const x = 1;\n",
        locator_line=1,
        descriptor=LocatorDescriptor(role="button", accessible_name="Save"),
        dom_candidates=[DomCandidate(role="button", accessible_name="Save")],
    )
    assert propose_locator_repair(inputs) is None


def test_deterministic_tie_break_by_name() -> None:
    candidates = [
        DomCandidate(role="button", accessible_name="Zeta"),
        DomCandidate(role="button", accessible_name="Alpha"),
        DomCandidate(role="button", accessible_name="Mu"),
    ]
    # No exact / landmark / fuzzy match — every candidate is role-only
    # at 0.5. Tie-break is alphabetical by accessible_name.
    proposal = propose_locator_repair(_inputs(candidates=candidates))
    assert proposal is not None
    assert "Alpha" in proposal.proposed_change


def test_returned_proposal_emits_unified_diff_header() -> None:
    candidates = [
        DomCandidate(
            role="button",
            accessible_name="Sign in",
            text="Sign in",
            landmarks=("main", "form"),
        )
    ]
    proposal = propose_locator_repair(_inputs(candidates=candidates))
    assert proposal is not None
    assert proposal.unified_diff.startswith("--- tests/sentinel/login.spec.ts")
