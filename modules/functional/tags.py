"""Tag conventions + slice modes for the functional module (Phase 10.03).

Generated Playwright specs (Phase 07) emit a canonical tag set that lets
CI modes (Phase 17) target the cheap slice without re-generating the
plan. The conventions:

- ``@p0`` .. ``@p3``           — priority bucket (one per flow).
- ``@flow:<extractor>``        — the planner extractor that produced the flow.
- ``@module:<module_name>``    — the SentinelQA module that owns the test.
- ``@risk:<level>``            — risk bucket (``critical|high|medium|low``).

Slice modes translate to a Playwright ``--grep`` value that the runner
(Phase 08) passes to ``playwright test``:

- ``smoke``    → ``@p0`` (must run on every PR).
- ``standard`` → ``@p0|@p1`` (the default for ``sentinel functional``).
- ``full``     → ``None`` (no tag filter; runs every functional spec).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Mode = Literal["smoke", "standard", "full"]
"""Slice mode names (Phase 10.03 + the documentation CI modes)."""

DEFAULT_MODE: Mode = "standard"
"""Default slice run by ``sentinel functional`` when ``--mode`` is omitted."""

_GREP_FOR_MODE: dict[Mode, str | None] = {
    "smoke": "@p0",
    "standard": "@p0|@p1",
    "full": None,
}


@dataclass(frozen=True)
class TagSelection:
    """Resolved tag selection for one ``sentinel functional`` invocation.

    Two inputs can produce a non-empty grep:

    - ``mode`` (slice mode → ``@p0`` etc.).
    - ``user_grep`` (raw value the user passed via ``--grep``).

    When both are provided we AND them by emitting
    ``(@p0|@p1).*<user_grep>`` so the user can intersect the slice. When
    only one is provided we forward it verbatim.
    """

    mode: Mode
    user_grep: str | None
    grep: str | None

    @classmethod
    def resolve(cls, *, mode: Mode | str | None, user_grep: str | None) -> TagSelection:
        resolved_mode: Mode = (
            mode if mode in ("smoke", "standard", "full") else DEFAULT_MODE  # type: ignore[assignment]
        )
        mode_grep = _GREP_FOR_MODE[resolved_mode]
        if mode_grep is None and user_grep is None:
            return cls(mode=resolved_mode, user_grep=None, grep=None)
        if mode_grep is None:
            return cls(mode=resolved_mode, user_grep=user_grep, grep=user_grep)
        if user_grep is None:
            return cls(mode=resolved_mode, user_grep=None, grep=mode_grep)
        combined = f"({mode_grep}).*{user_grep}"
        return cls(mode=resolved_mode, user_grep=user_grep, grep=combined)


def supported_modes() -> tuple[Mode, ...]:
    return ("smoke", "standard", "full")


def grep_for_mode(mode: Mode) -> str | None:
    """Return the raw grep for ``mode`` (no user-grep merge applied)."""

    return _GREP_FOR_MODE[mode]


__all__ = [
    "DEFAULT_MODE",
    "Mode",
    "TagSelection",
    "grep_for_mode",
    "supported_modes",
]
