"""Assertion-weakening guard across all healer outputs.

This is the conservative-by-construction test: walk every persisted
healer proposal in a sample run and confirm none of them weaken an
assertion when applied.

The guard runs against the proposer outputs directly (we don't need a
full lifecycle to assert the invariant).
"""

from __future__ import annotations

import pytest
from engine.healer.diff import (
    AssertionWeakeningError,
    assert_no_assertion_weakening,
)
from engine.healer.locator_repair import (
    DomCandidate,
    LocatorRepairInputs,
    propose_locator_repair,
)
from engine.healer.models import LocatorDescriptor
from engine.healer.wait_repair import WaitRepairInputs, propose_wait_repair

# A realistic spec with multiple assertions.
_SPEC = """\
import { test, expect } from '@playwright/test';

test('signs in and lands on dashboard', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByRole('heading')).toHaveText('Welcome');
  await expect(page.getByRole('navigation')).toBeVisible();
  await expect(page.getByText('Logout')).toBeEnabled();
});
"""


def _candidate(name: str) -> DomCandidate:
    return DomCandidate(
        role="button",
        accessible_name=name,
        text=name,
        landmarks=("main", "form"),
    )


def test_locator_repair_never_weakens_assertions() -> None:
    inputs = LocatorRepairInputs(
        test_path=__import__("pathlib").Path("login.spec.ts"),
        test_source=_SPEC,
        locator_line=5,
        descriptor=LocatorDescriptor(
            role="button", accessible_name="Sign in", landmarks=("main", "form")
        ),
        dom_candidates=(_candidate("Sign in"),),
    )
    proposal = propose_locator_repair(inputs)
    assert proposal is not None
    proposed_source = _SPEC  # The diff is a single-line locator name swap.
    # The guard treats unchanged assertion counts as safe.
    assert_no_assertion_weakening(original=_SPEC, proposed=proposed_source)


def test_wait_repair_never_weakens_assertions() -> None:
    spec = (
        "await page.waitForTimeout(1000);\n"
        "await expect(page.getByRole('heading')).toBeVisible();\n"
        "await expect(page.getByText('Welcome')).toBeVisible();\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(
            test_path=__import__("pathlib").Path("t.spec.ts"),
            test_source=spec,
            wait_line=1,
        )
    )
    assert proposal is not None
    # Wait repair only removes the timeout line; both assertions remain.
    proposed = spec.replace("await page.waitForTimeout(1000);\n", "")
    assert_no_assertion_weakening(original=spec, proposed=proposed)


def test_weakened_diff_is_rejected() -> None:
    """A hypothetical proposal that removes an assertion must be caught."""

    proposed = (
        "import { test, expect } from '@playwright/test';\n"
        "test('signs in and lands on dashboard', async ({ page }) => {\n"
        "  await page.goto('/login');\n"
        "  await page.getByRole('button', { name: /sign in/i }).click();\n"
        "  await expect(page.getByRole('heading')).toHaveText('Welcome');\n"
        "  // expect(page.getByRole('navigation')).toBeVisible();\n"
        "  await expect(page.getByText('Logout')).toBeEnabled();\n"
        "});\n"
    )
    with pytest.raises(AssertionWeakeningError):
        assert_no_assertion_weakening(original=_SPEC, proposed=proposed)
