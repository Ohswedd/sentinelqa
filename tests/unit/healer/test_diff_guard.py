"""Phase 20.09 — Assertion-weakening guard tests."""

from __future__ import annotations

import pytest
from engine.healer.diff import (
    AssertionWeakeningError,
    assert_no_assertion_weakening,
    unified_diff_for,
)


def test_unified_diff_emits_standard_header() -> None:
    diff = unified_diff_for(path="a.ts", original="x\n", proposed="y\n")
    assert diff.startswith("--- a.ts")
    assert "+++ a.ts" in diff
    assert diff.endswith("\n")


def test_empty_change_emits_empty_diff() -> None:
    diff = unified_diff_for(path="a.ts", original="x\n", proposed="x\n")
    assert diff == ""


def test_no_weakening_when_count_preserved() -> None:
    original = "expect(x).toBe(1);\nexpect(y).toHaveText('ok');\n"
    proposed = "expect(x).toBe(2);\nexpect(y).toHaveText('done');\n"
    # No exception means the guard accepted the proposal.
    assert_no_assertion_weakening(original=original, proposed=proposed)


def test_weakening_raises_when_assertion_removed() -> None:
    original = "expect(x).toBe(true);\nexpect(y).toHaveText('ok');\n"
    proposed = "expect(x).toBe(true);\n"
    with pytest.raises(AssertionWeakeningError):
        assert_no_assertion_weakening(original=original, proposed=proposed)


def test_weakening_with_allow_flag_passes_through() -> None:
    original = "expect(x).toBe(true);\nexpect(y).toBe(true);\n"
    proposed = "expect(x).toBe(true);\n"
    # No exception when allow_weaken=True.
    assert_no_assertion_weakening(original=original, proposed=proposed, allow_weaken=True)


def test_commenting_out_assertion_is_weakening() -> None:
    original = "expect(x).toBe(true);\nexpect(y).toBe(false);\n"
    proposed = "expect(x).toBe(true);\n// expect(y).toBe(false);\n"
    with pytest.raises(AssertionWeakeningError):
        assert_no_assertion_weakening(original=original, proposed=proposed)


def test_block_comment_around_assertion_is_weakening() -> None:
    original = "expect(x).toBe(true);\nexpect(y).toBe(false);\n"
    proposed = "expect(x).toBe(true);\n/* expect(y).toBe(false); */\n"
    with pytest.raises(AssertionWeakeningError):
        assert_no_assertion_weakening(original=original, proposed=proposed)


def test_adding_assertions_is_not_weakening() -> None:
    original = "expect(x).toBe(true);\n"
    proposed = "expect(x).toBe(true);\n" "expect(y).toBe(true);\n" "expect(z).toBe(true);\n"
    assert_no_assertion_weakening(original=original, proposed=proposed)
