"""Phase 23 — chaos scenario catalog unit tests."""

from __future__ import annotations

from modules.chaos.scenarios import (
    CATALOG,
    CATALOG_BY_ID,
    DEFAULT_CATEGORIES,
    is_known_scenario,
    scenarios_for_category,
)


def test_catalog_covers_every_default_category() -> None:
    for category in DEFAULT_CATEGORIES:
        entries = scenarios_for_category(category)
        assert entries, f"category {category} has no catalog entries"
        assert all(s.category == category for s in entries)


def test_catalog_ids_are_unique() -> None:
    ids = [s.id for s in CATALOG]
    assert len(ids) == len(set(ids))


def test_catalog_lookup_by_id() -> None:
    s = CATALOG_BY_ID["network.api_500"]
    assert s.category == "network"
    assert "no_error_state" in s.bad_observations


def test_is_known_scenario_handles_unknowns() -> None:
    assert is_known_scenario("network.api_500") is True
    assert is_known_scenario("network.totally_made_up") is False
    assert is_known_scenario("") is False


def test_catalog_has_all_prd_chaos_scenarios() -> None:
    # PRD §10.8 lists the 13 scenarios; verify the canonical IDs exist.
    expected = {
        "network.slow_3g",
        "network.offline",
        "network.api_500",
        "network.api_timeout",
        "session.expired_token",
        "session.missing_permissions",
        "ux.duplicate_submit",
        "ux.double_click_race",
        "ux.back_forward",
        "ux.refresh_mid_flow",
        "data.empty_dataset",
        "data.large_dataset",
        "data.storage_corruption",
    }
    assert {s.id for s in CATALOG} == expected
