"""Unit tests for :mod:`modules.visual.breakpoints` (Phase 21.05)."""

from __future__ import annotations

import pytest
from engine.config.schema import VisualViewportConfig

from modules.visual.breakpoints import resolve_viewports


def _vp(name: str, width: int = 100, height: int = 100) -> VisualViewportConfig:
    return VisualViewportConfig(name=name, width=width, height=height)


def test_resolve_viewports_none_returns_all() -> None:
    configured = (_vp("mobile"), _vp("desktop"))
    assert resolve_viewports(configured, None) == configured


def test_resolve_viewports_empty_iterable_returns_all() -> None:
    configured = (_vp("mobile"), _vp("desktop"))
    assert resolve_viewports(configured, ()) == configured


def test_resolve_viewports_filters_by_name() -> None:
    configured = (_vp("mobile"), _vp("desktop"))
    result = resolve_viewports(configured, ("mobile",))
    assert tuple(vp.name for vp in result) == ("mobile",)


def test_resolve_viewports_sorts_result() -> None:
    configured = (_vp("zeta"), _vp("alpha"), _vp("mu"))
    result = resolve_viewports(configured, ("zeta", "alpha"))
    assert tuple(vp.name for vp in result) == ("alpha", "zeta")


def test_resolve_viewports_unknown_raises() -> None:
    configured = (_vp("mobile"),)
    with pytest.raises(ValueError, match="Unknown visual viewport"):
        resolve_viewports(configured, ("xl",))
