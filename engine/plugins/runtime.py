"""Runtime ``PluginContext`` (Phase 24 task 24.03).

The orchestrator instantiates :class:`PluginContextImpl` per-call and
hands it to the loaded plugin. The context exposes only the APIs the
plugin's manifest granted; everything else raises
:class:`PluginPermissionError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from engine.plugins.errors import PluginPermissionError


class PluginContextImpl:
    """Concrete :class:`sentinelqa.plugins.PluginContext` implementation.

    The plugin author programs against the SDK Protocol; the
    orchestrator constructs this concrete type. The mismatch is
    intentional: the engine owns enforcement; the SDK only documents
    the shape.
    """

    def __init__(
        self,
        *,
        plugin_name: str,
        run_id: str,
        target_url: str,
        run_dir: Path,
        config_snapshot: Mapping[str, Any],
        granted_permissions: frozenset[str],
    ) -> None:
        self._plugin_name = plugin_name
        self.run_id = run_id
        self.target_url = target_url
        self.run_dir = run_dir
        self.config_snapshot = dict(config_snapshot)
        self.granted_permissions = granted_permissions

    # ----------------------------------------------------------------
    # Permission helpers (task 24.03)
    # ----------------------------------------------------------------
    def has_permission(self, permission: str) -> bool:
        """Return True if the plugin declared ``permission``.

        Scoped permissions match by prefix: a plugin declaring
        ``fs.read:/etc`` satisfies a request for ``fs.read`` (the
        unscoped variant is treated as "any scope").
        """

        if permission in self.granted_permissions:
            return True
        # Allow declared-scoped permissions to satisfy unscoped checks.
        prefix = permission + ":"
        return any(p.startswith(prefix) for p in self.granted_permissions)

    def require(self, permission: str) -> None:
        """Raise :class:`PluginPermissionError` if not granted."""

        if not self.has_permission(permission):
            raise PluginPermissionError(
                plugin=self._plugin_name,
                permission=permission,
                granted=self.granted_permissions,
            )

    # ----------------------------------------------------------------
    # Concrete capabilities exposed to plugins
    # ----------------------------------------------------------------
    def artifact_path(self, name: str) -> Path:
        """Return a writable path under the run's plugin artifact dir.

        Requires ``fs.write:.sentinel/runs``. The returned path is
        confined under ``<run_dir>/plugins/<plugin_name>/``; passing a
        ``name`` containing ``..`` or an absolute path raises.
        """

        self.require("fs.write:.sentinel/runs")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise PluginPermissionError(
                plugin=self._plugin_name,
                permission=f"fs.write:.sentinel/runs (attempted '{name}')",
                granted=self.granted_permissions,
            )
        plugin_dir = self.run_dir / "plugins" / self._plugin_name
        target = plugin_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def read_text(self, path: Path | str) -> str:
        """Read a UTF-8 text file. Requires ``fs.read``."""

        self.require("fs.read")
        return Path(path).read_text(encoding="utf-8")

    def env(self, name: str) -> str | None:
        """Return ``os.environ[name]`` if ``env.read:<name>`` was granted."""

        scoped = f"env.read:{name}"
        if scoped not in self.granted_permissions:
            raise PluginPermissionError(
                plugin=self._plugin_name,
                permission=scoped,
                granted=self.granted_permissions,
            )
        # Local import keeps the runtime module side-effect free.
        import os

        return os.environ.get(name)


def build_plugin_context(
    *,
    plugin_name: str,
    run_id: str,
    target_url: str,
    run_dir: Path,
    config_snapshot: Mapping[str, Any],
    granted_permissions: frozenset[str],
) -> PluginContextImpl:
    """Convenience factory matching the loader's call style."""

    return PluginContextImpl(
        plugin_name=plugin_name,
        run_id=run_id,
        target_url=target_url,
        run_dir=run_dir,
        config_snapshot=config_snapshot,
        granted_permissions=granted_permissions,
    )


__all__ = ["PluginContextImpl", "build_plugin_context"]
