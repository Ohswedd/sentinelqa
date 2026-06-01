"""Plugin-loader exceptions.

Every plugin error inherits :class:`engine.errors.base.PluginError` so
the CLI exit-code grid stays consistent: load-time failures map to
``E-PLG-001`` (exit code 5, treated as a missing dependency); runtime
failures map to ``E-PLG-002`` (exit code 7).
"""

from __future__ import annotations

from typing import Any

from engine.errors.base import PluginError


class PluginManifestError(PluginError):
    """Manifest failed schema validation."""

    DEFAULT_CODE = "E-PLG-001"


class PluginIncompatibleError(PluginError):
    """Plugin's ``requires_protocol`` is incompatible with host."""

    DEFAULT_CODE = "E-PLG-001"


class PluginCapabilityForbiddenError(PluginError):
    """Plugin declares a capability on the forbidden list."""

    DEFAULT_CODE = "E-PLG-001"


class PluginPermissionError(PluginError):
    """Plugin attempted an operation outside its declared permissions.

    Raised by :class:`engine.plugins.runtime.PluginContextImpl` when a
    plugin asks the context for something the manifest did not request.
    Exit code is 7 (runtime, internal-error class) because permission
    overreach indicates a misbehaving or malicious plugin.
    """

    DEFAULT_CODE = "E-PLG-002"

    def __init__(
        self,
        *,
        plugin: str,
        permission: str,
        granted: frozenset[str],
        **kwargs: Any,
    ) -> None:
        message = (
            f"Plugin {plugin!r} attempted operation requiring "
            f"{permission!r}; declared permissions are "
            f"{sorted(granted)!r}."
        )
        super().__init__(
            message,
            technical_context={
                "plugin": plugin,
                "permission": permission,
                "granted": sorted(granted),
            },
            **kwargs,
        )


__all__ = [
    "PluginCapabilityForbiddenError",
    "PluginIncompatibleError",
    "PluginManifestError",
    "PluginPermissionError",
]
