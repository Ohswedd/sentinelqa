"""Plugin manifest model (tasks 24.02 + 24.03).

A manifest is the wire format every plugin ships. For in-Python
plugins, the loader synthesises a manifest from class-level attributes
on the entry-point object; for external validation
(``sentinel plugins validate <path>``) the manifest can also be a
standalone JSON or TOML document under the plugin's source tree.

The shape is validated by :class:`Manifest` (a strict Pydantic model)
and by the published JSON Schema at
``packages/shared-schema/plugin-manifest.schema.json``. The two MUST
agree; ``tests/integration/plugins/test_manifest_schema.py`` checks
that on every CI run.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from engine.plugins.errors import (
    PluginCapabilityForbiddenError,
    PluginManifestError,
)
from engine.policy.forbidden_features import FORBIDDEN_CAPABILITIES

#: Permission tokens follow the ``<group>.<verb>`` or
#: ``<group>.<verb>:<scope>`` grammar. Plugins must declare every
#: permission they intend to exercise.
PERMISSION_GRAMMAR: Final[re.Pattern[str]] = re.compile(
    r"^[a-z]+(?:\.[a-z_]+)+(?::[A-Za-z0-9._/\-]+)?$"
)

#: Known plugin kinds (mirrors :data:`sentinelqa.plugins.PLUGIN_PROTOCOLS`).
_VALID_KINDS: Final[frozenset[str]] = frozenset(
    {
        "discovery",
        "scanner",
        "runner",
        "reporter",
        "policy",
        "auth",
        "data_fixture",
        "cloud_execution",
    }
)

_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9-]*$")
_SEMVER_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d+\.\d+\.\d+(?:[-+].+)?$")

#: Permissions plugins are allowed to declare. Anything else fails
#: manifest validation; ``fs.write`` is restricted to the run dir to
#: keep plugins from writing outside ``.sentinel/runs/<run-id>/``.
ALLOWED_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
        "fs.read",
        "fs.write:.sentinel/runs",
        "network.outbound",
        "subprocess.spawn",
    }
)

#: Permissions matching this prefix are also accepted ('fs.read:<path>'
#: limits a read scope; 'env.read:<NAME>' opens a specific env var;
#: 'auth.read:<host>' grants read access to the auth vault for a single
#: host — / ADR-0043. Plugins MUST declare the host they want
#: to consume sessions for; cross-host vault reads are refused at load
#: time.
ALLOWED_PERMISSION_PREFIXES: Final[tuple[str, ...]] = (
    "fs.read:",
    "env.read:",
    "auth.read:",
)


class Manifest(BaseModel):
    """Strict manifest model.

    Every field is required. Unknown keys raise — drift between the
    Pydantic shape and the JSON Schema is a contract violation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    version: str
    kind: str
    capabilities: tuple[str, ...] = Field(default_factory=tuple)
    permissions: tuple[str, ...] = Field(default_factory=tuple)
    requires_protocol: str
    entry_point: str | None = None
    description: str | None = None

    # --- validators --------------------------------------------------
    @field_validator("name")
    @classmethod
    def _name_ok(cls, value: str) -> str:
        if not _NAME_PATTERN.fullmatch(value):
            raise ValueError(f"Plugin name {value!r} must match {_NAME_PATTERN.pattern}")
        return value

    @field_validator("version")
    @classmethod
    def _version_ok(cls, value: str) -> str:
        if not _SEMVER_PATTERN.fullmatch(value):
            raise ValueError(f"Plugin version {value!r} must be a semver (X.Y.Z).")
        return value

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, value: str) -> str:
        if value not in _VALID_KINDS:
            raise ValueError(
                f"Unknown plugin kind {value!r}; expected one of " f"{sorted(_VALID_KINDS)!r}."
            )
        return value

    @field_validator("capabilities")
    @classmethod
    def _capabilities_ok(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        for cap in value:
            if cap in seen:
                raise ValueError(f"Duplicate capability {cap!r}.")
            seen.add(cap)
        return value

    @field_validator("permissions")
    @classmethod
    def _permissions_ok(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        seen: set[str] = set()
        for perm in value:
            if perm in seen:
                raise ValueError(f"Duplicate permission {perm!r}.")
            seen.add(perm)
            if not PERMISSION_GRAMMAR.fullmatch(perm):
                raise ValueError(
                    f"Permission {perm!r} does not match the permission "
                    f"grammar {PERMISSION_GRAMMAR.pattern!r}."
                )
            if perm in ALLOWED_PERMISSIONS:
                continue
            if any(perm.startswith(prefix) for prefix in ALLOWED_PERMISSION_PREFIXES):
                continue
            raise ValueError(
                f"Permission {perm!r} is not in the allow list "
                f"{sorted(ALLOWED_PERMISSIONS)!r} (or any of the scoped "
                f"prefixes {ALLOWED_PERMISSION_PREFIXES!r})."
            )
        return value

    @field_validator("requires_protocol")
    @classmethod
    def _requires_protocol_ok(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("requires_protocol must not be empty.")
        return value

    # --- behaviour ---------------------------------------------------
    def assert_no_forbidden_capabilities(self) -> None:
        """Reject manifests that declare a forbidden capability.

        Forbidden capabilities are the explicit deny-list in
        :data:`engine.policy.forbidden_features.FORBIDDEN_CAPABILITIES`. Any overlap fails the load.
        """

        offending = sorted(set(self.capabilities) & FORBIDDEN_CAPABILITIES)
        if offending:
            raise PluginCapabilityForbiddenError(
                f"Plugin {self.name!r} declares forbidden capabilities " f"{offending!r}.",
                technical_context={
                    "plugin": self.name,
                    "forbidden": offending,
                },
            )


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _coerce_lists(value: Mapping[str, Any]) -> dict[str, Any]:
    """Coerce capabilities/permissions to tuples for Pydantic.

    JSON arrays decode to ``list``; manifests may also use other
    iterables. Sorting normalises order so external manifests are
    stable across editors.
    """

    out = dict(value)
    for key in ("capabilities", "permissions"):
        raw = out.get(key, ())
        if isinstance(raw, Iterable) and not isinstance(raw, str | bytes):
            out[key] = tuple(raw)
    return out


def load_manifest_dict(payload: Mapping[str, Any]) -> Manifest:
    """Validate ``payload`` and return a :class:`Manifest`.

    Raises :class:`PluginManifestError` on any failure (schema drift,
    unknown key, bad permission grammar, etc.).
    """

    try:
        manifest = Manifest.model_validate(_coerce_lists(payload))
    except (ValueError, TypeError) as exc:
        raise PluginManifestError(
            f"Manifest failed validation: {exc}",
            technical_context={"errors": str(exc)},
        ) from exc
    return manifest


def load_manifest_file(path: Path | str) -> Manifest:
    """Read and validate a JSON or TOML manifest file."""

    p = Path(path)
    if not p.exists():
        raise PluginManifestError(
            f"Manifest file does not exist: {p}",
            technical_context={"path": str(p)},
        )
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise PluginManifestError(
            f"Could not read manifest at {p}: {exc}",
            technical_context={"path": str(p)},
        ) from exc

    suffix = p.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PluginManifestError(
                f"Manifest at {p} is not valid JSON: {exc.msg}",
                technical_context={"path": str(p), "line": exc.lineno},
            ) from exc
    elif suffix in {".toml"}:
        try:
            payload = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise PluginManifestError(
                f"Manifest at {p} is not valid TOML: {exc}",
                technical_context={"path": str(p)},
            ) from exc
    else:
        raise PluginManifestError(
            f"Manifest at {p} has unsupported suffix {suffix!r}; expected " ".json or .toml.",
            technical_context={"path": str(p), "suffix": suffix},
        )

    if not isinstance(payload, Mapping):
        raise PluginManifestError(
            f"Manifest at {p} must be a mapping at top level.",
            technical_context={"path": str(p)},
        )
    return load_manifest_dict(payload)


__all__ = [
    "ALLOWED_PERMISSIONS",
    "ALLOWED_PERMISSION_PREFIXES",
    "Manifest",
    "PERMISSION_GRAMMAR",
    "load_manifest_dict",
    "load_manifest_file",
]
