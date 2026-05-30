"""SentinelQA plugin loader (PRD §22, CLAUDE §22).

This package owns the host-side of the plugin contract: discovery via
``importlib.metadata.entry_points``, manifest validation, semver
compatibility check, runtime permission enforcement, and the optional
subprocess sandbox for plugins requesting risky permissions.

Plugin AUTHORS depend on :mod:`sentinelqa.plugins` (the SDK-public
surface). This module is the engine-internal loader; nothing here is
part of the SDK's pinned API snapshot (task 16.06).
"""

from __future__ import annotations

from engine.plugins.errors import (
    PluginCapabilityForbiddenError,
    PluginIncompatibleError,
    PluginManifestError,
    PluginPermissionError,
)
from engine.plugins.manifest import (
    PERMISSION_GRAMMAR,
    Manifest,
    load_manifest_dict,
    load_manifest_file,
)
from engine.plugins.registry import (
    LoadedPlugin,
    PluginRegistry,
    discover,
    load_from_entry_point,
)
from engine.plugins.runtime import PluginContextImpl, build_plugin_context
from engine.plugins.versioning import (
    PROTOCOL_VERSION,
    is_compatible,
    parse_requires_protocol,
)

__all__ = [
    "LoadedPlugin",
    "Manifest",
    "PERMISSION_GRAMMAR",
    "PROTOCOL_VERSION",
    "PluginCapabilityForbiddenError",
    "PluginContextImpl",
    "PluginIncompatibleError",
    "PluginManifestError",
    "PluginPermissionError",
    "PluginRegistry",
    "build_plugin_context",
    "discover",
    "is_compatible",
    "load_from_entry_point",
    "load_manifest_dict",
    "load_manifest_file",
    "parse_requires_protocol",
]
