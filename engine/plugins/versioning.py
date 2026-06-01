"""Semver compatibility for the plugin protocol.

The host pins :data:`PROTOCOL_VERSION`; plugins declare a
``requires_protocol`` PEP 440 specifier (e.g. ``">=1.0,<2.0"``). The
loader rejects plugins whose specifier excludes the host's version.

We reuse :mod:`packaging` (already a transitive dep of pip/hatch and
declared explicitly in ``engine/pyproject.toml``); reinventing semver
parsing inside the engine would be both wasteful and risky.

Bumping :data:`PROTOCOL_VERSION` major requires an ADR.
"""

from __future__ import annotations

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from engine.plugins.errors import PluginIncompatibleError, PluginManifestError
from sentinelqa.plugins import PROTOCOL_VERSION

__all__ = [
    "PROTOCOL_VERSION",
    "is_compatible",
    "parse_requires_protocol",
]


def parse_requires_protocol(spec: str) -> SpecifierSet:
    """Parse a ``requires_protocol`` string into a :class:`SpecifierSet`.

    Raises :class:`PluginManifestError` on malformed input.
    """

    try:
        return SpecifierSet(spec)
    except InvalidSpecifier as exc:
        raise PluginManifestError(
            f"requires_protocol {spec!r} is not a valid PEP 440 specifier.",
            technical_context={"requires_protocol": spec},
        ) from exc


def is_compatible(requires_protocol: str, host: str = PROTOCOL_VERSION) -> bool:
    """Return True if the host version satisfies ``requires_protocol``.

    Empty specifier strings are treated as "any version" — plugins that
    omit the field accept whatever the host ships. The loader will warn
    on omission but does not refuse the plugin.
    """

    if not requires_protocol.strip():
        return True
    spec = parse_requires_protocol(requires_protocol)
    try:
        host_v = Version(host)
    except InvalidVersion as exc:  # pragma: no cover - defensive only
        raise PluginIncompatibleError(
            f"Host PROTOCOL_VERSION {host!r} is not a valid version.",
            technical_context={"host_version": host},
        ) from exc
    return host_v in spec
