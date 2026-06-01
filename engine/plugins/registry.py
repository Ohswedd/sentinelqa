"""Plugin discovery + load-time validation.

The host calls :func:`discover` once per run; it iterates
``entry_points(group="sentinelqa.plugins")``, validates each
candidate, and returns the set that passed. Failures (import errors,
manifest drift, forbidden capabilities, incompatible protocol) are
logged and skipped — the run continues.

Plugin entry points must point to a *class* or an *instance* that
implements the matching Protocol from :mod:`sentinelqa.plugins`. The
loader extracts a manifest from class-level attributes:

- ``name`` / ``version`` / ``kind``
- ``capabilities`` / ``permissions`` (iterables of strings)
- ``requires_protocol`` (semver specifier, e.g. ``">=1.0,<2.0"``)
- optional ``description``

External JSON/TOML manifest files are validated by
:func:`engine.plugins.manifest.load_manifest_file` (used by
``sentinel plugins validate``).
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import logging
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from engine.plugins.errors import (
    PluginCapabilityForbiddenError,
    PluginIncompatibleError,
    PluginManifestError,
)
from engine.plugins.manifest import Manifest, load_manifest_dict
from engine.plugins.versioning import (
    PROTOCOL_VERSION,
    is_compatible,
    parse_requires_protocol,
)
from sentinelqa.plugins import (
    ENTRY_POINT_GROUP,
    PLUGIN_PROTOCOLS,
)

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedPlugin:
    """A plugin that passed discovery + validation."""

    manifest: Manifest
    instance: Any
    entry_point_name: str
    distribution: str | None
    distribution_version: str | None


class PluginRegistry:
    """Holds discovered plugins keyed by manifest name.

    Construct one per run. Duplicate names are rejected at load time
    (later registrations log and skip — first-write-wins).
    """

    def __init__(self) -> None:
        self._plugins: dict[str, LoadedPlugin] = {}
        self._load_errors: list[dict[str, str]] = []

    # ----------------------------------------------------------------
    # Accessors
    # ----------------------------------------------------------------
    def add(self, plugin: LoadedPlugin) -> None:
        if plugin.manifest.name in self._plugins:
            self._load_errors.append(
                {
                    "plugin": plugin.manifest.name,
                    "stage": "duplicate",
                    "detail": (
                        f"duplicate plugin name {plugin.manifest.name!r}; "
                        f"keeping the first registration"
                    ),
                }
            )
            return
        self._plugins[plugin.manifest.name] = plugin

    def get(self, name: str) -> LoadedPlugin:
        return self._plugins[name]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._plugins

    def __iter__(self) -> Iterator[LoadedPlugin]:
        for name in sorted(self._plugins):
            yield self._plugins[name]

    def __len__(self) -> int:
        return len(self._plugins)

    def by_kind(self, kind: str) -> tuple[LoadedPlugin, ...]:
        return tuple(p for p in self if p.manifest.kind == kind)

    @property
    def errors(self) -> tuple[Mapping[str, str], ...]:
        """Errors recorded for plugins that did NOT load."""

        return tuple(dict(e) for e in self._load_errors)

    def record_error(self, *, plugin: str, stage: str, detail: str) -> None:
        self._load_errors.append({"plugin": plugin, "stage": stage, "detail": detail})


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def _synthesise_manifest_from_object(obj: Any) -> Mapping[str, Any]:
    """Build a manifest dict from class-level plugin attributes."""

    return {
        "name": getattr(obj, "name", None),
        "version": getattr(obj, "version", None),
        "kind": getattr(obj, "kind", None),
        "capabilities": tuple(getattr(obj, "capabilities", ()) or ()),
        "permissions": tuple(getattr(obj, "permissions", ()) or ()),
        "requires_protocol": getattr(obj, "requires_protocol", ""),
        "description": getattr(obj, "description", None),
    }


def _instantiate(target: Any) -> Any:
    """Return an instance for either a class or an already-constructed object.

    Plugins are typically classes whose entry point points to the class
    itself. Instances are also acceptable for testing/factories.
    """

    if isinstance(target, type):
        return target()
    return target


def load_from_entry_point(
    entry_point: importlib_metadata.EntryPoint,
    *,
    host_version: str = PROTOCOL_VERSION,
) -> LoadedPlugin:
    """Resolve a single entry point into a :class:`LoadedPlugin`.

    Performs (in order):

    1. ``entry_point.load`` — import the target object.
    2. Instantiate if it is a class.
    3. Synthesise a manifest from class attrs and validate it.
    4. Reject forbidden capabilities.
    5. Reject incompatible ``requires_protocol``.
    6. ``isinstance`` check against the Protocol for the declared
    ``kind``.

    Raises :class:`PluginManifestError` /
    :class:`PluginCapabilityForbiddenError` /
    :class:`PluginIncompatibleError` on failure. Caller decides
    whether to log+skip (:func:`discover`) or propagate (CLI
    ``plugins validate``).
    """

    target = entry_point.load()
    instance = _instantiate(target)

    payload = _synthesise_manifest_from_object(instance)
    manifest = load_manifest_dict(payload)

    manifest.assert_no_forbidden_capabilities()

    # parse_requires_protocol re-raises as PluginManifestError; the
    # incompatible-version check returns False rather than raising so
    # we surface a distinct error code below.
    parse_requires_protocol(manifest.requires_protocol)
    if not is_compatible(manifest.requires_protocol, host=host_version):
        raise PluginIncompatibleError(
            f"Plugin {manifest.name!r} requires protocol "
            f"{manifest.requires_protocol!r}; host is {host_version}.",
            technical_context={
                "plugin": manifest.name,
                "requires_protocol": manifest.requires_protocol,
                "host_version": host_version,
            },
        )

    protocol = PLUGIN_PROTOCOLS.get(manifest.kind)
    if protocol is None:  # pragma: no cover - manifest validator catches it
        raise PluginManifestError(
            f"Unknown plugin kind {manifest.kind!r}.",
            technical_context={"plugin": manifest.name, "kind": manifest.kind},
        )
    if not isinstance(instance, protocol):
        raise PluginManifestError(
            f"Plugin {manifest.name!r} does not implement the " f"{manifest.kind!r} Protocol.",
            technical_context={
                "plugin": manifest.name,
                "kind": manifest.kind,
            },
        )

    distribution = getattr(entry_point, "dist", None)
    return LoadedPlugin(
        manifest=manifest,
        instance=instance,
        entry_point_name=entry_point.name,
        distribution=getattr(distribution, "name", None) if distribution else None,
        distribution_version=(getattr(distribution, "version", None) if distribution else None),
    )


def discover(
    *,
    entry_points: Iterable[importlib_metadata.EntryPoint] | None = None,
    host_version: str = PROTOCOL_VERSION,
) -> PluginRegistry:
    """Discover, validate, and return all installed plugins.

    By default reads from ``importlib.metadata.entry_points``; tests
    pass an explicit iterable so they don't depend on what's installed
    in the dev venv. Failures log + skip; the run continues without
    the broken plugin.
    """

    if entry_points is None:
        try:
            entry_points = importlib_metadata.entry_points().select(group=ENTRY_POINT_GROUP)
        except Exception as exc:  # pragma: no cover - defensive
            _log.warning("plugin entry-point discovery failed: %s", exc)
            entry_points = ()

    registry = PluginRegistry()
    for ep in entry_points:
        try:
            loaded = load_from_entry_point(ep, host_version=host_version)
        except (
            PluginCapabilityForbiddenError,
            PluginIncompatibleError,
            PluginManifestError,
        ) as exc:
            _log.warning("skipping plugin %s: %s", ep.name, exc.message)
            registry.record_error(plugin=ep.name, stage="validate", detail=exc.message)
            continue
        except Exception as exc:  # pragma: no cover - very defensive
            _log.warning("plugin %s failed to import: %s", ep.name, exc)
            registry.record_error(plugin=ep.name, stage="import", detail=str(exc))
            continue
        registry.add(loaded)
    return registry


__all__ = [
    "LoadedPlugin",
    "PluginRegistry",
    "discover",
    "load_from_entry_point",
]
