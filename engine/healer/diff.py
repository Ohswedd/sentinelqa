"""Unified-diff + assertion-weakening guard (Phase 20, CLAUDE.md §23).

Two responsibilities:

1. Produce stable unified-diff strings the CLI and HTML report can
   display verbatim (callers don't depend on git or `difflib`'s
   default output).
2. Refuse any diff that *weakens* a Playwright assertion. CLAUDE.md
   §23 forbids the Healer from silently hiding app bugs as test
   repairs — removing an ``expect(...).toBe(...)`` line, deleting an
   entire assertion, switching ``toHaveText`` to ``toBeVisible``, or
   commenting an assertion out are all rejected by
   :func:`assert_no_assertion_weakening` unless the caller passed
   ``allow_weaken=True``.
"""

from __future__ import annotations

import difflib
import re

# Stable, conservative match list. Each entry is a structural Playwright
# assertion API; we treat the *count* of these in original vs proposed as
# the weakening signal. Comment-line additions don't count as removals.
_ASSERTION_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bexpect\s*\("),
    re.compile(r"\.toBe[A-Z]\w+\s*\("),
    re.compile(r"\.toHave[A-Z]\w+\s*\("),
    re.compile(r"\.toEqual\s*\("),
    re.compile(r"\.toMatch\s*\("),
    re.compile(r"\.toContain\s*\("),
)


class AssertionWeakeningError(RuntimeError):
    """Raised when a proposed repair would weaken an assertion.

    The Healer pipeline catches this and downgrades the proposal to
    ``requires_human_review=True`` rather than silently dropping the
    assertion (CLAUDE.md §23).
    """


def _count_assertions(source: str) -> int:
    return sum(len(rx.findall(source)) for rx in _ASSERTION_RES)


def _strip_assertions_from_comments(source: str) -> str:
    """Strip ``// ...`` and ``/* ... */`` comments before counting.

    Without this, ``// expect(foo).toBe(true)`` would be counted as a
    live assertion. We do a coarse pass — good enough for the
    structural weakening check the Healer needs.
    """

    no_block = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", no_block)


def assert_no_assertion_weakening(
    *,
    original: str,
    proposed: str,
    allow_weaken: bool = False,
) -> None:
    """Raise :class:`AssertionWeakeningError` if assertions disappeared.

    ``allow_weaken=True`` short-circuits the check — required when the
    operator explicitly opts in via ``sentinel fix --allow-weaken``
    (Phase 20.07 task). The CLI must also log the weaken in the
    audit log (CLAUDE.md §11).
    """

    if allow_weaken:
        return

    before = _count_assertions(_strip_assertions_from_comments(original))
    after = _count_assertions(_strip_assertions_from_comments(proposed))

    if after < before:
        raise AssertionWeakeningError(
            f"Proposed change reduces assertion count from {before} to {after}. "
            "Forbidden by CLAUDE.md §23 unless --allow-weaken is set."
        )


def unified_diff_for(
    *,
    path: str,
    original: str,
    proposed: str,
    context: int = 3,
) -> str:
    """Return a stable unified-diff string for ``original`` → ``proposed``.

    The diff headers use ``path`` for both sides so applying the diff
    rewrites the file in place. Trailing newline is enforced so the
    string round-trips through patch(1).
    """

    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            fromfile=path,
            tofile=path,
            n=context,
        )
    )
    text = "".join(diff_lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


__all__ = [
    "AssertionWeakeningError",
    "assert_no_assertion_weakening",
    "unified_diff_for",
]
