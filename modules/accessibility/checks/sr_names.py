"""Normalise + detect missing accessible-name issues.

The accessible name for an interactive element is computed from the
ARIA chain (``aria-labelledby`` → ``aria-label`` → label text →
visible content → ``title`` → placeholder). When every fallback is
empty the element has no accessible name and screen readers cannot
announce it.

the documentation calls this out explicitly; the curated handful of rules
below is the deterministic Python mirror of the TS helper.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from modules.accessibility.models import AccessibleNameIssue

INTERACTIVE_ROLES: frozenset[str] = frozenset(
    {"button", "link", "textbox", "combobox", "checkbox", "radio", "switch", "menuitem"}
)


@dataclass(frozen=True)
class ElementSnapshot:
    """Minimal subset of a DOM element needed to compute an accessible name."""

    role: str
    selector: str
    aria_label: str = ""
    aria_labelledby_text: str = ""
    label_text: str = ""
    visible_text: str = ""
    title: str = ""
    placeholder: str = ""


def normalise_accessible_name_issues(
    raw: Iterable[Any],
) -> tuple[AccessibleNameIssue, ...]:
    """Coerce a sequence of raw dicts into typed records."""

    out: list[AccessibleNameIssue] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        selector = str(entry.get("selector") or "").strip()
        description = str(entry.get("description") or "").strip()
        if not selector or not description:
            continue
        out.append(
            AccessibleNameIssue(
                selector=selector,
                role=str(entry.get("role") or ""),
                description=description,
            )
        )
    return tuple(out)


def has_accessible_name(element: ElementSnapshot) -> bool:
    """Return True when the element carries a non-empty accessible name."""

    for value in (
        element.aria_labelledby_text,
        element.aria_label,
        element.label_text,
        element.visible_text,
        element.title,
    ):
        if value and value.strip():
            return True
    # `placeholder` is intentionally not a sufficient fallback —
    # CLAUDE §28 / the documentation: placeholders disappear on input, so
    # they fail accessible-name requirements.
    return False


def detect_missing_accessible_names(
    elements: Iterable[ElementSnapshot],
) -> tuple[AccessibleNameIssue, ...]:
    """Yield one issue per interactive element with no accessible name."""

    issues: list[AccessibleNameIssue] = []
    for element in elements:
        if element.role not in INTERACTIVE_ROLES:
            continue
        if has_accessible_name(element):
            continue
        issues.append(
            AccessibleNameIssue(
                selector=element.selector,
                role=element.role,
                description=(
                    f"{element.role!r} element has no computable accessible "
                    "name; screen readers cannot announce it."
                ),
            )
        )
    return tuple(issues)


__all__ = [
    "ElementSnapshot",
    "INTERACTIVE_ROLES",
    "detect_missing_accessible_names",
    "has_accessible_name",
    "normalise_accessible_name_issues",
]
