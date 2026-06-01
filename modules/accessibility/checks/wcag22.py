"""Deterministic WCAG 2.2 success-criterion checks ( / ADR-0046).

axe-core 4.10 covers most of WCAG 2.1 (the ``wcag21*`` tags) but only
some of the new 2.2 SCs, and several are page-shape dependent in ways
that axe's rule engine struggles with. This module ships the five
checks calls out:

- ``2.4.11`` Focus Not Obscured (Minimum) — bounding-box overlap test
 between each focusable element and any element with sticky / fixed
 positioning (typically a sticky header).
- ``2.5.7`` Dragging Movements — drag-only UI (``cursor: grab``,
 ``draggable=true``) with no documented keyboard alternative.
- ``2.5.8`` Target Size (Minimum) — clickable elements with a bounding
 box smaller than 24 x 24 CSS px (and no exception applies).
- ``3.3.7`` Redundant Entry — heuristic: forms that ask for the same
 information twice within one logical flow.
- ``3.3.8`` Accessible Authentication (Minimum) — login flows that
 require cognitive function tests (CAPTCHA puzzles) with no
 alternative.

Every check accepts simple, deterministic Python inputs (typed
``TypedDict`` shapes, primitives, or named tuples) so the same logic
can be exercised from unit tests and from the TS runtime's serialised
DOM probes without DOM dependencies.

CLAUDE §28 / wording rule: descriptions begin with
"Automated WCAG 2.2 check found" — never "your app is WCAG 2.2
compliant".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from modules.accessibility.models import Wcag22Issue

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WCAG22_TARGET_SIZE_MIN_PX: int = 24
"""WCAG 2.2 SC 2.5.8 Target Size (Minimum) — 24 CSS pixels."""


_DRAGGABLE_CURSORS: frozenset[str] = frozenset({"grab", "grabbing", "move", "all-scroll"})

_AUTO_PREFIX = "Automated WCAG 2.2 check found"


# ---------------------------------------------------------------------------
# Input shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundingBox:
    """A CSS-pixel bounding box (top-left origin)."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)


def _intersects(a: BoundingBox, b: BoundingBox) -> bool:
    if a.width <= 0 or a.height <= 0 or b.width <= 0 or b.height <= 0:
        return False
    if a.right <= b.x or b.right <= a.x:
        return False
    return not (a.bottom <= b.y or b.bottom <= a.y)


@dataclass(frozen=True)
class FocusableElement:
    """A focusable DOM element described by selector + bounding box."""

    selector: str
    box: BoundingBox


_PositionLiteral = Literal["sticky", "fixed"]


@dataclass(frozen=True)
class StickyOverlay:
    """A sticky / fixed element that may occlude focused content."""

    selector: str
    box: BoundingBox
    position: _PositionLiteral = "sticky"


@dataclass(frozen=True)
class ClickableElement:
    """A clickable target described by tag + role + box.

    ``inline`` flags inline links inside paragraphs (the spec's
    "inline text link" exception applies, so 2.5.8 is waived).
    ``user_agent_default`` marks controls rendered with default UA
    styling (browser-supplied checkboxes etc. — also waived).
    """

    selector: str
    box: BoundingBox
    tag: str = ""
    role: str = ""
    inline: bool = False
    user_agent_default: bool = False
    has_keyboard_alternative: bool = False


@dataclass(frozen=True)
class DraggableElement:
    """An element flagged as a drag handle."""

    selector: str
    cursor: str = ""
    draggable_attr: bool = False
    has_keyboard_alternative: bool = False


@dataclass(frozen=True)
class FormField:
    """One input/select/textarea on a page in a multi-step flow."""

    selector: str
    step: int
    name: str
    label: str = ""
    autocomplete: str = ""
    purpose: str = ""
    """Optional logical purpose tag — when set, the redundant-entry
    detector groups by purpose rather than the heuristic
    ``name``/``label``/``autocomplete`` triple.
    """


@dataclass(frozen=True)
class AuthChallenge:
    """A cognitive challenge surfaced by an auth flow."""

    selector: str
    kind: str
    """Free-form label: ``image-captcha``, ``puzzle``, ``recaptcha-v2``."""

    has_alternative: bool = False
    """True when the flow offers an alternative for users who cannot
    solve cognitive function tests (TOTP, passkey, magic link, etc.).
    """


# ---------------------------------------------------------------------------
# Check: 2.4.11 Focus Not Obscured (Minimum)
# ---------------------------------------------------------------------------


def detect_focus_obscured(
    focusables: Iterable[FocusableElement],
    overlays: Iterable[StickyOverlay],
) -> tuple[Wcag22Issue, ...]:
    """Flag focusable elements that intersect a sticky/fixed overlay."""

    overlay_list = tuple(overlays)
    issues: list[Wcag22Issue] = []
    for element in focusables:
        for overlay in overlay_list:
            if element.selector == overlay.selector:
                continue
            if _intersects(element.box, overlay.box):
                issues.append(
                    Wcag22Issue(
                        category="focus-obscured",
                        success_criterion="2.4.11",
                        selector=element.selector,
                        description=(
                            f"{_AUTO_PREFIX}: focusable element {element.selector!r} "
                            f"is occluded by sticky element {overlay.selector!r} "
                            "when focused (SC 2.4.11 Focus Not Obscured (Minimum))."
                        ),
                    )
                )
                break
    return tuple(issues)


# ---------------------------------------------------------------------------
# Check: 2.5.7 Dragging Movements
# ---------------------------------------------------------------------------


def detect_dragging_movements(
    draggables: Iterable[DraggableElement],
) -> tuple[Wcag22Issue, ...]:
    """Flag drag-only UI without a documented keyboard alternative."""

    issues: list[Wcag22Issue] = []
    for element in draggables:
        cursor = (element.cursor or "").strip().lower()
        is_drag_handle = element.draggable_attr or (cursor in _DRAGGABLE_CURSORS)
        if not is_drag_handle:
            continue
        if element.has_keyboard_alternative:
            continue
        why = _drag_reason(element)
        issues.append(
            Wcag22Issue(
                category="dragging-movements",
                success_criterion="2.5.7",
                selector=element.selector,
                description=(
                    f"{_AUTO_PREFIX}: element {element.selector!r} {why} "
                    "but has no documented keyboard alternative "
                    "(SC 2.5.7 Dragging Movements)."
                ),
            )
        )
    return tuple(issues)


def _drag_reason(element: DraggableElement) -> str:
    if element.draggable_attr and element.cursor:
        return f"is marked draggable=true and styled cursor={element.cursor!r}"
    if element.draggable_attr:
        return "is marked draggable=true"
    return f"is styled cursor={element.cursor!r}"


# ---------------------------------------------------------------------------
# Check: 2.5.8 Target Size (Minimum)
# ---------------------------------------------------------------------------


def detect_target_size(
    clickables: Iterable[ClickableElement],
    *,
    minimum_px: int = WCAG22_TARGET_SIZE_MIN_PX,
) -> tuple[Wcag22Issue, ...]:
    """Flag clickable targets smaller than ``minimum_px`` x ``minimum_px``.

    Exceptions per SC 2.5.8 (the ones our determinstic check honors):

    - ``inline`` — inline links in flowing text are exempt.
    - ``user_agent_default`` — UA-styled native controls are exempt.
    """

    issues: list[Wcag22Issue] = []
    for element in clickables:
        if element.inline or element.user_agent_default:
            continue
        width = element.box.width
        height = element.box.height
        if width <= 0 or height <= 0:
            continue
        if width >= minimum_px and height >= minimum_px:
            continue
        issues.append(
            Wcag22Issue(
                category="target-size-min",
                success_criterion="2.5.8",
                selector=element.selector,
                description=(
                    f"{_AUTO_PREFIX}: clickable element {element.selector!r} "
                    f"is {width:g}x{height:g} CSS px; "
                    f"SC 2.5.8 requires a minimum of {minimum_px}x{minimum_px} CSS px."
                ),
            )
        )
    return tuple(issues)


# ---------------------------------------------------------------------------
# Check: 3.3.7 Redundant Entry
# ---------------------------------------------------------------------------


def detect_redundant_entry(fields: Iterable[FormField]) -> tuple[Wcag22Issue, ...]:
    """Heuristic: same logical field asked for twice across steps."""

    seen: dict[str, FormField] = {}
    issues: list[Wcag22Issue] = []
    for field in fields:
        key = _redundant_key(field)
        if not key:
            continue
        prior = seen.get(key)
        if prior is not None and prior.step != field.step:
            issues.append(
                Wcag22Issue(
                    category="redundant-entry",
                    success_criterion="3.3.7",
                    selector=field.selector,
                    description=(
                        f"{_AUTO_PREFIX}: field {field.selector!r} (step {field.step}) "
                        f"asks for the same information as {prior.selector!r} "
                        f"(step {prior.step}) (SC 3.3.7 Redundant Entry)."
                    ),
                )
            )
            continue
        if prior is None:
            seen[key] = field
    return tuple(issues)


def _redundant_key(field: FormField) -> str:
    """Return the grouping key for the redundant-entry heuristic.

    ``purpose`` wins when provided. Otherwise, fall back to the
    autocomplete token, the field name, or the visible label —
    whichever is non-empty first.
    """

    candidates: Sequence[str] = (
        field.purpose,
        field.autocomplete,
        field.name,
        field.label,
    )
    for value in candidates:
        normalised = value.strip().lower()
        if normalised:
            return normalised
    return ""


# ---------------------------------------------------------------------------
# Check: 3.3.8 Accessible Authentication (Minimum)
# ---------------------------------------------------------------------------


def detect_accessible_authentication(
    challenges: Iterable[AuthChallenge],
) -> tuple[Wcag22Issue, ...]:
    """Flag cognitive auth challenges that lack an accessible alternative."""

    issues: list[Wcag22Issue] = []
    for challenge in challenges:
        if challenge.has_alternative:
            continue
        kind = (challenge.kind or "").strip().lower()
        issues.append(
            Wcag22Issue(
                category="accessible-authentication",
                success_criterion="3.3.8",
                selector=challenge.selector,
                description=(
                    f"{_AUTO_PREFIX}: authentication step {challenge.selector!r} "
                    f"requires a cognitive function test ({kind or 'unspecified'}) "
                    "with no alternative such as passkey, TOTP, or magic-link "
                    "(SC 3.3.8 Accessible Authentication (Minimum))."
                ),
            )
        )
    return tuple(issues)


__all__ = [
    "AuthChallenge",
    "BoundingBox",
    "ClickableElement",
    "DraggableElement",
    "FocusableElement",
    "FormField",
    "StickyOverlay",
    "WCAG22_TARGET_SIZE_MIN_PX",
    "detect_accessible_authentication",
    "detect_dragging_movements",
    "detect_focus_obscured",
    "detect_redundant_entry",
    "detect_target_size",
]
