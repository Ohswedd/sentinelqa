"""Viewport (breakpoint) resolution (Phase 21.05).

The visual module captures one PNG per (route, viewport). Defaults
match the the documentation reference:

- mobile  — 375 x 812 (iPhone 13/14 portrait).
- tablet  — 768 x 1024 (iPad portrait).
- desktop — 1280 x 800 (developer-laptop reference).

The defaults live in :mod:`engine.config.schema` (the loader-side
contract); this module re-exports the resolver so the CLI and the
module agree on how an empty ``--viewports`` flag is interpreted.
"""

from __future__ import annotations

from collections.abc import Iterable

from engine.config.schema import VisualViewportConfig


def resolve_viewports(
    configured: tuple[VisualViewportConfig, ...],
    requested: Iterable[str] | None,
) -> tuple[VisualViewportConfig, ...]:
    """Return the configured viewports filtered by ``requested`` (if any).

    Raises :class:`ValueError` when a requested name has no
    corresponding configured viewport — this is a user mistake at the
    CLI boundary, not silent skipping.
    """

    if requested is None:
        return configured
    requested_set = {name for name in requested if name}
    if not requested_set:
        return configured
    by_name = {vp.name: vp for vp in configured}
    unknown = sorted(requested_set - by_name.keys())
    if unknown:
        known = sorted(by_name.keys())
        raise ValueError(f"Unknown visual viewport(s): {unknown!r}. Configured: {known!r}.")
    return tuple(by_name[name] for name in sorted(requested_set))


__all__ = ["resolve_viewports"]
