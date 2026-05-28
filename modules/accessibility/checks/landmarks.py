"""Normalise + detect landmark structure issues.

Landmark roles SentinelQA checks for on every full page (PRD §10.4):

- ``main``   exactly one required.
- ``header`` recommended.
- ``nav``    recommended.
- ``footer`` recommended.

Missing landmarks are reported as ``missing-landmark`` (severity
medium). More than one ``main`` is reported as ``duplicate-landmark``
(severity low).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from modules.accessibility.models import LandmarkCategory, LandmarkIssue

REQUIRED_LANDMARKS: tuple[str, ...] = ("main",)
RECOMMENDED_LANDMARKS: tuple[str, ...] = ("header", "nav", "footer")
_VALID_CATEGORIES: frozenset[str] = frozenset({"missing-landmark", "duplicate-landmark"})


def normalise_landmark_issues(raw: Iterable[Any]) -> tuple[LandmarkIssue, ...]:
    """Coerce a sequence of raw dicts into typed :class:`LandmarkIssue` tuples."""

    out: list[LandmarkIssue] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        category_raw = entry.get("category")
        if not isinstance(category_raw, str) or category_raw not in _VALID_CATEGORIES:
            continue
        category: LandmarkCategory = category_raw  # type: ignore[assignment]
        landmark = str(entry.get("landmark") or "").strip()
        description = str(entry.get("description") or "").strip()
        if not landmark or not description:
            continue
        out.append(
            LandmarkIssue(
                category=category,
                landmark=landmark,
                description=description,
            )
        )
    return tuple(out)


def detect_landmark_issues(landmark_counts: Mapping[str, int]) -> tuple[LandmarkIssue, ...]:
    """Apply the required/recommended landmark policy to a count map."""

    issues: list[LandmarkIssue] = []
    for landmark in REQUIRED_LANDMARKS:
        count = landmark_counts.get(landmark, 0)
        if count == 0:
            issues.append(
                LandmarkIssue(
                    category="missing-landmark",
                    landmark=landmark,
                    description=f"No <{landmark}> landmark found on the page.",
                )
            )
        elif count > 1:
            issues.append(
                LandmarkIssue(
                    category="duplicate-landmark",
                    landmark=landmark,
                    description=(
                        f"Page contains {count} <{landmark}> landmarks; " "exactly one is required."
                    ),
                )
            )
    for landmark in RECOMMENDED_LANDMARKS:
        if landmark_counts.get(landmark, 0) == 0:
            issues.append(
                LandmarkIssue(
                    category="missing-landmark",
                    landmark=landmark,
                    description=(f"No <{landmark}> landmark found on the page (recommended)."),
                )
            )
    return tuple(issues)


__all__ = [
    "RECOMMENDED_LANDMARKS",
    "REQUIRED_LANDMARKS",
    "detect_landmark_issues",
    "normalise_landmark_issues",
]
