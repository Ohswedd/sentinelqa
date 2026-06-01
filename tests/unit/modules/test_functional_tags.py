"""Unit tests for :mod:`modules.functional.tags`."""

from __future__ import annotations

import pytest
from engine.domain.flow import Flow, FlowStep
from engine.generator.pipeline import _canonical_tag_set

from modules.functional.tags import (
    DEFAULT_MODE,
    TagSelection,
    grep_for_mode,
    supported_modes,
)


def _make_flow(**overrides: object) -> Flow:
    base: dict[str, object] = {
        "id": "FLW-AAAAAAAAAAAA",
        "name": "login",
        "steps": (FlowStep(description="step", expected_outcome="ok"),),
        "priority": "P0",
        "risk": "critical",
        "extractor": "login",
        "tags": ("auth", "login"),
    }
    base.update(overrides)
    return Flow.model_validate(base)


# ---------------------------------------------------------------------------
# Canonical tag set emitted by the generator
# ---------------------------------------------------------------------------


def test_canonical_tag_set_includes_priority_module_flow_risk() -> None:
    flow = _make_flow()
    tags = _canonical_tag_set(flow)
    assert "@p0" in tags
    assert "@module:functional" in tags
    assert "@flow:login" in tags
    assert "@risk:critical" in tags


def test_canonical_tag_set_routes_api_contract_to_api_module() -> None:
    flow = _make_flow(extractor="api.contract", tags=("api",))
    tags = _canonical_tag_set(flow)
    assert "@module:api" in tags
    assert "@flow:api.contract" in tags


def test_canonical_tag_set_preserves_planner_tags_with_prefix() -> None:
    flow = _make_flow(tags=("auth", "login", "auth_boundary"))
    tags = _canonical_tag_set(flow)
    assert "@auth" in tags
    assert "@login" in tags
    assert "@auth_boundary" in tags


def test_canonical_tag_set_drops_id_tags_via_stable_tags() -> None:
    flow = _make_flow(tags=("element:EL-XYZ", "auth"))
    tags = _canonical_tag_set(flow)
    assert "@auth" in tags
    assert not any("element:" in t for t in tags)


def test_canonical_tag_set_unknown_extractor_falls_back_to_functional() -> None:
    flow = _make_flow(extractor="custom_thing")
    tags = _canonical_tag_set(flow)
    assert "@module:functional" in tags
    assert "@flow:custom_thing" in tags


def test_canonical_tag_set_handles_blank_extractor() -> None:
    flow = _make_flow(extractor="")
    tags = _canonical_tag_set(flow)
    assert "@flow:unknown" in tags


# ---------------------------------------------------------------------------
# Slice modes (smoke / standard / full)
# ---------------------------------------------------------------------------


def test_supported_modes_returns_canonical_tuple() -> None:
    assert supported_modes() == ("smoke", "standard", "full")


def test_default_mode_is_standard() -> None:
    assert DEFAULT_MODE == "standard"


def test_grep_for_mode_smoke_matches_p0() -> None:
    assert grep_for_mode("smoke") == "@p0"


def test_grep_for_mode_standard_matches_p0_or_p1() -> None:
    assert grep_for_mode("standard") == "@p0|@p1"


def test_grep_for_mode_full_returns_none() -> None:
    assert grep_for_mode("full") is None


# ---------------------------------------------------------------------------
# TagSelection resolution
# ---------------------------------------------------------------------------


def test_tag_selection_smoke_no_user_grep() -> None:
    sel = TagSelection.resolve(mode="smoke", user_grep=None)
    assert sel.mode == "smoke"
    assert sel.grep == "@p0"


def test_tag_selection_full_no_user_grep_returns_none() -> None:
    sel = TagSelection.resolve(mode="full", user_grep=None)
    assert sel.grep is None


def test_tag_selection_full_with_user_grep_forwards_verbatim() -> None:
    sel = TagSelection.resolve(mode="full", user_grep="@flow:login")
    assert sel.grep == "@flow:login"


def test_tag_selection_smoke_with_user_grep_intersects() -> None:
    sel = TagSelection.resolve(mode="smoke", user_grep="@flow:login")
    assert sel.grep == "(@p0).*@flow:login"


def test_tag_selection_defaults_to_standard_when_mode_unknown() -> None:
    sel = TagSelection.resolve(mode=None, user_grep=None)
    assert sel.mode == "standard"
    assert sel.grep == "@p0|@p1"


@pytest.mark.parametrize(
    "mode",
    [
        "smoke",
        "standard",
        "full",
    ],
)
def test_tag_selection_known_modes_are_preserved(mode: str) -> None:
    sel = TagSelection.resolve(mode=mode, user_grep=None)
    assert sel.mode == mode
