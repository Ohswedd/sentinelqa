"""Wait-condition replacement tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.healer.wait_repair import WaitRepairInputs, propose_wait_repair


def test_wait_followed_by_to_be_visible_yields_high_confidence() -> None:
    src = (
        "  await page.waitForTimeout(2000);\n"
        "  await expect(page.getByRole('heading', { name: /welcome/i })).toBeVisible();\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(
            test_path=Path("t.spec.ts"),
            test_source=src,
            wait_line=1,
        )
    )
    assert proposal is not None
    assert proposal.kind == "wait"
    assert proposal.confidence == pytest.approx(0.9)
    assert proposal.requires_human_review is False
    # The diff removes the timeout line.
    assert "await page.waitForTimeout" in proposal.unified_diff
    assert proposal.unified_diff.startswith("--- t.spec.ts")


def test_wait_followed_by_to_have_text_yields_high_confidence() -> None:
    src = (
        "  await page.waitForTimeout(500);\n"
        "  await expect(page.getByTestId('status')).toHaveText('Done');\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source=src, wait_line=1)
    )
    assert proposal is not None
    assert proposal.confidence == pytest.approx(0.9)


def test_wait_followed_by_other_matcher_demotes_to_review() -> None:
    src = (
        "  await page.waitForTimeout(500);\n"
        "  await expect(page.getByLabel('email')).toHaveValue('user@example.com');\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source=src, wait_line=1)
    )
    assert proposal is not None
    assert proposal.confidence == pytest.approx(0.6)
    assert proposal.requires_human_review is True


def test_wait_with_no_following_expect_yields_low_confidence_removal() -> None:
    src = "  await page.waitForTimeout(1000);\n"
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source=src, wait_line=1)
    )
    assert proposal is not None
    assert proposal.confidence == pytest.approx(0.3)
    assert proposal.requires_human_review is True


def test_non_wait_line_returns_none() -> None:
    src = "  const x = await page.title();\n"
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source=src, wait_line=1)
    )
    assert proposal is None


def test_invalid_line_returns_none() -> None:
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source="", wait_line=5)
    )
    assert proposal is None


def test_scope_boundary_stops_search() -> None:
    """An assertion in a different test block should not anchor the repair."""

    src = (
        "test('a', async ({ page }) => {\n"
        "  await page.waitForTimeout(500);\n"
        "});\n"
        "\n"
        "test('b', async ({ page }) => {\n"
        "  await expect(page.getByRole('heading')).toBeVisible();\n"
        "});\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source=src, wait_line=2)
    )
    assert proposal is not None
    # The closing `});` should have stopped the search before the next test.
    assert proposal.confidence == pytest.approx(0.3)


def test_fractional_timeout_argument_is_parsed() -> None:
    src = (
        "  await page.waitForTimeout(1.5);\n"
        "  await expect(page.getByRole('heading')).toBeVisible();\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source=src, wait_line=1)
    )
    assert proposal is not None
    assert proposal.confidence == pytest.approx(0.9)


def test_blank_lines_are_skipped_when_searching_for_assertion() -> None:
    src = (
        "  await page.waitForTimeout(500);\n"
        "\n"
        "  \n"
        "  await expect(page.getByRole('heading')).toBeVisible();\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source=src, wait_line=1)
    )
    assert proposal is not None
    assert proposal.confidence == pytest.approx(0.9)


def test_describe_boundary_stops_search() -> None:
    src = (
        "describe('outer', () => {\n"
        "  await page.waitForTimeout(500);\n"
        "describe('next', () => {\n"
        "  await expect(page.getByRole('heading')).toBeVisible();\n"
        "});\n"
    )
    proposal = propose_wait_repair(
        WaitRepairInputs(test_path=Path("t.spec.ts"), test_source=src, wait_line=2)
    )
    assert proposal is not None
    assert proposal.confidence == pytest.approx(0.3)
