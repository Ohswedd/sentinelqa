"""Phase 31 — plugins must declare ``auth.read:<host>`` to use the vault."""

from __future__ import annotations

from pathlib import Path

import pytest
from engine.plugins.errors import PluginPermissionError
from engine.plugins.manifest import Manifest
from engine.plugins.runtime import PluginContextImpl

# We deliberately exercise PluginContextImpl directly instead of going
# through the loader so the test doesn't need an entry-point installed.


def _ctx(run_dir: Path, granted: tuple[str, ...]) -> PluginContextImpl:
    return PluginContextImpl(
        plugin_name="example-plugin",
        run_id="RUN-X",
        target_url="https://example.com",
        run_dir=run_dir,
        config_snapshot={},
        granted_permissions=frozenset(granted),
    )


def test_manifest_accepts_auth_read_permission() -> None:
    m = Manifest(
        name="example",
        version="1.0.0",
        kind="scanner",
        capabilities=(),
        permissions=("auth.read:example.com",),
        requires_protocol="1.0.0",
    )
    assert "auth.read:example.com" in m.permissions


def test_plugin_without_auth_read_refused(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, granted=("fs.read",))
    with pytest.raises(PluginPermissionError) as info:
        ctx.auth_session("example.com", "myorg")
    assert "auth.read:example.com" in str(info.value)


def test_plugin_cannot_read_session_for_other_host(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, granted=("auth.read:example.com",))
    with pytest.raises(PluginPermissionError):
        ctx.auth_session("other.com", "myorg")
