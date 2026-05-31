"""Migration registry stub tests."""

from __future__ import annotations

import pytest
from engine.config.migration import CONFIG_MIGRATIONS, migrate_config
from engine.domain.migrations import MIGRATIONS, run_migration


def test_only_findings_migration_registered() -> None:
    # Phase 32 / ADR-0044 registered findings 1→2; no other artifact has
    # bumped yet.
    assert CONFIG_MIGRATIONS == {}
    assert set(MIGRATIONS) == {("findings", "1", "2")}


def test_missing_migration_raises() -> None:
    with pytest.raises(KeyError):
        migrate_config({}, "1", "2")
    with pytest.raises(KeyError):
        # An unregistered (artifact, from, to) triple still raises.
        run_migration("score", "1", "2", {})


def test_run_migration_uses_registered_when_present() -> None:
    MIGRATIONS[("test", "1", "2")] = lambda d: {**d, "migrated": True}
    try:
        out = run_migration("test", "1", "2", {"x": 1})
        assert out == {"x": 1, "migrated": True}
    finally:
        del MIGRATIONS[("test", "1", "2")]
