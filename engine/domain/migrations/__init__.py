"""Migration registry for SentinelQA artifacts.

Empty in Phase 01 — every schema is at major version 1. When a constant in
:mod:`engine.domain.schema` bumps, a corresponding migration lives here as
``<artifact>_<from>_to_<to>.py``, exposing ``def migrate(data: dict) -> dict``.
The registry below names them so ``engine.domain.migrations.run_migration``
can pick the right one at read time.

See `docs/dev/schema-versioning.md` for the full policy.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Keyed by (artifact_name, from_version, to_version).
MIGRATIONS: dict[tuple[str, str, str], Callable[[dict[str, Any]], dict[str, Any]]] = {}


def run_migration(
    artifact: str, from_version: str, to_version: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Apply the registered migration for an artifact, or raise if missing."""

    key = (artifact, from_version, to_version)
    migrator = MIGRATIONS.get(key)
    if migrator is None:
        raise KeyError(f"No migration registered for {artifact} {from_version} -> {to_version}.")
    return migrator(data)


# Import side-effecting migration modules so they register themselves in
# ``MIGRATIONS`` at package import time. New migrations must be appended
# here (and a matching ADR added per ``docs/dev/schema-versioning.md``).
from engine.domain.migrations import findings_1_to_2  # noqa: E402,F401

__all__ = ["MIGRATIONS", "run_migration"]
