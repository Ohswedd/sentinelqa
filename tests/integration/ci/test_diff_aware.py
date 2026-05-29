"""Integration tests for diff-aware test selection (task 17.05).

Covers the pure-helper surface; CLI-level tests live in
``tests/integration/cli/test_ci_diff.py`` so they pick up the CLI
conftest fixtures.
"""

from __future__ import annotations

from engine.ci.diff_aware import select_from_files


def test_small_diff_produces_small_subset() -> None:
    sel = select_from_files(
        diff_range="origin/main...HEAD",
        changed_files=["app/login/page.tsx"],
    )
    grep = sel.grep()
    assert grep is not None
    assert sel.fallback_to_full is False
    # Smoke + p1 + one route tag → 3 alternatives joined by `|`.
    assert grep.count("|") == 2


def test_large_diff_falls_back_to_full() -> None:
    sel = select_from_files(
        diff_range="origin/main...HEAD",
        changed_files=[f"src/file{i}.ts" for i in range(60)],
    )
    assert sel.fallback_to_full is True
    assert sel.grep() is None
