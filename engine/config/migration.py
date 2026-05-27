"""Config schema migrations.

Empty in Phase 01 because ``CONFIG_SCHEMA_VERSION`` starts at ``"1"``. When
the constant bumps, a migration function lands here and the loader will
attempt it before validating against the new schema. See
``docs/dev/schema-versioning.md`` for the policy.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Keyed by (from_version, to_version).
CONFIG_MIGRATIONS: dict[tuple[str, str], Callable[[dict[str, Any]], dict[str, Any]]] = {}


def migrate_config(data: dict[str, Any], from_version: str, to_version: str) -> dict[str, Any]:
    """Apply the registered config migration, or raise if none exists."""

    key = (from_version, to_version)
    migrator = CONFIG_MIGRATIONS.get(key)
    if migrator is None:
        raise KeyError(f"No config migration registered for {from_version} -> {to_version}.")
    return migrator(data)


__all__ = ["CONFIG_MIGRATIONS", "migrate_config"]
