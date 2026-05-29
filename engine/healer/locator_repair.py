"""Locator repair (Phase 20.02).

Given a failed locator + the descriptor captured when the spec was
written, search the new DOM for the closest semantic match. The
algorithm is deterministic and confidence-tiered per CLAUDE.md §23 /
PRD §9.6:

- Exact role + name match in the same landmark → ``0.95``.
- Same role + fuzzy name match (string-similarity > 0.8) → ``0.75``.
- Same role only → ``0.5``.

Anything below the auto-apply threshold (default ``0.9``, configurable)
is returned with ``requires_human_review=True``.

The repair body is a single-line replacement: it rewrites
``page.getByRole('button', { name: /sign in/i })`` to
``page.getByRole('button', { name: /log in/i })`` when the page now
labels that button "Log in". For role-only matches we cannot guess a
name; we instead surface the candidate's text as a comment for the
reviewer.

DOM input is a normalized list of :class:`DomCandidate` records the
caller harvests from a fresh discovery pass; the Healer does not own
the discovery code path.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from engine.domain.evidence import Evidence
from engine.domain.ids import IdGenerator
from engine.healer.diff import assert_no_assertion_weakening, unified_diff_for
from engine.healer.models import LocatorDescriptor, RepairProposal


@dataclass(frozen=True)
class DomCandidate:
    """One semantic-locator candidate scraped from the new DOM.

    Mirrors what :func:`engine.discovery.dom_map.DomMapBuilder` extracts
    plus the ARIA landmarks for context-aware scoring.
    """

    role: str
    accessible_name: str
    text: str = ""
    landmarks: tuple[str, ...] = ()
    tag_name: str | None = None


@dataclass(frozen=True)
class LocatorRepairInputs:
    """Inputs needed to propose one locator repair."""

    test_path: Path
    """Absolute or run-rooted path to the failing spec."""

    test_source: str
    """Current contents of the spec — read once by the caller."""

    locator_line: int
    """1-based line where the failing ``page.getBy...`` call appears."""

    descriptor: LocatorDescriptor
    """Descriptor captured the last time the spec was healthy."""

    dom_candidates: Sequence[DomCandidate]
    """Fresh semantic candidates scraped from the page after the failure."""


_GETBYROLE_RE = re.compile(
    r"""getByRole\(\s*['"](?P<role>[a-zA-Z]+)['"]\s*,\s*\{\s*name:\s*(?P<name>(?:/[^/]*/[a-zA-Z]*|'[^']*'|"[^"]*"))\s*\}\s*\)""",
)


def _string_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=a.lower(), b=b.lower()).ratio()


def _score_candidate(
    descriptor: LocatorDescriptor,
    candidate: DomCandidate,
) -> tuple[float, str]:
    """Return ``(confidence, rationale)`` for one candidate match."""

    if descriptor.role is None or candidate.role != descriptor.role:
        return (0.0, "role mismatch")

    same_name = (
        descriptor.accessible_name is not None
        and candidate.accessible_name == descriptor.accessible_name
    )
    same_landmark = (
        bool(descriptor.landmarks)
        and bool(candidate.landmarks)
        and descriptor.landmarks[-1] == candidate.landmarks[-1]
    )

    if same_name and same_landmark:
        return (0.95, "exact role + name match in same landmark")
    if same_name:
        return (0.9, "exact role + name match (landmark differs)")

    if descriptor.accessible_name is None:
        return (0.5, "role match only; descriptor had no accessible name")

    similarity = _string_similarity(descriptor.accessible_name, candidate.accessible_name)
    if similarity >= 0.8 and same_landmark:
        return (0.75, f"role match + fuzzy name match in same landmark ({similarity:.2f})")
    if similarity >= 0.8:
        return (0.7, f"role match + fuzzy name match ({similarity:.2f})")

    return (0.5, "role match only")


def _best_candidate(
    descriptor: LocatorDescriptor,
    candidates: Sequence[DomCandidate],
) -> tuple[DomCandidate | None, float, str]:
    """Pick the highest-scoring candidate. Deterministic tie-break by name."""

    scored: list[tuple[float, str, DomCandidate]] = []
    for candidate in candidates:
        confidence, rationale = _score_candidate(descriptor, candidate)
        if confidence > 0.0:
            scored.append((confidence, rationale, candidate))
    if not scored:
        return (None, 0.0, "no candidate shares the descriptor's role")
    # Sort by (-confidence, accessible_name) for determinism.
    scored.sort(key=lambda item: (-item[0], item[2].accessible_name))
    confidence, rationale, candidate = scored[0]
    return (candidate, confidence, rationale)


def _name_arg_literal(name: str) -> str:
    """Render a string as a Playwright-compatible name regex literal.

    We always emit ``/.../i`` so casing flexibility is preserved, matching
    Phase 04's generated specs (CLAUDE.md §21).
    """

    escaped = re.escape(name)
    return f"/{escaped}/i"


def _replace_locator_in_line(line: str, *, new_name: str) -> tuple[str, bool]:
    """Replace the ``name:`` argument of the first ``getByRole`` on ``line``.

    Returns ``(new_line, replaced?)``. When no match is found the
    original line is returned unchanged.
    """

    match = _GETBYROLE_RE.search(line)
    if match is None:
        return (line, False)
    start, end = match.span("name")
    new_arg = _name_arg_literal(new_name)
    return (line[:start] + new_arg + line[end:], True)


def propose_locator_repair(
    inputs: LocatorRepairInputs,
    *,
    id_generator: IdGenerator | None = None,
    auto_apply_threshold: float = 0.9,
) -> RepairProposal | None:
    """Propose a single locator repair, or ``None`` when nothing fits.

    The function is pure: no I/O, no clocks. The caller persists the
    proposal (Phase 20.05 writer).
    """

    if not inputs.dom_candidates:
        return None

    candidate, confidence, rationale = _best_candidate(inputs.descriptor, inputs.dom_candidates)
    if candidate is None or confidence <= 0.0:
        return None

    lines = inputs.test_source.splitlines(keepends=True)
    if inputs.locator_line < 1 or inputs.locator_line > len(lines):
        return None
    target_line = lines[inputs.locator_line - 1]
    new_line, replaced = _replace_locator_in_line(target_line, new_name=candidate.accessible_name)
    if not replaced:
        return None

    proposed_lines = list(lines)
    proposed_lines[inputs.locator_line - 1] = new_line
    proposed_source = "".join(proposed_lines)

    # Locator repairs never touch assertions — but we still call the
    # weakening guard so a malformed regex replacement that accidentally
    # truncates a line stays observable.
    assert_no_assertion_weakening(
        original=inputs.test_source,
        proposed=proposed_source,
        allow_weaken=False,
    )

    diff = unified_diff_for(
        path=str(inputs.test_path),
        original=inputs.test_source,
        proposed=proposed_source,
    )

    gen = id_generator or IdGenerator()
    requires_review = confidence < auto_apply_threshold

    return RepairProposal(
        id=gen.new("RPR"),
        kind="locator",
        target_test=str(inputs.test_path),
        target_test_line=inputs.locator_line,
        original_behavior=target_line.rstrip("\n"),
        proposed_change=new_line.rstrip("\n"),
        confidence=confidence,
        reason=(
            f"Locator no longer matches. Descriptor: role={inputs.descriptor.role!r}, "
            f"name={inputs.descriptor.accessible_name!r}. Best new match: "
            f"name={candidate.accessible_name!r} ({rationale})."
        ),
        evidence=(
            Evidence(
                id=gen.new("EVD"),
                type="source_ref",
                path=inputs.test_path,
            ),
        ),
        requires_human_review=requires_review,
        unified_diff=diff,
        descriptor=LocatorDescriptor(
            role=candidate.role,
            accessible_name=candidate.accessible_name,
            text=candidate.text or None,
            landmarks=tuple(candidate.landmarks),
            tag_name=candidate.tag_name,
        ),
    )


__all__ = [
    "DomCandidate",
    "LocatorRepairInputs",
    "propose_locator_repair",
]
