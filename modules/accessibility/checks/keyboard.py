"""Normalise raw keyboard-check JSON into typed :class:`KeyboardIssue` records.

The TS subcommand emits raw dicts with the same field set; this helper
provides the Python-side validator + a small deterministic detector
used by the unit tests so the contract is checked on both runtimes.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from modules.accessibility.models import KeyboardCategory, KeyboardIssue

_VALID_CATEGORIES: frozenset[str] = frozenset(
    {"keyboard-navigation", "focus-trap", "focus-visible"}
)


def normalise_keyboard_issues(raw: Iterable[Any]) -> tuple[KeyboardIssue, ...]:
    """Coerce a sequence of raw dicts into typed :class:`KeyboardIssue` tuples."""

    out: list[KeyboardIssue] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        category_raw = entry.get("category")
        if not isinstance(category_raw, str) or category_raw not in _VALID_CATEGORIES:
            continue
        category: KeyboardCategory = category_raw  # type: ignore[assignment]
        description = str(entry.get("description") or "").strip()
        if not description:
            continue
        selector = str(entry.get("selector") or "")
        out.append(
            KeyboardIssue(
                category=category,
                selector=selector,
                description=description,
            )
        )
    return tuple(out)


def detect_focus_trap(
    *,
    focusables: int,
    can_escape_modal: bool,
    inside_modal: bool,
) -> KeyboardIssue | None:
    """Return a focus-trap issue when a modal traps focus.

    Used by the deterministic TS helper's mirrored Python tests:
    if a modal is open, has at least one focusable element, and the
    user cannot tab out, emit a finding. This is the same heuristic
    the TS helper applies.
    """

    if not inside_modal or focusables <= 0 or can_escape_modal:
        return None
    return KeyboardIssue(
        category="focus-trap",
        selector="[role='dialog'], .modal, [aria-modal='true']",
        description=(
            "Modal blocks keyboard focus: focus cannot escape via Tab "
            "or Escape after the modal opens."
        ),
    )


__all__ = ["detect_focus_trap", "normalise_keyboard_issues"]
