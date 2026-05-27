"""Sanity test: the SentinelQA codebase never registers stealth/evasion flags.

Phase 02 (CLI) will define real argument parsers; until then this test
scans the source tree for any string that looks like a stealth flag and
fails immediately if one shows up. The intent is to make it impossible to
accidentally re-introduce a forbidden capability later.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Substrings that, if present anywhere outside this test, indicate someone
# tried to wire a stealth/evasion path. We keep the list narrow so noisy
# words like "bypass" inside docstrings of the forbidden-features module
# can still be referenced (those live in tests/ for the test name, and in
# engine/policy/forbidden_features.py as denied items — both are allowed).
FORBIDDEN_FLAG_LITERALS: tuple[str, ...] = (
    "--stealth",
    "--evade",
    "--evasion",
    "--undetectable",
    "--rotate-proxies",
    "--spoof-fingerprint",
)

ALLOWED_PATHS = {
    Path("engine/policy/forbidden_features.py"),
    Path("plans"),
    Path("docs/adr"),
    Path("docs/dev"),
    Path("docs/user"),
    # Tests for the forbidden-features registry are allowed to reference
    # the literals — they exist precisely to assert the registry's content.
    Path("tests/security/test_no_stealth_flags.py"),
    Path("tests/unit/policy/test_forbidden_features.py"),
    Path("PRD.md"),
    Path("CLAUDE.md"),
}


def _is_allowed(path: Path) -> bool:
    for allowed in ALLOWED_PATHS:
        try:
            path.relative_to(allowed)
        except ValueError:
            continue
        return True
    return False


@pytest.mark.parametrize("flag", FORBIDDEN_FLAG_LITERALS)
def test_no_stealth_flag_strings_in_engine_or_apps(flag: str) -> None:
    """Forbidden flags must never appear outside the deny-list itself."""

    repo = Path(".")
    for path in repo.rglob("*.py"):
        # Skip third-party content and the explicit deny-list / docs.
        rel = path.relative_to(repo)
        parts = rel.parts
        if any(p in {".venv", "node_modules", ".pytest_cache", ".mypy_cache"} for p in parts):
            continue
        if _is_allowed(rel):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert flag not in text, (
            f"Forbidden stealth flag {flag!r} found in {path}; CLAUDE.md §6 "
            f"forbids stealth/evasion paths anywhere in the product."
        )
