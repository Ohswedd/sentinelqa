"""Unit tests for module-level helpers in :mod:`modules.visual.module`."""

from __future__ import annotations

from pathlib import Path

from modules.visual.module import _coerce_path, _read_options
from modules.visual.options import VisualModuleOptions
from tests.unit.modules.visual._fixtures import build_module_context


def test_coerce_path_none() -> None:
    assert _coerce_path(None) is None


def test_coerce_path_str() -> None:
    assert _coerce_path("a/b") == Path("a/b")


def test_coerce_path_pathlib() -> None:
    p = Path("/tmp")
    assert _coerce_path(p) is p


def test_read_options_passthrough_dataclass(tmp_path: Path) -> None:
    opts = VisualModuleOptions(viewports=("mobile",))
    ctx = build_module_context(tmp_path, options=[("visual", opts)])
    result = _read_options(ctx)
    assert result is opts


def test_read_options_csv_viewports_and_routes(tmp_path: Path) -> None:
    ctx = build_module_context(
        tmp_path,
        options=[("visual", {"viewports": "mobile, desktop", "routes": "home,about"})],
    )
    result = _read_options(ctx)
    assert result.viewports == ("mobile", "desktop")
    assert result.routes == ("home", "about")


def test_read_options_threshold_coerced(tmp_path: Path) -> None:
    ctx = build_module_context(tmp_path, options=[("visual", {"threshold": "0.05"})])
    result = _read_options(ctx)
    assert result.threshold == 0.05


def test_read_options_unknown_shape_returns_defaults(tmp_path: Path) -> None:
    ctx = build_module_context(tmp_path, options=[("visual", "not a mapping")])
    result = _read_options(ctx)
    assert result == VisualModuleOptions()
