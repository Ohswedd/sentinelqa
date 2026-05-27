"""Migration registry stub tests."""

from __future__ import annotations

import pytest
from engine.config.migration import CONFIG_MIGRATIONS, migrate_config
from engine.domain.migrations import MIGRATIONS, run_migration


def test_no_migrations_registered_yet() -> None:
    assert CONFIG_MIGRATIONS == {}
    assert MIGRATIONS == {}


def test_missing_migration_raises() -> None:
    with pytest.raises(KeyError):
        migrate_config({}, "1", "2")
    with pytest.raises(KeyError):
        run_migration("findings", "1", "2", {})


def test_run_migration_uses_registered_when_present() -> None:
    MIGRATIONS[("test", "1", "2")] = lambda d: {**d, "migrated": True}
    try:
        out = run_migration("test", "1", "2", {"x": 1})
        assert out == {"x": 1, "migrated": True}
    finally:
        del MIGRATIONS[("test", "1", "2")]
